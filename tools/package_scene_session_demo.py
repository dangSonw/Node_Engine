"""Ship the verified two-scene demo and exercise both standalone launchers."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint

def package():
    assert current(ROOT/'build/node_view.exe'),'Build the scene_session_demo project first'
    source=ROOT/'examples/scene_session_demo'; target=ROOT/'artifacts/demos/scene-playground'; target.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,package=str(target),native_fingerprint=fingerprint(),checks=[])
    try:
        for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(ROOT/'build'/name,target/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,target/name,dirs_exist_ok=True)
        shutil.copytree(source/'assets',target/'assets',dirs_exist_ok=True); shutil.copy2(source/'input-replay.json',target/'input-replay.json')
        (target/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
        (target/'Replay.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe --frames 71 --input-replay input-replay.json %*\n',encoding='ascii')
        (target/'README.md').write_text('''# Scene playground

Run Play.cmd without Python or Qt. Click the game window to use the keys:
C enters the level, M returns to the menu, R reloads the current scene.
S saves the entire game, L restores the saved scene and simulation.
P pauses the world, U resumes, Q quits. X tries a missing scene and shows the error.
Replay.cmd automatically visits menu / level / menu / level, then exits.

The menu has one Blockbench robot. The level has animated, timed and physical
robots, UI and looping audio. Scene changes replace the world at a frame boundary,
keep game time/pause and clear old scene state. On Game Start runs only once;
On Scene Loaded initializes each new/reloaded world. Load Game resumes a snapshot
without replaying either event. Save files are local to your user profile.

Editable project: examples/scene_session_demo/project.json.
Behavior and limits: docs/scenes.md. Windows/Vulkan was verified; other platforms
were not tested. Additive scenes, asynchronous loading and persistent objects
are not included. Third-party licenses are provided in licenses/.
''',encoding='utf-8')
        out=ROOT/'artifacts/validation/scene-session'; system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        reference=json.loads((out/'cycle-view-compiled.json').read_text('utf-8'))
        for label,launcher,args in [('package','Play.cmd',['--frames','71','--input-replay',str(target/'input-replay.json')]),('package-replay','Replay.cmd',[])]:
            r=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/launcher),*args,'--capture',str(out/(label+'.bmp')),
                '--save-root',str(ROOT/'.cache'/('scene-package-'+uuid.uuid4().hex[:8])),'--output',str(out/(label+'.json'))],cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            (out/(label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8'); assert r.returncode==0,r.stderr
            report['checks'].append(launcher+' runs with system-only PATH')
            assert json.loads((out/(label+'.json')).read_text('utf-8'))==reference and QImage(str(out/(label+'.bmp')))==QImage(str(out/'cycle-view-compiled.bmp'))
            report['checks'].append(launcher+' full state and GPU pixels equal four-host reference')
        assert fingerprint()==report['native_fingerprint']
        report['sha256']={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/scene-session-package.json',report)
    return report

if __name__=='__main__': print('Scene package:',len(package()['checks']),'checks passed.')
