"""Real native ownership, lifetime and persistence of scoped variables."""
from copy import deepcopy
import json
import pytest

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene, save_json
from tests.test_native import native


def chain(b, start, *steps):
    for nid, name, values in steps:
        b.add(nid, name, **values)
        b.connect(start, 'Out', nid, 'In')
        start = nid
    return start


def parity(native, b, scene=None, **kwargs):
    args = dict(scene=scene, graph=b.graph) if b else {}
    preview, game = native(**args, **kwargs)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    return left


def scoped_scene():
    scene = default_scene()
    enemy = deepcopy(scene['entities'][0]); enemy.update(id='enemy', name='Enemy')
    scene['entities'].append(enemy)
    scene['variables'] = dict(lives=declaration('int', 3), hp=declaration('int', 100), local=17.0)
    scene['variable_scopes'] = dict(lives='global', hp='entity')
    return scene


def test_global_survives_scene_roundtrip_local_and_entity_reset(native, tmp_path):
    scene = scoped_scene()
    a = GraphBuilder('Menu scopes'); a.add('start', 'On Game Start')
    chain(a, 'start', ('global', 'Set Integer Variable', dict(Name='lives', Value=9)),
          ('local', 'Set Variable', dict(Name='local', Value=41)),
          ('hp', 'Set Integer Variable', dict(Name='hp', Value=12)))
    a.add('C', 'On Key Pressed', Filter='C')
    chain(a, 'C', ('change', 'Change Scene', dict(Scene='level')))
    b = GraphBuilder('Level scopes'); b.add('loaded', 'On Scene Loaded')
    b.add('global', 'Get Global Integer Variable', Name='lives')
    chain(b, 'loaded', ('seen', 'Set Scene Integer Variable', dict(Name='seen')))
    b.connect('global', 'Value', 'seen', 'Value')
    b.add('M', 'On Key Pressed', Filter='M')
    chain(b, 'M', ('back', 'Change Scene', dict(Scene='menu')))
    program = dict(version=1, entry_scene='menu', scenes={'menu': a.compile(scene), 'level': b.compile()})
    replay = tmp_path/'keys.json'
    save_json(replay, dict(version=1, events=[dict(frame=1, button='C', down=True), dict(frame=3, button='M', down=True)]))
    state = parity(native, None, program=program, frames=5, extra=['--input-replay', str(replay)])
    assert state['scene_session']['active'] == 'menu'
    assert state['scene']['global_variables']['lives'] == declaration('int', 9)
    assert state['variables']['local'] == 17.0
    assert state['variables']['hp'] == declaration('int', 100)
    assert 'entity_variables' not in state['scene']


def test_entity_defaults_isolation_clone_and_destroy(native):
    b = GraphBuilder('Entity scopes'); b.add('start', 'On Game Start')
    end = chain(b, 'start', ('player', 'Set Entity Integer Variable', dict(Entity='player', Name='hp', Value=12)),
                ('enemy', 'Set Entity Integer Variable', dict(Entity='enemy', Name='hp', Value=7)),
                ('clone', 'Clone Entity', dict(Source='player', Name='Copy')),
                ('changed', 'Set Entity Integer Variable', dict(Name='hp', Value=5)),
                ('destroy', 'Destroy Entity', dict(Entity='player')))
    b.connect('clone', 'Entity', 'changed', 'Entity')
    state = parity(native, b, scoped_scene(), frames=0)
    stores = state['scene']['entity_variables']
    assert 'player' not in state['entities'] and 'player' not in stores
    assert stores['enemy']['hp'] == declaration('int', 7)
    copy = next(e['id'] for e in state['scene']['entities'] if e['name'] == 'Copy')
    assert stores[copy]['hp'] == declaration('int', 5)


def test_scene_reload_preserves_globals_and_resets_local_ownership(native, tmp_path):
    b = GraphBuilder('Reload scope lifetimes'); b.add('start', 'On Game Start')
    chain(b, 'start', ('g', 'Set Integer Variable', dict(Name='lives',Value=9)),
          ('s', 'Set Variable', dict(Name='local',Value=41.0)),
          ('e', 'Set Integer Variable', dict(Name='hp',Value=12)))
    b.add('R','On Key Pressed',Filter='R')
    chain(b,'R',('reload','Reload Scene',{}))
    replay=tmp_path/'reload.json'
    save_json(replay,dict(version=1,events=[dict(frame=1,button='R',down=True)]))
    state=parity(native,b,scoped_scene(),frames=3,extra=['--input-replay',str(replay)])
    assert state['scene']['global_variables']['lives'] == declaration('int',9)
    assert state['variables']['local'] == 17.0
    assert state['variables']['hp'] == declaration('int',100)
    assert 'entity_variables' not in state['scene']


def test_three_scopes_with_same_name_and_different_types(native):
    b = GraphBuilder('Independent namespaces'); b.add('start', 'On Game Start')
    chain(b, 'start', ('g', 'Set Global String Variable', dict(Name='hp', Value='global')),
          ('s', 'Set Scene Float Variable', dict(Name='hp', Value=1.5)),
          ('e', 'Set Entity Integer Variable', dict(Entity='player', Name='hp', Value=12)))
    state = parity(native, b, scoped_scene(), frames=0)
    assert state['scene']['global_variables']['hp'] == declaration('string', 'global')
    assert state['scene']['scene_variables']['hp'] == 1.5
    assert state['scene']['entity_variables']['player']['hp'] == declaration('int', 12)


