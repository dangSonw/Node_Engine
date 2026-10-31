"""Actual Qt latent-node authoring and native pause/save/load behavior."""
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
from tools.create_latent_flow_demo import POSITIONS


def verify():
    directory=ROOT/'.cache'/('latent-flow-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/latent_flow_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='latent-flow-editor-'+uuid.uuid4().hex
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
        for type_id,label in [(2012,'Delay'),(2013,'Wait Until'),(2014,'Retriggerable Delay')]:
            window.library_search.setText(label); QTest.qWait(80); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                      for j in range(library.topLevelItem(i).childCount())
                      if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(label+' can be created from Library',len(window.adapter.graph.all_nodes())==count+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            check(label+' exposes Owner and Out',{'In','Owner'}<=set(created.inputs()) and set(created.outputs())=={'Out'})
            window.actions['Undo'].trigger(); check('Undo removes '+label,len(window.adapter.graph.all_nodes())==count)
            window.actions['Redo'].trigger(); check('Redo restores '+label,len(window.adapter.graph.all_nodes())==count+1)
            window.actions['Undo'].trigger()
        window.adapter.clear_selection(); node=find('debounce'); node.set_selected(True); window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.property('domain_property')=='value_Seconds')
        field.setFocus(); field.selectAll(); QTest.keyClicks(field,'0.75'); QTest.keyClick(field,Qt.Key.Key_Return)
        check('Inspector edits delay duration',node.get_property('value_Seconds')==.75)
        window.actions['Undo'].trigger(); check('Undo restores delay duration',node.get_property('value_Seconds')==.5)
        check('Latent graph and function save and reopen',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        check('Preview is waiting for Space',first['variables']['progress']['value']==0 and len(first['continuations']['tasks'])==1)
        QTest.qWait(150); check('Pause preserves pending state',snapshot()==first)
        command('play'); key(' '); key('S'); command('pause'); saved=snapshot()
        check('Physical Space starts tour and S saves inside function',saved['persistence']['success'] and any(len(t['frames'])==2 for t in saved['continuations']['tasks']))
        QTest.qWait(200); check('Pause freezes delay and captured state',snapshot()==saved)
        command('play'); QTest.qWait(2400); command('pause'); reference=snapshot()
        check('Function and loop finish at all four stations',reference['variables']['progress']['value']==4 and reference['entities']['player']['position']==POSITIONS[3] and not reference['continuations']['tasks'])
        command('play'); key('L'); command('pause'); loaded=snapshot()
        check('Physical Load restores suspended call stack',loaded['persistence']['success'] and loaded['variables']['progress']['value']<4 and any(len(t['frames'])==2 for t in loaded['continuations']['tasks']))
        command('play'); QTest.qWait(2400); command('pause'); restored=snapshot()
        check('Restored loop reaches same pose and progress',restored['variables']==reference['variables'] and restored['entities']==reference['entities'] and not restored['continuations']['tasks'])
        command('play'); key('R'); key('R'); command('pause'); pending=snapshot()
        check('Repeated physical R leaves one retriggered wait',len(pending['continuations']['tasks'])==1 and pending['continuations']['tasks'][0]['remaining']>0)
        command('play'); QTest.qWait(650); command('pause'); check('Retriggered signal completes',not snapshot()['continuations']['tasks'])
        window.library_search.clear(); window.adapter.clear_selection(); node=find('wait'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/latent-flow-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop clears continuation state',stopped['frame']==0 and not stopped['continuations']['tasks'] and stopped['variables']['progress']['value']==0)
        command('play'); command('pause'); restarted=snapshot()
        check('Restart waits for Space again',not restarted['variables']['started']['value'] and len(restarted['continuations']['tasks'])==1)
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in ' RSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/latent-flow-editor-checks.json',report)
    return report


if __name__=='__main__': print('Latent flow editor:',len(verify()['checks']),'checks passed.')
