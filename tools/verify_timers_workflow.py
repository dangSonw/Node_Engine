"""Verify timer authoring, real native pause/reset, and exported SDL GPU parity."""
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
from PySide6.QtWidgets import QApplication, QLineEdit
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.ui.main_window import MainWindow

artifact=ROOT/'artifacts/validation'
project=ROOT/'.cache'/('timers-'+uuid.uuid4().hex[:8])
shutil.copytree(ROOT/'examples/timers_demo',project,ignore=shutil.ignore_patterns('build','generated'))
app=QApplication([])
app.setQuitOnLastWindowClosed(False)
window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
events, checks, builds = [], [], []
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
    index=len(events)
    serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event')=='ack' and m.get('id')==serial for m in events[index:]))
    return events[index:]


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')


def find(nid):
    return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)


try:
    window.library_search.setText('Start Timer')
    QTest.qWait(80)
    # Add a node via the actual library mouse gesture, then remove it via Undo.
    library=window.library_tree
    item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount())
              for j in range(library.topLevelItem(i).childCount())
              if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==5010)
    library.scrollToItem(item)
    count=len(window.adapter.graph.all_nodes())
    QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
    QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
    check('Timer node can be added from the library',len(window.adapter.graph.all_nodes())==count+1)
    window.actions['Undo'].trigger()
    check('Undo removes the newly added timer node',len(window.adapter.graph.all_nodes())==count)
    window.inspect_node(find('left_timer'))
    field=next(f for f in window.inspector.findChildren(QLineEdit) if f.property('domain_property')=='value_Seconds')
    field.setFocus(); field.selectAll(); QTest.keyClicks(field,'0.5'); QTest.keyClick(field,Qt.Key.Key_Return)
    check('Inspector changes the timer interval',find('left_timer').get_property('value_Seconds')==.5)
    window.actions['Undo'].trigger()
    check('Shared Undo restores timer properties',find('left_timer').get_property('value_Seconds')==.25)
    window.actions['Redo'].trigger()
    check('Shared Redo restores timer properties',find('left_timer').get_property('value_Seconds')==.5)
    window.actions['Undo'].trigger()
    check('Timer graph validates in the editor',window.validate_graph())
    window.play()
    wait(lambda:window.runtime.state=='running' and window.container is not None,240)
    wait(lambda:snapshot()['entities']['player']['rotation'][1]>=15)
    command('pause')
    frozen=snapshot()
    QTest.qWait(350)
    check('Pause freezes timer countdown and entity state',snapshot()==frozen)
    check('Both owners have independent timers',len(frozen['timers'])==2 and {t['owner'] for t in frozen['timers']}=={'player','partner'})
    command('play')
    QTest.qWait(320)
    command('pause')
    check('Play resumes existing timers',snapshot()['entities']['player']['rotation'][1]>frozen['entities']['player']['rotation'][1])
    command('stop')
    stopped=snapshot()
    check('Stop clears timers and restores scene',stopped['timers']==[] and stopped['frame']==0
          and all(e['rotation']==[0,0,0] for e in stopped['entities'].values()))
    command('play'); QTest.qWait(300); command('pause')
    check('Play after Stop creates one timer per owner',len(snapshot()['timers'])==2)
    window.inspect_node(find('left_event'))
    command('camera',yaw=10,pitch=15)
    command('frame_scene')
    window.frame_all()
    window.raise_(); window.activateWindow(); QTest.qWait(200)
    position=window.mapToGlobal(QPoint(0,0))
    window.screen().grabWindow(0,position.x(),position.y(),window.width(),window.height()).save(str(artifact/'timers-desktop.png'))
    position=window.container.mapToGlobal(QPoint(0,0))
    image=window.screen().grabWindow(0,position.x(),position.y(),window.container.width(),window.container.height()).toImage()
    pixels=0
    for y in range(0,image.height(),3):
        for x in range(0,image.width(),3):
            color=image.pixelColor(x,y)
            pixels += (color.blue()>color.red()*1.2 and color.red()>color.green()*1.2 and color.red()>40) or (color.green()>70 and color.blue()>70 and color.red()<60)
    check('Desktop compositor shows the native robot meshes',pixels>100)
    check('Timer graph saves',window.save_project())
    saved=window.adapter.document()
    heartbeat=[]
    ticker=QTimer(); ticker.setInterval(40); ticker.timeout.connect(lambda:heartbeat.append(1)); ticker.start()
    window.build_game()
    wait(lambda:bool(builds),240)
    ticker.stop()
    check('Editor stays responsive during native build',len(heartbeat)>5)
    check('GUI build exports timers and Flecs into standalone C++',builds[-1])
    (artifact/'timers-gui-build.log').write_text(window.build_output.toPlainText(),'utf-8')
    outputs={}
    for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
        args=[str(project/'build'/exe),'--project-root',str(project/'build'),'--frames','120',
              '--capture',str(artifact/f'timers-{mode}-120.bmp'),'--output',str(artifact/f'timers-{mode}-120.json')]
        if mode=='preview': args+=['--ir',str(project/'generated/game.ir.json')]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
        check(mode+' executes 120 native timer frames',result.returncode==0)
        outputs[mode]=json.loads((artifact/f'timers-{mode}-120.json').read_text('utf-8'))
    check('Preview and exported state match exactly',outputs['preview']==outputs['compiled'])
    state=outputs['compiled']
    check('Expected eight and four timer callbacks rotate the robots',state['entities']['player']['rotation']==[0,120,0]
          and state['entities']['partner']['rotation']==[0,-120,0] and len(state['timers'])==2)
    images=[(artifact/f'timers-{mode}-120.bmp').read_bytes() for mode in ('preview','compiled')]
    check('Preview and exported GPU frames are byte-identical',images[0]==images[1])
    window.open_project(project/'project.json')
    check('Timer graph and properties survive reopen',window.adapter.document()==saved and not window.dirty)
    save_json(artifact/'timers-workflow-checks.json',{'passed':True,'checks':checks,'events':events,
        'project':str(project/'project.json'),'robot_pixels':pixels,'bitmap_sha256':hashlib.sha256(images[0]).hexdigest()})
finally:
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
