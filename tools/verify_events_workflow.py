"""Exercise typed event authoring, native subscriptions and exported GPU parity."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QSettings, QPoint, QEvent, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLineEdit, QPushButton
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.core.events import node_id
from editor.ui.main_window import MainWindow
from editor.ui.events import EventSignatureDialog

artifact=ROOT/'artifacts/validation'
project=ROOT/'.cache'/('events-'+uuid.uuid4().hex[:8])
shutil.copytree(ROOT/'examples/events_demo',project,ignore=shutil.ignore_patterns('build','generated'))
app=QApplication([])
app.setQuitOnLastWindowClosed(False)
window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
messages, checks, builds = [], [], []
window.runtime.message.connect(messages.append)
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
    index=len(messages)
    serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event')=='ack' and m.get('id')==serial for m in messages[index:]))
    return messages[index:]


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')


def find(nid):
    return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)


def define_notice(cancel=False):
    failures=[]
    def fill():
        dialog=app.activeModalWidget()
        try:
            assert isinstance(dialog,EventSignatureDialog)
            dialog.name_field.selectAll()
            QTest.keyClicks(dialog.name_field,'Notice')
            add=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add parameter')
            QTest.mouseClick(add,Qt.MouseButton.LeftButton)
            table=dialog.tables['inputs']
            table.setCurrentCell(0,0)
            table.editItem(table.item(0,0))
            editor=next(f for f in table.findChildren(QLineEdit) if f.isVisible())
            editor.selectAll(); QTest.keyClicks(editor,'Count'); QTest.keyClick(editor,Qt.Key.Key_Return)
            table.cellWidget(0,1).setCurrentText('int')
            table.setCurrentCell(0,2)
            table.editItem(table.item(0,2))
            editor=next(f for f in table.findChildren(QLineEdit) if f.isVisible())
            editor.selectAll(); QTest.keyClicks(editor,'7'); QTest.keyClick(editor,Qt.Key.Key_Return)
            dialog.name_field.setFocus()
            QTest.qWait(80)
            if not cancel:
                dialog.grab().save(str(artifact/'event-signature.png'))
            button=QDialogButtonBox.StandardButton.Cancel if cancel else QDialogButtonBox.StandardButton.Ok
            QTest.mouseClick(dialog.buttons.button(button),Qt.MouseButton.LeftButton)
            assert not dialog.isVisible(),dialog.error.text()
        except BaseException as error:
            failures.append(error)
            if dialog:
                dialog.reject()
    QTimer.singleShot(100,fill)
    window.actions['Define Event…'].trigger()
    if failures:
        raise failures[0]


def add_from_library(type_id,label):
    window.library_search.setText(label)
    QTest.qWait(60)
    library=window.library_tree
    item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
              for j in range(library.topLevelItem(i).childCount())
              if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
    library.scrollToItem(item)
    before=set(window.adapter.graph.all_nodes())
    QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
    QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
    added=set(window.adapter.graph.all_nodes())-before
    assert len(added)==1
    return added.pop()


try:
    definitions=list(window.adapter.event_definitions)
    define_notice(cancel=True)
    check('Cancel leaves event definitions unchanged',window.adapter.event_definitions==definitions)
    define_notice()
    notice=window.adapter.event_definitions[-1]
    check('Define Event creates a typed payload with a default',notice['name']=='Notice'
          and notice['parameters']==[{'name':'Count','type':'int','default':7}])
    window.actions['Undo'].trigger()
    check('Undo removes the event and its five library nodes',window.adapter.event_definitions==definitions
          and node_id(notice['id'],'on') not in window.adapter.registry.nodes)
    window.actions['Redo'].trigger()
    check('Redo restores the same event identity',window.adapter.event_definitions[-1]==notice)
    send=add_from_library(node_id(notice['id'],'send'),'Send Notice'); send.set_pos(1150,0)
    handler=add_from_library(node_id(notice['id'],'on'),'On Notice'); handler.set_pos(0,1050)
    setter_type=next(s.id for s in window.adapter.registry.nodes.values()
                     if s.variable_type=='int' and s.variable_access=='write')
    setter=window.adapter.add(setter_type,[340,1050])
    setter.set_property('value_Name','notice_result')
    # Domain connections use the exact typed ports exposed on the visible canvas.
    find('subscribe').outputs()['Out'].connect_to(send.inputs()['In'])
    handler.outputs()['Out'].connect_to(setter.inputs()['In'])
    handler.outputs()['Count'].connect_to(setter.inputs()['Value'])
    check('Library event nodes connect with their typed payload',window.validate_graph())
    window.inspect_node(find('broadcast'))
    field=next(f for f in window.inspector.findChildren(QLineEdit) if f.property('domain_property')=='value_Angle')
    field.setFocus(); field.selectAll(); QTest.keyClicks(field,'30'); QTest.keyClick(field,Qt.Key.Key_Return)
    check('Inspector edits a custom event payload',find('broadcast').get_property('value_Angle')==30)
    window.actions['Undo'].trigger()
    check('Undo restores the custom event payload',find('broadcast').get_property('value_Angle')==15)
    window.actions['Redo'].trigger()
    check('Redo restores the custom event payload',find('broadcast').get_property('value_Angle')==30)
    window.actions['Undo'].trigger()
    window.play()
    wait(lambda:window.runtime.state=='running' and window.container is not None,240)
    wait(lambda:snapshot()['entities']['player']['rotation'][1]>=120)
    command('pause')
    frozen=snapshot()
    check('Native handlers receive the authored integer payload',frozen['variables']['notice_result']=={'type':'int','value':7})
    check('Unsubscribe disables only the partner receiver',frozen['entities']['partner']['rotation']==[0,-45,0]
          and {'event':100001,'receiver':'partner','enabled':False} in frozen['events']['subscriptions'])
    QTest.qWait(350)
    check('Pause freezes event and timer simulation',snapshot()==frozen)
    command('play'); QTest.qWait(320); command('pause')
    resumed=snapshot()
    check('Resumed broadcasts reach only the subscribed robot',resumed['entities']['player']['rotation'][1]>frozen['entities']['player']['rotation'][1]
          and resumed['entities']['partner']['rotation']==[0,-45,0])
    command('stop')
    stopped=snapshot()
    check('Stop clears queued events and restores initial subscriptions',stopped['events']['pending']==0 and stopped['timers']==[]
          and stopped['frame']==0 and stopped['variables']=={}
          and {'event':100001,'receiver':'partner','enabled':False} in stopped['events']['subscriptions'])
    command('play'); QTest.qWait(300); command('pause')
    restarted=snapshot()
    check('Play after Stop rebinds handlers once',len(restarted['events']['subscriptions'])==3
          and restarted['variables']['notice_result']['value']==7
          and restarted['entities']['player']['rotation'][1]==15
          and restarted['entities']['partner']['rotation'][1]==-15)
    window.inspect_node(find('player_event'))
    command('camera',yaw=10,pitch=15); command('frame_scene')
    window.library_search.clear(); window.frame_all()
    window.raise_(); window.activateWindow(); QTest.qWait(180)
    position=window.mapToGlobal(QPoint(0,0))
    window.screen().grabWindow(0,position.x(),position.y(),window.width(),window.height()).save(str(artifact/'events-desktop.png'))
    position=window.container.mapToGlobal(QPoint(0,0))
    image=window.screen().grabWindow(0,position.x(),position.y(),window.container.width(),window.container.height()).toImage()
    pixels=0
    for y in range(0,image.height(),3):
        for x in range(0,image.width(),3):
            color=image.pixelColor(x,y)
            pixels += (color.blue()>color.red()*1.2 and color.red()>color.green()*1.2 and color.red()>40) or (color.green()>70 and color.blue()>70 and color.red()<60)
    check('Desktop compositor shows both native robot meshes',pixels>100)
    check('Event definitions and graph save',window.save_project())
    saved=window.adapter.document()
    heartbeat=[]
    ticker=QTimer(); ticker.setInterval(40); ticker.timeout.connect(lambda:heartbeat.append(1)); ticker.start()
    window.build_game()
    wait(lambda:bool(builds),240)
    ticker.stop()
    check('Editor stays responsive during native build',len(heartbeat)>5)
    check('GUI build exports typed custom events to standalone C++',builds[-1])
    (artifact/'events-gui-build.log').write_text(window.build_output.toPlainText(),'utf-8')
    outputs={}
    for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
        args=[str(project/'build'/exe),'--project-root',str(project/'build'),'--frames','120',
              '--capture',str(artifact/f'events-{mode}-120.bmp'),'--output',str(artifact/f'events-{mode}-120.json')]
        if mode=='preview': args+=['--ir',str(project/'generated/game.ir.json')]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
        check(mode+' executes 120 native custom event frames',result.returncode==0)
        outputs[mode]=json.loads((artifact/f'events-{mode}-120.json').read_text('utf-8'))
    check('Preview and exported event state match exactly',outputs['preview']==outputs['compiled'])
    state=outputs['compiled']
    check('Broadcasts, cancellation and direct send produce the expected rotations',state['entities']['player']['rotation']==[0,180,0]
          and state['entities']['partner']['rotation']==[0,-45,0]
          and state['variables']['notice_result']['value']==7 and state['events']['pending']==0)
    images=[(artifact/f'events-{mode}-120.bmp').read_bytes() for mode in ('preview','compiled')]
    check('Preview and exported GPU frames are byte-identical',images[0]==images[1])
    window.open_project(project/'project.json')
    check('Typed events, functions and connections survive reopen',window.adapter.document()==saved and not window.dirty)
    save_json(artifact/'events-workflow-checks.json',{'passed':True,'checks':checks,'messages':messages,
        'project':str(project/'project.json'),'robot_pixels':pixels,'bitmap_sha256':hashlib.sha256(images[0]).hexdigest()})
finally:
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close(); window.deleteLater()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
