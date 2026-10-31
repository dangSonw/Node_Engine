"""Real Qt/SDL viewport driven by an SDL virtual controller in the shared host."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.builder import GraphBuilder
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow

def verify():
    directory=ROOT/'.cache'/('gamepad-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/gamepad_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='gamepad-editor-'+uuid.uuid4().hex
    b=GraphBuilder(); b.graph=graph; b.add('probe_mouse_update','On Update'); b.add('probe_mouse_held','Is Key Held',Key='MouseLeft'); b.add('probe_mouse_save','Set Boolean Variable',Name='mouse_held')
    b.connect('probe_mouse_update','Out','probe_mouse_save','In').connect('probe_mouse_held','Value','probe_mouse_save','Value')
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8')); scene['variables']['mouse_held']=dict(type='bool',value=False)
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
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
    def value(s,key):
        v=s['variables'][key]; return v['value'] if isinstance(v,dict) else v
    def focus():
        window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId())); u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(80)
        check('Gamepad synchronization preserves the physical focus-click hold',value(snapshot(),'mouse_held'))
        u.mouse_event(4,0,0,0,0); QTest.qWait(160)
        status=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Embedded SDL receives real native focus',status['focused'] and status['sdl_focused'])
    def key(letter):
        u.keybd_event(ord(letter),0,0,0); QTest.qWait(80); u.keybd_event(ord(letter),0,2,0); QTest.qWait(130)
    try:
        check('Production native sources match build',current(ROOT/'build/node_view.exe'))
        for type_id,name,inputs,outputs in [(10018,'Get Connected Controllers',set(),{'Value'}),
            (10019,'Get Gamepad Axis',{'Controller','Axis','Dead Zone'},{'Value'}),(10020,'On Gamepad Button',{'Filter'},{'Out','Button','Down','Controller'})]:
            window.library_search.setText(name); QTest.qWait(50); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount()) for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); before=len(window.adapter.graph.all_nodes()); QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center()); QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(name+' created from Library',len(window.adapter.graph.all_nodes())==before+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            check(name+' typed ports present',set(created.inputs())==inputs and set(created.outputs())==outputs)
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1); window.actions['Undo'].trigger()
        window.library_search.clear(); check('Gamepad graph saves and reopens',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle'); focus()
        initial=snapshot(); report['physical_controller_count']=value(initial,'count'); check('No attached hardware interferes with virtual-controller acceptance',value(initial,'count')==0)
        first=probe('connect'); s=snapshot(); check('SDL hotplug updates graph inventory',value(s,'controllers')==[first])
        probe('axis',axis=0,value=1000); check('Default dead zone removes stick jitter',value(snapshot(),'left_x')==0)
        before=snapshot(); probe('axis',axis=0,value=16384); moved=snapshot()
        check('Actual SDL analog events move the rendered robot',.4<value(moved,'left_x')<.5 and moved['entities']['player']['position'][0]>before['entities']['player']['position'][0])
        probe('axis',axis=0,value=0); probe('axis',axis=4,value=32767); check('SDL trigger reaches normalized one',value(snapshot(),'trigger')==1)
        probe('button',button=0,down=True); down=snapshot(); check('South press turns robot and records controller',value(down,'presses')==1 and value(down,'last_controller')==first and down['entities']['player']['rotation']==[0,90,0])
        QTest.qWait(180); check('Held button does not repeat',value(snapshot(),'presses')==1)
        probe('button',button=0,down=False); check('Release callback reaches graph',value(snapshot(),'releases')==1)
        probe('button',button=1,down=True); command('pause'); paused=snapshot(); command('play'); focus(); resumed=snapshot()
        check('Resume does not fabricate a held-button press',value(resumed,'presses')==value(paused,'presses'))
        probe('button',button=1,down=False); probe('button',button=1,down=True); rearmed=snapshot()
        check('Release and repress rearm after Pause',value(rearmed,'presses')==value(paused,'presses')+1)
        QTest.mouseClick(window.hierarchy.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(30,30)); QTest.qWait(180); unfocused=snapshot()
        check('Qt panel focus releases held gamepad button',value(unfocused,'releases')==value(rearmed,'releases')+1)
        probe('axis',axis=0,value=32767); check('Unfocused gamepad does not move gameplay',value(snapshot(),'left_x')==0)
        focus(); refocused=snapshot(); check('Refocus samples analog without repeating held button',value(refocused,'left_x')==1 and value(refocused,'presses')==value(rearmed,'presses'))
        probe('axis',axis=0,value=0); probe('button',button=1,down=False); probe('button',button=0,down=True); key('S'); saved=snapshot(); check('Physical keyboard saves live gamepad state',saved['persistence']['success'])
        probe('button',button=0,down=False); probe('button',button=0,down=True); key('R'); key('L'); loaded=snapshot()
        check('Load restores pose and counters without repeating held input',loaded['entities']==saved['entities'] and value(loaded,'presses')==value(saved,'presses'))
        probe('button',button=0,down=False); probe('button',button=0,down=True); before=snapshot(); probe('disconnect'); unplugged=snapshot()
        check('Unplug clears inventory and emits the final release',value(unplugged,'controllers')==[] and value(unplugged,'releases')==value(before,'releases')+1)
        second=probe('connect'); probe('button',button=0,down=True); probe('button',button=0,down=False); QTest.qWait(240); s=snapshot()
        check('Reconnection has a new ID and delayed payload retains it',second!=first and value(s,'controllers')==[second] and value(s,'delayed_controller')==second)
        command('stop'); command('play'); focus(); check('Fresh Play sees connected device with reset counters',value(snapshot(),'controllers')==[second] and value(snapshot(),'presses')==0)
        command('pause'); window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='axis_left_x'); node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/gamepad-editor.png'; check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture))); report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        probe('disconnect'); command('quit'); wait(lambda:not window.runtime.ready); check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); report['messages']=messages[-40:]; report['console']=window.console.toPlainText(); window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/gamepad-editor-failure.png')); raise
    finally:
        for code in [ord(c) for c in 'SRL']: u.keybd_event(code,0,2,0)
        u.mouse_event(4,0,0,0,0)
        if window.runtime.ready: window.runtime.send('quit'); QTest.qWait(200)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3); window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents(); save_json(ROOT/'artifacts/validation/gamepad-editor-checks.json',report)
    return report

if __name__=='__main__': print('Gamepad editor:',len(verify()['checks']),'checks passed.')
