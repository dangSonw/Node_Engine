"""File decoding, bounds and PCM sample checks against the built native runtime."""
import json
import shutil
import struct
import subprocess
import wave
import pytest
from editor.core.audio import new_asset
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.document import default_scene,save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from tools.verify_audio_workflow import pcm


@pytest.fixture
def audio_runtime(tmp_path):
    exe=ROOT/'build/node_preview.exe'
    assert current(ROOT/'build/node_view.exe'),'Rebuild native runtime first'
    assets=tmp_path/'assets'; assets.mkdir()
    with wave.open(str(assets/'tone.wav'),'wb') as wav:
        wav.setparams((2,2,48000,0,'NONE','not compressed')); wav.writeframes(struct.pack('<hh',8192,4096)*4800)
    scene=default_scene(); scene['audio_assets']=[dict(new_asset('assets/tone.wav'),id='tone')]
    def run(actions=(),raw=None,extra=()):
        b=GraphBuilder(); b.add('start','On Game Start'); last='start'
        for i,(label,values) in enumerate(actions):
            key=f'a{i}'; b.add(key,label,**values); b.connect(last,'Out',key,'In'); last=key
        ir=compile_graph(b.graph,scene)
        if raw: raw(ir)
        save_json(tmp_path/'game.ir.json',ir)
        result=subprocess.run([str(exe),'--ir',str(tmp_path/'game.ir.json'),'--project-root',str(tmp_path),
            '--frames','3','--audio-output',str(tmp_path/'audio.wav'),*extra],capture_output=True,text=True,encoding='utf-8',timeout=20)
        return result,tmp_path
    return run


def test_voice_replacement_master_gain_and_exact_samples(audio_runtime):
    result,root=audio_runtime([('Play Sound',dict(Sound='tone',Voice='same',Volume=1.)),
        ('Play Sound',dict(Sound='tone',Voice='same',Volume=.5)),('Set Master Volume',dict(Volume=.5))])
    assert result.returncode==0,result.stderr
    state=json.loads(result.stdout); assert list(state['audio']['voices'])==['same']
    samples=pcm(root/'audio.wav'); assert len(samples)==4800
    assert set(samples[::2])=={.0625} and set(samples[1::2])=={.03125}


def test_fractional_sample_timestep_and_zero_step(audio_runtime):
    actions=[('Play Sound',dict(Sound='tone',Loop=True))]
    result,root=audio_runtime(actions,extra=['--frames','441','--dt',str(1/44100)])
    assert result.returncode==0,result.stderr
    assert len(pcm(root/'audio.wav'))==960 and json.loads(result.stdout)['audio']['sample_frames']==480
    result,root=audio_runtime(actions,extra=['--dt','0'])
    assert result.returncode==0 and pcm(root/'audio.wav')==()


@pytest.mark.parametrize('path',['assets//tone.wav','assets/./tone.wav','assets/../tone.wav','assets/a:tone.wav','assets/missing.wav'])
def test_raw_native_sound_paths_are_rejected(audio_runtime,path):
    result,_=audio_runtime(raw=lambda ir:ir['scene']['audio_assets'][0].update(file=path))
    assert result.returncode==1


def test_malformed_and_truncated_sound_files_fail(audio_runtime):
    _,root=audio_runtime()
    (root/'assets/tone.wav').write_bytes(b'RIFF'+b'\0'*128)
    result,_=audio_runtime()
    assert result.returncode==1 and 'Decode sound asset' in result.stderr


def test_mp3_uses_the_native_decoder(audio_runtime):
    _,root=audio_runtime()
    source=ROOT/'deps/SDL3_mixer-3.2.4/x86_64-w64-mingw32/libexec/installed-examples/SDL3_mixer/music.mp3'
    shutil.copy2(source,root/'assets/music.mp3')
    result,_=audio_runtime([('Play Sound',dict(Sound='tone'))],
        raw=lambda ir:ir['scene']['audio_assets'][0].update(file='assets/music.mp3'),extra=['--frames','60'])
    assert result.returncode==0,result.stderr
    assert max(map(abs,pcm(root/'audio.wav')))>.001


@pytest.mark.parametrize('loop',[False,True])
def test_file_loop_metadata_does_not_override_play_loop_flag(audio_runtime,loop):
    _,root=audio_runtime()
    path=root/'assets/tone.wav'; data=bytearray(path.read_bytes())
    metadata=struct.pack('<9I',0,0,20833,60,0,0,0,1,0)+struct.pack('<6I',0,0,0,4799,0,0)
    data.extend(b'smpl'+struct.pack('<I',len(metadata))+metadata)
    struct.pack_into('<I',data,4,len(data)-8); path.write_bytes(data)
    result,_=audio_runtime([('Play Sound',dict(Sound='tone',Loop=loop))],extra=['--frames','20'])
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['audio']['voices']['sound']['playing']==loop
    samples=pcm(root/'audio.wav')
    assert set(samples[:4800*2:2])=={.25} and set(samples[1:4800*2:2])=={.125}
    assert set(samples[4800*2:])==({.25,.125} if loop else {0.})
