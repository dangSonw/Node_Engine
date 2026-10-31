"""Before-deletion data reads and loot spawning, including prefab Reset/Apply."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.prefabs import capture_prefab
from editor.core.registry import ROOT
from tools.create_entity_lifecycle_demo import create as create_base

GAME='node-engine-entity-destroyed-demo'
SLOT='entities'


def create(directory=ROOT/'examples/entity_destroyed_demo'):
    directory=create_base(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    next(e for e in scene['entities'] if e['id']=='player')['tags']=['loot_source']
    scene['prefab_assets']=[capture_prefab(scene,'player','Robot pair',asset_id='robot_pair')]
    scene['variables'].update(destroyed=dict(type='int',value=0),loot=dict(type='int',value=0),
        dead_name=dict(type='string',value='None'),dead_active=dict(type='bool',value=False))
    scene['ui_assets'][0]['rml']=scene['ui_assets'][0]['rml'].replace('Entity lifecycle: Blockbench robot family','Before deletion: read data and drop loot').replace(
        'X: destroy last spawn / R: reset last prefab','X: destroy last spawn / A: add prefab attachment<br/>R: reset last prefab / P: apply its overrides').replace(
        'S/L: save/load the game<br/>','S/L: save/load the game<br/>Destroyed: <span id="destroyed">0</span> / Loot: <span id="loot">0</span><br/>Before removal: <span id="dead_name">None</span> / active: <span id="dead_active">false</span><br/>')
    b=GraphBuilder('Before deletion and loot'); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='Before deletion and loot'
    next(n for n in b.graph['nodes'] if n['id']=='storage')['values']['Game ID']=GAME
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def increment(source,name):
        end=action(source,'write_'+name,'Set Integer Variable',Name=name)
        b.add('get_'+name,'Get Integer Variable',Name=name); b.add('inc_'+name,'Integer Add',B=1)
        b.connect('get_'+name,'Value','inc_'+name,'A').connect('inc_'+name,'Value',end,'Value'); return end
    b.add('on_destroyed','On Object Destroyed')
    end=increment('on_destroyed','destroyed')
    end=action(end,'dead_name','Set String Variable',Name='dead_name'); b.add('read_dead_name','Get Entity Name')
    b.connect('on_destroyed','Entity','read_dead_name','Entity').connect('read_dead_name','Value',end,'Value')
    end=action(end,'dead_active','Set Boolean Variable',Name='dead_active'); b.connect('on_destroyed','Active',end,'Value')
    end=action(end,'drop_if','Branch'); b.add('has_loot','Has Entity Tag',Tag='loot_source')
    b.connect('on_destroyed','Entity','has_loot','Entity').connect('has_loot','Value',end,'Condition')
    end=action(end,'drop','Spawn Entity',port='True',Name='Dropped loot',Mesh='assets/robot.glb')
    b.add('drop_position','Get World Position'); b.connect('on_destroyed','Entity','drop_position','Entity').connect('drop_position','Value',end,'Position')
    end=action(end,'drop_scale','Set Scale',Value=[.25,.25,.25]); b.connect('drop','Entity',end,'Entity')
    end=action(end,'drop_tag','Add Entity Tag',Tag='loot'); b.connect('drop','Entity',end,'Entity')
    end=increment(end,'loot')
    # A repeated self-destroy is idempotent while this object is pending deletion.
    end=action(end,'self_destroy','Destroy Entity'); b.connect('on_destroyed','Entity',end,'Entity')
    for key in 'AP':
        b.add('input_'+key,'On Update'); b.add('pressed_'+key,'Is Key Pressed',Key=key)
        end=action('input_'+key,'if_'+key,'Branch'); b.connect('pressed_'+key,'Value',end,'Condition')
        end=action(end,'prefab_'+key,'Branch',port='True'); b.connect('is_prefab','Value',end,'Condition')
        if key=='P':
            end=action(end,'apply','Apply Prefab Overrides',port='True'); b.connect('last_spawn','Value',end,'Instance')
        else:
            end=action(end,'attach_spawn','Spawn Entity',port='True',Name='Temporary attachment',Mesh='assets/robot.glb',Position=[1,0,0])
            end=action(end,'attach_parent','Set Parent'); b.connect('attach_spawn','Entity',end,'Child').connect('last_spawn','Value',end,'Parent')
            end=action(end,'attach_scale','Set Scale',Value=[.3,.3,.3]); b.connect('attach_spawn','Entity',end,'Entity')
            end=action(end,'attach_tag','Add Entity Tag',Tag='loot_source'); b.connect('attach_spawn','Entity',end,'Entity')
    end='show_last_active'
    for name,type in [('destroyed','Integer'),('loot','Integer'),('dead_name','String'),('dead_active','Boolean')]:
        end=action(end,'show_'+name,'Set Widget Text',Element=name)
        if type in ('String','Boolean'): b.add('get_'+name,'Get '+type+' Variable',Name=name)
        source='get_'+name
        if type!='String':
            b.add('format_'+name,'Format '+type); b.connect(source,'Value','format_'+name,'Value'); source='format_'+name
        b.connect(source,'Value',end,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*280]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Before deletion and loot',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
