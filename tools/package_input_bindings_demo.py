"""Package the built mixed-input demo and verify both standalone launchers."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint

def package():
    assert current(ROOT/'build/node_view.exe'),'Build examples/input_bindings_demo/project.json first'
    source=ROOT/'examples/input_bindings_demo'; target=ROOT/'artifacts/demos/input-bindings-playground'; target.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,package=str(target),native_fingerprint=fingerprint(),checks=[])
    try:
        for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(ROOT/'build'/name,target/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,target/name,dirs_exist_ok=True)
        shutil.copytree(source/'assets',target/'assets',dirs_exist_ok=True); shutil.copy2(source/'input-replay.json',target/'input-replay.json')
        (target/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
        (target/'Replay.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe --frames 180 --input-replay input-replay.json %*\n',encoding='ascii')
        (target/'README.md').write_text('''# Shared input bindings

Play.cmd runs the robot game without Python or Qt. Click the window for input.
Left stick, D-pad, A/D and arrows move it. Space, left mouse and South share one
turn action: holding another alternative does not turn twice. R resets; S/L save/load.
Replay.cmd runs the included multi-controller trace without requiring hardware.

Edit Scene > Input Actions and Axes in examples/input_bindings_demo/project.json.
Gamepad bindings use controller 0 for any connected device; analog selects the
largest magnitude (lowest ID wins equal magnitudes). Digital and analog values
add and clamp to [-1,1]. Dead zone is 0.2 in this demo. Reconnect IDs can change.

Pause/Load/focus return resample analog and require releasing/repressing already
held buttons. Third-party licenses are included. SDL virtual controllers were
tested; physical USB/Bluetooth models and other platforms are not certified.
See docs/input-bindings.md and tools/create_input_bindings_demo.py.
''',encoding='utf-8')
        out=ROOT/'artifacts/validation/input-bindings'; system=Path(os.environ['SystemRoot'])
        env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        for label,launcher,args in [('package','Play.cmd',['--frames','30','--input-replay',str(target/'input-replay.json'),'--capture',str(out/'package.bmp')]),
                                    ('package-replay','Replay.cmd',[])]:
            result=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/launcher),*args,
                '--save-root',str(ROOT/'.cache'/('input-bindings-package-'+uuid.uuid4().hex[:8])),
                '--output',str(out/(label+'.json'))],cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            (out/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
            report['checks'].append(launcher+' runs with system-only PATH')
        reference=json.loads((out/'reference-view-compiled.json').read_text('utf-8')); played=json.loads((out/'package.json').read_text('utf-8'))
        assert played==reference and QImage(str(out/'package.bmp'))==QImage(str(out/'reference-view-compiled.bmp'))
        report['checks'].append('Packaged full state and GPU pixels equal the four-host reference')
        replay=json.loads((out/'package-replay.json').read_text('utf-8'))
        assert replay['frame']==180 and all(replay[k]==reference[k] for k in ('variables','entities'))
        report['checks'].append('Hardware-free 180-frame replay retains expected gameplay state')
        assert fingerprint()==report['native_fingerprint']
        report['sha256']={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
        report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/input-bindings-package.json',report)
    return report

if __name__=='__main__': print('Input bindings package:',len(package()['checks']),'checks passed.')
