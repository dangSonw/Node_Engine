"""Actual Qt Multi Gate authoring and native route/save/load behavior."""
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
from tools.create_multi_gate_demo import POSITIONS


def verify():
    directory=ROOT/'.cache'/('multi-gate-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/multi_gate_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='multi-gate-editor-'+uuid.uuid4().hex
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
    def history(data): return list(map(int,data['variables']['history']['value'].split()))
    def pose(data):
        selected=data['variables']['selected']['value']; entity=data['entities']['player']
        return entity['position']==POSITIONS[selected] and entity['rotation']==[0,selected*90,0]
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        window.library_search.setText('Multi Gate'); QTest.qWait(80); library=window.library_tree
        item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                  for j in range(library.topLevelItem(i).childCount())
                  if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==2011)
        library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
        QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
        check('Multi Gate is created from Library',len(window.adapter.graph.all_nodes())==count+1)
        created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==2011)
        check('All eight exec routes and typed Index are available',set(created.outputs())=={'Index',*('Out '+str(i) for i in range(8))})
        window.actions['Undo'].trigger(); check('Undo removes created gate',len(window.adapter.graph.all_nodes())==count)
        window.actions['Redo'].trigger(); check('Redo restores created gate',len(window.adapter.graph.all_nodes())==count+1)
        window.actions['Undo'].trigger()
        node=find('route'); node.set_selected(True); window.inspect_node(node)
        for name,value in [('Branches',8),('Start Index',7)]:
            field=next(w for w in window.inspector.findChildren(QLineEdit) if w.property('domain_property')=='value_'+name)
            field.setFocus(); field.selectAll(); QTest.keyClicks(field,str(value)); QTest.keyClick(field,Qt.Key.Key_Return)
            check('Inspector sets '+name,node.get_property('value_'+name)==value)
        window.actions['Undo'].trigger(); window.actions['Undo'].trigger()
        check('Undo restores authored branch configuration',node.get_property('value_Branches')==4 and node.get_property('value_Start Index')==-1)
        node.outputs()['Out 7'].connect_to(node.inputs()['Reset'])
        check('Last output can connect to Reset',node.inputs()['Reset'] in node.outputs()['Out 7'].connected_ports() and window.validate_graph())
        check('Eight-output gate saves and reopens with all wires',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Undo'].trigger()
        check('Undo removes unused-route feedback',not node.outputs()['Out 7'].connected_ports() and window.save_project())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        check('No route is consumed before input',not first['flow']['states'] and not history(first))
        QTest.qWait(150); check('Pause preserves all state',snapshot()==first)
        command('play')
        for _ in range(5): key(' ')
        command('pause'); sequential=snapshot()
        check('Physical Space traverses four routes then stops',history(sequential)==[0,1,2,3] and pose(sequential))
        command('play'); key('T'); key(' '); command('pause'); looped=snapshot()
        check('Loop resumes an exhausted cycle',history(looped)==[0,1,2,3,0] and pose(looped))
        command('play'); key('M'); key('R'); key(' '); key(' '); command('pause'); partial=snapshot()
        check('Random mode has two distinct visited routes',len(history(partial))==len(set(history(partial)))==2 and partial['variables']['random']['value'])
        command('play'); key('S'); command('pause'); saved=snapshot()
        check('Save preserves a partial random cycle',saved['persistence']['success'] and saved['flow']==partial['flow'] and saved['random']==partial['random'])
        command('play')
        for _ in range(6): key(' ')
        command('pause'); reference=snapshot()
        check('Two complete random cycles contain every route',len(history(reference))==8 and sorted(history(reference)[:4])==sorted(history(reference)[4:])==[0,1,2,3])
        command('play'); key('L'); command('pause'); loaded=snapshot()
        check('Load restores visited routes and RNG together',loaded['persistence']['success'] and loaded['flow']==saved['flow'] and loaded['random']==saved['random'] and history(loaded)==history(saved) and loaded['entities']==saved['entities'])
        command('play')
        for _ in range(6): key(' ')
        command('pause'); restored=snapshot()
        check('Physical input after Load reproduces future choices and pose',history(restored)==history(reference) and restored['flow']==reference['flow'] and restored['random']==reference['random'] and restored['entities']==reference['entities'])
        window.library_search.clear(); window.adapter.clear_selection(); node=find('route'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/multi-gate-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop clears gate state and tour history',stopped['frame']==0 and not stopped['flow']['states'] and not history(stopped))
        command('play'); key(' '); command('pause'); restarted=snapshot()
        check('Restart begins sequentially at route zero',history(restarted)==[0] and pose(restarted) and not restarted['variables']['random']['value'])
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in ' MTRSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/multi-gate-editor-checks.json',report)
    return report


if __name__=='__main__': print('Multi Gate editor:',len(verify()['checks']),'checks passed.')
