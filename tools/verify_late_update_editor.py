"""Author Late Update and verify camera tracking in the actual embedded SDL editor."""
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
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('late-update-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/late_update_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='late-update-editor-'+uuid.uuid4().hex
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
    def key(code):
        user32.keybd_event(code,0,0,0); QTest.qWait(90); user32.keybd_event(code,0,2,0); QTest.qWait(70)
    def world(state): return {key:state[key] for key in ('time','entities','physics','animation')}
    def find(nid): return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    def follows(state):
        player=state['entities']['player']['position']; camera=state['entities']['camera']['position']
        return all(abs(a-b-offset)<2e-6 for a,b,offset in zip(camera,player,(0,1,7)))
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        window.library_search.setText('On Late Update'); QTest.qWait(80)
        library=window.library_tree
        item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                  for j in range(library.topLevelItem(i).childCount())
                  if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==1005)
        library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
        QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        check('Late Update is creatable through the library',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger(); check('Undo removes late entry',len(window.adapter.graph.all_nodes())==count)
        window.actions['Redo'].trigger(); check('Redo restores late entry',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger()
        check('Late graph validates and saves',window.validate_graph() and window.save_project())
        check('Late graph reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); initial=snapshot()
        command('play'); QTest.qWait(350); command('pause'); moved=snapshot()
        check('Late camera tracks current physical position',moved['entities']['player']['position'][0]>initial['entities']['player']['position'][0] and follows(moved))
        check('Late phase observes advanced animation',abs(moved['variables']['animation']-moved['animation']['player']['time'])<1e-12)
        QTest.qWait(200); check('Editor Pause stops late callbacks',snapshot()==moved)
        command('play'); key(ord('A')); QTest.qWait(250); command('pause'); left=snapshot()
        check('Physical A reverses motion while camera stays aligned',left['entities']['player']['position'][0]<moved['entities']['player']['position'][0] and follows(left))
        command('play'); key(ord('0')); command('pause'); frozen=snapshot()
        command('play'); QTest.qWait(220); command('pause'); later=snapshot()
        check('Late callbacks continue during time freeze',world(later)==world(frozen) and later['variables']['late_frame']>frozen['variables']['late_frame'] and later['variables']['delta']==0)
        command('play'); key(ord('S')); command('pause'); saved=snapshot()
        check('Save requested in late phase succeeds',saved['persistence']['success'])
        command('play'); key(ord('1')); key(ord('D')); QTest.qWait(320); command('pause'); changed=snapshot()
        check('Physical D moves right and late camera follows',changed['time']>saved['time'] and follows(changed))
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Late Load restores frozen world and camera',loaded['persistence']['success'] and world(loaded)==world(saved) and loaded['clock']['scale']==0 and follows(loaded))
        from editor.core.compiler import compile_graph
        bad=compile_graph(window.adapter.document(),window.scene); bad['events']['late_update']={}
        before=snapshot(); begin=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[begin:]))
        check('Malformed late phase preserves current world',snapshot()==before)
        window.adapter.graph.clear_selection(); node=find('late'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/late-update-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot()
        check('Stop clears frame state',stopped['frame']==0 and stopped['time']==0)
        command('play'); QTest.qWait(100); command('pause'); restarted=snapshot()
        check('Restart reinstates late callback',restarted['variables']['late_frame']==restarted['frame']-1 and follows(restarted))
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in '01ADSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/late-update-editor-checks.json',report)
    return report


if __name__=='__main__': print('Late Update editor:',len(verify()['checks']),'checks passed.')
