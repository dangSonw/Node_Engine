"""Real Qt binding authoring and mixed physical-key/SDL-gamepad gameplay."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QSettings,QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from editor.core.document import load_project,save_json
from editor.core.builder import GraphBuilder
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.input import InputDialog

def verify():
    directory=ROOT/'.cache'/('input-bindings-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/input_bindings_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for n in graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']='input-bindings-editor-'+uuid.uuid4().hex
    builder=GraphBuilder(); builder.graph=graph
    builder.add('probe_update','On Update'); builder.add('probe_pads','Get Connected Controllers'); builder.add('probe_inventory','Set Integer Array Variable',Name='connected')
    builder.connect('probe_update','Out','probe_inventory','In').connect('probe_pads','Value','probe_inventory','Value')
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8')); scene['variables']['connected']=dict(type='array<int>',value=[])
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',builder.graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat)); window.resize(1600,960); window.show()
    start=window.runtime.start; window.runtime.start=lambda exe,ir,root:start(ROOT/'build/node_gamepad_host_probe.exe',ir,root)
    messages=[]; window.runtime.message.connect(messages.append)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory),host_probe_sha256=hashlib.sha256((ROOT/'build/node_gamepad_host_probe.exe').read_bytes()).hexdigest())
    u=ctypes.windll.user32; u.SetForegroundWindow.argtypes=[wintypes.HWND]; u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
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
    def probe(op,**data):
        result=command('probe_gamepad',operation=op,**data); QTest.qWait(130)
        return next(m['controller'] for m in result if m.get('event')=='probe_gamepad')
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    def value(s,k):
        v=s['variables'][k]; return v['value'] if isinstance(v,dict) else v
    def focus():
        window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId())); u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(80); u.mouse_event(4,0,0,0,0); QTest.qWait(160)
        s=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Real native viewport focus',s['focused'] and s['sdl_focused'])
    def key(letter,down=None):
        code=32 if letter=='Space' else ord(letter)
        if down is None: key(letter,True); key(letter,False); return
        u.keybd_event(code,0,0 if down else 2,0); QTest.qWait(100)
    try:
        check('Native build matches source',current(ROOT/'build/node_view.exe'))
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.container is not None)
        pid=window.runtime.process.processId(); original=json.loads(json.dumps(window.scene['input']))
        errors=[]
        def edit():
            dialog=app.activeModalWidget()
            try:
                check('Real bindings dialog opened',isinstance(dialog,InputDialog)); dialog.tabs.setCurrentIndex(1)
                table=dialog.gamepad_table
                action=next(r for r in range(table.rowCount()) if table.cellWidget(r,0).currentText()=='Action')
                combo=table.cellWidget(action,3); combo.setFocus(); QTest.keyClick(combo,Qt.Key.Key_E)
                check('Keyboard selects East gamepad button',combo.currentText()=='East')
                row=next(r for r in range(table.rowCount()) if table.cellWidget(r,0).currentText()=='Analog axis' and table.item(r,1).text()=='horizontal')
                zone=table.cellWidget(row,5); zone.setFocus(); zone.selectAll(); QTest.keyClicks(zone,'1')
                ok=dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
                QTest.mouseClick(ok,Qt.MouseButton.LeftButton); check('Invalid dead zone stays editable',dialog.isVisible() and bool(dialog.error.text()))
                zone.setFocus(); zone.selectAll(); QTest.keyClicks(zone,'0.25')
                QTest.mouseClick(ok,Qt.MouseButton.LeftButton)
            except Exception as e: errors.append(e); dialog.reject()
        QTimer.singleShot(80,edit); window.actions['Input Actions and Axes…'].trigger()
        if errors: raise errors[0]
        wait(lambda:window.reload_request is None); changed=json.loads(json.dumps(window.scene['input']))
        check('Scene stores mixed gamepad bindings',changed['actions']['turn'][-1]['button']=='East' and changed['axes']['horizontal']['gamepads'][0]['dead_zone']==.25)
        check('Live binding edit reloads the same native process',window.runtime.process.processId()==pid and snapshot()['scene']['input']==changed)
        window.actions['Undo'].trigger(); wait(lambda:window.reload_request is None); check('Undo restores original mapping',window.scene['input']==original and snapshot()['scene']['input']==original)
        window.actions['Redo'].trigger(); wait(lambda:window.reload_request is None); check('Redo restores new mapping',window.scene['input']==changed and snapshot()['scene']['input']==changed)
        check('Bindings save and reopen intact',window.save_project() and load_project(directory/'project.json')[2]['input']==changed)
        command('play'); hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle'); focus()
        initial=snapshot(); report['physical_controller_count']=len(value(initial,'connected'))
        check('No physical device interferes with virtual acceptance',not value(initial,'connected'))
        first=probe('connect'); before=snapshot(); baseline=value(before,'turns')
        probe('axis',axis=0,value=1000); check('Authored dead zone suppresses jitter',value(snapshot(),'horizontal')==0)
        probe('axis',axis=0,value=16384); moved=snapshot()
        check('Authored analog binding moves the robot',.33<value(moved,'horizontal')<.34 and moved['entities']['player']['position'][0]>before['entities']['player']['position'][0])
        key('D',True); check('Physical keyboard and analog saturate together',value(snapshot(),'horizontal')==1)
        key('D',False); probe('axis',axis=0,value=0)
        probe('button',button=13,down=True); check('Bound D-pad drives the same axis',value(snapshot(),'horizontal')==-1); probe('button',button=13,down=False)
        probe('button',button=0,down=True); probe('button',button=0,down=False); check('Removed South binding no longer turns',value(snapshot(),'turns')==baseline)
        key('Space',True); probe('button',button=1,down=True); key('Space',False); handoff=snapshot()
        check('Keyboard-to-gamepad handoff holds one action without a second press',value(handoff,'turns')==baseline+1 and value(handoff,'turn_held'))
        u.mouse_event(2,0,0,0,0); QTest.qWait(100); probe('button',button=1,down=False)
        check('Gamepad-to-mouse handoff stays held',value(snapshot(),'turn_held') and value(snapshot(),'turns')==baseline+1)
        u.mouse_event(4,0,0,0,0); QTest.qWait(140); released=snapshot()
        check('Final alternative release ends action once',not value(released,'turn_held') and value(released,'action_releases')==value(handoff,'action_releases')+1)
        probe('button',button=1,down=True); command('pause'); paused=snapshot(); command('play'); focus()
        check('Resume does not activate an already-held mapped button',not value(snapshot(),'turn_held'))
        probe('button',button=1,down=False); before=snapshot(); probe('button',button=1,down=True)
        check('Release/repress rearms mapped action',value(snapshot(),'turns')==value(before,'turns')+1)
        QTest.mouseClick(window.hierarchy.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(30,30)); QTest.qWait(180)
        check('Editor focus releases the mapped action',not value(snapshot(),'turn_held'))
        probe('axis',axis=0,value=32767); check('Unfocused mapped analog is neutral',value(snapshot(),'horizontal')==0)
        focus(); check('Refocus samples current mapped analog',value(snapshot(),'horizontal')==1 and not value(snapshot(),'turn_held'))
        probe('axis',axis=0,value=0); probe('button',button=1,down=False); probe('button',button=1,down=True)
        key('S'); saved=snapshot(); check('Physical Save succeeds',saved['persistence']['success'])
        probe('button',button=1,down=False); probe('button',button=1,down=True); key('R'); key('L'); loaded=snapshot()
        check('Load restores pose and action counters without held repeat',loaded['entities']==saved['entities'] and value(loaded,'turns')==value(saved,'turns') and not value(loaded,'turn_held'))
        probe('button',button=1,down=False); probe('button',button=1,down=True); before=snapshot(); probe('disconnect'); unplug=snapshot()
        check('Unplug delivers one mapped release',not value(unplug,'turn_held') and value(unplug,'action_releases')==value(before,'action_releases')+1)
        second=probe('connect'); before=snapshot(); probe('button',button=1,down=True); probe('button',button=1,down=False)
        check('Any-controller binding follows reconnect ID',second!=first and value(snapshot(),'turns')==value(before,'turns')+1)
        command('stop'); command('play'); command('pause'); check('Stop/fresh Play resets gameplay',value(snapshot(),'turns')==0)
        window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='axis'); node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/input-bindings-editor.png'; check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture))); report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        probe('disconnect'); command('quit'); wait(lambda:not window.runtime.ready); check('Sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); report['messages']=messages[-40:]; report['console']=window.console.toPlainText(); window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/input-bindings-editor-failure.png')); raise
    finally:
        for code in [32,*[ord(c) for c in 'ADSRL']]: u.keybd_event(code,0,2,0)
        u.mouse_event(4,0,0,0,0)
        if window.runtime.ready: window.runtime.send('quit'); QTest.qWait(200)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3); window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents(); save_json(ROOT/'artifacts/validation/input-bindings-editor-checks.json',report)
    return report

if __name__=='__main__': print('Input bindings editor:',len(verify()['checks']),'checks passed.')
