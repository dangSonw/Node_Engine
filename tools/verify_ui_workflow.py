"""Real Qt authoring, scene rollback, and relocated four-path game UI parity.

--desktop also waits for a user/desktop driver to click Add point and submit
the name 'Đỗ Việt' in the embedded game, before the rest of the checks.
"""
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent,QSettings,QTimer,Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QComboBox,QDialogButtonBox
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.runtime_build import fingerprint,current
from editor.core.registry import ROOT
from editor.ui.main_window import MainWindow
from editor.ui.game_ui import UiLibraryDialog,TemplateDialog
from tools.create_ui_demo import create


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--desktop',action='store_true'); args=parser.parse_args()
    artifact=ROOT/'artifacts/validation'; artifact.mkdir(parents=True,exist_ok=True)
    report=artifact/'ui-workflow-checks.json'; save_json(report,dict(passed=False,status='running'))
    workspace=ROOT/'.cache'/('ui-workflow-'+uuid.uuid4().hex[:8]); project=create(workspace/'project')
    shutil.copy2(ROOT/'examples/ui_demo/ui-replay.json',project/'ui-replay.json')
    assert current(ROOT/'build/node_view.exe'),'Rebuild main Preview first'
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); window.splitter.setSizes([620,700])
    messages,checks=[],[]; window.runtime.message.connect(messages.append)
    def wait(predicate,timeout=30):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(10)
        assert predicate(),window.console.toPlainText()+'\n'+window.build_output.toPlainText()
    def check(label,result):
        assert result,label
        checks.append(label); print('PASS '+label,flush=True)
    def command(name,error=False,**data):
        start=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[start:]))
        result=messages[start:]
        assert any(m.get('event')=='node_error' for m in result)==error,result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    try:
        def edit_template():
            dialog=app.activeModalWidget(); assert isinstance(dialog,UiLibraryDialog)
            def edit():
                editor=app.activeModalWidget(); assert isinstance(editor,TemplateDialog)
                editor.name.setText('Robot HUD')
                editor.markup.setPlainText(editor.markup.toPlainText().replace('Robot playground','Robot UI playground'))
                QTest.mouseClick(editor.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
            QTimer.singleShot(20,edit); dialog.edit()
            QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
        QTimer.singleShot(20,edit_template); window.actions['UI Templates…'].trigger()
        check('Template dialog authors scene UI with stable IDs',window.scene['ui_assets'][0]['name']=='Robot HUD' and window.scene['ui_assets'][0]['id']=='hud')
        window.actions['Undo'].trigger(); check('Undo restores template markup and name',window.scene['ui_assets'][0]['name']=='HUD')
        window.actions['Redo'].trigger(); check('Redo restores edited template',window.scene['ui_assets'][0]['name']=='Robot HUD')
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='create')
        window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName()=='Create Widget Template')
        check('Create Widget Inspector lists the scene template by name',field.currentText()=='Robot HUD' and field.currentData()=='hud')
        window.actions['Save'].trigger(); signature=window.signature(); window.open_project(project/'project.json')
        check('Save/reopen retains authored UI and graph',window.signature()==signature)
        window.actions['Play'].trigger()
        wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        pid=window.runtime.process.processId()
        if args.desktop:
            print('DESKTOP_READY: click Add point, then replace Player with Đỗ Việt and press Enter',flush=True)
            deadline=time.monotonic()+900; state=snapshot()
            while time.monotonic()<deadline:
                state=snapshot()
                if state['variables']['score']>=1 and state['variables']['player_name']['value']=='Đỗ Việt': break
                QTest.qWait(100)
            save_json(artifact/'ui-desktop-state.json',state)
            check('Desktop click runs graph and updates HUD/robot',state['variables']['score']>=1 and state['entities']['player']['rotation'][1]>=30)
            check('Desktop Unicode text and Enter reach the submit handler',state['variables']['player_name']['value']=='Đỗ Việt' and state['ui']['widgets']['hud']['elements']['status']['text']=='Welcome, Đỗ Việt')
            check('UI clicks and typing do not trigger gameplay controls',state['variables']['clicks_outside']==0 and state['entities']['player']['position']==[0.,0.,0.])
        command('pause'); frozen=snapshot(); QTest.qWait(150)
        check('Pause freezes game and UI state',snapshot()==frozen)
        valid=compile_graph(window.adapter.document(),window.scene)
        for label,markup in [('missing image','<img src="assets/missing.png" />'),
                             ('outside assets','<link type="text/rcss" href="project.json" />')]:
            invalid=deepcopy(valid)
            if label=='missing image': invalid['scene']['ui_assets'][0]['rml']=invalid['scene']['ui_assets'][0]['rml'].replace('</body>',markup+'</body>')
            else: invalid['scene']['ui_assets'][0]['rml']=invalid['scene']['ui_assets'][0]['rml'].replace('</head>',markup+'</head>')
            command('load_ir',error=True,ir=invalid)
            check(f'{label} fails preflight while preserving live scene and UI',snapshot()==frozen and window.runtime.process.processId()==pid)
        command('stop'); check('Stop removes document instances',snapshot()['ui']['instances']=={})
        command('play'); command('pause')
        check('Play recreates template defaults',snapshot()['variables']['score']==0 and snapshot()['ui']['widgets']['hud']['elements']['name']['text']=='Player')
        capture=artifact/'ui-editor.bmp'; command('capture',path=str(capture)); wait(lambda:capture.exists())
        window.grab().save(str(artifact/'ui-editor.png'))
        results,ticks=[],[]; window.builder.finished.connect(results.append)
        timer=QTimer(); timer.timeout.connect(lambda:ticks.append(time.monotonic())); timer.start(100)
        window.actions['Build Game'].trigger(); wait(lambda:not window.builder.busy and bool(results),600); timer.stop()
        (artifact/'ui-editor-build.log').write_text(window.build_output.toPlainText(),'utf-8')
        check('Build Game packages UI while editor remains responsive',results==[True] and len(ticks)>5)
        package=workspace/'giao diện game'; package.mkdir(); build=project/'build'
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(build/name,package/name)
        for name in ('assets','shaders','fonts','licenses'): shutil.copytree(build/name,package/name)
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json'); shutil.copy2(project/'ui-replay.json',package/'ui-replay.json')
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        window.saved_signature=window.signature(); window.document_changed(); window.close(); project.rename(workspace/'source-moved')
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        hashes={}
        for frames,score,enabled in ((4,1,False),(10,2,True)):
            states,images={},{}
            for mode,exe in [('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]:
                prefix=artifact/f'ui-{frames}-{mode}'
                flags=[str(package/exe),'--frames',str(frames),'--ui-replay','ui-replay.json','--output',str(prefix.with_suffix('.json'))]
                if 'preview' in mode: flags+=['--ir','game.ir.json']
                if mode.startswith('view'): flags+=['--capture',str(prefix.with_suffix('.bmp'))]
                run=subprocess.run(flags,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
                (prefix.with_suffix('.log')).write_text(run.stdout+run.stderr,'utf-8')
                check(f'{frames} frames {mode} runs from Unicode package with clean PATH',run.returncode==0)
                states[mode]=json.loads(prefix.with_suffix('.json').read_text('utf-8'))
                if mode.startswith('view'): images[mode]=prefix.with_suffix('.bmp').read_bytes()
            check(f'{frames} frames all four paths have identical UI, scene and events',len({json.dumps(s,sort_keys=True) for s in states.values()})==1)
            check(f'{frames} frames Preview/export GPU pixels match',images['view-preview']==images['view-compiled'])
            state=states['view-compiled']; hud=state['ui']['widgets']['hud']['elements']
            check(f'{frames} frames expected click/checkbox/progress behavior',state['variables']['score']==score and hud['add']['enabled']==enabled and abs(hud['progress']['value']-score/10)<1e-6)
            if frames==10:
                check('Slider input and Unicode submission execute node graph',state['variables']['volume']==.9 and hud['status']['text']=='Welcome, Player Việt')
            hashes[str(frames)]=hashlib.sha256(images['view-compiled']).hexdigest()
        QImage(str(artifact/'ui-10-view-compiled.bmp')).save(str(artifact/'ui-compiled.png'))
        save_json(report,dict(passed=True,checks=checks,package=str(package),heartbeat_ticks=len(ticks),
                             native_fingerprint=fingerprint(),gpu_sha256=hashes,desktop=args.desktop))
    except BaseException as error:
        save_json(report,dict(passed=False,checks=checks,error=str(error))); raise
    finally:
        if window.builder.busy: window.builder.cancel(); wait(lambda:not window.builder.busy)
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        window.saved_signature=window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()


if __name__=='__main__': main()
