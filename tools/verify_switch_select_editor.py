"""Actual Qt latent-node authoring and native pause/save/load behavior."""
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
from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton,QDialogButtonBox
from editor.core.document import load_project,save_json
from editor.core.compiler import compile_graph
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo
from tools.create_switch_select_demo import POSITIONS
from editor.ui.switches import SwitchCasesDialog


def verify():
    directory=ROOT/'.cache'/('switch-select-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/switch_select_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='switch-select-editor-'+uuid.uuid4().hex
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
    def key(letter):
        user32.keybd_event(ord(letter),0,0,0); QTest.qWait(90); user32.keybd_event(ord(letter),0,2,0); QTest.qWait(70)
    def find(nid): return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    def tap(letter):
        user32.keybd_event(ord(letter),0,0,0); QTest.qWait(25); user32.keybd_event(ord(letter),0,2,0); QTest.qWait(25)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for type_id,label in [(2015,'Switch Integer'),(2016,'Switch String'),(2104,'Select Vector3'),(2111,'Select Integer Array'),(2123,'Select String Map')]:
            window.library_search.setText(label); QTest.qWait(80); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                      for j in range(library.topLevelItem(i).childCount())
                      if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(label+' is created from Library',len(window.adapter.graph.all_nodes())==count+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            expected={'Case case_0','Case case_1','Default'} if type_id<2100 else {'Value'}
            check(label+' exposes its declared ports',set(created.outputs())==expected)
            window.actions['Undo'].trigger(); check('Undo removes '+label,len(window.adapter.graph.all_nodes())==count)
            window.actions['Redo'].trigger(); check('Redo restores '+label,len(window.adapter.graph.all_nodes())==count+1)
            window.actions['Undo'].trigger()
        window.library_search.clear(); window.adapter.clear_selection(); node=find('facing'); node.set_selected(True); window.inspect_node(node)
        before=window.adapter.document(); outcomes=[]
        def edit_cases():
            dialog=next(w for w in app.topLevelWidgets() if isinstance(w,SwitchCasesDialog) and w.isVisible())
            try:
                dialog.table.setCurrentCell(0,0); dialog.table.editItem(dialog.table.item(0,0))
                field=dialog.table.findChild(QLineEdit); field.selectAll(); QTest.keyClicks(field,'Left edited'); QTest.keyClick(field,Qt.Key.Key_Return)
                button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Move down'); QTest.mouseClick(button,Qt.MouseButton.LeftButton)
                check('Case dialog edits value and preserves its ID while reordering',dialog.table.item(1,0).text()=='Left edited' and dialog.table.item(1,0).data(Qt.ItemDataRole.UserRole)=='left')
                box=dialog.findChild(QDialogButtonBox); QTest.mouseClick(box.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
                outcomes.append(True)
            except Exception as error:
                outcomes.append(error); dialog.reject()
        QTimer.singleShot(60,edit_cases)
        button=next(b for b in window.inspector.findChildren(QPushButton) if b.accessibleName()=='Edit Switch cases')
        QTest.mouseClick(button,Qt.MouseButton.LeftButton)
        check('Inspector case dialog accepted',outcomes==[True])
        check('Case edit retains every wire',window.adapter.document()['links']==before['links'])
        window.actions['Undo'].trigger(); check('One Undo restores cases and wires',window.adapter.document()==before)
        window.actions['Redo'].trigger(); check('Redo restores changed case value',find('facing').get_property('switch_cases')[1]['value']=='Left edited')
        window.actions['Undo'].trigger()
        check('Dynamic output supports typed connection search',any(s.name=='Delay' and p.name=='In' for s,p in window.adapter.compatible_ports(find('facing').outputs()['Case left'])))
        check('Cases and function save and reopen',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        check('No route before input',first['variables']['visits']['value']==0 and not first['continuations']['tasks'])
        command('play'); key('3'); tap(' '); tap('S'); command('pause'); saved=snapshot()
        check('Physical input saves a suspended Switch branch',saved['persistence']['success'] and len(saved['continuations']['tasks'])==1 and saved['continuations']['tasks'][0]['frames'][1]['stack'][1]['kind']=='switch')
        QTest.qWait(160); check('Pause preserves branch and pending delay',snapshot()==saved)
        command('play'); tap('M'); tap('1'); QTest.qWait(450); command('pause'); reference=snapshot()
        check('Captured Right branch and live mirror Select both execute',reference['variables']['selected']['value']=='Right' and reference['variables']['mode']['value']==0 and reference['variables']['mirror']['value'] and reference['entities']['player']['position']==POSITIONS[0])
        command('play'); tap('L'); command('pause'); loaded=snapshot()
        check('Load restores selected branch and original inputs',loaded['persistence']['success'] and loaded['variables']['mode']['value']==2 and not loaded['variables']['mirror']['value'] and len(loaded['continuations']['tasks'])==1)
        command('play'); tap('M'); tap('1'); QTest.qWait(450); command('pause'); restored=snapshot()
        check('Restored Switch and Select reproduce pose and counters',restored['variables']==reference['variables'] and restored['entities']==reference['entities'] and not restored['continuations']['tasks'])
        command('play'); tap('M'); key('9'); key(' '); QTest.qWait(350); command('pause'); fallback=snapshot()
        check('Unknown integer and string values take Default',fallback['variables']['selected']['value']=='Fallback' and fallback['entities']['player']['position']==POSITIONS[3] and fallback['entities']['player']['rotation']==[0,0,0])
        window.adapter.clear_selection(); node=find('facing'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/switch-select-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop clears captures and route counters',stopped['frame']==0 and not stopped['continuations']['tasks'] and stopped['variables']['visits']['value']==0)
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in ' MSL139': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/switch-select-editor-checks.json',report)
    return report


if __name__=='__main__': print('Switch/Select editor:',len(verify()['checks']),'checks passed.')
