"""Playable Blockbench capsule character with authored prefab and game checkpoints."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.physics import default_body,default_character
from editor.core.prefabs import capture_prefab
from editor.core.registry import ROOT
from tools.create_physics_demo import create as create_base

GAME='node-engine-character-demo'


def create(directory=ROOT/'examples/character_demo'):
    directory=create_base(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    for e in scene['entities']:
        if e['id']=='player':
            e.update(name='Character',position=[0,2,0],rigid_body=dict(default_body(),
                shape='capsule',motion='kinematic',radius=.35,half_height=.5,mass=80.,character=default_character()))
        elif e['id']=='floor': e['rigid_body']=dict(default_body(),motion='static')
        elif e['id']=='robot_mesh': e['position']=[0,-.85,0]
    for eid,pos,scale in [('wall',[3,1.5,0],[.3,3,5]),('step',[-2,.1,0],[.7,.2,3]),
                          ('ceiling',[0,1.7,-3],[2,.2,2])]:
        scene['entities'].append(dict(id=eid,name=eid.title(),position=pos,rotation=[0,0,0],scale=scale,
            mesh='assets/floor.gltf',rigid_body=dict(default_body(),motion='static')))
    scene['prefab_assets']=[capture_prefab(scene,'player','Character robot',asset_id='character_robot')]
    scene['prefab_instances']=[dict(prefab='character_robot',root='player',mapping={'root':'player','e1':'robot_mesh'},
        owned_components={'root':['transform'],'e1':[]})]
    scene['ui_assets'][0]['rml']='''<rml><head><style>body {width:100%;height:100%;pointer-events:none;font-family:node-ui;font-size:16px;color:#ffffff;}
    #help {display:block;position:absolute;left:16px;top:16px;width:410px;padding:12px;background-color:#171e32ee;}
    #ground, #posture {display:block;}</style></head>
    <body><div id="help">Character playground<br/>W/A/D / arrows: move; Space: jump<br/>
    C: crouch; V: stand (needs clearance)<br/>R: reset; S: save; L: load<br/>
    Step on the left; wall on the right;<br/>crouch to pass below the roof ahead.
    <div id="ground">Ground: waiting</div><div id="posture">Posture: standing</div></div></body></rml>'''
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    removed={'ground','body','damping','reset_angular'}
    b.graph['nodes']=[n for n in b.graph['nodes'] if n['id'] not in removed]
    b.graph['links']=[l for l in b.graph['links'] if l['from'][0] not in removed and l['to'][0] not in removed]
    b.connect('start','Out','aim','In')
    for node in b.graph['nodes']:
        if node['id']=='force': node.update(type=b.registry.by_name('Character Move').id,values={})
        if node['id']=='strength': node['values']['Scale']=3
        if node['id']=='jump': node.update(type=b.registry.by_name('Character Jump').id,values={'Speed':5})
        if node['id']=='storage': node['values']['Game ID']=GAME
    for link in b.graph['links']:
        if link['to']==['force','Value']: link['to']=['force','Velocity']
    def action(source,nid,label,port='Out',**values):
        b.add(nid,label,**values); b.connect(source,port,nid,'In'); return nid
    for prefix,key,height,offset,scale,text in [('crouch','C',.2,-.55,1.1/1.7,'crouching'),('stand','V',.5,-.85,1.,'standing')]:
        b.add(prefix+'_event','On Update'); b.add(prefix+'_key','Is Key Pressed',Key=key)
        action(prefix+'_event',prefix+'_branch','Branch'); b.connect(prefix+'_key','Value',prefix+'_branch','Condition')
        last=action(prefix+'_branch',prefix,'Character Resize',port='True',Radius=.35,**{'Half Height':height})
        last=action(last,prefix+'_fits','Branch'); b.connect(prefix,'Resized',last,'Condition')
        last=action(last,prefix+'_mesh','Set Scale',port='True',Entity='robot_mesh',Value=[1,scale,1])
        last=action(last,prefix+'_offset','Set Position',Entity='robot_mesh',Value=[0,offset,0])
        action(last,prefix+'_hud','Set Widget Text',Element='posture',Text='Posture: '+text)
    b.add('status','On Update'); last=action('status','ground_check','Character Ground Check')
    last=action(last,'ground_hud','Set Widget Text',Element='ground')
    b.add('ground_text','Concat Strings',A='Ground: ')
    b.connect('ground_check','State','ground_text','B').connect('ground_text','Value','ground_hud','Text')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%7)*285,(i//7)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Character playground'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
