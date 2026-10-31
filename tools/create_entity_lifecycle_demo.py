"""Editable Blockbench robot playground for entity creation and inherited activity."""
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.prefabs import capture_prefab
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-entity-lifecycle-demo'
SLOT='entities'


def create(directory=ROOT/'examples/entity_lifecycle_demo'):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/animation_demo/assets/robot.glb',directory/'assets/robot.glb')
    previous=json.loads((ROOT/'examples/switch_select_demo/scenes/main.json').read_text('utf-8'))
    camera=next(e for e in previous['entities'] if e['id']=='camera')
    scene=dict(version=1,active_camera='camera',entities=[
        dict(id='group',name='Toggle this parent'),
        dict(id='player',name='Robot',parent='group',mesh='assets/robot.glb'),
        dict(id='child',name='Child robot',parent='player',mesh='assets/robot.glb',position=[0,1.5,0],scale=[.35,.35,.35]),camera],variables={})
    for item in scene['entities']:
        for key,value in [('position',[0,0,0]),('rotation',[0,0,0]),('scale',[1,1,1])]: item.setdefault(key,value)
    scene['prefab_assets']=[capture_prefab(scene,'player','Robot pair',asset_id='robot_pair')]
    scene['variables']={k:dict(type='int',value=0) for k in ('created','enabled','disabled','owned_disabled')}
    scene['variables'].update(last_entity=dict(type='entity',value=''),last_active=dict(type='bool',value=False),
                              last_event=dict(type='string',value='None'),spawned=dict(type='entity',value=''))
    markup='''<rml><head><style>body {width:100%;height:100%;font-family:node-ui;font-size:14px;color:#ffffff;pointer-events:none;}
    #help {position:absolute;left:8px;top:8px;padding:8px;width:94%;max-width:480px;box-sizing:border-box;background-color:#171e32dd;}</style></head>
    <body><div id="help">Entity lifecycle: Blockbench robot family<br/>
    T: toggle parent / N: spawn prefab / C: clone robot<br/>X: destroy last spawn / R: reset last prefab<br/>S/L: save/load the game<br/>
    Created: <span id="created">0</span> / Enabled: <span id="enabled">0</span> / Disabled: <span id="disabled">0</span><br/>
    Robot disabled callbacks: <span id="owned_disabled">0</span><br/>
    Last: <span id="last_event">None</span> / <span id="last_entity"></span> / Active: <span id="last_active">false</span></div></body></rml>'''
    scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
    b=GraphBuilder('Entity lifecycle robot family')
    def action(source,nid,name,port='Out',**values):
        b.add(nid,name,**values); b.connect(source,port,nid,'In'); return nid
    def increment(source,name):
        end=action(source,'write_'+name,'Set Integer Variable',Name=name)
        b.add('get_'+name,'Get Integer Variable',Name=name); b.add('add_'+name,'Integer Add',B=1)
        b.connect('get_'+name,'Value','add_'+name,'A').connect('add_'+name,'Value',end,'Value'); return end
    for kind in ('Created','Enabled','Disabled'):
        name=kind.lower(); b.add('on_'+name,'On Object '+kind)
        end=increment('on_'+name,name)
        end=action(end,'event_'+name,'Set String Variable',Name='last_event',Value=kind)
        end=action(end,'entity_'+name,'Set Entity Variable',Name='last_entity'); b.connect('on_'+name,'Entity',end,'Value')
        end=action(end,'active_'+name,'Set Boolean Variable',Name='last_active'); b.connect('on_'+name,'Active',end,'Value')
    b.add('own','On Object Disabled',Receiver='player'); increment('own','owned_disabled')
    b.add('start','On Game Start'); end=action('start','storage','Open Save Storage',**{'Game ID':GAME})
    end=action(end,'hud','Create Widget'); action(end,'animation','Play Animation',Clip='Idle')
    b.add('last_spawn','Get Entity Variable',Name='spawned')
    for key in 'TNCX RSL'.replace(' ',''):
        b.add('input_'+key,'On Update'); b.add('pressed_'+key,'Is Key Pressed',Key=key)
        branch=action('input_'+key,'if_'+key,'Branch'); b.connect('pressed_'+key,'Value',branch,'Condition')
        if key=='T':
            end=action(branch,'toggle','Set Entity Active',port='True',Entity='group')
            b.add('group_active','Get Entity Active Self',Entity='group'); b.add('opposite','NOT')
            b.connect('group_active','Value','opposite','Value').connect('opposite','Value',end,'Active')
        elif key in 'NC':
            if key=='N': end=action(branch,'spawn','Instantiate Prefab',port='True',Prefab='robot_pair',Position=[2,0,0])
            else:
                end=action(branch,'clone','Clone Entity',port='True',Name='Clone')
                end=action(end,'clone_place','Set Position',Value=[-2,0,0]); b.connect('clone','Entity',end,'Entity')
            saved=action(end,'last_'+key,'Set Entity Variable',Name='spawned')
            b.connect('spawn' if key=='N' else 'clone','Entity',saved,'Value')
        elif key=='X':
            end=action(branch,'destroy','Destroy Entity',port='True'); b.connect('last_spawn','Value',end,'Entity')
        elif key=='R':
            check=action(branch,'check_prefab','Branch',port='True'); b.add('is_prefab','Is Prefab Instance')
            b.connect('last_spawn','Value','is_prefab','Entity').connect('is_prefab','Value',check,'Condition')
            end=action(check,'reset','Reset Prefab Instance',port='True'); b.connect('last_spawn','Value',end,'Instance')
        else: action(branch,'save' if key=='S' else 'load','Save Game' if key=='S' else 'Load Game',port='True',Slot=SLOT)
    b.add('late','On Late Update'); end='late'
    for name in ('created','enabled','disabled','owned_disabled','last_event','last_entity','last_active'):
        end=action(end,'show_'+name,'Set Widget Text',Element=name)
        if name in ('created','enabled','disabled','owned_disabled'):
            b.add('format_'+name,'Format Integer'); b.connect('get_'+name,'Value','format_'+name,'Value'); source='format_'+name
        else:
            type={'last_event':'String','last_entity':'Entity','last_active':'Boolean'}[name]
            b.add('get_'+name,'Get '+type+' Variable',Name=name); source='get_'+name
            if type!='String':
                b.add('format_'+name,'Entity ID' if type=='Entity' else 'Format Boolean')
                b.connect(source,'Value','format_'+name,'Entity' if type=='Entity' else 'Value'); source='format_'+name
        b.connect(source,'Value',end,'Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[i%6*280,i//6*280]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Entity lifecycle robot family',scene='scenes/main.json',graph='graphs/gameplay.json'))
    export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
