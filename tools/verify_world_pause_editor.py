"""Real editor authoring and physical P/R/S/L input in its production SDL viewport."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QProcess,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.create_world_pause_demo import SLOT

def verify():
    directory=ROOT/'.cache'/('world-pause-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/world_pause_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    game='world-pause-editor-'+uuid.uuid4().hex; graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    next(n for n in graph['nodes'] if n['id']=='storage')['values']['Game ID']=game; save_json(directory/'graphs/gameplay.json',graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=window.screen().availableGeometry(); window.resize(min(1600,screen.width()-24),min(960,screen.height()-60)); window.show()
    out=ROOT/'artifacts/validation/world-pause'; out.mkdir(parents=True,exist_ok=True)
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
    def simulation(s): return {k:s[k] for k in ('entities','physics','animation','time')}
    def focus():
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId())); u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(80); u.mouse_event(4,0,0,0,0); QTest.qWait(100)
        s=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Native viewport receives physical input',s['focused'] and s['sdl_focused'])
    def key(letter):
        u.keybd_event(ord(letter),0,0,0); QTest.qWait(80); u.keybd_event(ord(letter),0,2,0); QTest.qWait(160)
    try:
        check('Production runtime is current',current(ROOT/'build/node_view.exe'))
        for type_id,name in [(1017,'On Game Pause'),(1018,'On Game Resume'),(7001,'Pause World'),(7002,'Resume World'),(7003,'Is World Paused')]:
            window.library_search.setText(name); QTest.qWait(50); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount()) for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            before=len(window.adapter.graph.all_nodes()); library.scrollToItem(item); QTest.qWait(60)
            pos=library.visualItemRect(item).center(); QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=pos)
            check(name+' creates from Library',len(window.adapter.graph.all_nodes())==before+1)
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1); window.actions['Undo'].trigger()
        window.library_search.clear(); check('Graph saves and reopens',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document()); signature=window.signature()
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.container is not None and window.runtime.state=='running'); focus()
        key('P'); first=snapshot('paused'); QTest.qWait(400); later=snapshot('paused-later')
        check('Physical P pauses simulation while host and unscaled timers advance',first['clock']['paused'] and simulation(first)==simulation(later) and later['frame']>first['frame'] and later['variables']['unscaled_ticks']>first['variables']['unscaled_ticks'])
        key('P'); repeated=snapshot('repeated'); check('Repeated physical P is idempotent',repeated['variables']['pauses']==1 and repeated['variables']['resumes']==0)
        command('pause'); before=snapshot('editor-paused'); QTest.qWait(200)
        check('Editor Pause suspends host without a game transition',snapshot('editor-paused-later')==before)
        command('play'); focus(); key('R'); resumed=snapshot('resumed')
        check('Physical R resumes all simulation systems',not resumed['clock']['paused'] and resumed['physics']['ticks']>before['physics']['ticks'] and resumed['animation']!=before['animation'] and resumed['variables']['resumes']==1)
        command('pause'); count=resumed['variables']['pauses']; command('play'); focus(); after_debug=snapshot('after-debug')
        check('Editor debug Pause/Play does not synthesize Game Pause/Resume',after_debug['variables']['pauses']==count and after_debug['variables']['resumes']==1)
        key('P'); key('S'); saved=snapshot('saved'); slot=directory/'saves'/game/('slot-'+SLOT.encode().hex()+'.json')
        raw=slot.read_bytes(); record=json.loads(raw)['checkpoint']; check('Physical S saves the paused world',record['clock']['paused'] and saved['persistence']['success'])
        key('R'); moving=snapshot('moving-again'); key('L'); loaded=snapshot('loaded')
        check('Physical L restores paused state without replaying lifecycle events',loaded['clock']['paused'] and loaded['time']==record['clock']['time'] and loaded['variables']['pauses']==record['scene']['variables']['pauses'] and loaded['variables']['resumes']==record['scene']['variables']['resumes'] and moving['time']>loaded['time'] and slot.read_bytes()==raw)
        command('pause'); before=snapshot('rollback-before'); bad=compile_graph(window.adapter.document(),window.scene); bad['events']['world_pause'][0]['event']=999
        begin=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[begin:])); check('Invalid pause event reload preserves live world',snapshot('rollback-after')==before)
        window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='world_P')
        node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); window.output_tabs.setCurrentIndex(0); QTest.qWait(150)
        picture=ROOT/'artifacts/validation/world-pause-editor.png'; check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(picture))); report['screenshot_sha256']=hashlib.sha256(picture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot('stopped')
        check('Editor Stop resets pause and callback counters',not stopped['clock']['paused'] and stopped['frame']==0 and stopped['variables']['pauses']==stopped['variables']['resumes']==0)
        command('play'); restarted=snapshot('restarted'); check('Fresh Play starts unpaused',not restarted['clock']['paused'] and restarted['variables']['pauses']==0)
        check('Editor graph remains unchanged',signature==window.signature()); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for keycode in map(ord,'PRSL'): u.keybd_event(keycode,0,2,0)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        if window.runtime.active:
            window.runtime.shutdown()
            end=time.monotonic()+12
            while window.runtime.active and time.monotonic()<end: QTest.qWait(20)
            if window.runtime.active: window.runtime.process.kill(); window.runtime.process.waitForFinished(3000)
        report['passed']=report['passed'] and fingerprint()==report['native_fingerprint']
        (out/'editor-console.log').write_text(window.console.toPlainText(),encoding='utf-8'); save_json(ROOT/'artifacts/validation/world-pause-editor-checks.json',report)
        window.close(); QTest.qWait(50)
    return report

if __name__=='__main__': print('World pause editor:',len(verify()['checks']),'checks passed.')
