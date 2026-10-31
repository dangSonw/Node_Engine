"""Exercise real Qt function authoring, live native reload and compiled GPU parity."""
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
from PySide6.QtCore import Qt, QSettings, QTimer, QPointF, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit, QPushButton
from PySide6.QtGui import QImage
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog, FunctionSignatureDialog

artifact=ROOT/'artifacts/validation'
source=ROOT/'examples/functions_demo'
project=ROOT/'.cache'/('functions-'+uuid.uuid4().hex[:8])
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


def find(adapter,nid):
    return next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id')==nid)


def double_click(adapter,node):
    adapter.graph.center_on([node])
    QTest.qWait(40)
    viewer=adapter.graph.viewer()
    point=viewer.mapFromScene(node.view.mapToScene(node.view.boundingRect().center()))
    QTest.mouseClick(viewer.viewport(),Qt.MouseButton.LeftButton,pos=point)
    QTest.mouseDClick(viewer.viewport(),Qt.MouseButton.LeftButton,pos=point)


def field_commit(dialog,adapter,node,port,text):
    adapter.selected.emit(node)
    field=next(f for f in dialog.findChildren(QLineEdit) if f.property('domain_property')=='value_'+port)
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field,text)
    QTest.keyClick(field,Qt.Key.Key_Return)


def edit_delta(cancel=False):
    failures=[]
    opened=[]
    def fill():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,FunctionEditorDialog)
            opened.append(True)
            check('Double-click opens the function graph',dialog.current_id==1000002)
            double_click(dialog.adapter,find(dialog.adapter,'delta'))
            check('Nested function navigation updates breadcrumb',dialog.current_id==1000001 and 'Rotation Delta' in dialog.breadcrumb.text())
            field_commit(dialog,dialog.adapter,find(dialog.adapter,'degrees'),'X','1')
            button=QDialogButtonBox.StandardButton.Cancel if cancel else QDialogButtonBox.StandardButton.Save
            QTest.mouseClick(dialog.buttons.button(button),Qt.MouseButton.LeftButton)
            assert not dialog.isVisible(),dialog.message.text()
        except BaseException as e:
            failures.append(e)
            if dialog:
                dialog.reject()
    QTimer.singleShot(140,fill)
    double_click(window.adapter,find(window.adapter,'left'))
    wait(lambda:bool(opened) or bool(failures),2)
    if failures:
        raise failures[0]
    wait(lambda:window.reload_request is None)


