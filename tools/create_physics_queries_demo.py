"""Ground probes driven by graph nodes on the playable Blockbench robot."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from tools.create_physics_authoring_demo import create as create_base

GAME = 'node-engine-physics-queries-demo'
QUERIES = {'ray': ('Physics Raycast', {}),
           'sphere': ('Physics Sphere Cast', {'Radius': .25}),
           'box': ('Physics Box Cast', {'Half Extents': [.3, .5, .2]}),
           'capsule': ('Physics Capsule Cast', {'Radius': .2, 'Half Height': .5})}


def create(directory=ROOT/'examples/physics_queries_demo'):
    directory = create_base(directory)
    scene = json.loads((directory/'scenes/main.json').read_text('utf-8'))
    hud = scene['ui_assets'][0]
    rows = ''.join(f'<br/><span id="{key}">{key.title()}: waiting</span>' for key in QUERIES)
    hud['rml'] = hud['rml'].replace('Scene colliders / robot prefab', 'Ground queries / Blockbench robot').replace(
        '</div>', '<br/>Probes: robot center + 0.5m, down 10m' + rows + '</div>')
    b = GraphBuilder(); b.graph = json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name'] = 'Ground probes and physics robot'
    for node in b.graph['nodes']:
        if node['id'] == 'storage': node['values']['Game ID'] = GAME
    b.add('probe_position', 'Get World Position')
    b.add('probe_origin', 'Vector Add', B=[0,.5,0])
    b.connect('probe_position','Value','probe_origin','A')
    for key, (name, values) in QUERIES.items():
        def action(source, suffix, label, port='Out', **settings):
            target = key + '_' + suffix
            b.add(target,label,**settings); b.connect(source,port,target,'In')
            return target
        event = b.add(key+'_update','On Update')
        origin = action(event,'origin','Set Vector3 Variable',Name=key+'_origin')
        b.connect('probe_origin','Value',origin,'Value')
        query = action(origin,'query',name,Exclude='player',**values)
        b.connect('probe_origin','Value',query,'Origin')
        last = query
        for field, label in [('Hit','Boolean'),('Entity','Entity'),('Point','Vector3'),('Normal','Vector3'),('Fraction',''),('Distance','')]:
            last = action(last,field.lower(),'Set '+(label+' ' if label else '')+'Variable',Name=key+'_'+field.lower())
            b.connect(query,field,last,'Value')
        branch = action(last,'branch','Branch'); b.connect(query,'Hit',branch,'Condition')
        hit = action(branch,'hit_text','Set Widget Text',port='True',Element=key)
        action(branch,'miss_text','Set Widget Text',port='False',Element=key,Text=key.title()+': clear')
        b.add(key+'_format','Format Float'); b.connect(query,'Distance',key+'_format','Value')
        b.add(key+'_units','Concat Strings',B=' m')
        b.connect(key+'_format','Value',key+'_units','A')
        b.add(key+'_label','Concat Strings',A=key.title()+' hit: ')
        b.connect(key+'_units','Value',key+'_label','B').connect(key+'_label','Value',hit,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%8)*285,(i//8)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Physics queries and Blockbench robot'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
