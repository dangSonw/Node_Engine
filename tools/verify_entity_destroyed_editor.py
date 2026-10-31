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
from PySide6.QtCore import QEvent,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('entity-destroyed-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/entity_destroyed_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='entity-destroyed-editor-'+uuid.uuid4().hex
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
    def counts(data): return [data['variables'][k]['value'] for k in ('created','enabled','disabled','owned_disabled','destroyed','loot')]
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
        window.library_search.setText('On Object Destroyed'); QTest.qWait(80); library=window.library_tree
        item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                  for j in range(library.topLevelItem(i).childCount()) if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==1009)
        library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
        QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        check('Destroyed node is created from Library',len(window.adapter.graph.all_nodes())==count+1)
        created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==1009)
        check('Destroyed exposes typed Entity and Active outputs',set(created.outputs())=={'Out','Entity','Active'})
        check('Receiver rejects data-wire suggestions',not window.adapter.compatible_ports(created.inputs()['Receiver']))
        window.actions['Undo'].trigger(); check('Undo removes Destroyed node',len(window.adapter.graph.all_nodes())==count)
        window.actions['Redo'].trigger(); check('Redo restores Destroyed node',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger()
        window.library_search.clear(); window.adapter.clear_selection(); node=find('on_destroyed'); node.set_selected(True); window.inspect_node(node)
        field=next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()=='On Object Destroyed Receiver')
        QTest.qWait(60); QTest.mouseClick(field,Qt.MouseButton.LeftButton)
        field.selectAll(); QTest.keyClicks(field,'player'); QTest.keyClick(field,Qt.Key.Key_Return); QTest.qWait(60)
        check('Inspector changes the pre-destruction receiver',find('on_destroyed').get_property('value_Receiver')=='player')
        ir=compile_graph(window.adapter.document(),window.scene)
        check('Compiler uses edited Destroyed receiver',next(h for h in ir['events']['entity_lifecycle'] if h['node']=='on_destroyed')['owner']=='player')
        window.actions['Undo'].trigger(); check('Undo restores global Destroyed receiver',find('on_destroyed').get_property('value_Receiver')=='')
        window.actions['Redo'].trigger(); check('Redo restores owned Destroyed receiver',find('on_destroyed').get_property('value_Receiver')=='player')
        window.actions['Undo'].trigger()
        check('Destroyed graph and receiver survive save and reopen',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        check('Play emits no destruction',counts(first)==[4,4,0,0,0,0])
        command('play'); key('T'); key('C'); key('X'); command('pause'); inactive=snapshot()
        check('Physical clone removal reads inactive entity and spawns loot',counts(inactive)==[6,5,3,1,1,1] and inactive['variables']['dead_name']['value']=='Clone' and not inactive['variables']['dead_active']['value'])
        command('play'); key('T'); key('N'); key('A'); key('R'); key('S'); command('pause'); saved=snapshot()
        check('Physical prefab Reset notifies once and preserves callback loot',counts(saved)==[10,12,3,1,2,2] and saved['variables']['dead_name']['value']=='Temporary attachment' and saved['persistence']['success'])
        QTest.qWait(160); check('Pause preserves destruction and loot counts',snapshot()==saved)
        command('play'); key('X'); key('N'); key('A'); key('P'); command('pause'); reference=snapshot()
        check('Cascade removal, spawn and Apply preserve expected callbacks',counts(reference)==[14,16,3,1,4,3])
        command('play'); key('L'); command('pause'); restored=snapshot()
        check('Load restores destroyed counters without replaying removals',restored['variables']==saved['variables'] and restored['entities']==saved['entities'])
        command('play'); key('X'); key('N'); key('A'); key('P'); command('pause'); repeated=snapshot()
        check('After Load the same removals reproduce IDs, loot and counters',repeated['variables']==reference['variables'] and repeated['entities']==reference['entities'])
        window.adapter.clear_selection(); node=find('on_destroyed'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/entity-destroyed-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot()
        check('Stop resets state without removal callbacks',counts(stopped)==[0,0,0,0,0,0] and not stopped['events']['lifecycle_started'])
        command('play'); command('pause'); check('Fresh Play has no stale deletion',counts(snapshot())==[4,4,0,0,0,0])
        command('stop'); check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in 'TNCXRSLAP': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/entity-destroyed-editor-checks.json',report)
    return report


if __name__=='__main__': print('Entity Destroyed editor:',len(verify()['checks']),'checks passed.')
