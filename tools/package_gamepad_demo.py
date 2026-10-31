"""Stage and verify the already-built native gamepad example."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from PySide6.QtGui import QImage

def package():
    assert current(ROOT/'build/node_view.exe'),'Build examples/gamepad_demo/project.json first'
    target=ROOT/'artifacts/demos/gamepad-playground'; target.mkdir(parents=True,exist_ok=True)
    for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(ROOT/'build'/name,target/name)
    for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,target/name,dirs_exist_ok=True)
    shutil.copytree(ROOT/'examples/gamepad_demo/assets',target/'assets',dirs_exist_ok=True)
    shutil.copy2(ROOT/'examples/gamepad_demo/input-replay.json',target/'input-replay.json')
    (target/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
    (target/'Replay.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe --frames 180 --input-replay input-replay.json %*\n',encoding='ascii')
    (target/'README.md').write_text('''# Gamepad robot

Run Play.cmd, click the game window and use a connected SDL-compatible gamepad.
Left stick moves the Blockbench robot; the South face button turns it.
A/D provide keyboard movement, R resets the pose and S/L save/load the game.
The HUD shows connected count, analog values and button/controller callbacks.

Replay.cmd runs the supplied trace without requiring a controller. It includes
two simultaneous connections, held buttons, disconnect/reconnect and one Save.
Normal play requires neither Python nor Qt. Third-party licenses are included.

The default dead zone is 0.15 per axis, adjustable in Get Gamepad Axis.
Controller 0 chooses the lowest live connection ID. A reconnected controller may
have a new ID. Focus loss releases gameplay input; Resume/Load sample the current
analog state and require release/repress of buttons already held.

Editable project: examples/gamepad_demo/project.json.
Python authoring: tools/create_gamepad_demo.py.
See docs/gamepad.md for semantics and verification. SDL virtual-device tests pass;
physical USB/Bluetooth controllers and other platforms have not been certified.
''',encoding='utf-8')
    out=ROOT/'artifacts/validation/gamepad'; system=Path(os.environ['SystemRoot'])
    env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
    result=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/'Play.cmd'),'--frames','30',
        '--input-replay',str(target/'input-replay.json'),'--save-root',str(ROOT/'.cache'/('gamepad-package-'+uuid.uuid4().hex[:8])),
        '--output',str(out/'package.json'),'--capture',str(out/'package.bmp')],cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    (out/'package.log').write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
    assert json.loads((out/'package.json').read_text('utf-8'))==json.loads((out/'reference-view-compiled.json').read_text('utf-8'))
    assert QImage(str(out/'package.bmp'))==QImage(str(out/'reference-view-compiled.bmp'))
    replay=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/'Replay.cmd'),
        '--save-root',str(ROOT/'.cache'/('gamepad-replay-package-'+uuid.uuid4().hex[:8])),
        '--output',str(out/'package-replay.json')],cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    (out/'package-replay.log').write_text(replay.stdout+replay.stderr,encoding='utf-8'); assert replay.returncode==0,replay.stderr
    reference=json.loads((out/'package.json').read_text('utf-8')); played=json.loads((out/'package-replay.json').read_text('utf-8'))
    assert played['frame']==180 and all(played[k]==reference[k] for k in ('variables','entities'))
    report=dict(passed=True,package=str(target),native_fingerprint=fingerprint(),checks=[
        'Play.cmd runs with system-only PATH','Packaged replay state matches four-host reference','Packaged GPU pixels match four-host reference',
        'Replay.cmd completes 180 frames without hardware and retains final gameplay state'],
        sha256={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()})
    save_json(ROOT/'artifacts/validation/gamepad-package.json',report); return report

if __name__=='__main__': print('Gamepad package:',len(package()['checks']),'checks passed.')
