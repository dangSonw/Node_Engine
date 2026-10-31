"""Stage and verify the already-built native cursor example."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from PySide6.QtGui import QImage

def package():
    assert current(ROOT/'build/node_view.exe'),'Build examples/cursor_demo/project.json first'
    target=ROOT/'artifacts/demos/cursor-playground'; target.mkdir(parents=True,exist_ok=True)
    for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(ROOT/'build'/name,target/name)
    for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,target/name,dirs_exist_ok=True)
    shutil.copytree(ROOT/'examples/cursor_demo/assets',target/'assets',dirs_exist_ok=True)
    shutil.copy2(ROOT/'examples/cursor_demo/input-replay.json',target/'input-replay.json')
    (target/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
    (target/'README.md').write_text('''# Cursor robot

Run Play.cmd, then click the game window. K/U lock/unlock the cursor; H/V
hide/show it. Locked mouse movement or left-drag rotates the Blockbench robot.
Wheel moves it nearer/farther, R resets its pose, and S/L save/load the game.
Esc unlocks and shows the cursor. Losing focus or closing the game also releases
the physical cursor. Lock always hides the cursor until unlocked.

The HUD displays requested lock/visibility; the OS cursor also depends on focus.
In the editor, Esc temporarily releases focus while retaining game requests;
clicking the viewport reclaims them. Pause releases the cursor; Stop resets it.

Play.cmd --frames 30 --input-replay input-replay.json runs the included trace.
Replay saves one checkpoint and keeps logical cursor requests without grabbing
or hiding the user's physical cursor. Normal play needs neither Python nor Qt.

Editable project: examples/cursor_demo/project.json.
Python authoring: tools/create_cursor_demo.py.
The Windows SDL library includes the pinned child-window focus adapter documented
in docs/sdl-embedded-focus.md. Third-party licenses are under licenses/.
''',encoding='utf-8')
    out=ROOT/'artifacts/validation/cursor'; out.mkdir(parents=True,exist_ok=True)
    system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
    result=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(target/'Play.cmd'),'--frames','30',
        '--input-replay',str(target/'input-replay.json'),'--save-root',str(ROOT/'.cache'/('cursor-package-'+uuid.uuid4().hex[:8])),
        '--output',str(out/'package.json'),'--capture',str(out/'package.bmp')],cwd=target,env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=45)
    (out/'package.log').write_text(result.stdout+result.stderr,encoding='utf-8'); assert result.returncode==0,result.stderr
    assert json.loads((out/'package.json').read_text('utf-8'))==json.loads((out/'reference-view-compiled.json').read_text('utf-8'))
    assert QImage(str(out/'package.bmp'))==QImage(str(out/'reference-view-compiled.bmp'))
    report=dict(passed=True,package=str(target),native_fingerprint=fingerprint(),
        checks=['Play.cmd runs with restricted system PATH','Complete cursor state equals four-host reference','GPU capture equals four-host reference'],
        sha256={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()})
    save_json(ROOT/'artifacts/validation/cursor-package.json',report); return report

if __name__=='__main__': print('Cursor package:',len(package()['checks']),'checks passed.')
