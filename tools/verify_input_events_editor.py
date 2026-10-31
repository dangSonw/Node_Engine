"""Actual Qt authoring, physical viewport input, Pause/Stop and Save/Load."""
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
from PySide6.QtCore import QEvent,QPoint,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('input-events-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/input_events_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='input-events-editor-'+uuid.uuid4().hex
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
    def counts(data): return [data['variables'][k]['value'] for k in ('presses','releases','mouse_edges','turns','action_releases','settled')]
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
        user32.keybd_event(ord(letter),0,0,0); QTest.qWait(90); user32.keybd_event(ord(letter),0,2,0); QTest.qWait(90)
    def find(nid): return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for type_id,name,ports in [(10008,'On Key Pressed',{'Out','Key'}),(10009,'On Key Released',{'Out','Key'}),
                                   (10010,'On Mouse Button',{'Out','Button','Down'}),(10011,'On Action Pressed',{'Out','Action'}),(10012,'On Action Released',{'Out','Action'})]:
            window.library_search.setText(name); QTest.qWait(60); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                      for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); before=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(name+' is created from Library',len(window.adapter.graph.all_nodes())==before+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            check(name+' has typed scoped outputs',set(created.outputs())==ports)
            check(name+' Filter rejects data wires',not window.adapter.compatible_ports(created.inputs()['Filter']))
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1)
            window.actions['Undo'].trigger()
        window.library_search.clear(); window.adapter.clear_selection(); node=find('turn'); node.set_selected(True); window.inspect_node(node)
        field=next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()=='On Action Pressed Filter')
        QTest.mouseClick(field,Qt.MouseButton.LeftButton); field.selectAll(); QTest.keyClick(field,Qt.Key.Key_Backspace); QTest.keyClick(field,Qt.Key.Key_Return); QTest.qWait(60)
        check('Inspector edits input action filter',find('turn').get_property('value_Filter')=='')
        ir=compile_graph(window.adapter.document(),window.scene)
        check('Compiler uses Inspector wildcard filter',next(h for h in ir['events']['input'] if h['node']=='turn')['filter']=='')
        window.actions['Undo'].trigger(); check('Undo restores turn filter',find('turn').get_property('value_Filter')=='turn')
        window.actions['Redo'].trigger(); check('Redo restores wildcard filter',find('turn').get_property('value_Filter')=='')
        window.actions['Undo'].trigger()
        check('Input handlers survive save and reopen',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        check('Startup does not synthesize input',counts(snapshot())==[0]*6)
        focus(); command('stop'); command('play'); QTest.qWait(80)
        check('Focused fresh Play starts with neutral input',counts(snapshot())==[0]*6)
        user32.mouse_event(2,0,0,0,0); QTest.qWait(90); user32.mouse_event(4,0,0,0,0); QTest.qWait(300)
        command('pause'); baseline=snapshot(); report['baseline_counts']=counts(baseline)
        window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/input-events-editor-diagnostic.png'))
        check('Physical focused click is a complete mapped mouse action',counts(baseline)==[0,0,2,1,1,1])
        command('play'); user32.keybd_event(32,0,0,0); QTest.qWait(100); user32.keybd_event(32,0,0,0); QTest.qWait(100)
        user32.mouse_event(2,0,0,0,0); QTest.qWait(80); user32.keybd_event(32,0,2,0); QTest.qWait(80)
        held=snapshot()
        check('Alternative mouse button retains held action without retrigger',counts(held)[:5]==[1,1,3,2,1] and held['variables']['last_down']['value'])
        user32.mouse_event(4,0,0,0,0); QTest.qWait(300); command('pause'); tapped=snapshot()
        check('Physical key repeat and alternative release produce exact events',counts(tapped)==[1,1,4,2,2,2] and not tapped['variables']['last_down']['value'])
        command('play'); user32.keybd_event(32,0,0,0); QTest.qWait(100); command('pause'); paused=snapshot()
        user32.keybd_event(32,0,2,0)
        # A non-text key avoids desktop IME composition rewriting a later S press.
        user32.keybd_event(0x70,0,0,0); QTest.qWait(90); user32.keybd_event(0x70,0,2,0); QTest.qWait(100)
        check('Paused physical input is discarded',snapshot()==paused)
        command('play'); QTest.qWait(300); resumed=snapshot()
        check('Resume does not replay paused input or synthesize release',counts(resumed)[:5]==counts(paused)[:5])
        key('S'); QTest.qWait(120); command('pause'); saved=snapshot()
        check('Physical input callback saves successfully',saved['persistence']['success'] and saved['variables']['last_key']['value']=='S' and saved['variables']['presses']['value']==resumed['variables']['presses']['value']+1)
        command('play'); key(' '); QTest.qWait(300); command('pause'); changed=snapshot()
        check('Physical action changes pose and counters after save',changed['variables']['turns']['value']==saved['variables']['turns']['value']+1)
        command('play'); key('L'); command('pause'); loaded=snapshot()
        expected=dict(saved['variables']); expected['releases']=dict(expected['releases'],value=expected['releases']['value']-1)
        report['load_observation']={'saved':saved['variables'],'loaded':loaded['variables'],'persistence':loaded['persistence'],'saved_entities':saved['entities'],'loaded_entities':loaded['entities']}
        check('Load restores saved counters without replaying input',loaded['variables']==expected and loaded['entities']==saved['entities'] and loaded['persistence']['success'])
        command('play'); key('S'); command('pause'); resaved=snapshot()
        check('Load clears saved held keys so the next Save press is recognized',resaved['variables']['presses']['value']==loaded['variables']['presses']['value']+1 and resaved['persistence']['success'])
        command('play'); user32.keybd_event(32,0,0,0); QTest.qWait(100); before_focus=snapshot()
        local=window.hierarchy.viewport().mapTo(window,QPoint(30,30)); ratio=window.devicePixelRatioF()
        point=wintypes.POINT(round(local.x()*ratio),round(local.y()*ratio))
        user32.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        assert user32.ClientToScreen(int(window.winId()),ctypes.byref(point))
        user32.SetForegroundWindow(int(window.winId())); user32.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        QTest.qWait(80)
        user32.WindowFromPoint.argtypes=[wintypes.POINT]; user32.WindowFromPoint.restype=wintypes.HWND
        report['focus_click']={'point':[point.x,point.y],'ratio':ratio,'hit':int(user32.WindowFromPoint(point) or 0),'qt':int(window.winId()),'enabled':window.hierarchy.isEnabled(),'before_widget':type(app.focusWidget()).__name__}
        user32.SetCursorPos(point.x,point.y); user32.mouse_event(2,0,0,0,0); QTest.qWait(60); user32.mouse_event(4,0,0,0,0)
        user32.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        QTest.qWait(200); after_focus=snapshot()
        report['focus_counts']=[counts(before_focus),counts(after_focus)]
        info=GuiInfo(); info.cbSize=ctypes.sizeof(info); user32.GetGUIThreadInfo(0,ctypes.byref(info))
        report['focus_handles']={'focus':int(info.focus or 0),'native':next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')}
        report['focus_click']['after_widget']=type(app.focusWidget()).__name__
        window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/input-events-focus-diagnostic.png'))
        check('Focus loss emits the held key and action release once',after_focus['variables']['releases']['value']==before_focus['variables']['releases']['value']+1 and after_focus['variables']['action_releases']['value']==before_focus['variables']['action_releases']['value']+1)
        user32.keybd_event(32,0,2,0); command('pause')
        window.adapter.clear_selection(); node=find('turn'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/input-events-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); check('Stop clears input counters',counts(snapshot())==[0]*6)
        command('play'); command('pause'); check('Fresh Play does not replay old input',counts(snapshot())==[0]*6)
        command('stop'); check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in ' ADRSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/input-events-editor-checks.json',report)
    return report


if __name__=='__main__': print('Input events editor:',len(verify()['checks']),'checks passed.')
