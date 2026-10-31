"""Build and record shared clock, shutdown, pause and staged checkpoint checks."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import fingerprint

def verify():
    out=ROOT/'artifacts/validation'; source=ROOT/'tools/time_probe/main.cpp'
    report=dict(passed=False,native_fingerprint=fingerprint(),probe_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        result=subprocess.run([cmake,'--build',str(ROOT/'build'),'--target','node_time_probe','--parallel','2'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=300)
        (out/'world-pause-native-build.log').write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
        executable=ROOT/'build/node_time_probe.exe'; report['binary_sha256']=hashlib.sha256(executable.read_bytes()).hexdigest()
        result=subprocess.run([str(executable)],cwd=executable.parent,capture_output=True,text=True,encoding='utf-8',timeout=30)
        (out/'world-pause-native.log').write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
        native=json.loads(result.stdout); assert native['passed']; report['check_count']=native['checks']
        assert fingerprint()==report['native_fingerprint'] and hashlib.sha256(source.read_bytes()).hexdigest()==report['probe_source_sha256']; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(out/'world-pause-native-checks.json',report)
    return report

if __name__=='__main__': print('World pause native:',verify()['check_count'],'checks passed.')
