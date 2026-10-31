"""Verify Qt authoring, optional desktop save/restart, and relocated native parity."""
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
from PySide6.QtCore import QEvent,QSettings,Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.create_persistence_demo import create,GAME


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--desktop',action='store_true'); args=parser.parse_args()
    artifact=ROOT/'artifacts/validation'; artifact.mkdir(parents=True,exist_ok=True)
    report=artifact/'persistence-workflow-checks.json'
    save_json(report,dict(passed=False,status='running'))
    token=uuid.uuid4().hex[:10]; workspace=ROOT/'.cache'/('persistence-workflow-'+token)
    project=create(workspace/'source',game_id='persistence-editor-'+token)
    assert current(ROOT/'build/node_view.exe'),'Rebuild main runtime first'
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); window.splitter.setSizes([600,740])
    checks,messages=[],[]; window.runtime.message.connect(messages.append)
    def check(label,condition):
        assert condition,label
        checks.append(label); print('PASS '+label,flush=True)
    def wait(predicate,timeout=30):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(20)
        assert predicate(),window.console.toPlainText()
    def command(name,**data):
        start=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[start:]))
        result=messages[start:]; assert not any(m.get('event')=='node_error' for m in result),result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    try:
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='open')
        window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName()=='Open Save Storage Game ID')
        old=field.text(); new=old+'-edited'; field.setText(new); QTest.keyClick(field,Qt.Key_Return)
        check('Inspector edits save identity as one graph operation',node.get_property('value_Game ID')==new and window.dirty)
        window.actions['Undo'].trigger(); check('Undo restores original save identity',node.get_property('value_Game ID')==old)
        window.actions['Redo'].trigger(); check('Redo restores edited save identity',node.get_property('value_Game ID')==new)
        check('Save graph succeeds',window.save_project()); signature=window.signature()
        window.open_project(project/'project.json'); check('Save/reopen retains persistence nodes and wires',window.signature()==signature)
        window.actions['Play'].trigger()
        wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        state=snapshot()
        check('Editor Preview opens isolated per-game storage',state['persistence']==dict(game_id=new,success=True,error='') and state['variables']['score']==0)
        if args.desktop:
            print('DESKTOP_READY: click Add point once, then Save in the embedded robot game',flush=True)
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                state=snapshot()
                if state['variables']['score']==1 and state['ui']['widgets']['hud']['elements']['status']['text'].startswith('Saved.'): break
                QTest.qWait(150)
            check('Real desktop Add and Save persist robot progress',state['variables']['score']==1 and state['variables']['robot_rotation']['value']==[0.,30.,0.] and
                state['ui']['widgets']['hud']['elements']['status']['text'].startswith('Saved.'))
            save_json(artifact/'persistence-desktop-saved.json',state)
            command('stop'); command('play'); state=snapshot()
            check('Stop/Play restores saved score and robot without replaying input',state['variables']['score']==1 and state['entities']['player']['rotation']==[0.,30.,0.] and
                state['ui']['widgets']['hud']['elements']['status']['text']=='Loaded saved progress.')
            save_json(artifact/'persistence-desktop-restored.json',state)
        window.grab().save(str(artifact/'persistence-editor.png'))
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        package=workspace/'initial-package'; package.mkdir(); build=ROOT/'build'
        for filename in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(build/filename,package/filename)
        for folder in ('shaders','fonts','licenses'): shutil.copytree(build/folder,package/folder)
        shutil.copytree(ROOT/'examples/persistence_demo/assets',package/'assets')
        shutil.copy2(ROOT/'examples/persistence_demo/generated/game.ir.json',package/'game.ir.json')
        project.rename(workspace/'source-moved')
        def click(frame,x,y):
            return [dict(frame=frame,type='move',x=x,y=y),dict(frame=frame,type='button',button=0,down=True),dict(frame=frame,type='button',button=0,down=False)]
        events=click(0,170,195)+click(2,170,195)+click(3,170,140)
        events += [dict(frame=3,type='key',key='End',down=True),dict(frame=3,type='key',key='End',down=False),
                   dict(frame=3,type='text',text=' Việt')]
        events += click(5,100,250)+[dict(frame=6,type='clear')]
        save_json(package/'save-replay.json',dict(version=1,events=events))
        save_json(package/'load-replay.json',dict(version=1,events=click(0,170,195)+click(2,260,250)+[dict(frame=3,type='clear')]))
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        save_bytes={}; hashes={}
        for phase,frames,replay in [('save',8,'save-replay.json'),('restart',2,None),('manual-load',5,'load-replay.json')]:
            if phase=='restart':
                moved=workspace/'Trò chơi đã di chuyển'; package.rename(moved); package=moved
            states,images={},{}
            for mode,exe in modes:
                prefix=artifact/f'persistence-{phase}-{mode}'; store=workspace/'saves'/mode
                flags=[str(package/exe),'--frames',str(frames),'--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
                if 'preview' in mode: flags+=['--ir','game.ir.json']
                if mode.startswith('view'): flags+=['--capture',str(prefix.with_suffix('.bmp'))]
                if replay: flags+=['--ui-replay',replay]
                result=subprocess.run(flags,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
                prefix.with_suffix('.log').write_text(result.stdout+result.stderr,'utf-8')
                check(f'{phase}: {mode} runs from standalone package',result.returncode==0)
                state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states[mode]=state
                check(f'{phase}: {mode} has the expected saved score/name/rotation',state['variables']=={
                    'score':2.,'player_name':dict(type='string',value='Player Việt'),'robot_rotation':dict(type='vec3',value=[0.,60.,0.])} and
                    state['entities']['player']['rotation']==[0.,60.,0.] and state['persistence']['success'])
                slot=store/GAME/('slot-'+b'slot-1'.hex()+'.json')
                if phase=='save': save_bytes[mode]=slot.read_bytes()
                else: check(f'{phase}: {mode} leaves the saved file unchanged',slot.read_bytes()==save_bytes[mode])
                if mode.startswith('view'): images[mode]=prefix.with_suffix('.bmp').read_bytes()
            check(f'{phase}: all four native paths have identical state',len({json.dumps(s,sort_keys=True) for s in states.values()})==1)
            check(f'{phase}: Preview and exported GPU bytes match',images['view-preview']==images['view-compiled'])
            hashes[phase]=hashlib.sha256(images['view-compiled']).hexdigest()
        check('All four paths write identical save file bytes',len(set(save_bytes.values()))==1)
        QImage(str(artifact/'persistence-restart-view-compiled.bmp')).save(str(artifact/'persistence-restored.png'))
        save_json(report,dict(passed=True,checks=checks,package=str(package),desktop=args.desktop,
            native_fingerprint=fingerprint(),gpu_sha256=hashes))
    except BaseException as error:
        save_json(report,dict(passed=False,checks=checks,error=str(error))); raise
    finally:
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        window.saved_signature=window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()


if __name__=='__main__': main()
