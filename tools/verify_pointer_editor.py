"""Actual Qt/embedded SDL pointer input, DPI coordinates and lifecycle checks."""
import ctypes
from ctypes import wintypes
import hashlib,json,shutil,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo

def verify():
    directory=ROOT/'.cache'/('pointer-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/pointer_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='pointer-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['ui_assets'][0]['rml']=scene['ui_assets'][0]['rml'].replace('</body>',
        '<div id="guard" style="display:block;position:absolute;left:10px;bottom:10px;width:150px;height:60px;overflow-y:auto;pointer-events:auto;background-color:#24324a;"><div style="display:block;height:400px;">UI scroll guard</div></div></body>')
    save_json(directory/'scenes/main.json',scene)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory))
    user32=ctypes.windll.user32
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
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
    def value(data,key): return data['variables'][key]['value']
    def near(a,b): return len(a)==len(b) and all(abs(x-y)<.02 for x,y in zip(a,b))
    def difference(a,b): return [x-y for x,y in zip(a,b)]
    def point(x,y):
        p=wintypes.POINT(x,y); assert user32.ClientToScreen(hwnd,ctypes.byref(p)); return p
    def move(x,y):
        p=point(x,y); assert user32.SetCursorPos(p.x,p.y); QTest.qWait(180)
    def key(letter):
        user32.keybd_event(ord(letter),0,0,0); QTest.qWait(100); user32.keybd_event(ord(letter),0,2,0); QTest.qWait(150)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for type_id,name in [(10013,'Get Mouse Position'),(10014,'Get Mouse Delta'),(10015,'Get Mouse Wheel')]:
            window.library_search.setText(name); QTest.qWait(60); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                      for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); before=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(name+' is created from Library',len(window.adapter.graph.all_nodes())==before+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            check(name+' has a typed vector output without mutable fields',set(created.outputs())=={'Value'} and not created.inputs())
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1)
            window.actions['Undo'].trigger()
        window.library_search.clear()
        check('Pointer graph survives save and reopen',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        user32.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        rect=wintypes.RECT(); assert user32.GetClientRect(hwnd,ctypes.byref(rect)); x,y=rect.right//2,rect.bottom*3//4
        move(x,y); user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(120)
        info=GuiInfo(); info.cbSize=ctypes.sizeof(info); user32.GetGUIThreadInfo(0,ctypes.byref(info))
        check('Embedded SDL has native keyboard focus',info.focus==hwnd)
        command('stop'); command('play'); QTest.qWait(100); baseline=snapshot()
        check('Fresh Play samples physical cursor without a motion impulse',near(value(baseline,'position'),[x,y,0]) and near(value(baseline,'start_position'),[x,y,0]) and value(baseline,'total_delta')==[0,0,0])
        move(x+40,y-20); moved=snapshot(); displacement=difference(value(moved,'position'),value(baseline,'position'))
        report['motion']={'baseline':baseline['variables'],'moved':moved['variables'],'client_size':[rect.right,rect.bottom],'dpi':window.devicePixelRatioF()}
        check('Physical absolute coordinates match window client coordinates',near(value(moved,'position'),[x+40,y-20,0]))
        check('Motion sums relative displacement and resets at the next frame',near(value(moved,'total_delta'),displacement) and value(moved,'delta')==[0,0,0])
        user32.mouse_event(2,0,0,0,0); QTest.qWait(80); move(x+70,y-10); user32.mouse_event(4,0,0,0,0); QTest.qWait(100); dragged=snapshot()
        check('Physical left drag rotates the robot using relative motion',near(dragged['entities']['player']['rotation'],[5,15,0]))
        user32.mouse_event(0x800,0,0,120,0); QTest.qWait(150); user32.mouse_event(0x1000,0,0,120,0); QTest.qWait(150); wheeled=snapshot()
        check('Physical vertical and horizontal wheel preserve direction',near(value(wheeled,'total_wheel'),[1,1,0]) and value(wheeled,'wheel')==[0,0,0] and abs(wheeled['entities']['player']['position'][2]-.15)<1e-9)
        command('pause'); paused=snapshot(); move(x-20,y-30); user32.mouse_event(0x800,0,0,120,0); QTest.qWait(150)
        check('Paused physical motion and wheel are discarded',snapshot()==paused)
        command('play'); QTest.qWait(150); resumed=snapshot()
        check('Resume resamples position without replaying paused motion/wheel',value(resumed,'total_delta')==value(paused,'total_delta') and value(resumed,'total_wheel')==value(paused,'total_wheel') and near(value(resumed,'position'),[x-20,y-30,0]))
        key('S'); saved=snapshot(); check('Physical Save succeeds',saved['persistence']['success'])
        move(x+15,y-5); user32.mouse_event(0x800,0,0,120,0); QTest.qWait(150); changed=snapshot()
        check('Later input changes saved totals',value(changed,'total_wheel')!=value(saved,'total_wheel'))
        key('L'); loaded=snapshot(); report['load']={'saved':saved['variables'],'loaded':loaded['variables']}
        check('Physical Load restores totals and pose with a neutral cursor impulse',loaded['persistence']['success'] and loaded['entities']==saved['entities'] and
              value(loaded,'total_delta')==value(saved,'total_delta') and value(loaded,'total_wheel')==value(saved,'total_wheel') and value(loaded,'delta')==value(loaded,'wheel')==[0,0,0] and near(value(loaded,'position'),[x+15,y-5,0]))
        move(30,rect.bottom-30); over_ui=snapshot()
        move(70,rect.bottom-30); user32.mouse_event(0x800,0,0,ctypes.c_ulong(-120).value,0); QTest.qWait(150); guarded=snapshot()
        report['ui_guard']={'before':loaded['variables'],'over':over_ui['variables'],'after':guarded['variables']}
        check('Interactive UI consumes motion and wheel but keeps position readable',near(value(guarded,'position'),[70,rect.bottom-30,0]) and
              value(guarded,'total_delta')==value(over_ui,'total_delta')==value(loaded,'total_delta') and
              value(guarded,'total_wheel')==value(loaded,'total_wheel') and guarded['entities']==loaded['entities'])
        # A real Qt panel click exercises the explicit native focus bridge.
        local=window.hierarchy.viewport().mapTo(window,QPoint(30,30)); ratio=window.devicePixelRatioF()
        p=wintypes.POINT(round(local.x()*ratio),round(local.y()*ratio)); user32.ClientToScreen(int(window.winId()),ctypes.byref(p))
        user32.SetCursorPos(p.x,p.y); user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(200)
        before_focus=snapshot(); user32.mouse_event(0x800,0,0,120,0); QTest.qWait(150); after_focus=snapshot()
        check('Wheel over Qt does not reach gameplay',value(after_focus,'total_wheel')==value(before_focus,'total_wheel'))
        command('pause'); window.adapter.clear_selection()
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='delta'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/pointer-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture))); report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); command('play'); QTest.qWait(80); fresh=snapshot()
        check('Stop/fresh Play clears prior totals',value(fresh,'total_delta')==value(fresh,'total_wheel')==[0,0,0])
        command('stop'); check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error)
        window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/pointer-editor-failure.png')); raise
    finally:
        user32.mouse_event(4,0,0,0,0)
        for letter in 'SL': user32.keybd_event(ord(letter),0,2,0)
        user32.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/pointer-editor-checks.json',report)
    return report

if __name__=='__main__': print('Pointer editor:',len(verify()['checks']),'checks passed.')
