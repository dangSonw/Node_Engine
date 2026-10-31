"""Run sprite, tilemap, skeletal mesh, camera and physics in the same native scene."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import create_project, load_project, save_json
from editor.core.projects import compile_project, project_snapshot
from editor.core.scene import entity
from editor.core.sprite_states import new_asset as new_states
from editor.core.tilemaps import new_asset as new_tilemap
from tools.create_sprite_demo import create as create_sprites
from tools.create_animated_robot import create as create_robot
from tests.test_native import native
from tests.test_physics_scene import chain


def hybrid_project(directory, projection='orthographic'):
    path=create_project(directory/'Hybrid','Hybrid 2D and 3D')
    root=path.parent
    create_sprites(root); create_robot(root/'assets/robot')
    _,_,scene=load_project(path)
    scene['entities']=[e for e in scene['entities'] if e['id']!='fourth']
    scene['entities'].append(dict(id='robot',name='Animated model',mesh='assets/robot/robot.glb',
        position=[1.5,-2,1],rotation=[0,15,0],scale=[1.5,1.5,1.5]))
    states=new_states('atlas','Sprite states')
    states.update(id='states',states={'idle':[0,1],'jump':[2,3]},initial='idle',fps=4.)
    scene['sprite_state_assets']=[states]
    entity(scene,'player')['sprite_state']={'asset':'states','state':'idle'}
    tiles=new_tilemap('atlas','Tiles',2,1); tiles.update(id='tiles',tiles=[2,3])
    scene['tilemap_assets']=[tiles]
    b=GraphBuilder('One graph: sprite + model + physics + camera')
    b.add('start','On Game Start')
    lens=('Set Camera Orthographic',{'Camera':'camera','Height':8.}) if projection=='orthographic' else ('Set Camera Perspective',{'Camera':'camera','FOV':53.13010235415598})
    chain(b,'start',('lens',*lens),
        ('state','Set Sprite State',{'State':'jump'}),
        ('play','Play Animation',{'Entity':'robot','Clip':'Wave'}),
        ('gravity','Set Physics Gravity',{'Gravity':[0,0,0]}),
        ('sprite_body','Create Box Rigid Body',{'Half Extents':[.5,.5,.05]}),
        ('model_body','Create Sphere Rigid Body',{'Entity':'robot','Motion':'static','Radius':.2}),
        ('damping','Set Damping',{'Linear':0,'Angular':0}),
        ('velocity','Set Velocity',{'Value':[1,0,0]}))
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%4)*300,(i//4)*220]
    save_json(root/'scenes/main.json',scene); save_json(root/'graphs/gameplay.json',b.graph)
    return path


@pytest.mark.parametrize('projection',['orthographic','perspective'])
def test_native_mixed_scene_and_projection_parity(native,tmp_path,projection):
    path=hybrid_project(tmp_path,projection)
    a,b=native(program=compile_project(project_snapshot(path)),frames=30,
               extra=['--project-root',str(path.parent)])
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    state=json.loads(a.stdout); assert state==json.loads(b.stdout)
    assert state['entities']['player']['position']==pytest.approx([-1,1.5,0],abs=1e-5)
    assert state['animation']['robot']['clip']=='Wave'
    assert state['animation']['robot']['time']==pytest.approx(.5)
    assert entity(state['scene'],'player')['sprite_state']['state']=='jump'
    assert entity(state['scene'],'camera')['camera']['projection']==projection
    assert {'player','robot'}.issubset(state['physics']['bodies'])
    assert state['scene']['tilemap_assets'][0]['tiles']==[2,3]
