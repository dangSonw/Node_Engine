import shutil
import subprocess
import pytest
from editor.core.registry import ROOT
from editor.core.project_markdown import PROJECT_GITIGNORE
from tools.clean_workspace import clean, checked_target


def test_cleanup_is_preview_first_preserves_sources_and_kept_evidence(tmp_path):
    keep = 'artifacts/validation/latest'
    sources = ['editor/main.py','runtime/generated/adapters.generated.cpp','templates/games/game/graphs/main.json',
               'templates/games/game/docs/guide.md','templates/games/game/assets/bird.png',keep+'/checks.json']
    outputs = ['.cache/test.json','.work/state.json','artifacts/validation/old/checks.json','editor/__pycache__/main.pyc']
    for name in [*sources,*outputs]:
        path = tmp_path/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('keep',encoding='utf-8')
    preview = clean(tmp_path,keep=(keep,))
    assert not preview['applied'] and all((tmp_path/name).exists() for name in sources+outputs)
    result = clean(tmp_path,apply=True,keep=(keep,))
    assert result['files']==4 and result['bytes']==16
    assert all((tmp_path/name).exists() for name in sources)
    assert all(not (tmp_path/name).exists() for name in outputs)
    with pytest.raises(ValueError):checked_target(tmp_path,tmp_path)
    with pytest.raises(ValueError):checked_target(tmp_path,tmp_path/'../outside')


def test_gitignore_ignores_outputs_and_retains_all_source_types(tmp_path):
    if not shutil.which('git'):pytest.skip('Git is not installed')
    subprocess.run(['git','-c','init.templateDir=','init','--quiet',str(tmp_path)],check=True,capture_output=True)
    shutil.copy2(ROOT/'.gitignore',tmp_path/'.gitignore')
    project = tmp_path/'MyGame'; project.mkdir(); (project/'.gitignore').write_text(PROJECT_GITIGNORE,encoding='utf-8')
    ignored = ['.work/test.json','.cache/test.json','artifacts/validation/current/checks.json','build-physics/a.exe',
               'templates/games/flappy_bird/generated/game.ir.json','templates/games/flappy_bird/dist/Play.cmd',
               'examples/demo/generated/preview.ir.json','MyGame/generated/build-request.json','MyGame/saves/slot.json']
    kept = ['nodes/registry.yaml','runtime/generated/adapters.generated.cpp','templates/games/flappy_bird/flappy_bird.nen',
            'templates/games/flappy_bird/acceptance.json','templates/games/flappy_bird/replays/score.json',
            'templates/games/flappy_bird/graphs/gameplay.json','templates/games/flappy_bird/scenes/main.json',
            'docs/images/node-examples/index.json','docs/images/games/flappy.png','docs/games/flappy-bird.md',
            'MyGame/README.md','MyGame/docs/guide.md','MyGame/assets/bird.png']
    result = subprocess.run(['git','check-ignore','--no-index','-z','--stdin'],input=('\0'.join(ignored+kept)+'\0').encode(),
                            cwd=tmp_path,capture_output=True,check=False)
    assert result.returncode==0,result.stderr
    assert set(result.stdout.decode().rstrip('\0').split('\0'))==set(ignored)
