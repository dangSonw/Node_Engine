"""Exercise native Jolt simulation and compare independent process traces."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.runtime_build import fingerprint


def verify(build=ROOT/'build',output=ROOT/'artifacts/validation/physics-checks.json'):
    build,output=Path(build).resolve(),Path(output).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    probe=ROOT/'tools/physics_probe/main.cpp'
    report={'passed':False,'native_fingerprint':fingerprint(),
            'probe_source_sha256':hashlib.sha256(probe.read_bytes()).hexdigest(),'checks':[],'runs':[]}
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        built=subprocess.run([cmake,'--build',str(build),'--target','node_physics_probe','--parallel','2'],
                             cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=600)
        output.with_suffix('.build.log').write_text(built.stdout+built.stderr,encoding='utf-8')
        if built.returncode:
            raise RuntimeError('Physics build failed; see '+str(output.with_suffix('.build.log')))
        executable=build/('node_physics_probe.exe' if os.name=='nt' else 'node_physics_probe')
        report['binary_sha256']=hashlib.sha256(executable.read_bytes()).hexdigest()
        trace=None
        for index in range(2):
            process=subprocess.run([str(executable)],cwd=build,capture_output=True,text=True,encoding='utf-8',timeout=90)
            run={'exit_code':process.returncode,'stderr':process.stderr}
            report['runs'].append(run)
            if not process.stdout:
                raise RuntimeError(f'Physics process failed ({process.returncode}): {process.stderr}')
            result=json.loads(process.stdout)
            run['checks']=result.get('checks',[])
            if process.returncode or not result['ok']:
                run['error']=result.get('error','Native probe failed')
                raise RuntimeError(run['error'])
            encoded=json.dumps(result['trace'],sort_keys=True,separators=(',',':')).encode()
            run['trace_sha256']=hashlib.sha256(encoded).hexdigest()
            if index==0:
                report['checks'].extend(result['checks'])
                report['trace_frames']=len(result['trace'])
                trace=encoded
                output.with_suffix('.trace.json').write_bytes(encoded)
            elif encoded!=trace:
                raise RuntimeError('Independent process physics traces diverged')
        report['checks'].append('Independent processes match all 240 frames exactly')
        checkpoint_file=output.with_suffix('.checkpoints.json')
        before=None
        for operation in ('--write-checkpoints','--read-checkpoints'):
            process=subprocess.run([str(executable),operation,str(checkpoint_file)],cwd=build,
                                   capture_output=True,text=True,encoding='utf-8',timeout=120)
            run={'operation':operation,'exit_code':process.returncode,'stderr':process.stderr}
            report['runs'].append(run)
            if not process.stdout:
                raise RuntimeError(f'Checkpoint process failed ({process.returncode}): {process.stderr}')
            result=json.loads(process.stdout); run['checks']=result.get('checks',[])
            if process.returncode or not result['ok']:
                run['error']=result.get('error','Native checkpoint probe failed')
                raise RuntimeError(run['error'])
            report['checks'].extend(result['checks'])
            if operation=='--write-checkpoints':
                before=checkpoint_file.read_bytes()
                report['checkpoint_cases']=result['cases']; report['continuation_frames']=result['frames']
                report['checkpoint_sha256']=hashlib.sha256(before).hexdigest()
            elif checkpoint_file.read_bytes()!=before:
                raise RuntimeError('Restoration changed checkpoint bytes on disk')
        report['checks'].append('Fresh-process restoration preserves saved checkpoint bytes')
        if fingerprint()!=report['native_fingerprint'] or hashlib.sha256(probe.read_bytes()).hexdigest()!=report['probe_source_sha256']:
            raise RuntimeError('Sources changed during physics verification')
        report['passed']=True
        return report
    except Exception as error:
        report['error']=str(error)
        raise
    finally:
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,default=ROOT/'build')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/validation/physics-checks.json')
    args=parser.parse_args()
    result=verify(args.build,args.output)
    print(f"Physics: {len(result['checks'])} checks; {result['trace_frames']} deterministic frames; "
          f"{result['continuation_frames']} checkpoint continuation frames.")
