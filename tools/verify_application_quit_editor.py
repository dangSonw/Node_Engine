"""Physical quit/restart, asynchronous editor close and standalone Alt+F4."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QProcess,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.create_application_quit_demo import SLOT


def verify():
    directory=ROOT/'.cache'/('application-quit-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/application_quit_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    game='application-quit-editor-'+uuid.uuid4().hex; graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    next(n for n in graph['nodes'] if n['id']=='storage')['values']['Game ID']=game; save_json(directory/'graphs/gameplay.json',graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=window.screen().availableGeometry(); window.resize(min(1600,screen.width()-24),min(960,screen.height()-60)); window.show()
    out=ROOT/'artifacts/validation/application-quit'; out.mkdir(parents=True,exist_ok=True)
    messages=[]; exits=[]; runs=[]; window.runtime.message.connect(messages.append); window.runtime.stopped.connect(exits.append)
    original_start=window.runtime.process.start
    def start_process(exe,args):
        prefix=out/('editor-run-'+str(len(runs)+1)); runs.append(dict(output=str(prefix.with_suffix('.json')),capture=str(prefix.with_suffix('.bmp'))))
        original_start(exe,[*args,'--save-root',str(directory/'saves'),'--output',runs[-1]['output'],'--capture',runs[-1]['capture']])
    window.runtime.process.start=start_process
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory),runs=runs,
        binary_sha256={n:hashlib.sha256((ROOT/'build'/n).read_bytes()).hexdigest() for n in ('node_view.exe','node_game_view.exe')})
    standalone=QProcess(); standalone_output=[]; standalone_errors=[]
    standalone.readyReadStandardOutput.connect(lambda:standalone_output.append(bytes(standalone.readAllStandardOutput()).decode('utf-8','replace')))
    standalone.readyReadStandardError.connect(lambda:standalone_errors.append(bytes(standalone.readAllStandardError()).decode('utf-8','replace')))
    u=ctypes.windll.user32; u.SetForegroundWindow.argtypes=[wintypes.HWND]; u.GetForegroundWindow.restype=wintypes.HWND
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
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    def value(s,k):
        v=s['variables'][k]; return v['value'] if isinstance(v,dict) else v
    def slot(): return directory/'saves'/game/('slot-'+SLOT.encode().hex()+'.json')
    def saved(): return json.loads(slot().read_text('utf-8'))['checkpoint']
    def focus():
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId())); u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(80); u.mouse_event(4,0,0,0,0); QTest.qWait(100)
        s=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Embedded native viewport has focus',s['focused'] and s['sdl_focused'])
    def key(letter,hold=80):
        code=32 if letter=='Space' else ord(letter)
        u.keybd_event(code,0,0,0); QTest.qWait(hold); u.keybd_event(code,0,2,0); QTest.qWait(140)
    def play():
        begin=len(messages); window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.container is not None and window.runtime.state=='running')
        return begin
    def finished(begin):
        wait(lambda:not window.runtime.active); QTest.qWait(100)
        check('Native game exits with code zero',exits[-1]==0)
        notices=[m for m in messages[begin:] if m.get('event')=='application_quit']; check('Exactly one shutdown notification',len(notices)==1 and notices[0]['success'])
        check('No graph error during shutdown',not any(m.get('event')=='node_error' for m in messages[begin:]))
        state=json.loads(Path(runs[-1]['output']).read_text('utf-8'))
        check('Final GPU capture saved',Path(runs[-1]['capture']).is_file()); return state,notices[0]
    try:
        check('Production runtime is current',current(ROOT/'build/node_view.exe'))
        for type_id,name in [(1010,'On Application Quit'),(26001,'Quit Application')]:
            window.library_search.setText(name); QTest.qWait(50); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount()) for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            before=len(window.adapter.graph.all_nodes()); library.scrollToItem(item); QTest.qWait(60)
            pos=library.visualItemRect(item).center(); QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=pos)
            check(name+' creates from Library',len(window.adapter.graph.all_nodes())==before+1)
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1); window.actions['Undo'].trigger()
        window.library_search.clear(); check('Graph saves and reopens',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        signature=window.signature(); begin=play(); command('stop')
        check('Editor Stop resets preview without invoking application quit',snapshot()['frame']==0 and not slot().exists())
        command('play'); focus(); key('D',180); key('Space'); command('pause'); before=snapshot()
        check('Physical input changes the robot before quit',before['entities']['player']['position'][0]>0 and value(before,'turns')>=1)
        bad=compile_graph(window.adapter.document(),window.scene); bad['events']['quit']={}; count=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[count:])); check('Malformed quit phase preserves paused live state',snapshot()==before)
        window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='quitting')
        node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(100)
        window.output_tabs.setCurrentIndex(0); QTest.qWait(100)
        capture=ROOT/'artifacts/validation/application-quit-editor.png'; check('Editor authoring screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        begin=len(messages); command('play'); focus(); key('Q'); state,notice=finished(begin)
        check('Physical Q runs cleanup once after the request output',value(state,'quit_count')==1 and value(state,'after_request') and value(state,'save_completed'))
        check('Quit checkpoint contains actual played pose and final frame',saved()['clock']['frame']==state['frame'] and saved()['scene']['variables']['quit_count']['value']==1)
        check('Quitting game leaves editor and graph intact',window.isVisible() and window.signature()==signature and window.actions['Play'].isEnabled())
        begin=play(); focus(); key('L'); command('pause'); restored=snapshot()
        check('Fresh preview loads exit save and remains open',value(restored,'quit_count')==1 and value(restored,'load_completed') and window.runtime.active)
        window.runtime.shutdown(); state,notice=finished(begin)
        check('IPC quit dispatches once while paused without advancing time',state['frame']==restored['frame'] and value(state,'quit_count')==2 and notice['started'])
        begin=play(); command('stop'); raw=slot().read_bytes(); window.runtime.shutdown(); state,notice=finished(begin)
        check('Unstarted preview does not run quit handlers or overwrite saves',state['frame']==0 and value(state,'quit_count')==0 and not notice['started'] and slot().read_bytes()==raw)
        # A real standalone window receives the native Alt+F4 close gesture.
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        standalone.setWorkingDirectory(str(ROOT/'examples/application_quit_demo'))
        final=out/'standalone-close.json'; picture=out/'standalone-close.bmp'
        standalone.start(str(ROOT/'build/node_game_view.exe'),['--project-root',str(ROOT/'examples/application_quit_demo'),'--save-root',str(directory/'standalone-saves'),
            '--output',str(final),'--capture',str(picture)])
        def standalone_messages(): return [json.loads(line) for line in ''.join(standalone_output).splitlines() if line.startswith('{') and line.endswith('}')]
        wait(lambda:any(m.get('event')=='state' and m.get('state')=='running' for m in standalone_messages()))
        hwnd=next(m['handle'] for m in standalone_messages() if m.get('event')=='window_handle'); u.SetForegroundWindow(hwnd); QTest.qWait(150)
        check('Standalone native window owns foreground',u.GetForegroundWindow()==hwnd)
        u.keybd_event(0x12,0,0,0); u.keybd_event(0x73,0,0,0); QTest.qWait(60); u.keybd_event(0x73,0,2,0); u.keybd_event(0x12,0,2,0)
        wait(lambda:standalone.state()==QProcess.ProcessState.NotRunning)
        (out/'standalone-close.log').write_text(''.join(standalone_output+standalone_errors),encoding='utf-8')
        state=json.loads(final.read_text('utf-8'))
        check('Physical Alt+F4 saves once before successful process exit',standalone.exitCode()==0 and value(state,'quit_count')==1 and value(state,'save_completed'))
        check('Native close reports once and produces final GPU image',sum(m.get('event')=='application_quit' for m in standalone_messages())==1 and picture.is_file())
        begin=play(); command('pause'); before=snapshot(); window.close(); wait(lambda:not window.runtime.active and not window.isVisible())
        state,notice=finished(begin); check('Closing editor waits asynchronously for game cleanup and save',state['frame']==before['frame'] and value(state,'quit_count')==1 and value(state,'save_completed'))
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); report['messages']=messages[-40:]; report['console']=window.console.toPlainText()
        window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/application-quit-editor-failure.png')); raise
    finally:
        for code in [32,0x12,0x73,*[ord(c) for c in 'DQL']]: u.keybd_event(code,0,2,0)
        u.mouse_event(4,0,0,0,0)
        if standalone.state()!=QProcess.ProcessState.NotRunning: standalone.kill(); standalone.waitForFinished(3000)
        if window.runtime.ready: window.runtime.send('quit'); QTest.qWait(500)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3); window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents(); save_json(ROOT/'artifacts/validation/application-quit-editor-checks.json',report)
    return report


if __name__=='__main__': print('Application quit editor:',len(verify()['checks']),'checks passed.')
