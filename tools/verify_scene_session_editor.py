"""Actual editor, physical keyboard input and SDL audio/UI/GPU scene handoff."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QInputDialog
from editor.core.document import save_json
from editor.core.projects import compile_project
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.create_scene_session_demo import SLOT

def verify():
    directory=ROOT/'.cache'/('scene-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/scene_session_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=window.screen().availableGeometry(); window.resize(min(1600,screen.width()-24),min(960,screen.height()-60)); window.show()
    out=ROOT/'artifacts/validation/scene-session'; out.mkdir(parents=True,exist_ok=True)
    messages=[]; window.runtime.message.connect(messages.append)
    original_start=window.runtime.process.start
    window.runtime.process.start=lambda exe,args:original_start(exe,[*args,'--save-root',str(directory/'saves')])
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory),binary_sha256=hashlib.sha256((ROOT/'build/node_view.exe').read_bytes()).hexdigest())
    u=ctypes.windll.user32; u.SetForegroundWindow.argtypes=[wintypes.HWND]
    u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]; u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    u.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,seconds=35):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText())
    def command(name,**data):
        begin=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]; check('Preview '+name,not any(m.get('event')=='node_error' for m in result)); return result
    def snapshot(label):
        s=next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot'); save_json(out/('editor-'+label+'.json'),s); return s
    def audio(): return next(m['status'] for m in command('audio_output_status') if m.get('event')=='audio_output_status')
    def state_until(label,predicate):
        end=time.monotonic()+15
        while True:
            state=snapshot(label)
            if predicate(state) or time.monotonic()>=end: return state
            QTest.qWait(150)
    def focus():
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId())); u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(80); u.mouse_event(4,0,0,0,0); QTest.qWait(100)
        s=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Native viewport receives physical input',s['focused'] and s['sdl_focused'])
    def key(letter):
        u.keybd_event(ord(letter),0,0,0); QTest.qWait(80); u.keybd_event(ord(letter),0,2,0); QTest.qWait(180)
    def dialog_action(action,value):
        def accept():
            dialog=next(w for w in app.topLevelWidgets() if isinstance(w,QInputDialog) and w.isVisible())
            dialog.setTextValue(value); dialog.accept()
        QTimer.singleShot(150,accept); window.actions[action].trigger(); QTest.qWait(100)
    try:
        check('Production runtime is current',current(ROOT/'build/node_view.exe'))
        for type_id in [1019,1020,7004,7005,7006,7007,7008,7009]:
            name=window.adapter.registry[type_id].name; window.library_search.setText(name); QTest.qWait(40); tree=window.library_tree
            item=next(tree.topLevelItem(i).child(j) for i in range(tree.topLevelItemCount()) for j in range(tree.topLevelItem(i).childCount()) if tree.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            count=len(window.adapter.graph.all_nodes()); tree.scrollToItem(item); QTest.qWait(40)
            pos=tree.visualItemRect(item).center(); QTest.mouseClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos)
            check(name+' Library insertion',len(window.adapter.graph.all_nodes())==count+1)
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==count)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==count+1); window.actions['Undo'].trigger()
        window.library_search.clear(); window.save_project()
        dialog_action('New Scene…','scratch'); check('New Scene dialog creates editable documents',window.scene_id=='scratch' and (directory/'graphs/scratch.json').is_file())
        window.actions['Use as Startup Scene'].trigger(); check('Startup choice marks project dirty',window.dirty); window.save_project()
        dialog_action('Choose Scene…','menu — Menu'); check('Scene picker changes graph without changing startup',window.scene_id=='menu' and window.project['entry_scene']=='scratch')
        check('Preview and build select different entry scenes correctly',window.snapshot_project(preview=True)['entry_scene']=='menu' and window.snapshot_project()['entry_scene']=='scratch')
        window.actions['Use as Startup Scene'].trigger(); window.save_project(); signature=window.signature()
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.container is not None and window.runtime.state=='running'); focus()
        first=snapshot('menu'); check('Menu starts with no playback device',first['scene_session']['active']=='menu' and not audio()['connected'])
        key('C'); level=state_until('level',lambda s:s['scene_session']['active']=='level' and s['physics']['ticks']>0); check('Physical C replaces world and graph',level['scene_session']['active']=='level' and len(level['entities'])==4 and level['physics']['ticks']>0)
        check('Entering first audible scene opens device',audio()['connected'])
        check('Runtime scene change does not switch authored graph',window.scene_id=='menu' and window.runtime_scene=='level' and window.signature()==signature)
        key('S'); saved=snapshot('saved'); slot=next((directory/'saves').rglob('slot-*.json')); raw=slot.read_bytes(); record=json.loads(raw)['checkpoint']
        check('Scene checkpoint saves',saved['persistence']['success'] and record['scene_session']['active']=='level')
        key('M'); menu=snapshot('returned'); check('Return removes simulation systems and shows menu',menu['scene_session']['active']=='menu' and len(menu['entities'])==2 and not menu['timers'])
        key('L'); restored=snapshot('loaded'); check('Cross-scene load restores graph bindings without Scene Loaded',restored['scene_session']['active']=='level' and restored['logs'].count('Loaded level')==1 and slot.read_bytes()==raw)
        key('M'); key('P'); frozen=snapshot('before-failure')
        asset=directory/'assets/robot.glb'; original=asset.read_bytes(); asset.write_bytes(b'broken asset for rollback probe')
        try:
            key('C'); failed=snapshot('failed'); check('Changed asset rejects scene before replacing live world',failed['scene_session']['active']=='menu' and not failed['scene_session']['success'] and failed['entities']==frozen['entities'] and failed['clock']['paused'])
            check('Scene failure callback runs on previous graph',len(failed['logs'])==len(frozen['logs'])+1 and failed['scene_session']['error'] in failed['logs'][-1])
        finally: asset.write_bytes(original)
        key('C'); retried=snapshot('retried'); check('Restored resources allow retry while keeping pause',retried['scene_session']['active']=='level' and retried['clock']['paused'] and retried['physics']['ticks']==0)
        key('U'); key('R'); reloaded=snapshot('reloaded'); check('Reload initializes scene again',reloaded['logs'].count('Loaded level')==3 and not reloaded['clock']['paused'])
        command('pause'); before=snapshot('before-invalid-ir'); bad=compile_project(window.snapshot_project(preview=True)); bad['entry_scene']='missing'
        begin=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[begin:]))
        check('Invalid project reload preserves current scene and all state',snapshot('after-invalid-ir')==before)
        window.adapter.clear_selection()
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='C_action')
        node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node])
        window.output_tabs.setCurrentWidget(window.console); QTest.qWait(120)
        picture=ROOT/'artifacts/validation/scene-session-editor.png'; check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(picture))); report['screenshot_sha256']=hashlib.sha256(picture.read_bytes()).hexdigest()
        dialog_action('Choose Scene…','level — Level'); wait(lambda:not window.runtime.active)
        check('Scene picker shuts down embedded preview before switching documents',window.scene_id=='level' and window.container is None and not window.dirty)
        report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for code in map(ord,'CMRPSLU'): u.keybd_event(code,0,2,0)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        if window.runtime.active:
            window.runtime.shutdown(); end=time.monotonic()+12
            while window.runtime.active and time.monotonic()<end: QTest.qWait(20)
            if window.runtime.active: window.runtime.process.kill(); window.runtime.process.waitForFinished(3000)
        report['passed']=report['passed'] and fingerprint()==report['native_fingerprint']
        (out/'editor-console.log').write_text(window.console.toPlainText(),encoding='utf-8'); save_json(ROOT/'artifacts/validation/scene-session-editor-checks.json',report)
        window.dirty=False; window.close(); QTest.qWait(50)
    return report

if __name__=='__main__': print('Scene editor:',len(verify()['checks']),'checks passed.')