def test_scoped_whole_game_checkpoint_restores_all_namespaces(native, tmp_path):
    b = GraphBuilder('Scope checkpoint'); b.add('start', 'On Game Start')
    chain(b, 'start', ('open', 'Open Save Storage', {'Game ID':'scope-test'}),
          ('g', 'Set Integer Variable', dict(Name='lives', Value=9)),
          ('s', 'Set Scene Float Variable', dict(Name='hp', Value=1.5)),
          ('e', 'Set Integer Variable', dict(Name='hp', Value=12)))
    for key, name in [('S', 'Save Game'), ('L', 'Load Game')]:
        b.add(key, 'On Key Pressed', Filter=key)
        chain(b, key, (key+'action', name, dict(Slot='checkpoint')))
    b.add('K', 'On Key Pressed', Filter='K')
    chain(b, 'K', ('kg', 'Set Integer Variable', dict(Name='lives', Value=1)),
          ('ks', 'Set Scene Float Variable', dict(Name='hp', Value=5.0)),
          ('ke', 'Set Entity Integer Variable', dict(Entity='player', Name='hp', Value=2)))
    replay = tmp_path/'replay.json'
    save_json(replay, dict(version=1, events=[dict(frame=f, button=k, down=d) for f,k,d in
         [(1,'S',True),(2,'S',False),(3,'K',True),(4,'K',False),(5,'L',True)]]))
    state = parity(native, b, scoped_scene(), frames=7, extra=['--input-replay', str(replay), '--save-root', str(tmp_path/'saves')])
    assert state['persistence']['success'], state['persistence']
    assert state['scene']['global_variables']['lives'] == declaration('int', 9)
    assert state['scene']['scene_variables']['hp'] == 1.5
    assert state['scene']['entity_variables']['player']['hp'] == declaration('int', 12)


def test_progress_save_load_uses_declared_scope(native, tmp_path):
    b = GraphBuilder('Scoped progress'); b.add('start', 'On Game Start')
    chain(b, 'start', ('open', 'Open Save Storage', {'Game ID':'scope-progress'}),
          ('g', 'Set Integer Variable', dict(Name='lives', Value=9)),
          ('e', 'Set Integer Variable', dict(Name='hp', Value=12)),
          ('save', 'Save Variables', dict(Slot='progress', Names=['lives','hp','local'])),
          ('g2', 'Set Integer Variable', dict(Name='lives', Value=1)),
          ('e2', 'Set Integer Variable', dict(Name='hp', Value=2)),
          ('l2', 'Set Variable', dict(Name='local', Value=23)),
          ('load', 'Load Variables', dict(Slot='progress', Names=['lives','hp','local'])))
    state = parity(native, b, scoped_scene(), frames=0, extra=['--save-root', str(tmp_path)])
    assert state['persistence']['success'], state['persistence']
    assert state['scene']['global_variables']['lives'] == declaration('int', 9)
    assert state['scene']['entity_variables']['player']['hp'] == declaration('int', 12)
    assert state['variables']['local'] == 17


def test_entity_variable_access_requires_live_owner(native):
    b = GraphBuilder('Stale entity scope'); b.add('start', 'On Game Start')
    chain(b, 'start', ('destroy', 'Destroy Entity', dict(Entity='enemy')),
          ('write', 'Set Entity Integer Variable', dict(Entity='enemy', Name='hp', Value=1)))
    preview, game = native(b.graph, scene=scoped_scene(), frames=0)
    assert preview.returncode != 0 and game.returncode != 0
    assert 'owner does not exist: enemy' in preview.stderr and 'owner does not exist: enemy' in game.stderr


def test_named_struct_and_enum_progress_values_keep_their_type_tags(native, tmp_path):
    scene = default_scene()
    scene['struct_definitions'] = [dict(name='Stats',fields=[dict(name='hp',type='int',default=10)])]
    scene['enum_definitions'] = [dict(name='Mode',values=['Idle','Run'])]
    scene['variables'] = dict(stats={'type':'struct:Stats','value':{'hp':10}}, mode={'type':'enum:Mode','value':'Idle'})
    scene['variable_scopes'] = dict(stats='global', mode='entity')
    b = GraphBuilder('Named scoped values'); b.add('start', 'On Game Start')
    chain(b, 'start', ('open', 'Open Save Storage', {'Game ID':'named-scopes'}), ('setup', 'C++ Code', {}),
          ('save', 'Save Variables', dict(Slot='data',Names=['stats','mode'])), ('mutate','C++ Code',{}),
          ('load', 'Load Variables', dict(Slot='data',Names=['stats','mode'])))
    for node in b.graph['nodes']:
        if node['id'] == 'setup':
            node['code'] = 'rt::SetVariableAs<rt::StructValue>(ctx, "stats", {"struct:Stats", rt::Json{{"hp",42}}});\nrt::SetVariableAs<rt::EnumValue>(ctx, "mode", {"enum:Mode","Run"});'
        elif node['id'] == 'mutate':
            node['code'] = 'rt::SetVariableAs<rt::StructValue>(ctx, "stats", {"struct:Stats", rt::Json{{"hp",1}}});\nrt::SetVariableAs<rt::EnumValue>(ctx, "mode", {"enum:Mode","Idle"});'
    state = parity(native, b, scene, frames=0, extra=['--save-root',str(tmp_path)])
    assert state['persistence']['success'], state['persistence']
    assert state['scene']['global_variables']['stats'] == {'type':'struct:Stats','value':{'hp':42}}
    assert state['scene']['entity_variables']['player']['mode'] == {'type':'enum:Mode','value':'Run'}
