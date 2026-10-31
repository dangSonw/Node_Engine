"""Actual context authoring, physical menu keys and SDL virtual-gamepad gating."""
import ctypes,hashlib,json,shutil,sys,time,uuid
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QSettings,QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QListWidget
from editor.core.document import load_project,save_json
from editor.core.builder import GraphBuilder
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.input import InputDialog

def verify():
    directory=ROOT/'.cache'/('input-contexts-editor-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/input_contexts_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for n in graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']='input-contexts-editor-'+uuid.uuid4().hex
    b=GraphBuilder(); b.graph=graph; b.add('probe_update','On Update'); b.add('probe_pads','Get Connected Controllers'); b.add('probe_store','Set Integer Array Variable',Name='connected')
    b.connect('probe_update','Out','probe_store','In').connect('probe_pads','Value','probe_store','Value')
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8')); scene['variables']['connected']=dict(type='array<int>',value=[])
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=window.screen().availableGeometry(); window.resize(min(1600,screen.width()-24),min(960,screen.height()-60)); window.show()
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
        s=next(m for m in command('cursor_status') if m.get('event')=='cursor_status'); check('Embedded viewport has real native focus',s['focused'] and s['sdl_focused'])
    def key(letter):
        u.keybd_event(ord(letter),0,0,0); QTest.qWait(80); u.keybd_event(ord(letter),0,2,0); QTest.qWait(140)
    try:
        check('Production runtime matches current source',current(ROOT/'build/node_view.exe'))
        for type_id,name in [(10021,'Set Input Context Enabled'),(10022,'Is Input Context Enabled')]:
            window.library_search.setText(name); QTest.qWait(40); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount()) for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            before=len(window.adapter.graph.all_nodes()); library.scrollToItem(item); QTest.qWait(60)
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center()); QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center()); QTest.qWait(60)
            check(name+' creates from Library',len(window.adapter.graph.all_nodes())==before+1)
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
        window.library_search.clear(); window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.container is not None)
        pid=window.runtime.process.processId(); original=json.loads(json.dumps(window.scene['input'])); errors=[]
        def edit():
            dialog=app.activeModalWidget()
            try:
                check('Input dialog exposes Contexts tab',isinstance(dialog,InputDialog)); dialog.tabs.setCurrentIndex(2)
                table=dialog.context_table; toggle=table.cellWidget(0,1)
                QTest.mouseClick(toggle,Qt.MouseButton.LeftButton,pos=QPoint(9,toggle.height()//2))
                def members():
                    child=app.activeModalWidget()
                    try:
                        axes=next(w for w in child.findChildren(QListWidget) if w.accessibleName()=='Context axes')
                        item=next(axes.item(i) for i in range(axes.count()) if axes.item(i).data(Qt.ItemDataRole.UserRole)=='trigger')
                        rect=axes.visualItemRect(item); QTest.mouseClick(axes.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(rect.left()+9,rect.center().y()))
                        check('Checkbox removes trigger from the context',item.checkState()==Qt.CheckState.Unchecked)
                        QTest.qWait(100)
                        capture=ROOT/'artifacts/validation/input-contexts-members.png'; check('Context member dialog capture',child.screen().grabWindow(int(child.winId())).save(str(capture)))
                        QTest.mouseClick(child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
                    except Exception as e: errors.append(e); child.reject()
                QTimer.singleShot(80,members); table.cellWidget(0,2).click()
                wait(lambda:app.activeModalWidget() is dialog)
                if errors: raise errors[0]
                check('Context starts disabled and retains selected members',not table.cellWidget(0,1).isChecked() and table.cellWidget(0,2).property('members')['axes']==['horizontal','vertical'])
                QTest.qWait(100)
                capture=ROOT/'artifacts/validation/input-contexts-dialog.png'; check('Context table capture',dialog.screen().grabWindow(int(dialog.winId())).save(str(capture)))
                QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
            except Exception as e: errors.append(e); dialog.reject()
        QTimer.singleShot(80,edit); window.actions['Input Actions and Axes…'].trigger()
        if errors: raise errors[0]
        wait(lambda:window.reload_request is None); changed=json.loads(json.dumps(window.scene['input']))
        check('Context edit reloads same native process',window.runtime.process.processId()==pid and snapshot()['scene']['input']==changed)
        window.actions['Undo'].trigger(); wait(lambda:window.reload_request is None); check('Undo restores context definition',window.scene['input']==original and snapshot()['scene']['input']==original)
        window.actions['Redo'].trigger(); wait(lambda:window.reload_request is None); check('Redo restores context definition',window.scene['input']==changed and snapshot()['scene']['input']==changed)
        check('Context project saves and reopens',window.save_project() and load_project(directory/'project.json')[2]['input']==changed)
        command('play'); hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle'); focus()
        initial=snapshot(); report['physical_controller_count']=len(value(initial,'connected')); check('Authored disabled context is live with no physical controller',not value(initial,'game_enabled') and not value(initial,'connected'))
        probe('connect'); probe('axis',axis=0,value=16384); probe('axis',axis=4,value=32767); probe('button',button=0,down=True)
        disabled=snapshot(); check('Context blocks gameplay but unassigned trigger axis still works',value(disabled,'horizontal')==0 and value(disabled,'turns')==0 and value(disabled,'trigger')==1)
        key('M'); enabled=snapshot(); check('Raw menu key enables context without repeating held South',value(enabled,'game_enabled') and .37<value(enabled,'horizontal')<.38 and not value(enabled,'turn_held') and value(enabled,'turns')==0)
        probe('button',button=0,down=False); probe('button',button=0,down=True); check('New press after neutral rearms gameplay action',value(snapshot(),'turns')==1)
        key('M'); menu=snapshot(); check('Menu disables movement and releases held action once',not value(menu,'game_enabled') and value(menu,'horizontal')==0 and not value(menu,'turn_held') and value(menu,'action_releases')==1)
        key('S'); saved=snapshot(); check('Physical Save while context disabled succeeds',saved['persistence']['success'])
        key('M'); probe('axis',axis=0,value=0); probe('button',button=0,down=False); probe('button',button=0,down=True); key('L'); loaded=snapshot()
        check('Load restores disabled context, pose and counters',not value(loaded,'game_enabled') and loaded['entities']==saved['entities'] and value(loaded,'turns')==value(saved,'turns'))
        key('M'); check('Physical Load reconciliation keeps held action neutral',value(snapshot(),'game_enabled') and not value(snapshot(),'turn_held'))
        probe('button',button=0,down=False); probe('button',button=0,down=True); key('M'); key('M'); key('S'); rearm=snapshot()
        check('Can save enabled context while waiting for held-button rearm',rearm['persistence']['success'] and value(rearm,'game_enabled') and not value(rearm,'turn_held'))
        key('M'); probe('button',button=0,down=False); key('L'); restored=snapshot()
        check('Load restores enabled context with physical neutral controls',value(restored,'game_enabled') and not value(restored,'turn_held') and value(restored,'turns')==value(rearm,'turns'))
        probe('button',button=0,down=True); check('Fresh press after Load is accepted once',value(snapshot(),'turns')==value(rearm,'turns')+1)
        command('pause'); command('play'); focus(); check('Pause retains enabled context and suppresses held gamepad',value(snapshot(),'game_enabled') and not value(snapshot(),'turn_held'))
        probe('button',button=0,down=False); probe('button',button=0,down=True); before=snapshot()
        QTest.mouseClick(window.hierarchy.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(30,30)); QTest.qWait(180)
        lost=snapshot(); check('Focus loss releases action without disabling context',value(lost,'game_enabled') and not value(lost,'turn_held') and value(lost,'action_releases')==value(before,'action_releases')+1)
        command('stop'); command('play'); QTest.qWait(180); command('pause'); fresh=snapshot()
        check('Fresh Play restores authored disabled context and zero counters',not value(fresh,'game_enabled') and value(fresh,'turns')==0)
        window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='context_set'); node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(100)
        capture=ROOT/'artifacts/validation/input-contexts-editor.png'; check('Context editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        report['dialog_sha256']={n:hashlib.sha256((ROOT/'artifacts/validation'/n).read_bytes()).hexdigest() for n in ('input-contexts-dialog.png','input-contexts-members.png')}
        probe('disconnect'); command('quit'); wait(lambda:not window.runtime.ready); check('Sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as e:
        report['error']=str(e); report['messages']=messages[-40:]; report['console']=window.console.toPlainText(); window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/input-contexts-editor-failure.png')); raise
    finally:
        for c in 'MSL': u.keybd_event(ord(c),0,2,0)
        u.mouse_event(4,0,0,0,0)
        if window.runtime.ready: window.runtime.send('quit'); QTest.qWait(200)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3); window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents(); save_json(ROOT/'artifacts/validation/input-contexts-editor-checks.json',report)
    return report

if __name__=='__main__': print('Input contexts editor:',len(verify()['checks']),'checks passed.')
