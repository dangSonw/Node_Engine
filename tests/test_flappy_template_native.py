"""Native Flappy gameplay; these checks never call the legacy Python simulator."""
import json
import os
from pathlib import Path
import subprocess
import pytest

from editor.core.projects import compile_project,project_snapshot
from editor.core.runtime_build import current
from tools.verify_template_games import assert_state

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'templates/games/flappy_bird/flappy_bird.nen'
BUILD=Path(os.environ.get('NODE_ENGINE_TEMPLATE_FLAPPY_BUILD',str(ROOT/'.work/build-template-flappy')))


def test_game_is_editable_native_graph_and_saved_export_matches():
    graph=json.loads((PROJECT.parent/'graphs/gameplay.json').read_text('utf-8'))
    assert len(graph.get('functions',[]))>=7
    assert not any(n.get('code') for body in [graph,*[f['graph'] for f in graph['functions']]] for n in body['nodes'])
    assert json.loads((PROJECT.parent/'generated/game.ir.json').read_text('utf-8'))==compile_project(project_snapshot(PROJECT))


@pytest.mark.parametrize('scenario',['ready','score','death','pipe_death','restart','pause','recycle'])
def test_native_gameplay_scenario_and_backend_parity(scenario,tmp_path):
    if not current(BUILD/'node_view.exe'):
        pytest.skip('Build the Flappy .nen in .work/build-template-flappy before native acceptance')
    contract=json.loads((PROJECT.parent/'acceptance.json').read_text('utf-8'))
    case=next(c for c in contract['scenarios'] if c['id']==scenario)
    states=[]
    for mode in ('node_preview','node_game'):
        output=tmp_path/(mode+'.json')
        args=[str(BUILD/(mode+'.exe')),'--frames',str(case['frames']),'--project-root',str(PROJECT.parent),
              '--input-replay',str(PROJECT.parent/case['replay']),'--output',str(output)]
        if mode=='node_preview':args+=['--ir',str(PROJECT.parent/'generated/game.ir.json')]
        result=subprocess.run(args,cwd=PROJECT.parent,capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert result.returncode==0,result.stdout+result.stderr
        state=json.loads(output.read_text('utf-8'));states.append(state)
        for assertion in case['assertions']:assert_state(state,assertion)
    assert states[0]==states[1]
