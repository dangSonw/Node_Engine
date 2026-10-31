"""Build and record the native gamepad/checkpoint/SDL virtual-device probe."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import fingerprint

def verify():
    out=ROOT/'artifacts/validation'; source=ROOT/'tools/gamepad_probe/main.cpp'
    report=dict(passed=False,native_fingerprint=fingerprint(),probe_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),checks=[])
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        result=subprocess.run([cmake,'--build',str(ROOT/'build'),'--target','node_gamepad_probe','--parallel','2'],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8',timeout=600)
        (out/'gamepad-probe-build.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode: raise RuntimeError('Gamepad native probe build failed')
        executable=ROOT/'build'/('node_gamepad_probe.exe' if os.name=='nt' else 'node_gamepad_probe')
        report['binary_sha256']=hashlib.sha256(executable.read_bytes()).hexdigest()
        result=subprocess.run([str(executable)],cwd=executable.parent,capture_output=True,text=True,encoding='utf-8',timeout=60)
        (out/'gamepad-probe.log').write_text(result.stdout+result.stderr,encoding='utf-8'); native=json.loads(result.stdout)
        report['checks']=native['checks']
        if result.returncode or not native['passed']: raise RuntimeError(native.get('error',result.stderr))
        assert fingerprint()==report['native_fingerprint'] and hashlib.sha256(source.read_bytes()).hexdigest()==report['probe_source_sha256']
        report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(out/'gamepad-native-checks.json',report)
    return report

if __name__=='__main__': print('Gamepad native:',len(verify()['checks']),'checks passed.')
