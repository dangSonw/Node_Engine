"""Actual editor/device playback and relocated Preview/export PCM equivalence."""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent,QSettings,QTimer,Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.ui.main_window import MainWindow
from editor.ui.audio import SoundLibraryDialog
from tools.create_audio_demo import create,tone


def pcm(path):
    data=path.read_bytes()
    assert data[:4]==b'RIFF' and data[8:16]==b'WAVEfmt ' and data[36:40]==b'data'
    assert struct.unpack_from('<HHI',data,20)==(3,2,48000)
    assert struct.unpack_from('<I',data,40)[0]==len(data)-44
    return struct.unpack('<'+'f'*((len(data)-44)//4),data[44:])


def main():
    artifact=ROOT/'artifacts/validation'; workspace=ROOT/'.cache'/('audio-'+uuid.uuid4().hex[:8])
    project=create(workspace/'project'); tone(workspace/'extra.wav',880,.1)
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); window.splitter.setSizes([700,560])
    messages,checks=[],[]; window.runtime.message.connect(messages.append)
    def wait(predicate,timeout=30):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(10)
        assert predicate(),window.console.toPlainText()+'\n'+window.build_output.toPlainText()
    def check(label,condition):
        assert condition,label
        checks.append(label); print('PASS '+label,flush=True)
    def command(name,error=False,**data):
        start=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[start:]))
        result=messages[start:]
        assert any(m.get('event')=='node_error' for m in result)==error,result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    def status(): return next(m['status'] for m in command('audio_output_status') if m['event']=='audio_output_status')
    def library_import():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,SoundLibraryDialog)
        dialog.import_sound(workspace/'extra.wav'); dialog.accept()
    try:
        window.actions['Play'].trigger()
        wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        command('pause'); pid=window.runtime.process.processId(); before=snapshot(); device=status()
        check('Editor opens a real audio output and pauses the device',device['connected'] and device['paused'] and device['driver']!='dummy')
        QTest.qWait(200); check('Editor Pause freezes mixer and gameplay state',snapshot()==before)
        capture=artifact/'audio-editor.wav'; command('begin_audio_capture',path=str(capture)); command('play')
        QTest.qWait(250); running=status(); command('pause'); command('end_audio_capture')
        check('Resume sends nonzero mixed PCM through the active device stream',not running['paused'] and max(map(abs,pcm(capture)))>.01)
        check('Resume advances the existing voice in the same process',snapshot()['audio']['sample_frames']>before['audio']['sample_frames'] and window.runtime.process.processId()==pid)
        QTimer.singleShot(10,library_import); window.actions['Sounds…'].trigger(); wait(lambda:window.reload_request is None)
        check('Sounds dialog imports a third asset',len(window.scene['audio_assets'])==3)
        window.actions['Undo'].trigger(); wait(lambda:window.reload_request is None)
        check('Undo restores the sound library',len(window.scene['audio_assets'])==2)
        window.actions['Redo'].trigger(); wait(lambda:window.reload_request is None)
        check('Redo restores the imported sound',len(window.scene['audio_assets'])==3)
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='music')
        window.inspect_node(node)
        volume=next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName()=='Play Sound Volume')
        volume.setFocus(); QTest.keyClick(volume,Qt.Key_A,Qt.ControlModifier); QTest.keyClicks(volume,'0.2'); QTest.keyClick(volume,Qt.Key_Return)
        check('Inspector authors Play Sound volume',node.get_property('value_Volume')==.2)
        window.actions['Undo'].trigger(); check('Graph Undo restores the prior volume',node.get_property('value_Volume')==.4)
        window.actions['Redo'].trigger(); check('Graph Redo restores the edited volume',node.get_property('value_Volume')==.2)
        valid=compile_graph(window.adapter.document(),window.scene)
        command('load_ir',ir=valid); command('play'); command('pause')
        before=snapshot(); check('Authored volume reaches the native voice',before['audio']['voices']['music']['volume']==.2)
        (project/'assets/broken.wav').write_bytes(b'not audio'); invalid=deepcopy(valid)
        invalid['scene']['audio_assets'][0]['file']='assets/broken.wav'; failure=command('load_ir',error=True,ir=invalid)
        check('Sound load errors do not blame the last executed graph node',
            next(m for m in failure if m['event']=='node_error')['node']=='' and
            window.problems.item(window.problems.count()-1).text().startswith('Runtime: '))
        check('Failed sound decode preserves live scene and paused audio',snapshot()==before and status()['paused'])
        invalid_graph=deepcopy(window.adapter.document())
        next(n for n in invalid_graph['nodes'] if n['id']=='music')['values']['Volume']=-1
        command('load_ir',ir=compile_graph(invalid_graph,window.scene)); failure=command('play',error=True)
        check('Gameplay sound errors still identify the originating node',
            next(m for m in failure if m['event']=='node_error')['node']=='music' and
            window.problems.item(window.problems.count()-1).text().startswith('music: '))
        command('load_ir',ir=valid); command('play'); command('pause')
        check('Valid audio reload recovers in the same process',snapshot()['audio']['voices']['music']['volume']==.2 and window.runtime.process.processId()==pid)
        window.screen().grabWindow(int(window.winId())).save(str(artifact/'audio-desktop.png'))
        check('Audio project saves',window.save_project()); signature=window.signature()
        window.runtime.shutdown(); wait(lambda:not window.runtime.active); window.open_project(project/'project.json')
        check('Save/reopen preserves the library and graph',window.signature()==signature)
        results,ticks=[],[]; window.builder.finished.connect(results.append)
        timer=QTimer(); timer.timeout.connect(lambda:ticks.append(time.monotonic())); timer.start(100)
        window.actions['Build Game'].trigger(); wait(lambda:not window.builder.busy and bool(results),360); timer.stop()
        (artifact/'audio-editor-build.log').write_text(window.build_output.toPlainText(),'utf-8')
        check('Build Game succeeds while the editor stays responsive',results==[True] and len(ticks)>5)
        packaged=workspace/'relocated game'; packaged.mkdir(); build=project/'build'
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(build/name,packaged/name)
        for name in ('assets','shaders'): shutil.copytree(build/name,packaged/name)
        shutil.copy2(project/'generated/game.ir.json',packaged/'game.ir.json'); shutil.copy2(project/'input-replay.json',packaged/'input-replay.json')
        window.saved_signature=window.signature(); window.document_changed(); window.close(); project.rename(workspace/'source-moved')
        system=Path(os.environ['SystemRoot']); clean=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        hashes={}
        for frames in (8,16,26,34,42):
            states,sounds,images={},{},{}
            for mode,exe in [('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]:
                prefix=artifact/f'audio-{frames}-{mode}'
                args=[str(packaged/exe),'--frames',str(frames),'--input-replay',str(packaged/'input-replay.json'),
                    '--audio-output',str(prefix.with_suffix('.wav')),'--output',str(prefix.with_suffix('.json'))]
                if 'preview' in mode: args+=['--ir',str(packaged/'game.ir.json')]
                if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
                run=subprocess.run(args,cwd=packaged,env=clean,capture_output=True,text=True,encoding='utf-8',timeout=30)
                check(f'{frames} frames {mode} runs after relocation with clean PATH',run.returncode==0)
                states[mode]=json.loads(prefix.with_suffix('.json').read_text('utf-8')); sounds[mode]=prefix.with_suffix('.wav').read_bytes()
                if mode.startswith('view'): images[mode]=prefix.with_suffix('.bmp').read_bytes()
            check(f'{frames} frames all four native paths match state and WAV bytes',len({json.dumps(v,sort_keys=True) for v in states.values()})==1 and len(set(sounds.values()))==1)
            check(f'{frames} frames graphical Preview/export GPU bytes match',images['view-preview']==images['view-compiled'])
            hashes[str(frames)]=hashlib.sha256(sounds['view-compiled']).hexdigest()
        samples=pcm(artifact/'audio-42-view-compiled.wav')
        def rms(first,last):
            values=samples[first*800*2:last*800*2]
            return math.sqrt(sum(v*v for v in values)/len(values))
        check('Music produces audible-range nonzero PCM',rms(0,2)>.01)
        check('Pause and finished effect leave silence',rms(9,12)==0)
        check('Resume produces PCM again',rms(14,17)>.01)
        check('Per-voice volume halves the signal',.48<rms(20,23)/rms(14,17)<.52)
        check('Master mute produces silence',rms(24,30)==0)
        check('Restart restores playback and master gain',rms(30,34)>.04)
        check('Stop All Sounds produces silence',rms(38,42)==0)
        QImage(str(artifact/'audio-42-view-compiled.bmp')).save(str(artifact/'audio-compiled.png'))
        save_json(artifact/'audio-workflow-checks.json',dict(passed=True,checks=checks,device=device,package=str(packaged),
            heartbeat_ticks=len(ticks),wave_sha256=hashes,rms={k:rms(*v) for k,v in dict(start=(0,2),pause=(9,12),resume=(14,17),quiet=(20,23),mute=(24,30),restart=(30,34),stop=(38,42)).items()}))
    finally:
        if window.builder.busy: window.builder.cancel(); wait(lambda:not window.builder.busy)
        window.runtime.shutdown(); wait(lambda:not window.runtime.active)
        window.saved_signature=window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()


if __name__=='__main__': main()
