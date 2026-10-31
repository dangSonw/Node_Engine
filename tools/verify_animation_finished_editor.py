"""Actual Qt authoring and embedded SDL completion/persistence behavior."""
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('animation-finished-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/animation_finished_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='animation-finished-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory))
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate):
        end=time.monotonic()+40
        while not predicate() and time.monotonic()<end: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText())
    def command(name):
        begin=len(messages); serial=window.runtime.send(name)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]; check('Preview '+name,not any(m.get('event')=='node_error' for m in result)); return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    user32=ctypes.windll.user32
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    def focus():
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert user32.GetWindowRect(hwnd,ctypes.byref(rect))
        assert user32.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        try:
            user32.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
            user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(80)
        finally: user32.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        info=GuiInfo(); info.cbSize=ctypes.sizeof(info)
        check('Embedded viewport has physical focus',bool(user32.GetGUIThreadInfo(0,ctypes.byref(info))) and info.focus==hwnd)
    def key(letter):
        user32.keybd_event(ord(letter),0,0,0); QTest.qWait(90); user32.keybd_event(ord(letter),0,2,0); QTest.qWait(70)
    def find(nid): return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        window.library_search.setText('On Animation Finished'); QTest.qWait(80)
        library=window.library_tree
        item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                  for j in range(library.topLevelItem(i).childCount())
                  if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==13014)
        library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
        QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        check('Library creates animation completion entry',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger(); check('Undo removes new entry',len(window.adapter.graph.all_nodes())==count)
        window.actions['Redo'].trigger(); check('Redo restores entry',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger()
        node=find('finished'); node.set_selected(True); window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.property('domain_property')=='value_Clip Filter')
        field.setFocus(); field.selectAll(); QTest.keyClicks(field,'Walk'); QTest.keyClick(field,Qt.Key.Key_Return)
        check('Inspector edits exact clip filter',node.get_property('value_Clip Filter')=='Walk')
        window.actions['Undo'].trigger(); check('Undo restores Wave filter',node.get_property('value_Clip Filter')=='Wave')
        check('Completion graph validates and saves',window.validate_graph() and window.save_project())
        check('Completion graph reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        QTest.qWait(150); check('Editor Pause prevents callback delivery',snapshot()==first)
        command('play'); QTest.qWait(2400); command('pause'); finished=snapshot()
        check('Wave transitions to Idle once and Late Update observes it',finished['variables']['completed']==finished['variables']['late_completed']==1 and
            finished['animation']['player']['clip']=='Idle' and finished['animation']['walker']['clip']=='Walk')
        check('Completion callback saves successfully',finished['persistence']['success'])
        command('play'); key('1'); key('P'); command('pause'); paused=snapshot()
        check('Physical playback and pause retain unfinished Wave',paused['animation']['player']['clip']=='Wave' and paused['animation']['player']['paused'] and paused['variables']['completed']==1)
        command('play'); key('S'); command('pause'); saved=snapshot()
        check('Manual save keeps paused clip',saved['persistence']['success'] and saved['animation']['player']['paused'])
        command('play'); key('R'); QTest.qWait(2400); command('pause'); second=snapshot()
        check('Resuming finishes a second playback once',second['variables']['completed']==2 and second['animation']['player']['clip']=='Idle')
        command('play'); key('L'); command('pause'); loaded=snapshot()
        check('Physical Load restores unfinished paused clip and count',loaded['persistence']['success'] and loaded['variables']['completed']==1 and
              loaded['animation']['player']==saved['animation']['player'])
        command('play'); key('R'); QTest.qWait(2400); command('pause'); replayed=snapshot()
        check('Restored receiver delivers exactly one future completion',replayed['variables']['completed']==2 and replayed['animation']['player']['clip']=='Idle')
        bad=compile_graph(window.adapter.document(),window.scene); bad['events']['animation_finished'][0]['filter']='a\0b'
        before=snapshot(); begin=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[begin:]))
        check('Invalid completion filter preserves live world',snapshot()==before)
        window.adapter.graph.clear_selection(); node=find('finished'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/animation-finished-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop clears playback and counters',stopped['frame']==0 and stopped['variables']['completed']==0 and 'animation' not in stopped)
        command('play'); QTest.qWait(2400); command('pause'); restarted=snapshot()
        check('Restart binds one completion handler',restarted['variables']['completed']==1 and restarted['animation']['player']['clip']=='Idle')
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in '1PRSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/animation-finished-editor-checks.json',report)
    return report


if __name__=='__main__': print('Animation finished editor:',len(verify()['checks']),'checks passed.')
