"""Character authoring and real interpreted/generated scene integration."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.physics import default_body, default_character
from editor.core.scene import entity, set_entity_property, validate_scene
from editor.core.prefabs import capture_prefab, instantiate_scene_prefab
from editor.core.prefab_edits import apply_prefab_overrides
from tests.test_native import native
from tests.test_physics_scene import chain, run


def character_body(**changes):
    return dict(default_body(), shape='capsule', motion='kinematic', radius=.35,
                half_height=.5, mass=80., character=dict(default_character(), **changes))


def scene(authored=True, height=2):
    result=default_scene(); result['entities'][0]['position']=[0,height,0]
    if authored: result['entities'][0]['rigid_body']=character_body()
    result['entities'].append(dict(id='floor',name='Floor',position=[0,-.5,0],
        rotation=[0,0,0],scale=[1,1,1],rigid_body=dict(default_body(),motion='static',half_extents=[20,.5,20])))
    return result


@pytest.mark.parametrize('key,value',[('max_slope',0),('max_slope',90),('step_height',-1),
    ('floor_snap',101),('max_strength',float('nan')),('max_strength',True),('unknown',1)])
def test_invalid_character_authoring_is_atomic(key,value):
    source=scene(); before=deepcopy(source)
    with pytest.raises(ValueError): set_entity_property(source,'player','rigid_body',character_body(**{key:value}))
    assert source==before


def test_upright_world_rotation_and_prefab_settings():
    source=scene(); source['entities'].append(dict(id='rig',name='Rig',position=[0,0,0],rotation=[20,0,0],scale=[2,2,2]))
    source['entities'][0]['parent']='rig'
    with pytest.raises(ValueError,match='upright'): validate_scene(source)
    source['entities'][0]['rotation']=[-20,0,0]; validate_scene(source)
    asset=capture_prefab(scene(),'player','Character',asset_id='hero')
    target=default_scene(); target['prefab_assets']=[asset]
    target,a=instantiate_scene_prefab(target,'hero',position=[-3,2,0])
    target,b=instantiate_scene_prefab(target,'hero',position=[3,2,0])
    target=set_entity_property(target,a,'rigid_body',character_body(step_height=.6))
    target=apply_prefab_overrides(target,a)
    assert entity(target,b)['rigid_body']['character']['step_height']==.6


def test_character_dialog_retains_settings_and_enforces_capsule(app):
    from editor.ui.physics import RigidBodyDialog
    dialog=RigidBodyDialog(); dialog.character.setChecked(True)
    assert dialog.choices['shape'].currentText()=='capsule'
    assert dialog.choices['motion'].currentText()=='kinematic'
    assert not dialog.flags['sensor'].isEnabled()
    dialog.character_fields['step_height'].setText('.6'); dialog.accept()
    assert dialog.result_body['character']['step_height']==.6
    reopened=RigidBodyDialog(dialog.result_body); reopened.accept()
    assert reopened.result_body==dialog.result_body
    reopened.character.setChecked(False); reopened.accept()
    assert 'character' not in reopened.result_body
    dialog.close(); reopened.close()


def ground_store(b,source,prefix='ground'):
    end=chain(b,source,(prefix,'Character Ground Check',{}))
    for port,name in [('Grounded','Boolean'),('State','String'),('Entity','Entity'),('Point','Vector3'),('Normal','Vector3'),('Velocity','Vector3')]:
        nid=prefix+'_'+port.lower()
        end=chain(b,end,(nid,'Set '+name+' Variable',{'Name':nid}))
        b.connect(prefix,port,nid,'Value')
    return end


@pytest.mark.parametrize('authored',[False,True])
def test_character_moves_and_returns_captured_ground_outputs(native,authored):
    b=GraphBuilder(); b.add('start','On Game Start')
    end='start' if authored else chain(b,'start',('create','Create Character',{}))
    chain(b,end,('move','Character Move',{'Velocity':[2,0,0]}))
    b.add('update','On Update'); ground_store(b,'update')
    result=run(native,b,scene(authored),120)
    player=result['physics']['bodies']['player']; values=result['variables']
    assert player['position'][0]==pytest.approx(4,abs=.001)
    assert .84<player['position'][1]<.9 and player['character']['grounded']
    assert values['ground_grounded']['value'] and values['ground_entity']['value']=='floor'
    assert values['ground_state']['value']=='on_ground'
    assert values['ground_normal']['value']==pytest.approx([0,1,0])
    assert values['ground_velocity']['value']==[0,0,0]
    assert abs(values['ground_point']['value'][1])<1e-4


def test_jump_queues_once_and_ground_result_is_a_snapshot(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('timer','Start Timer',{'Seconds':.5}))
    b.add('landed','On Timer Finished',Filter='timer')
    end=ground_store(b,'landed')
    end=chain(b,end,('jump','Character Jump',{}),('accepted','Set Boolean Variable',{'Name':'jumped'}),
              ('again','Character Jump',{}),('rejected','Set Boolean Variable',{'Name':'again'}))
    b.connect('jump','Accepted','accepted','Value').connect('again','Accepted','rejected','Value')
    result=run(native,b,scene(height=.87),45)
    assert result['variables']['jumped']['value'] and not result['variables']['again']['value']
    assert result['variables']['ground_grounded']['value']
    player=result['physics']['bodies']['player']
    assert player['position'][1]>1.6 and not player['character']['grounded']


def test_clone_copies_live_movement_then_removal_cleans_up(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('move','Character Move',{'Velocity':[2,0,0]}),
          ('clone','Clone Entity',{}),('place','Set Position',{'Value':[0,2,3]}),
          ('remember','Set Entity Variable',{'Name':'copy'}))
    b.connect('clone','Entity','place','Entity').connect('clone','Entity','remember','Value')
    result=run(native,b,scene(),60)
    bodies=result['physics']['bodies']; copy=result['variables']['copy']['value']
    assert 'character' in bodies[copy] and bodies[copy]['position'][0]==pytest.approx(2,abs=.001)
    assert bodies[copy]['position'][2]==pytest.approx(3,abs=.001)
    chain(b,'remember',('remove','Remove Character',{}),('has','Set Boolean Variable',{'Name':'has'}))
    b.add('query','Has Character'); b.connect('query','Value','has','Value')
    result=run(native,b,scene(),1)
    assert 'player' not in result['physics']['bodies'] and not result['variables']['has']['value']
    assert 'character' in result['physics']['bodies'][copy]


def test_resize_under_parent_keeps_feet_and_syncs_local_dimensions(native):
    source=scene(height=2); source['entities'][0]['parent']='rig'
    source['entities'].append(dict(id='rig',name='Rig',position=[3,0,0],rotation=[0,90,0],scale=[2,2,2]))
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('resize','Character Resize',{'Radius':.35,'Half Height':.2}),
          ('ok','Set Boolean Variable',{'Name':'resized'}),('move','Character Move',{'Velocity':[1,0,0]}))
    b.connect('resize','Resized','ok','Value')
    initial=run(native,b,source,0); player=initial['physics']['bodies']['player']
    assert initial['variables']['resized']['value'] and player['position']==pytest.approx([3,3.4,0])
    assert initial['entities']['player']['position'][1]==pytest.approx(1.7)
    result=run(native,b,source,60); player=result['physics']['bodies']['player']
    assert player['position'][0]==pytest.approx(4,abs=.001)
    assert player['character']['radius']==.7 and player['character']['half_height']==.4
    assert player['character']['grounded']


def test_uniform_live_scale_updates_capsule_center(native):
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('scale','Set Scale',{'Value':[2,2,2]}),('query','Character Ground Check',{}))
    result=run(native,b,scene(height=4),0)
    player=result['physics']['bodies']['player']
    assert player['position']==[0,4,0] and player['character']['radius']==.7


def test_character_prefab_reset_restores_authored_capsule_and_controller(native):
    source=scene(); asset=capture_prefab(source,'player','Hero',asset_id='hero')
    source['prefab_assets']=[asset]; source['entities'][0].pop('rigid_body')
    b=GraphBuilder(); b.add('start','On Game Start')
    chain(b,'start',('spawn','Instantiate Prefab',{'Prefab':'hero','Position':[0,2,3]}),
          ('resize','Character Resize',{'Half Height':.2}),('move','Character Move',{'Velocity':[3,0,0]}),
          ('reset','Reset Prefab Instance',{}))
    b.connect('spawn','Entity','resize','Entity').connect('spawn','Entity','move','Entity').connect('spawn','Entity','reset','Instance')
    result=run(native,b,source,10); player=result['physics']['bodies']['spawned_1']
    assert player['character']['half_height']==.5 and player['velocity'][0]==0


@pytest.mark.parametrize('operation,values',[('Create Character',{'Max Slope':0}),
    ('Character Move',{'Velocity':[0,1,0]}),('Character Resize',{'Radius':0}),('Character Jump',{'Speed':-1})])
def test_invalid_character_nodes_report_origin(native,operation,values):
    b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('bad',operation,values))
    a,z=native(b.graph,scene=scene(authored=operation!='Create Character'),frames=0)
    assert a.returncode==z.returncode==1
    assert json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']=='bad'