def create_triple():
    failures=[]
    def body():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,FunctionEditorDialog)
            dialog.search.setText('integer multiply')
            item=next(dialog.library.item(i) for i in range(dialog.library.count()) if not dialog.library.item(i).isHidden())
            QTest.mouseClick(dialog.library.viewport(),Qt.MouseButton.LeftButton,pos=dialog.library.visualItemRect(item).center())
            QTest.mouseDClick(dialog.library.viewport(),Qt.MouseButton.LeftButton,pos=dialog.library.visualItemRect(item).center())
            multiply=next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('type_id')==4032)
            multiply.set_pos(240,0)
            entry,output=find(dialog.adapter,'entry'),find(dialog.adapter,'return')
            output.set_pos(520,0)
            # Domain adapter connections exercise the same typed ports as canvas wires.
            entry.outputs()['Number'].connect_to(multiply.inputs()['A'])
            multiply.outputs()['Value'].connect_to(output.inputs()['Result'])
            field_commit(dialog,dialog.adapter,multiply,'B','3')
            assert dialog.isVisible(), 'Enter in an input field must not save/close the function editor'
            dialog.frame_all()
            QTest.qWait(150)
            dialog.grab().save(str(artifact/'function-graph.png'))
            QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Save),Qt.MouseButton.LeftButton)
            assert not dialog.isVisible(),dialog.message.text()
        except BaseException as e:
            failures.append(e)
            if dialog:
                dialog.reject()
    def signature():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,FunctionSignatureDialog)
            dialog.name_field.setText('Triple')
            QTest.mouseClick(dialog.pure,Qt.MouseButton.LeftButton,pos=QPoint(10,dialog.pure.height()//2))
            assert dialog.pure.isChecked()
            for side,name in [('inputs','Number'),('outputs','Result')]:
                button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add '+side[:-1])
                QTest.mouseClick(button,Qt.MouseButton.LeftButton)
                table=dialog.tables[side]
                table.setCurrentCell(0,0)
                table.editItem(table.item(0,0))
                editor=next(f for f in table.findChildren(QLineEdit) if f.isVisible())
                editor.setText(name)
                QTest.keyClick(editor,Qt.Key.Key_Return)
                table.cellWidget(0,1).setCurrentText('int')
            QTest.qWait(100)
            dialog.screen().grabWindow(dialog.winId()).save(str(artifact/'function-signature.png'))
            QTimer.singleShot(200,body)
            QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
        except BaseException as e:
            failures.append(e)
            if dialog:
                dialog.reject()
    QTimer.singleShot(100,signature)
    window.actions['New Function…'].trigger()
    if failures:
        raise failures[0]
    return next(f for f in window.adapter.functions if f['name']=='Triple')


try:
    QTest.qWait(180)
    check('Function demo validates before playing',window.validate_graph())
    (project/'build').mkdir()
    (project/'build/node_view.exe').write_bytes(b'old runtime fixture; never execute')
    check('Old local runtime is rejected in favor of current shared build',window.preview_executable()==ROOT/'build/node_view.exe')
    window.play()
    wait(lambda:window.runtime.state=='running' and window.container is not None)
    QTest.qWait(150)
    command('pause')
    state=snapshot()
    check('Two calls to one function control separate robots',state['entities']['player']['rotation'][1]>0 and state['entities']['partner']['rotation'][1]<0)
    check('Action return survives a later call frame',state['variables']['left_rotation']['value']==state['entities']['player']['rotation'])
    before=window.signature()
    edit_delta()
    check('Saved function edits reset paused preview without playing',window.runtime.state=='stopped' and snapshot()['frame']==0)
    command('play')
    QTest.qWait(100)
    command('pause')
    state=snapshot()
    check('Edited pure function changes both callers',state['entities']['player']['rotation'][0]==state['frame']>0 and state['entities']['partner']['rotation'][0]==state['frame'])
    window.actions['Undo'].trigger()
    wait(lambda:window.reload_request is None)
    check('Whole function edit undoes without losing gameplay nodes',window.signature()==before)
    command('play')
    QTest.qWait(80)
    command('pause')
    check('Undo restores original runtime behavior',all(e['rotation'][0]==0 for e in snapshot()['entities'].values()))
    window.actions['Redo'].trigger()
    wait(lambda:window.reload_request is None)
    command('play')
    QTest.qWait(60)
    command('pause')
    check('Redo restores the function implementation',snapshot()['entities']['player']['rotation'][0]>0)
    window.actions['Undo'].trigger()
    wait(lambda:window.reload_request is None)
    before=window.signature()
    edit_delta(cancel=True)
    check('Cancel discards function edits',window.signature()==before)
    f=create_triple()
    check('Signature dialog and graph editor create a reusable pure function',f['pure'] and f['inputs'][0]['type']=='int')
    call=window.adapter.add(f['id'],[40,430])
    call.set_property('value_Number',7)
    setter=window.adapter.add(3111,[650,-200])
    setter.set_property('value_Name','triple_result')
    find(window.adapter,'log').outputs()['Out'].connect_to(setter.inputs()['In'])
    call.outputs()['Result'].connect_to(setter.inputs()['Value'])
    check('New function can be wired in Gameplay',window.validate_graph())
    window.play()
    wait(lambda:window.runtime.state=='running')
    command('pause')
    check('Function created through dialogs executes in native preview',snapshot()['variables']['triple_result']=={'type':'int','value':21})
    command('camera',yaw=10,pitch=15)
    command('frame_scene')
    previous=len(events)
    command('capture',path=str(artifact/'functions-viewport.bmp'))
    wait(lambda:any(m.get('event')=='capture_done' for m in events[previous:]))
    image=QImage(str(artifact/'functions-viewport.bmp'))
    background=image.pixelColor(0,0)
    check('Functions drive real SDL GPU meshes',sum(image.pixelColor(x,y)!=background for y in range(0,image.height(),4) for x in range(0,image.width(),4))>100)
    window.frame_all()
    window.output_tabs.setCurrentWidget(window.console)
    window.library_search.setText('Spin Robot')
    QTest.qWait(150)
    window.screen().grabWindow(window.winId()).save(str(artifact/'functions-editor.png'))
    check('Project saves with function definitions',window.save_project())
    saved=window.adapter.document()
    window.build_game()
    wait(lambda:bool(builds),240)
    check('GUI build compiles typed functions into standalone C++',builds[-1])
    (artifact/'functions-gui-build.log').write_text(window.build_output.toPlainText(),'utf-8')
    outputs={}
    for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
        args=[str(project/'build'/exe),'--project-root',str(project/'build'),'--frames','120',
              '--capture',str(artifact/f'functions-{mode}-120.bmp'),
              '--output',str(artifact/f'functions-{mode}-120.json')]
        if mode=='preview':
            args+=['--ir',str(project/'generated/game.ir.json')]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
        check(mode+' executes function graph for 120 frames',result.returncode==0)
        outputs[mode]=json.loads((artifact/f'functions-{mode}-120.json').read_text('utf-8'))
    check('Preview and compiled state match exactly',outputs['preview']==outputs['compiled'])
    state=outputs['compiled']
    check('Independent expected rotation and typed return values',state['entities']['player']['rotation']==[0,90,0]
          and state['entities']['partner']['rotation']==[0,-180,0]
          and state['variables']['left_rotation']['value']==[0,90,0]
          and state['variables']['triple_result']=={'type':'int','value':21})
    images=[(artifact/f'functions-{mode}-120.bmp').read_bytes() for mode in ('preview','compiled')]
    check('Function preview and compiled GPU images are byte-identical',images[0]==images[1])
    window.open_project(project/'project.json')
    check('Function graphs, call IDs and typed ports survive reopen',window.adapter.document()==saved and not window.dirty)
    save_json(artifact/'functions-workflow-checks.json',{'passed':True,'checks':checks,'events':events,
        'project':str(project/'project.json'),'bitmap_sha256':hashlib.sha256(images[0]).hexdigest()})
finally:
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
    app.processEvents()
