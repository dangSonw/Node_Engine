"""The Blockbench physics example authored as scene/prefab collider settings."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.physics import default_body
from editor.core.prefabs import capture_prefab
from editor.core.registry import ROOT
from tools.create_physics_events_demo import create as create_base

GAME = 'node-engine-physics-authoring-demo'


def create(directory=ROOT/'examples/physics_authoring_demo'):
    directory = create_base(directory)
    scene = json.loads((directory/'scenes/main.json').read_text('utf-8'))
    settings = {
        'player': dict(default_body(), half_extents=[.6,.75,.3], continuous=True, linear_damping=.35, angular_damping=.5),
        'floor': dict(default_body(), motion='static'),
        'zone': dict(default_body(), motion='static', sensor=True, half_extents=[1,3,1]),
    }
    for item in scene['entities']:
        if item['id'] in settings: item['rigid_body'] = settings[item['id']]
    asset = capture_prefab(scene, 'player', 'Physics robot', asset_id='physics_robot')
    scene['prefab_assets'] = [asset]
    scene['prefab_instances'] = [dict(prefab='physics_robot', root='player',
        mapping={'root':'player','e1':'robot_mesh'}, owned_components={'root':['transform'],'e1':[]})]
    scene['ui_assets'][0]['rml'] = scene['ui_assets'][0]['rml'].replace('Collision / trigger playground','Scene colliders / robot prefab')
    b = GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    removed = {'ground','zone_body','body','damping'}
    b.graph['nodes'] = [n for n in b.graph['nodes'] if n['id'] not in removed]
    b.graph['links'] = [l for l in b.graph['links'] if l['from'][0] not in removed and l['to'][0] not in removed]
    b.connect('start','Out','aim','In')
    for node in b.graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']=GAME
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Scene colliders and prefab robot'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
