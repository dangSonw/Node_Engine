"""Verify whole-context staging/commit, host-resource handoff and process restart."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.runtime_build import fingerprint


def verify(driver='dummy', output_directory=None):
    build=ROOT/'build'
    suffix='' if driver=='dummy' else '-device'
    directory=Path(output_directory) if output_directory is not None else ROOT/('artifacts/validation/game-checkpoint'+suffix)
    assets=directory/'assets'
    assets.mkdir(parents=True,exist_ok=True)
    output=directory.with_name(directory.name+'-checks.json')
    source=ROOT/'tools/game_checkpoint_probe/main.cpp'
    report=dict(passed=False,native_fingerprint=fingerprint(),
                probe_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),checks=[],runs=[],pcm=[])
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        result=subprocess.run([cmake,'--build',str(build),'--target','node_game_checkpoint_probe','--parallel','2'],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=600)
        output.with_suffix('.build.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Native probe build failed; see '+str(output.with_suffix('.build.log')))
        executable=build/('node_game_checkpoint_probe.exe' if os.name=='nt' else 'node_game_checkpoint_probe')
        report['binary_sha256']=hashlib.sha256(executable.read_bytes()).hexdigest()
        with wave.open(str(assets/'tone.wav'),'wb') as wav:
            wav.setparams((2,2,44100,0,'NONE','not compressed'))
            wav.writeframes(b''.join(struct.pack('<hh',i*97%24000-12000,i*131%16000-8000) for i in range(7000)))
        env=dict(os.environ,SDL_AUDIO_DRIVER=driver)
        report['audio_driver']=driver
        for command in ('--self-test','--write','--read','--persistence'):
            result=subprocess.run([str(executable),command,str(directory)],cwd=build,env=env,
                                  capture_output=True,text=True,encoding='utf-8',timeout=120)
            report['runs'].append(dict(command=command,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
            native=json.loads(result.stdout)
            report['checks'].extend(native['checks'])
            if result.returncode or not native['passed']:
                raise RuntimeError(native.get('error',result.stderr))
            if command=='--self-test':
                report['device']=native['device']
                if report['device']['driver']!=driver:
                    raise RuntimeError('Unexpected audio backend')
            if command=='--write':
                saved=(directory/'checkpoint.json').read_bytes()
        if (directory/'checkpoint.json').read_bytes()!=saved:
            raise RuntimeError('Restoration changed saved bytes')
        report['checks'].append('Loading leaves checkpoint bytes unchanged')
        for label,first,second in [('handoff','handoff-reference.wav','handoff-restored.wav')]+[
                (str(cut),f'reference-{cut}.wav',f'restored-{cut}.wav') for cut in (0,3,8,17,25,31)]:
            reference,restored=[(directory/name).read_bytes() for name in (first,second)]
            report['pcm'].append(dict(label=label,reference_sha256=hashlib.sha256(reference).hexdigest(),
                                      restored_sha256=hashlib.sha256(restored).hexdigest(),bytes=len(reference)))
            if reference!=restored:
                raise RuntimeError('PCM differs for '+label)
            report['checks'].append('PCM bytes match for '+label)
        report['trace_frames']=sum(len(item['trace']) for item in json.loads(saved))
        if fingerprint()!=report['native_fingerprint'] or hashlib.sha256(source.read_bytes()).hexdigest()!=report['probe_source_sha256']:
            raise RuntimeError('Sources changed during verification')
        report['passed']=True
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--audio-driver',choices=['dummy','wasapi'],default='dummy')
    report=verify(parser.parse_args().audio_driver)
    print(f"Game checkpoint: {len(report['checks'])} checks passed; {report['trace_frames']} continuation frames.")
