"""Author a new multi-entity game through the real editor and verify its export."""
from pathlib import Path
import json
import subprocess
import sys
import time
import uuid
import base64
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit, QFileDialog
from editor.core.registry import ROOT
from editor.core.document import save_json, create_project
from editor.ui.main_window import MainWindow

artifact=ROOT/'artifacts/validation'
directory=ROOT/'examples/scene_demo'
if directory.exists():
    directory=ROOT/'.cache'/('scene-demo-'+uuid.uuid4().hex[:8])
app=QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
window=MainWindow(settings=QSettings(str(ROOT/'.cache/scene-workflow.ini'),QSettings.IniFormat))
events,checks,builds=[],[],[]
window.runtime.message.connect(events.append)
window.builder.finished.connect(builds.append)
window.show()

def wait(predicate,timeout=15):
    end=time.monotonic()+timeout
    while not predicate() and time.monotonic()<end:
        QTest.qWait(10)
    assert predicate(),window.console.toPlainText()+'\n'+window.build_output.toPlainText()

def check(name,result):
    assert result,name
    checks.append(name)
    print('PASS '+name,flush=True)

def field(eid,key):
    return next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()==f'{eid} {key}')

def edit(eid,key,value):
    window.refresh_hierarchy(eid)
    widget=field(eid,key)
    widget.setText(value if key=='name' else json.dumps(value))
    widget.editingFinished.emit()

def command(name,**data):
    start=len(events)
    serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event')=='ack' and m.get('id')==serial for m in events[start:]))
    return events[start:]

def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')

def capture(path):
    before=len(events)
    command('capture',path=str(path))
    wait(lambda:any(m.get('event')=='capture_done' and Path(m['path'])==path for m in events[before:]))
    return QImage(str(path))

