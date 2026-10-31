"""Real Qt/SDL entity authoring, lifetime reset and exported GPU equivalence."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow

artifact=ROOT/'artifacts/validation'
project=ROOT/'.cache'/('entities-'+uuid.uuid4().hex[:8])
shutil.copytree(ROOT/'examples/entities_demo',project,ignore=shutil.ignore_patterns('build','generated'))
assert current(ROOT/'build/node_view.exe')
app=QApplication([]); app.setQuitOnLastWindowClosed(False)
window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
messages,checks=[],[]
window.runtime.message.connect(messages.append)
window.resize(1600,960); window.show()

def wait(predicate,timeout=20):
    end=time.monotonic()+timeout
    while not predicate() and time.monotonic()<end: QTest.qWait(10)
    assert predicate(),window.console.toPlainText()

def check(label,result):
    assert result,label
    checks.append(label); print('PASS '+label,flush=True)

def command(name,**data):
    begin=len(messages); serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[begin:]))
    result=messages[begin:]
    assert not any(m.get('event')=='node_error' for m in result),result
    return result

def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')

def capture(path):
    begin=len(messages); command('capture',path=str(path))
    wait(lambda:any(m.get('event')=='capture_done' for m in messages[begin:]))
    return QImage(str(path))

def colored_pixels(image):
    count=0
    for y in range(0,image.height(),3):
        for x in range(0,image.width(),3):
            color=image.pixelColor(x,y)
            count += (color.blue()>color.red()*1.2 and color.red()>color.green()*1.2 and color.red()>40) or (color.green()>70 and color.blue()>70 and color.red()<60)
    return count

try:
    start=window.adapter.graph.undo_stack().index()
    window.actions['Create Entity'].trigger(); child=window.selected_entity_id()
    combo=next(w for w in window.findChildren(QComboBox) if w.accessibleName()==f'{child} parent')
    combo.setFocus(); QTest.keyClick(combo,Qt.Key.Key_Down)
    check('Inspector parent selection produces an actual hierarchy edge',next(e for e in window.scene['entities'] if e['id']==child)['parent']=='player')
    check('Hierarchy nests the child under its parent',window.hierarchy.topLevelItem(0).child(0).childCount()==1)
    window.adapter.graph.undo_stack().undo()
    check('Undo detaches the child',not next(e for e in window.scene['entities'] if e['id']==child).get('parent'))
    window.adapter.graph.undo_stack().redo()
    check('Redo restores the parent',next(e for e in window.scene['entities'] if e['id']==child)['parent']=='player')
    while window.adapter.graph.undo_stack().index()>start: window.adapter.graph.undo_stack().undo()
    check('Scene returns to its original template after undo',len(window.scene['entities'])==1)
    check('Project saves',window.save_project())
    window.actions['Play'].trigger()
    wait(lambda:window.runtime.ready and window.runtime.state=='running')
    command('pause'); early=snapshot()
    check('Spawn and Clone create three live entities',set(early['entities'])=={'player','spawned_1','spawned_2','spawned_3'})
    metadata={e['id']:e for e in early['scene']['entities']}
    check('Both robots share the pivot through Flecs ChildOf',metadata['spawned_2']['parent']==metadata['spawned_3']['parent']=='spawned_1')
    command('frame_scene'); command('camera',yaw=15,pitch=15)
    early_image=capture(artifact/'entities-early.bmp')
    check('Runtime-created meshes reach the native GPU viewport',colored_pixels(early_image)>100)
    command('play'); QTest.qWait(1200); command('pause'); later=snapshot()
    check('Timer destroys only the temporary robot',set(later['entities'])=={'player','spawned_1','spawned_2'} and len(later['logs'])==1)
    later_image=capture(artifact/'entities-later.bmp')
    check('Surviving child still renders after deletion',colored_pixels(later_image)>50)
    check('Deleting an instance changes the GPU image',early_image!=later_image)
    command('stop'); stopped=snapshot()
    check('Stop restores the authored scene and clears timers and variables',set(stopped['entities'])=={'player'} and stopped['timers']==[] and stopped['variables']=={})
    command('play'); command('pause'); restarted=snapshot()
    check('Fresh Play resets entity IDs and creates each entity once',set(restarted['entities'])=={'player','spawned_1','spawned_2','spawned_3'})
    command('frame_scene'); window.frame_all(); window.raise_(); window.activateWindow(); QTest.qWait(150)
    pos=window.mapToGlobal(QPoint(0,0))
    window.screen().grabWindow(0,pos.x(),pos.y(),window.width(),window.height()).save(str(artifact/'entities-desktop.png'))
    pos=window.container.mapToGlobal(QPoint(0,0))
    compositor=window.screen().grabWindow(0,pos.x(),pos.y(),window.container.width(),window.container.height()).toImage()
    pixels=colored_pixels(compositor)
    check('Desktop compositor contains the embedded native meshes',pixels>100)
    window.runtime.shutdown(); wait(lambda:not window.runtime.active)
    saved=window.adapter.document(); window.open_project(project/'project.json')
    check('Save and reopen preserve all lifecycle nodes and links',window.adapter.document()==saved)
    parity={}
    for frames in (30,120):
        states,images={},{}
        for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
            prefix=artifact/f'entities-{mode}-{frames}'
            args=[str(ROOT/'build'/exe),'--project-root',str(ROOT/'examples/entities_demo'),
                '--frames',str(frames),'--capture',str(prefix.with_suffix('.bmp')),'--output',str(prefix.with_suffix('.json'))]
            if mode=='preview': args+=['--ir',str(ROOT/'examples/entities_demo/generated/game.ir.json')]
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
            check(f'{mode} executes {frames} native frames',result.returncode==0)
            states[mode]=json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            images[mode]=prefix.with_suffix('.bmp').read_bytes()
        check(f'{frames}-frame preview and compiled state match exactly',states['preview']==states['compiled'])
        check(f'{frames}-frame preview and compiled GPU images match exactly',images['preview']==images['compiled'])
        expected={'player','spawned_1','spawned_2'} | ({'spawned_3'} if frames==30 else set())
        check(f'{frames}-frame lifetime and parent rotation are correct',set(states['compiled']['entities'])==expected and states['compiled']['entities']['spawned_1']['rotation']==[0,frames,0])
        parity[str(frames)]={'state_equal':True,'bitmap_sha256':hashlib.sha256(images['compiled']).hexdigest()}
    check('No runtime node errors occurred',not any(m.get('event')=='node_error' for m in messages))
    save_json(artifact/'entities-workflow-checks.json',{'passed':True,'checks':checks,'messages':messages,
        'project':str(project/'project.json'),'compositor_pixels':pixels,'parity':parity})
finally:
    window.runtime.shutdown(); wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature(); window.document_changed()
    window.close(); window.deleteLater()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
