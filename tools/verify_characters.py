"""Check native character movement and replay checkpoints in a fresh process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.runtime_build import fingerprint


def verify(build=ROOT/'build',output=ROOT/'artifacts/validation/character-checks.json'):
    build,output=Path(build).resolve(),Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    probe=ROOT/'tools/character_probe/main.cpp'
    report=dict(passed=False,native_fingerprint=fingerprint(),probe_source_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),checks=[],runs=[])
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        result=subprocess.run([cmake,'--build',str(build),'--target','node_character_probe','--parallel','2'],
                              cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=600)
        output.with_suffix('.build.log').write_text(result.stdout+result.stderr,'utf-8')
        if result.returncode: raise RuntimeError('Character probe build failed; see '+str(output.with_suffix('.build.log')))
        executable=build/('node_character_probe.exe' if os.name=='nt' else 'node_character_probe')
        report['binary_sha256']=hashlib.sha256(executable.read_bytes()).hexdigest()
        saved=output.with_suffix('.checkpoints.json'); before=None
        for operation in ('behavior','--write-checkpoints','--read-checkpoints'):
            args=[] if operation=='behavior' else [operation,str(saved)]
            result=subprocess.run([str(executable),*args],cwd=build,capture_output=True,text=True,encoding='utf-8',timeout=120)
            row=dict(operation=operation,exit_code=result.returncode,stderr=result.stderr); report['runs'].append(row)
            if not result.stdout: raise RuntimeError(f'Character process failed ({result.returncode}): {result.stderr}')
            data=json.loads(result.stdout); row['checks']=data.get('checks',[])
            if result.returncode or not data['ok']: raise RuntimeError(data.get('error','Native character probe failed'))
            report['checks']+=row['checks']
            if operation=='--write-checkpoints':
                before=saved.read_bytes(); report['checkpoint_cases']=data['cases']; report['continuation_frames']=data['frames']
                report['checkpoint_sha256']=hashlib.sha256(before).hexdigest()
            if operation=='--read-checkpoints' and saved.read_bytes()!=before: raise RuntimeError('Character restore modified the saved checkpoint bytes')
        if fingerprint()!=report['native_fingerprint'] or hashlib.sha256(probe.read_bytes()).hexdigest()!=report['probe_source_sha256']:
            raise RuntimeError('Sources changed during character verification')
        report['checks'].append('Fresh-process character restore preserves saved checkpoint bytes'); report['passed']=True
        return report
    except Exception as error:
        report['error']=str(error); raise
    finally: output.write_text(json.dumps(report,indent=2)+'\n','utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--build',type=Path,default=ROOT/'build')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/validation/character-checks.json'); args=parser.parse_args()
    result=verify(args.build,args.output)
    print(f"Characters: {len(result['checks'])} checks; {result['checkpoint_cases']} checkpoints; {result['continuation_frames']} fresh-process continuation frames.")
