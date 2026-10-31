"""Exercise scene variable dialogs, live reload, typed entity groups and native export."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QComboBox, QLineEdit, QPushButton
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.core.data_types import declaration
from editor.ui.main_window import MainWindow
from editor.ui.variables import VariablesDialog

artifact=ROOT/'artifacts/validation'
source=ROOT/'examples/collections_demo'
project=ROOT/'.cache'/('collections-'+uuid.uuid4().hex[:8])
project.mkdir()
for directory in ('graphs','scenes','assets'):
    shutil.copytree(source/directory,project/directory)
shutil.copy2(source/'project.json',project/'project.json')
app=QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
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


def command(name,**data):
    start=len(events)
    serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event')=='ack' and m.get('id')==serial for m in events[start:]))
    return events[start:]


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')


def edit_variables(name,value,capture=False,extra=False,cancel=False):
    failures=[]
    def fill():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,VariablesDialog)
            row=next(i for i in range(dialog.table.rowCount()) if dialog.table.item(i,0).text()==name)
            dialog.table.setCurrentCell(row,2)
            dialog.table.editItem(dialog.table.item(row,2))
            editor=next(w for w in dialog.table.findChildren(QLineEdit) if w.isVisible())
            assert editor is not None
            editor.setText(json.dumps(value,ensure_ascii=False))
            QTest.keyClick(editor,Qt.Key.Key_Return)
            if extra:
                add=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add Variable')
                QTest.mouseClick(add,Qt.MouseButton.LeftButton)
                editor=next(w for w in dialog.table.findChildren(QLineEdit) if w.isVisible())
                editor.setText('route')
                QTest.keyClick(editor,Qt.Key.Key_Return)
                QTest.qWait(20)
                row=dialog.table.rowCount()-1
                dialog.table.setCurrentCell(row,1)
                dialog.table.editItem(dialog.table.item(row,1))
                QTest.qWait(20)
                combo=next(w for w in dialog.table.findChildren(QComboBox) if w.isVisible())
                combo.setCurrentText('array<int>')
                QTest.keyClick(combo,Qt.Key.Key_Return)
                QTest.qWait(20)
                dialog.table.setCurrentCell(row,2)
                dialog.table.editItem(dialog.table.item(row,2))
                QTest.qWait(20)
                editor=next(w for w in dialog.table.findChildren(QLineEdit) if w.isVisible())
                editor.setText('[1, 2, 3]')
                QTest.keyClick(editor,Qt.Key.Key_Return)
            if capture:
                QTest.qWait(150)
                dialog.screen().grabWindow(dialog.winId()).save(str(artifact/'typed-variables.png'))
            buttons=dialog.findChild(QDialogButtonBox)
            choice=QDialogButtonBox.StandardButton.Cancel if cancel else QDialogButtonBox.StandardButton.Ok
            QTest.mouseClick(buttons.button(choice),Qt.MouseButton.LeftButton)
        except BaseException as error:
            failures.append(error)
            dialog.reject()
    QTimer.singleShot(100,fill)
    window.actions['Scene Variables…'].trigger()
    if failures:
        raise failures[0]
    wait(lambda:window.reload_request is None)


try:
    QTest.qWait(150)
    original=window.signature()
    check('Typed demo validates in editor',window.validate_graph())
    window.play()
    wait(lambda:window.runtime.state=='running' and window.container is not None)
    command('pause')
    initial=snapshot()
    check('Map values and integer For Each compute inventory total',initial['variables']['total']==declaration('int',12))
    check('Unicode string reaches native log',initial['logs']==['Vật phẩm: 12'])
    check('Typed entity array drives both robots',all(e['rotation'][1]>0 for e in initial['entities'].values()))
    edit_variables('inventory',{'coin':20,'potion':2},capture=True,extra=True)
    state=snapshot()
    check('Type dropdown adds array variable',state['variables']['route']==declaration('array<int>',[1,2,3]))
    check('Editing initial values while paused resets without playing',state['frame']==0 and state['variables']['total']==declaration('int',0) and window.runtime.state=='stopped')
    command('play')
    check('Changed map is used by fresh On Start',snapshot()['variables']['total']==declaration('int',22))
    edit_variables('inventory',{'coin':30,'potion':2})
    wait(lambda:window.runtime.state=='running')
    check('Editing while running resumes only after reload',snapshot()['variables']['total']==declaration('int',32))
    window.actions['Undo'].trigger()
    wait(lambda:window.reload_request is None and window.runtime.state=='running')
    check('Undo updates typed runtime state',snapshot()['variables']['total']==declaration('int',22))
    window.actions['Undo'].trigger()
    wait(lambda:window.reload_request is None and window.runtime.state=='running')
    state=snapshot()
    check('Undo restores original variables and clean document',state['variables']['total']==declaration('int',12) and 'route' not in state['variables'] and window.signature()==original and not window.dirty)
    command('pause')
    edit_variables('targets',['player'])
    command('play')
    QTest.qWait(150)
    command('pause')
    state=snapshot()
    check('Entity array membership controls which robot rotates',state['entities']['player']['rotation'][1]>0 and state['entities']['partner']['rotation']==[0,0,0])
    window.actions['Undo'].trigger()
    wait(lambda:window.reload_request is None)
    before=snapshot()
    edit_variables('speed',999,cancel=True)
    check('Cancel leaves initial values and runtime untouched',window.signature()==original and snapshot()==before)
    command('camera',yaw=10,pitch=15)
    command('frame_scene')
    before_events=len(events)
    command('capture',path=str(artifact/'collections-viewport.bmp'))
    wait(lambda:any(m.get('event')=='capture_done' for m in events[before_events:]))
    image=QImage(str(artifact/'collections-viewport.bmp'))
    background=image.pixelColor(0,0)
    colored=sum(image.pixelColor(x,y)!=background for y in range(0,image.height(),4) for x in range(0,image.width(),4))
    check('Typed graph retains real GPU model rendering',colored>100)
    window.library_search.setText('entity each')
    check('Node library matches type and operation in either word order',not window.library_tree.topLevelItem(1).isHidden())
    window.output_tabs.setCurrentWidget(window.console)
    active_nodes={'update','isready','branch','targets','each','axis','speed','dt','angle','degrees','rotate'}
    for node in window.adapter.graph.all_nodes():
        node.set_property('selected',node.get_property('stable_id') in active_nodes,push_undo=False)
    window.adapter.graph.fit_to_selection()
    window.adapter.clear_selection()
    QTest.qWait(200)
    window.screen().grabWindow(window.winId()).save(str(artifact/'collections-editor.png'))
    window.save_project()
    window.build_game()
    wait(lambda:bool(builds),240)
    check('Editor builds typed graph into standalone C++ game',builds[-1])
    (artifact/'collections-build.log').write_text(window.build_output.toPlainText(),'utf-8')
    outputs={}
    for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
        args=[str(project/'build'/exe),'--project-root',str(project/'build'),'--frames','120',
              '--capture',str(artifact/f'collections-{mode}-120.bmp'),
              '--output',str(artifact/f'collections-{mode}-120.json')]
        if mode=='preview':
            args+=['--ir',str(project/'generated/game.ir.json')]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
        check(mode+' executes 120 native frames',result.returncode==0)
        outputs[mode]=json.loads((artifact/f'collections-{mode}-120.json').read_text('utf-8'))
    check('Preview and compiled typed state match',outputs['preview']==outputs['compiled'])
    state=outputs['compiled']
    check('Independent expected result after 120 frames',state['variables']['total']==declaration('int',12)
          and state['logs']==['Vật phẩm: 12'] and all(e['rotation']==[0,90,0] for e in state['entities'].values()))
    images=[(artifact/f'collections-{mode}-120.bmp').read_bytes() for mode in ('preview','compiled')]
    check('Preview and compiled GPU images are byte-identical',images[0]==images[1])
    window.open_project(project/'project.json')
    check('Typed scene and graph reopen without lost data',window.scene['variables']==json.loads((source/'scenes/main.json').read_text('utf-8'))['variables'] and not window.dirty)
    save_json(artifact/'collections-workflow-checks.json',{'passed':True,'checks':checks,'events':events,
        'project':str(project/'project.json'),'bitmap_sha256':hashlib.sha256(images[0]).hexdigest()})
finally:
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
    app.processEvents()
