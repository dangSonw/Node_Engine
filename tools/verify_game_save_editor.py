"""Exercise public checkpoint nodes through the editor and real native buttons."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.create_game_save_demo import create,SLOT


def main():
    artifacts=ROOT/'artifacts/validation'; report=artifacts/'game-save-editor-checks.json'
    token=uuid.uuid4().hex[:10]; game='game-save-editor-'+token
    project=create(ROOT/'.cache'/('game-save-editor-'+token),game)
    store=Path(os.environ['APPDATA'])/'NodeEngine'/game
    slot=store/('slot-'+SLOT.encode().hex()+'.json')
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); window.splitter.setSizes([600,740])
    checks=[]; messages=[]; window.runtime.message.connect(messages.append)
    result=dict(passed=False,checks=checks,project=str(project),native_fingerprint=fingerprint())
    save_json(report,result)
    def check(label,ok):
        assert ok,label
        checks.append(label); print('PASS '+label,flush=True)
    def wait(predicate,timeout=30):
        end=time.monotonic()+timeout
        while not predicate() and time.monotonic()<end: QTest.qWait(20)
        assert predicate(),window.console.toPlainText()+'\n'+window.build_output.toPlainText()[-2000:]
    def command(name,**values):
        start=len(messages); serial=window.runtime.send(name,**values)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[start:]))
        incoming=messages[start:]
        assert not any(m.get('event')=='node_error' for m in incoming),incoming
        return incoming
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    try:
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='save_button')
        window.inspect_node(node)
        field=next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName()=='Save Game Slot')
        field.setText('another-slot'); QTest.keyClick(field,Qt.Key_Return)
        check('Inspector edits Save Game slot and marks the graph dirty',node.get_property('value_Slot')=='another-slot' and window.dirty)
        window.actions['Undo'].trigger(); check('Undo restores the save slot',node.get_property('value_Slot')==SLOT)
        window.actions['Redo'].trigger(); check('Redo restores the edited slot',node.get_property('value_Slot')=='another-slot')
        window.actions['Undo'].trigger()
        check('Save and reopen preserve checkpoint nodes and connections',window.save_project())
        signature=window.signature(); window.open_project(project/'project.json')
        check('Reopened graph is identical',window.signature()==signature)
        # A stale copied asset would break the new strict package identity.
        stale=project/'build/assets/removed.bin'; stale.parent.mkdir(parents=True); stale.write_bytes(b'previous build')
        build_results=[]; window.builder.finished.connect(build_results.append)
        beats=[]; heartbeat=QTimer(); heartbeat.timeout.connect(lambda:beats.append(time.monotonic())); heartbeat.start(20)
        window.actions['Build Game'].trigger(); wait(lambda:bool(build_results),600); heartbeat.stop()
        (artifacts/'game-save-editor-build.log').write_text(window.build_output.toPlainText(),'utf-8')
        check('Editor Build Game finishes while Qt keeps responding',build_results==[True] and len(beats)>10)
        check('Build replaces stale assets with the exact source library',not stale.exists() and
              sorted(p.name for p in (project/'build/assets').iterdir())==sorted(p.name for p in (project/'assets').iterdir()))
        check('Editor-produced runtime stamp is current',current(project/'build/node_view.exe'))
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        check('Embedded Preview runs the checkpoint graph',snapshot()['variables']['score']>0)
        print('DESKTOP_SAVE_READY: click Save in the embedded game',flush=True)
        wait(slot.exists,240)
        saved=slot.read_bytes(); data=json.loads(saved)
        check('Real desktop Save writes the whole-game checkpoint',data['version']==2 and data['checkpoint']['clock']['frame']>0)
        window.grab().save(str(artifacts/'game-save-editor.png'))
        QTest.qWait(2000); previous=snapshot()['frame']
        print('DESKTOP_LOAD_READY: click Load in the embedded game',flush=True)
        deadline=time.monotonic()+240; restored=None
        while time.monotonic()<deadline:
            state=snapshot()
            if state['frame']<previous: restored=state; break
            previous=state['frame']; QTest.qWait(80)
        check('Real desktop Load rewinds the running simulation',restored is not None and restored['persistence']['success'])
        command('pause'); save_json(artifacts/'game-save-desktop-restored.json',restored)
        check('Desktop Load leaves the save file unchanged',slot.read_bytes()==saved)
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        # The built game reads a slot created by the embedded preview on another process.
        output=artifacts/'game-save-editor-built-restored.json'
        run=subprocess.run([str(project/'build/node_game.exe'),'--frames','0','--output',str(output)],
                           cwd=project/'build',capture_output=True,text=True,encoding='utf-8',timeout=60)
        (artifacts/'game-save-editor-built.log').write_text(run.stdout+run.stderr,'utf-8')
        built=json.loads(output.read_text('utf-8')) if output.exists() else {}
        check('Editor-built standalone game loads the Preview slot exactly',run.returncode==0 and
              built.get('frame')==data['checkpoint']['clock']['frame'] and built.get('variables')==data['checkpoint']['scene']['variables'] and built['persistence']['success'])
        check('Cross-process load retains saved bytes',slot.read_bytes()==saved)
        result.update(passed=True,save_sha256=hashlib.sha256(saved).hexdigest(),saved_frame=data['checkpoint']['clock']['frame'])
    except Exception as error:
        result['error']=str(error); raise
    finally:
        save_json(report,result); window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        if window.builder.busy: window.builder.cancel(); wait(lambda:not window.builder.busy)
        window.saved_signature=window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()


if __name__=='__main__': main()
