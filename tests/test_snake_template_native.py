"""Real native gameplay assertions for the editable isometric Snake template."""
import json
import os
from pathlib import Path
import subprocess
import pytest
from editor.core.projects import compile_project,project_snapshot
from tools.verify_template_games import assert_state,checked_contract

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'templates/games/isometric_snake_3d/isometric_snake_3d.nen'


def run(mode,frames,replay,tmp_path):
    build=Path(os.environ.get('NODE_ENGINE_SNAKE_BUILD',str(ROOT/'build')))
    args=[str(build/(mode+'.exe')),'--frames',str(frames),'--project-root',str(PROJECT.parent),
          '--input-replay',str(replay),'--output',str(tmp_path/(mode+'.json'))]
    if mode=='node_preview':args+=['--ir',str(PROJECT.parent/'generated/game.ir.json')]
    result=subprocess.run(args,cwd=PROJECT.parent,text=True,encoding='utf-8',capture_output=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    return json.loads((tmp_path/(mode+'.json')).read_text('utf-8'))


@pytest.mark.parametrize('case_id',['start','eat','wall','restart','reverse_rejected','pause','self_collision'])
def test_complete_snake_round_in_both_native_backends(case_id,tmp_path):
    case=next(s for s in checked_contract(PROJECT)['scenarios'] if s['id']==case_id)
    states=[run(mode,case['frames'],PROJECT.parent/case['replay'],tmp_path) for mode in ('node_preview','node_game')]
    assert states[0]==states[1]
    state=states[0]
    for assertion in case['assertions']:assert_state(state,assertion)
    variables={k:v['value'] for k,v in state['variables'].items()}
    assert variables['food'] not in variables['snake']
    assert len(variables['snake'])==variables['score']+4
    # Rendered pool entities must exactly track every logical body position.
    scene_entities={e['id']:e for e in state['scene']['entities']}
    for i,entity in enumerate(variables['body_entities']):
        actual=state['entities'][entity]
        assert scene_entities[entity].get('active',True)==(i<len(variables['snake']))
        if i<len(variables['snake']):assert actual['position']==variables['snake'][i]


def test_one_turn_per_tick_and_pause_resume_preserve_body(tmp_path):
    replay=tmp_path/'turns.json'
    replay.write_text(json.dumps(dict(version=1,events=[
        dict(frame=1,button='Down',down=True),dict(frame=2,button='Down',down=False),
        dict(frame=3,button='Left',down=True),dict(frame=4,button='Left',down=False)])),encoding='utf-8')
    state=run('node_preview',12,replay,tmp_path)
    assert state['variables']['direction']['value']==[0,0,1]
    assert state['variables']['snake']['value'][0]==[3,.5,6]
    replay.write_text(json.dumps(dict(version=1,events=[
        dict(frame=1,button='P',down=True),dict(frame=2,button='P',down=False),
        dict(frame=22,button='P',down=True),dict(frame=23,button='P',down=False)])),encoding='utf-8')
    state=run('node_preview',34,replay,tmp_path)
    assert state['variables']['paused']['value'] is False
    assert state['variables']['steps']['value']==1


def test_saved_project_ir_is_current_and_gameplay_is_authored_as_nodes():
    program=compile_project(project_snapshot(PROJECT))
    assert program==json.loads((PROJECT.parent/'generated/game.ir.json').read_text('utf-8'))
    graph=json.loads((PROJECT.parent/'graphs/gameplay.json').read_text('utf-8'))
    assert len(graph['functions'])==6
    for body in [graph,*[f['graph'] for f in graph['functions']]]:
        assert all(not n.get('code') for n in body['nodes'])
        assert all('position' in n for n in body['nodes'])
