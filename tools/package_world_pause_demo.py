"""Package and execute the pause playground without Python or Qt on PATH."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint

def package():
    assert current(ROOT/'build/node_view.exe'),'Build examples/world_pause_demo/project.json first'
    source=ROOT/'examples/world_pause_demo'; target=ROOT/'artifacts/demos/world-pause-playground'; target.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,package=str(target),native_fingerprint=fingerprint(),checks=[])
    try:
        for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(ROOT/'build'/name,target/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,target/name,dirs_exist_ok=True)
        shutil.copytree(source/'assets',target/'assets',dirs_exist_ok=True); shutil.copy2(source/'input-replay.json',target/'input-replay.json')
        (target/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
        (target/'Replay.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe --frames 71 --input-replay input-replay.json %*\n',encoding='ascii')
        (target/'README.md').write_text('''# World pause playground

Play.cmd runs without Python or Qt. Click the game window, then P pauses and
R resumes the world. S saves, L loads, Q quits. Keys 0/1/2/3 set Time Scale to
0/0.25/1/2. Resume preserves the selected scale; choose 2 to move after scale 0.
The left robot animates, the middle turns on a scaled timer, the right uses physics.
Audio and the displayed unscaled timer keep running during world pause.
Replay.cmd demonstrates pause and resume automatically, then exits after 71 frames.

Pause/Resume events fire once per actual transition. Simulation changes apply
on the next frame. Scaled timers and Delay freeze; input, UI callbacks, Update,
Late Update and unscaled work keep running. Pause does not prevent explicit edits
made by gameplay code. Whole-game Save/Load retains pause without synthetic events.
Editor Pause is a separate debugger control that stops the entire preview loop.

Editable project: examples/world_pause_demo/project.json.
Documentation: docs/world-pause.md. Third-party licenses are included.
Windows was verified; other platforms and physical audio devices were not retested.
''',encoding='utf-8')
        out=ROOT/'artifacts/validation/world-pause'; system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        reference=json.loads((out/'resumed-view-compiled.json').read_text('utf-8'))
        for label,launcher,args in [('package','Play.cmd',['--frames','71','--input-replay',str(target/'input-replay.json')]),('package-replay','Replay.cmd',[])]:
            result=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/launcher),*args,'--capture',str(out/(label+'.bmp')),
                '--save-root',str(ROOT/'.cache'/('world-pause-package-'+uuid.uuid4().hex[:8])),'--output',str(out/(label+'.json'))],cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            (out/(label+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
            report['checks'].append(launcher+' runs with system-only PATH')
            assert json.loads((out/(label+'.json')).read_text('utf-8'))==reference and QImage(str(out/(label+'.bmp')))==QImage(str(out/'resumed-view-compiled.bmp'))
            report['checks'].append(launcher+' full state and GPU pixels equal four-host reference')
        assert fingerprint()==report['native_fingerprint']
        report['sha256']={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/world-pause-package.json',report)
    return report

if __name__=='__main__': print('World pause package:',len(package()['checks']),'checks passed.')