try:
    def fill_project():
        dialog=app.activeModalWidget()
        fields={w.accessibleName():w for w in dialog.findChildren(QLineEdit)}
        fields['Project name'].setText('Scene Authoring Demo')
        fields['New project folder'].setText(str(directory))
        box=dialog.findChild(QDialogButtonBox)
        QTest.mouseClick(box.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    QTimer.singleShot(100,fill_project)
    window.actions['New Project…'].trigger()
    check('New Project dialog creates and opens valid files',window.project_path==directory/'project.json')
    window.actions['Create Entity'].trigger()
    left=window.selected_entity_id()
    original_picker=QFileDialog.getOpenFileName
    external=ROOT/'.cache'/('external-model-'+uuid.uuid4().hex[:8])
    (external/'data').mkdir(parents=True)
    model=json.loads((ROOT/'examples/blockbench_demo/assets/robot.gltf').read_text())
    (external/'data/robot mesh.bin').write_bytes(base64.b64decode(model['buffers'][0]['uri'].split(',',1)[1]))
    model['buffers'][0]['uri']='data/robot%20mesh.bin'
    save_json(external/'robot.gltf',model)
    QFileDialog.getOpenFileName=lambda *a,**kw:(str(external/'robot.gltf'),'')
    try:
        window.actions['Import Model…'].trigger()
    finally:
        QFileDialog.getOpenFileName=original_picker
    edit(left,'name','Robot trái')
    edit(left,'position',[-1,0,0])
    window.actions['Duplicate Entity'].trigger()
    right=window.selected_entity_id()
    edit(right,'name','Robot phải')
    edit(right,'position',[1,0,0])
    check('Create/import/duplicate retain distinct stable entity IDs',left!=right and len(window.scene['entities'])==3)
    check('Real glTF external buffer copied with model',(directory/'assets/robot/data/robot mesh.bin').is_file())
    window.activateWindow()
    wait(window.isActiveWindow)
    window.hierarchy.setFocus()
    QTest.qWait(50)
    QTest.keyClick(window.hierarchy,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier)
    check('Ctrl+Z from hierarchy undoes scene transform',json.loads(field(right,'position').text())==[-1,0,0])
    QTest.keyClick(window.hierarchy,Qt.Key.Key_Z,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.ShiftModifier)
    check('Ctrl+Shift+Z restores scene transform',json.loads(field(right,'position').text())==[1,0,0])
    # Author actual typed graph nodes using the same editor adapter as the library.
    nodes={n.get_property('stable_id'):n for n in window.adapter.graph.all_nodes()}
    delta=window.adapter.add(5001,[0,350])
    spin=window.adapter.add(4022,[220,350])
    spin.set_property('value_Vector',[0,45,0])
    rotate=window.adapter.add(9004,[440,180])
    rotate.set_property('value_Entity',left)
    delta.outputs()['Value'].connect_to(spin.inputs()['Scale'])
    spin.outputs()['Value'].connect_to(rotate.inputs()['Degrees'])
    nodes['update'].outputs()['Out'].connect_to(rotate.inputs()['In'])
    check('New project graph validates and saves',window.validate_graph() and window.save_project())
    window.frame_all()
    window.actions['Play'].trigger()
    wait(lambda:window.runtime.state=='running' and any(e.get('event')=='scene_loaded' for e in events))
    check('Two mesh entities share one uploaded mesh',any(e.get('mesh_instances')==2 and e.get('unique_meshes')==1 for e in events))
    window.actions['Pause'].trigger()
    wait(lambda:window.runtime.state=='paused')
    command('set_property',entity=left,property='rotation',value=[0,0,0])
    command('camera',yaw=10,pitch=15)
    command('frame_scene')
    image=capture(artifact/'scene-two-robots.bmp')
    background=image.pixelColor(0,0)
    columns=[any(image.pixelColor(x,y)!=background for y in range(0,image.height(),3)) for x in range(image.width())]
    runs=sum(v and (i==0 or not columns[i-1]) for i,v in enumerate(columns))
    check('GPU image contains two separated models',runs==2)
    check('Camera frames all models in narrow viewport',not columns[0] and not columns[-1])
    edit(right,'position',[1.5,0,0])
    command('snapshot')  # Serial barrier after the inspector's property command.
    check('Inspector transform reaches native entity',snapshot()['entities'][right]['position']==[1.5,0,0])
    window.actions['Undo'].trigger()
    check('Scene undo updates native entity',snapshot()['entities'][right]['position']==[1,0,0])
    start=len(events)
    window.actions['Delete Entity'].trigger()
    wait(lambda:any(e.get('event')=='scene_loaded' and e['mesh_instances']==1 for e in events[start:]))
    check('Delete entity removes its runtime instance',right not in snapshot()['entities'])
    start=len(events)
    window.actions['Undo'].trigger()
    wait(lambda:any(e.get('event')=='scene_loaded' and e['mesh_instances']==2 for e in events[start:]))
    check('Undo restores deleted runtime instance',right in snapshot()['entities'])
    command('camera',yaw=10,pitch=15)
    window.splitter.setSizes([600,600])
    window.output_tabs.setCurrentWidget(window.console)
    QTest.qWait(150)
    window.screen().grabWindow(window.winId()).save(str(artifact/'scene-authoring.png'))
    window.save_project()
    window.actions['Build Game'].trigger()
    wait(lambda:bool(builds),timeout=240)
    check('Build safely closes preview and succeeds',builds[-1] and not window.runtime.active)
    destination=directory/'build'
    result=subprocess.run([str(destination/'node_game_view.exe'),'--project-root',str(destination),
        '--frames','120','--output',str(artifact/'scene-export-state.json'),
        '--capture',str(artifact/'scene-export.bmp')],capture_output=True,text=True,timeout=30)
    check('Standalone multi-entity game runs',result.returncode==0)
    state=json.loads((artifact/'scene-export-state.json').read_text())
    check('Export executes graph on selected entity only',state['entities'][left]['rotation']==[0,90,0]
          and state['entities'][right]['rotation']==[0,0,0] and state['entities'][right]['position']==[1,0,0])
    window.actions['Play'].trigger()
    wait(lambda:window.runtime.state=='running')
    second=create_project(ROOT/'.cache'/('switch-'+uuid.uuid4().hex[:8]),'Switch Test')
    window.switch_project(second)
    wait(lambda:window.project_path==second and not window.runtime.active)
    check('Opening another project shuts down active preview',window.project['name']=='Switch Test')
    window.open_project(directory/'project.json')
    check('Saved scene and graph reopen without lost entities',len(window.scene['entities'])==3 and not window.dirty)
    save_json(artifact/'scene-workflow-checks.json',{'passed':True,'project':str(directory/'project.json'),
              'checks':checks,'events':events,'left':left,'right':right})
finally:
    if window.runtime.active:
        window.runtime.process.kill()
        wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
