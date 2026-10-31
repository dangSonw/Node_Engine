"""Keep the pre-scene clock, application and whole-game transactions intact."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import fingerprint
from tools.verify_game_checkpoint import verify as checkpoint

def verify():
    out=ROOT/'artifacts/validation'; report=dict(passed=False,native_fingerprint=fingerprint())
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        r=subprocess.run([cmake,'--build',str(ROOT/'build'),'--target','node_time_probe','--parallel','2'],capture_output=True,text=True,encoding='utf-8',timeout=300)
        (out/'scene-session-time-build.log').write_text(r.stdout+r.stderr,encoding='utf-8'); assert r.returncode==0,r.stderr
        exe=ROOT/'build/node_time_probe.exe'; report['binary_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
        r=subprocess.run([str(exe)],cwd=exe.parent,capture_output=True,text=True,encoding='utf-8',timeout=30)
        (out/'scene-session-time.log').write_text(r.stdout+r.stderr,encoding='utf-8'); assert r.returncode==0,r.stderr
        native=json.loads(r.stdout); assert native['passed']; report['check_count']=native['checks']
        assert fingerprint()==report['native_fingerprint']; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(out/'scene-session-time-checks.json',report)
    combined=checkpoint(output_directory=out/'scene-session-checkpoint')
    print('Clock checks:',report['check_count'],'; checkpoint:',len(combined['checks']),'checks /',combined['trace_frames'],'frames')

if __name__=='__main__': verify()
