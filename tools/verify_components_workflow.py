"""Real Qt authoring, embedded SDL behavior and preview/export GPU parity."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint, QSettings, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox, QLineEdit, QPushButton
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.components import ComponentSignatureDialog
from editor.ui.main_window import MainWindow, SearchDialog

artifact = ROOT/'artifacts/validation'
project = ROOT/'.cache'/('components-'+uuid.uuid4().hex[:8])
shutil.copytree(ROOT/'examples/components_demo', project, ignore=shutil.ignore_patterns('build','generated'))
assert current(ROOT/'build/node_view.exe')
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
window = MainWindow(project/'project.json', QSettings(str(project/'layout.ini'), QSettings.IniFormat))
messages, checks = [], []
window.runtime.message.connect(messages.append)
window.resize(1600, 960); window.show()


def wait(predicate, timeout=20):
    end = time.monotonic()+timeout
    while not predicate() and time.monotonic()<end:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label); print('PASS '+label, flush=True)


def command(name, **data):
    begin = len(messages); serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[begin:]))
    result = messages[begin:]
    assert not any(m.get('event')=='node_error' for m in result), result
    return result


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')


def capture(path):
    begin = len(messages); command('capture', path=str(path))
    wait(lambda: any(m.get('event')=='capture_done' for m in messages[begin:]))
    return QImage(str(path))


def metadata(state):
    return {e['id']: e for e in state['scene']['entities']}


def colored_pixels(image):
    count = 0
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            c = image.pixelColor(x,y)
            count += (c.blue()>c.red()*1.2 and c.red()>c.green()*1.2 and c.red()>40) or (c.green()>70 and c.blue()>70 and c.red()<60)
    return count


try:
    wait(lambda: window.isVisible())
    window.refresh_hierarchy('collector')
    baseline = window.signature(); start = window.adapter.graph.undo_stack().index()
    def define():
        d = app.activeModalWidget(); assert isinstance(d, ComponentSignatureDialog)
        d.name_field.selectAll(); QTest.keyClicks(d.name_field, 'Stats')
        button = next(w for w in d.findChildren(QPushButton) if w.text()=='Add property')
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        table = d.tables['inputs']; table.item(0,0).setText('Lives')
        table.cellWidget(0,1).setCurrentText('int'); table.item(0,2).setText('3')
        QTest.mouseClick(d.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    QTimer.singleShot(50, define); window.actions['Define Component…'].trigger()
    cid = window.scene['component_definitions'][-1]['id']
    check('Definition dialog creates typed Get/Set nodes', window.adapter.registry.by_name('Set Stats Lives').component_id==cid)
    def attach():
        d=app.activeModalWidget(); assert isinstance(d, SearchDialog)
        QTest.keyClicks(d.search, 'Stats'); QTest.keyClick(d.search, Qt.Key.Key_Return)
    QTimer.singleShot(50, attach); window.actions['Add Component…'].trigger()
    def instance():
        return next(e for e in window.scene['entities'] if e['id']=='collector')['components'][str(cid)]
    def widget(cls, suffix):
        return next(w for w in window.inspector.findChildren(cls) if w.accessibleName()==f'collector component {cid} {suffix}')
    check('Attach uses declared defaults', instance()['properties']['1']==3)
    field=widget(QLineEdit,'property 1'); field.setFocus(); field.selectAll()
    QTest.keyClicks(field,'5'); QTest.keyClick(field, Qt.Key.Key_Return)
    check('Inspector keyboard edit changes typed data', instance()['properties']['1']==5)
    enabled=widget(QCheckBox,'enabled')
    QTest.mouseClick(enabled, Qt.MouseButton.LeftButton, pos=QPoint(8,enabled.height()//2))
    check('Checkbox disables component and retains data', instance()=={'enabled':False,'properties':{'1':5}})
    QTest.mouseClick(widget(QPushButton,'remove'), Qt.MouseButton.LeftButton)
    check('Remove detaches the selected component', str(cid) not in next(e for e in window.scene['entities'] if e['id']=='collector')['components'])
    window.actions['Undo'].trigger()
    check('Undo restores component values and enabled state', instance()=={'enabled':False,'properties':{'1':5}})
    window.actions['Redo'].trigger(); window.actions['Undo'].trigger()
    check('Redo and Undo remain stable', instance()['properties']['1']==5)
    check('Authored component saves', window.save_project())
    saved=window.signature(); window.open_project(project/'project.json')
    check('Reopen preserves schemas, values and nodes', window.signature()==saved)
    # Reopening clears history. Restore the original example through scene undo,
    # so the rendered fixture is identical to the independently exported project.
    original=json.loads((ROOT/'examples/components_demo/scenes/main.json').read_text('utf-8'))
    window.push_scene('Restore demo fixture',original,'player'); window.save_project()
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state=='running')
    command('pause'); early=snapshot()
    check('Play loads user components into the native world', metadata(early)['player']['components']['1']['enabled'])
    command('frame_scene'); command('camera',yaw=15,pitch=15)
    early_image=capture(artifact/'components-early.bmp')
    check('Both Blockbench robots render in SDL', colored_pixels(early_image)>100)
    command('play'); QTest.qWait(1200); command('pause'); late=snapshot(); entities=metadata(late)
    check('Timer and action function reduce Health to zero', entities['player']['components']['1']['properties']['1']==0)
    check('Zero Health disables its query participation', entities['player']['components']['1']['enabled'] is False)
    check('Collector receives exactly one token', entities['collector']['components']['2']['properties']['1']==['robot token'])
    check('Gameplay hides the defeated robot', entities['player']['visible'] is False)
    late_image=capture(artifact/'components-later.bmp')
    check('Gameplay changes the GPU image', early_image!=late_image and colored_pixels(late_image)>50)
    command('play'); QTest.qWait(600); command('pause')
    check('Disabled component remains excluded on later queries', metadata(snapshot())['collector']['components']['2']['properties']['1']==['robot token'])
    window.frame_all(); window.library_search.clear(); window.refresh_hierarchy('collector')
    window.raise_(); window.activateWindow(); QTest.qWait(150)
    pos=window.mapToGlobal(QPoint(0,0))
    window.screen().grabWindow(0,pos.x(),pos.y(),window.width(),window.height()).save(str(artifact/'components-desktop.png'))
    pos=window.container.mapToGlobal(QPoint(0,0))
    pixels=colored_pixels(window.screen().grabWindow(0,pos.x(),pos.y(),window.container.width(),window.container.height()).toImage())
    check('Desktop compositor contains the embedded native mesh', pixels>50)
    command('stop'); stopped=metadata(snapshot())
    check('Stop restores authored Health and clears collected inventory', stopped['player']['components']['1']['properties']['1']==100 and stopped['collector']['components']['2']['properties']['1']==[])
    command('play'); command('pause')
    check('Fresh Play resets component state', metadata(snapshot())['player']['components']['1']['enabled'])
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    parity={}
    for frames in (30,120):
        states, images={},{}
        for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
            prefix=artifact/f'components-{mode}-{frames}'
            args=[str(ROOT/'build'/exe),'--project-root',str(ROOT/'examples/components_demo'), '--frames',str(frames),
                  '--capture',str(prefix.with_suffix('.bmp')),'--output',str(prefix.with_suffix('.json'))]
            if mode=='preview': args+=['--ir',str(ROOT/'examples/components_demo/generated/game.ir.json')]
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
            check(f'{mode} executes {frames} native frames',result.returncode==0)
            states[mode]=json.loads(prefix.with_suffix('.json').read_text('utf-8')); images[mode]=prefix.with_suffix('.bmp').read_bytes()
        check(f'{frames}-frame states match exactly',states['preview']==states['compiled'])
        check(f'{frames}-frame GPU bitmaps match exactly',images['preview']==images['compiled'])
        entities=metadata(states['compiled'])
        check(f'{frames}-frame gameplay has expected component values',entities['player']['components']['1']['properties']['1']==(50 if frames==30 else 0) and entities['collector']['components']['2']['properties']['1']==([] if frames==30 else ['robot token']))
        parity[str(frames)]={'state_equal':True,'bitmap_sha256':hashlib.sha256(images['compiled']).hexdigest()}
    check('No runtime node errors occurred',not any(m.get('event')=='node_error' for m in messages))
    save_json(artifact/'components-workflow-checks.json',{'passed':True,'checks':checks,'messages':messages,
        'project':str(project/'project.json'),'compositor_pixels':pixels,'parity':parity})
finally:
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature=window.signature(); window.document_changed()
    window.close(); window.deleteLater()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
