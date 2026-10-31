"""Exercise actual Qt node authoring and an embedded SDL physics preview."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
import argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QPushButton
from editor.ui.physics import RigidBodyDialog
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow


class GuiInfo(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('flags',wintypes.DWORD),
              ('active',wintypes.HWND),('focus',wintypes.HWND),
              ('capture',wintypes.HWND),('menu',wintypes.HWND),
              ('move',wintypes.HWND),('caret',wintypes.HWND),('rect',wintypes.RECT)]


def verify(events=False,authoring=False,queries=False,overlaps=False):
    authoring=authoring or queries or overlaps
    events=events or authoring
    name='physics-queries-editor' if queries else ('physics-authoring-editor' if authoring else ('physics-events-editor' if events else 'physics-editor'))
    project='physics_queries_demo' if queries else ('physics_authoring_demo' if authoring else ('physics_events_demo' if events else 'physics_demo'))
    if overlaps: name='physics-overlaps-editor'; project='physics_overlaps_demo'
    bodies={'floor','player','zone'} if events else {'floor','player'}
    directory=ROOT/'.cache'/('physics-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples'/project,directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='physics-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[])
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    user32=ctypes.windll.user32; user32.GetForegroundWindow.restype=wintypes.HWND
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,timeout=40):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText()+'\n'+window.build_output.toPlainText())
    def command(name,**data):
        begin=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]
        check('Preview command '+name+' succeeds',not any(m.get('event')=='node_error' for m in result))
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    try:
        check('Native runtime is current',current(ROOT/'build/node_view.exe'))
        if authoring:
            errors=[]
            before=json.loads(json.dumps(window.scene))
            def fill_body():
                try:
                    dialog=QApplication.activeModalWidget()
                    check('Inspector opens the rigid-body settings dialog',isinstance(dialog,RigidBodyDialog))
                    check('Collider dialog screenshot is saved',dialog.grab().save(str(ROOT/'artifacts/validation'/(name+'-dialog.png'))))
                    buttons=dialog.findChild(QDialogButtonBox)
                    dialog.fields['mass'].setText('0')
                    QTest.mouseClick(buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
                    check('Invalid collider settings keep the dialog open and scene unchanged',
                          dialog.isVisible() and bool(dialog.error.text()) and window.scene==before)
                    dialog.fields['mass'].setText('2')
                    QTest.mouseClick(buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
                except Exception as error:
                    errors.append(error)
                    if QApplication.activeModalWidget(): QApplication.activeModalWidget().reject()
            QTimer.singleShot(80,fill_body)
            window.refresh_hierarchy('player')
            button=next(w for w in window.findChildren(QPushButton) if w.accessibleName()=='player rigid body settings')
            QTest.mouseClick(button,Qt.LeftButton)
            if errors: raise errors[0]
            edited=json.loads(json.dumps(window.scene))
            check('Inspector stores mass as one prefab collider override',
                  next(e for e in edited['entities'] if e['id']=='player')['rigid_body']['mass']==2 and
                  'rigid_body' in edited['prefab_instances'][0]['owned_components']['root'])
            window.actions['Undo'].trigger(); check('Undo restores the collider and its inherited ownership',window.scene==before)
            window.actions['Redo'].trigger(); check('Redo restores the exact collider edit',window.scene==edited)
            window.actions['Undo'].trigger()
            window.refresh_hierarchy('camera')
            QTimer.singleShot(80,lambda: QApplication.activeModalWidget().accept())
            button=next(w for w in window.findChildren(QPushButton) if w.accessibleName()=='camera rigid body settings')
            QTest.mouseClick(button,Qt.LeftButton)
            check('Add Rigid Body creates valid scene settings',next(e for e in window.scene['entities'] if e['id']=='camera').get('rigid_body') is not None)
            QTest.qWait(30)
            button=next(w for w in window.findChildren(QPushButton) if w.text()=='Remove Rigid Body' and w.isVisible())
            QTest.mouseClick(button,Qt.LeftButton)
            QTest.qWait(30)
            check('Remove Rigid Body clears scene settings',next(e for e in window.scene['entities'] if e['id']=='camera').get('rigid_body') is None)
            window.actions['Undo'].trigger(); window.actions['Undo'].trigger()
            check('Undo removal and addition restores the original scene exactly',window.scene==before)
        handler=window.adapter.add(1014 if events else 1004)
        force=window.adapter.add(window.adapter.registry.by_name('Apply Force').id)
        handler.outputs()['Out'].connect_to(force.inputs()['In'])
        connected=window.adapter.document()
        window.actions['Undo'].trigger(); check('Undo removes the physics handler connection',window.adapter.document()!=connected)
        window.actions['Redo'].trigger(); check('Redo restores the physics handler connection',window.adapter.document()==connected)
        if queries:
            event=window.adapter.add(1002); query=window.adapter.add(11031)
            event.outputs()['Out'].connect_to(query.inputs()['In'])
            check('Query node exposes every typed result port',set(query.outputs())=={'Out','Hit','Entity','Point','Normal','Fraction','Distance'})
            last=query
            for field,label in [('Hit','Boolean'),('Entity','Entity'),('Point','Vector3'),('Normal','Vector3'),('Fraction',''),('Distance','')]:
                setter=window.adapter.add(window.adapter.registry.by_name('Set '+(label+' ' if label else '')+'Variable').id)
                setter.set_property('value_Name','gui_query_'+field.lower())
                last.outputs()['Out'].connect_to(setter.inputs()['In'])
                query.outputs()[field].connect_to(setter.inputs()['Value']); last=setter
            connected=window.adapter.document(); window.actions['Undo'].trigger()
            check('Undo removes a query result connection',window.adapter.document()!=connected)
            window.actions['Redo'].trigger(); check('Redo restores the query result connection',window.adapter.document()==connected)
        if overlaps:
            for node_type in (11035,11036):
                event=window.adapter.add(1002); query=window.adapter.add(node_type)
                setter=window.adapter.add(window.adapter.registry.by_name('Set Entity Array Variable').id)
                setter.set_property('value_Name','gui_overlap_'+str(node_type))
                event.outputs()['Out'].connect_to(setter.inputs()['In'])
                query.outputs()['Value'].connect_to(setter.inputs()['Value'])
                connected=window.adapter.document(); window.actions['Undo'].trigger()
                check(str(node_type)+': Undo removes the overlap array connection',window.adapter.document()!=connected)
                window.actions['Redo'].trigger()
                check(str(node_type)+': Redo restores the overlap array connection',window.adapter.document()==connected)
        check('Physics graph validates and saves through the editor',window.validate_graph() and window.save_project())
        check('Saved physics graph reopens without losing nodes or links',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger()
        wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        QTest.qWait(900 if events else 450); command('pause'); first=snapshot()
        check('Embedded Preview simulates actual graph rigid bodies',first['physics']['ticks']>0 and set(first['physics']['bodies'])==bodies)
        if events:
            check('Embedded Preview delivers collision and trigger handlers',first['variables']['collision_enter']>=1 and first['variables']['trigger_enter']>=1)
        if queries:
            check('Editor-authored query executes all six connected outputs',
                  first['variables']['gui_query_hit']['value'] and
                  all('gui_query_'+field in first['variables'] for field in ('entity','point','normal','fraction','distance')))
            check('Embedded game displays all four live ground probes',
                  all(key.title()+' hit: ' in first['ui']['widgets']['hud']['elements'][key]['text'] for key in ('ray','sphere','box','capsule')))
        if overlaps:
            check('Both editor-authored overlap arrays execute in the embedded game',
                  all(first['variables']['gui_overlap_'+str(node_type)]['type']=='array<entity>' and
                      'floor' in first['variables']['gui_overlap_'+str(node_type)]['value'] for node_type in (11035,11036)))
            check('Live regions detect the robot and distinguish the trigger policy',
                  first['variables']['box_overlaps']['value']==['player','zone'] and
                  first['variables']['capsule_overlaps']['value']==['player'] and
                  first['ui']['widgets']['hud']['elements']['box_overlap']['text']=='Box overlap: 2 bodies' and
                  first['ui']['widgets']['hud']['elements']['capsule_overlap']['text']=='Capsule overlap: 1 bodies')
        QTest.qWait(250); check('Pause freezes physics and its accumulator',snapshot()==first)
        command('play')
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        wait(lambda:user32.GetForegroundWindow()==int(window.winId()))
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert user32.GetWindowRect(hwnd,ctypes.byref(rect))
        user32.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
        user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(100)
        focus=GuiInfo(); focus.cbSize=ctypes.sizeof(focus)
        check('Click focuses the embedded SDL viewport',
              bool(user32.GetGUIThreadInfo(0,ctypes.byref(focus))) and focus.focus==hwnd)
        before=snapshot(); user32.keybd_event(ord('D'),0,0,0); QTest.qWait(350); user32.keybd_event(ord('D'),0,2,0)
        command('pause'); moved=snapshot()
        artifact=ROOT/'artifacts/validation'/(name+'.png')
        check('Desktop screenshot is saved',window.screen().grabWindow(int(window.winId())).save(str(artifact)))
        report['keyboard_motion']={'before':before['entities']['player']['position'],
                                   'after':moved['entities']['player']['position'],
                                   'ticks':moved['physics']['ticks']-before['physics']['ticks']}
        check('Physical D key applies force to the visible robot',moved['entities']['player']['position'][0]>before['entities']['player']['position'][0]+.1)
        command('stop'); stopped=snapshot()
        check('Stop restores authored colliders and transforms' if authoring else 'Stop removes runtime bodies and restores authored transforms',
              set(stopped['physics']['bodies'])==(bodies if authoring else set()) and stopped['physics']['ticks']==0 and stopped['entities']['player']['position']==[0,3,0])
        command('play'); QTest.qWait(80); command('pause')
        check('Restart recreates colliders without duplicate bodies',set(snapshot()['physics']['bodies'])==bodies)
        check('Sources remain unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally:
        user32.keybd_event(ord('D'),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation'/(name+'-checks.json'),report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--events',action='store_true')
    parser.add_argument('--authoring',action='store_true')
    parser.add_argument('--queries',action='store_true')
    parser.add_argument('--overlaps',action='store_true')
    args=parser.parse_args(); print(f"Physics editor: {len(verify(args.events,args.authoring,args.queries,args.overlaps)['checks'])} checks passed.")
