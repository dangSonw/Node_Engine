"""Real function editor authoring and embedded SDL Break/Continue gameplay."""
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
from PySide6.QtCore import QEvent,QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('loop-control-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/loop_control_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='loop-control-editor-'+uuid.uuid4().hex
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
    def selection(s,entity,visits,scans): return (s['variables']['selected']['value']==entity and s['variables']['visited']['value']==visits and s['variables']['scans']==scans)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        failures=[]
        def edit():
            dialog=app.activeModalWidget()
            try:
                check('Function editor opens target scanner',isinstance(dialog,FunctionEditorDialog) and dialog.current_id==1000200)
                for type_id,name in [(2005,'Break Loop'),(2006,'Continue Loop')]:
                    dialog.search.setText(name); QTest.qWait(50)
                    item=next(dialog.library.item(i) for i in range(dialog.library.count()) if not dialog.library.item(i).isHidden())
                    count=len(dialog.adapter.graph.all_nodes())
                    QTest.mouseClick(dialog.library.viewport(),Qt.MouseButton.LeftButton,pos=dialog.library.visualItemRect(item).center())
                    QTest.mouseDClick(dialog.library.viewport(),Qt.MouseButton.LeftButton,pos=dialog.library.visualItemRect(item).center())
                    check(name+' is creatable in function library',len(dialog.adapter.graph.all_nodes())==count+1 and any(n.get_property('type_id')==type_id for n in dialog.adapter.graph.all_nodes()))
                    stack=dialog.adapter.graph.undo_stack(); stack.undo(); check(name+' Undo removes node',len(dialog.adapter.graph.all_nodes())==count)
                    stack.redo(); check(name+' Redo restores node',len(dialog.adapter.graph.all_nodes())==count+1); stack.undo()
                dialog.frame_all(); QTest.qWait(100)
                capture=ROOT/'artifacts/validation/loop-control-function.png'
                check('Function graph screenshot saved',dialog.grab().save(str(capture)))
                report['function_screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
                # A loop control attached to the function entry must block saving.
                entry=next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='entry')
                bad=dialog.adapter.add(2005); entry.outputs()['Out'].clear_connections(); entry.outputs()['Out'].connect_to(bad.inputs()['In'])
                QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Save),Qt.MouseButton.LeftButton)
                check('Unscoped Break blocks save with a readable diagnostic',dialog.isVisible() and 'loop Body' in dialog.message.text())
                while len(dialog.adapter.graph.all_nodes())>len(graph['functions'][0]['graph']['nodes']): dialog.adapter.graph.undo_stack().undo()
                QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Save),Qt.MouseButton.LeftButton)
                check('Undo repair allows function save',not dialog.isVisible())
            except BaseException as error:
                failures.append(error)
                if dialog: dialog.reject()
        QTimer.singleShot(150,edit); window.edit_function(1000200)
        if failures: raise failures[0]
        check('Gameplay graph validates and saves',window.validate_graph() and window.save_project())
        check('Function with loop controls reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); initial=snapshot(); check('Initial scanner skips inactive robot and breaks early',selection(initial,'robot_b',3,1))
        QTest.qWait(120); check('Editor Pause preserves scan state',snapshot()==initial)
        command('play'); key(ord('1')); key(32); command('pause'); first=snapshot()
        check('Physical input selects first robot and reduces visits',selection(first,'player',2,2) and first['entities']['player']['scale']==[1.25]*3)
        command('play'); key(ord('S')); command('pause'); saved=snapshot(); check('Save preserves selected entity',saved['persistence']['success'])
        command('play'); key(ord('1')); key(ord('2')); key(ord('3')); key(32); command('pause'); empty=snapshot()
        check('All inactive robots produce an empty result after full traversal',selection(empty,'',4,3))
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Load restores selected entity, activity and loop result',loaded['persistence']['success'] and selection(loaded,'player',2,2) and loaded['entities']==saved['entities'])
        command('play'); key(ord('1')); key(32); command('pause'); later=snapshot()
        check('A scan after Load runs with fresh control scope',selection(later,'robot_b',3,3))
        capture=ROOT/'artifacts/validation/loop-control-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop resets scan counters',stopped['variables']['scans']==0)
        command('play'); QTest.qWait(120); command('pause'); check('Restart reruns initial selection once',selection(snapshot(),'robot_b',3,1))
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for code in [32,*map(ord,'123SL')]: user32.keybd_event(code,0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/loop-control-editor-checks.json',report)
    return report


if __name__=='__main__': print('Loop control editor:',len(verify()['checks']),'checks passed.')
