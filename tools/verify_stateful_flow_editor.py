"""Actual Qt authoring, reset feedback and embedded SDL stateful gameplay."""
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
    directory=ROOT/'.cache'/('stateful-flow-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/stateful_flow_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='stateful-flow-editor-'+uuid.uuid4().hex
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
    def flow(data): return {s['node']:s for s in data['flow']['states']}
    def pose(data,position,scale=1):
        entity=data['entities']['player']; return entity['position']==position and entity['scale']==[scale]*3
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for type_id,label in [(2007,'Do Once'),(2008,'Do N'),(2009,'Gate'),(2010,'Flip Flop')]:
            window.library_search.setText(label); QTest.qWait(80)
            library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
                      for j in range(library.topLevelItem(i).childCount())
                      if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); count=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(label+' created from Library',len(window.adapter.graph.all_nodes())==count+1)
            window.actions['Undo'].trigger(); check(label+' Undo removes node',len(window.adapter.graph.all_nodes())==count)
            window.actions['Redo'].trigger(); check(label+' Redo restores node',len(window.adapter.graph.all_nodes())==count+1)
            window.actions['Undo'].trigger()
        node=find('quota'); node.set_selected(True); window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.property('domain_property')=='value_N')
        field.setFocus(); field.selectAll(); QTest.keyClicks(field,'5'); QTest.keyClick(field,Qt.Key.Key_Return)
        check('Inspector changes the quota',node.get_property('value_N')==5)
        window.actions['Undo'].trigger(); check('Quota Undo restores 3',node.get_property('value_N')==3)
        scratch=window.adapter.add(2007); scratch_id=scratch.get_property('stable_id')
        scratch.outputs()['Out'].connect_to(scratch.inputs()['Reset'])
        check('Reset feedback is connectable and valid',scratch.inputs()['Reset'] in scratch.outputs()['Out'].connected_ports() and window.validate_graph())
        window.actions['Undo'].trigger(); check('Connection Undo removes Reset feedback',not scratch.outputs()['Out'].connected_ports())
        window.actions['Redo'].trigger(); check('Connection Redo restores Reset feedback',scratch.inputs()['Reset'] in scratch.outputs()['Out'].connected_ports())
        check('Feedback graph saves',window.save_project())
        reopened=load_project(directory/'project.json')[1]; window.adapter.load(reopened)
        check('All multi-input links including feedback reopen exactly',window.adapter.document()==reopened)
        scratch=find(scratch_id); scratch.outputs()['Out'].connect_to(scratch.inputs()['In'])
        check('Execution feedback is reported before running',not window.validate_graph() and any('Execution cycle' in window.problems.item(i).text() for i in range(window.problems.count())))
        window.actions['Undo'].trigger(); check('Undo repairs execution feedback',window.validate_graph())
        check('Repaired graph saves and reopens exactly',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); command('pause'); first=snapshot()
        check('Gate initially blocks rotation',pose(first,[0,0,0]) and not flow(first)['gate']['flag'])
        QTest.qWait(150); check('Pause preserves all gate state',snapshot()==first)
        command('play')
        for letter in 'OONNNNFFF': key(letter)
        command('pause'); limited=snapshot()
        check('Physical input exercises Once, quota and alternating scale',pose(limited,[1.5,.5,0],1.25) and limited['variables']['used']['value']==3 and limited['variables']['is_a']['value'])
        command('play'); key('G'); QTest.qWait(150); key('G'); command('pause'); turned=snapshot()
        check('Physical Gate toggle admits rotation and closes again',turned['entities']['player']['rotation'][1]>0 and not flow(turned)['gate']['flag'])
        command('play'); key('S'); command('pause'); saved=snapshot()
        check('Save preserves all gate states',saved['persistence']['success'] and len(flow(saved))==4)
        command('play'); key('R'); command('pause'); reset=snapshot()
        check('Reset clears counters, pose and next flip branch',pose(reset,[0,0,0]) and reset['entities']['player']['rotation']==[0,0,0] and flow(reset)['once']['count']==flow(reset)['quota']['count']==0 and flow(reset)['flip']['flag'])
        command('play'); key('L'); command('pause'); loaded=snapshot()
        check('Load restores all gates and visual state',loaded['persistence']['success'] and loaded['flow']==saved['flow'] and loaded['entities']==saved['entities'])
        command('play'); key('O'); key('N'); key('F'); command('pause'); later=snapshot()
        check('Loaded quota stays blocked and Flip continues with B',pose(later,[1.5,.5,0],.75) and not later['variables']['is_a']['value'] and flow(later)['quota']['count']==3)
        bad=compile_graph(window.adapter.document(),window.scene)
        def damage(value):
            if isinstance(value,dict):
                if value.get('op')=='flow': value['type']=2099; return True
                return any(damage(child) for child in value.values())
            if isinstance(value,list): return any(damage(child) for child in value)
            return False
        assert damage(bad)
        before=snapshot(); begin=len(messages); serial=window.runtime.send('load_ir',ir=bad)
        wait(lambda:any(m.get('id')==serial and m.get('event')=='node_error' for m in messages[begin:]))
        check('Invalid flow binding leaves the live world unchanged',snapshot()==before)
        assert window.validate_graph()
        window.library_search.clear(); window.adapter.clear_selection(); node=find('quota'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/stateful-flow-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot(); check('Stop clears all allocated gate state',stopped['frame']==0 and not stopped['flow']['states'])
        command('play'); QTest.qWait(120); command('pause'); restarted=snapshot()
        check('Restart restores initial closed Gate and empty counters',pose(restarted,[0,0,0]) and len(flow(restarted))==1 and not flow(restarted)['gate']['flag'])
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in 'ONGFRSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/stateful-flow-editor-checks.json',report)
    return report


if __name__=='__main__': print('Stateful flow editor:',len(verify()['checks']),'checks passed.')
