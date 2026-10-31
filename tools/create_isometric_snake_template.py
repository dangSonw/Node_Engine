"""Author the playable Snake template entirely with editable native graph nodes."""
import argparse
import base64
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.materials import default_parameters
from editor.core.project_format import nen_manifest
from editor.core.projects import compile_project,project_snapshot

SIZE=12
BODY=[[3,0.5,5],[2,0.5,5],[1,0.5,5],[0,0.5,5]]
TICK=.18
TYPES={'bool':'Boolean','int':'Integer','vec3':'Vector3','array<vec3>':'Vector3 Array',
       'array<entity>':'Entity Array','string':'String','float':''}
FUNCTIONS=[dict(id=1100100+i,name=n,pure=False,inputs=inputs,outputs=[],
               graph=dict(version=1,nodes=[],links=[])) for i,(n,inputs) in enumerate([
    ('Refresh board',[]),('Spawn food',[]),('End round',[dict(name='Reason',type='string')]),
    ('Reset round',[]),('Advance snake',[]),
    ('Request turn',[dict(name='Direction',type='vec3'),dict(name='Yaw',type='float')])])]


class Nodes:
    def __init__(self,function=None):
        self.b=GraphBuilder('Isometric Snake',functions=FUNCTIONS,function=function)
        self.serial=0
    def node(self,name,**values):
        self.serial+=1; nid='n'+str(self.serial);self.b.add(nid,name,**values);return nid
    def wire(self,a,port,b,input): self.b.connect(a,port,b,input)
    def expr(self,name,**values):
        literals={k:v for k,v in values.items() if not isinstance(v,tuple)}
        n=self.node(name,**literals)
        for key,value in values.items():
            if isinstance(value,tuple):self.wire(value[0],value[1],n,key)
        return n,'Value'
    def get(self,name,kind): return self.expr('Get '+(TYPES[kind]+' ' if kind!='float' else '')+'Variable',Name=name)
    def action(self,previous,name,port='Out',**values):
        literals={k:v for k,v in values.items() if not isinstance(v,tuple)}
        n=self.node(name,**literals);self.wire(previous,port,n,'In')
        for key,value in values.items():
            if isinstance(value,tuple):self.wire(value[0],value[1],n,key)
        return n
    def set(self,previous,name,kind,value,port='Out'):
        return self.action(previous,'Set '+(TYPES[kind]+' ' if kind!='float' else '')+'Variable',port,Name=name,Value=value)
    def branch(self,previous,condition,port='Out'):
        return self.action(previous,'Branch',port,Condition=condition)
    def finish(self,function):
        for i,n in enumerate(self.b.graph['nodes']):n['position']=[(i%6)*290,(i//6)*230]
        function['graph']=self.b.graph


def author():
    # Rendering is an ordinary reusable graph function: each pool entity has
    # independent active/position state, while the cube geometry stays shared.
    f=FUNCTIONS[0];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output')
    each=n.action(entry,'For Each Entity',Array=n.get('body_entities','array<entity>'))
    length=n.expr('Vector3 Array Length',Array=n.get('snake','array<vec3>'))
    condition=n.expr('Integer Less',A=(each,'Index'),B=length)
    active=n.action(each,'Set Entity Active','Body',Entity=(each,'Item'),Active=condition)
    choose=n.branch(active,condition)
    position=n.expr('Get Vector3 Item',Array=n.get('snake','array<vec3>'),Index=(each,'Index'))
    n.action(choose,'Set Position','True',Entity=(each,'Item'),Value=position)
    last=n.action(each,'Set Position','Done',Entity='food',Value=n.get('food','vec3'))
    for variable,label in [('score','score'),('best','best')]:
        last=n.action(last,'Set Widget Text',Element=label,Text=n.expr('Format Integer',Value=n.get(variable,'int')))
    last=n.action(last,'Set Widget Text',Element='status',Text=n.get('status','string'))
    n.wire(last,'Out',ret,'In');n.finish(f)

    # A randomized starting cell plus a bounded complete scan always finds a
    # free cell when one exists and never places food inside the snake.
    f=FUNCTIONS[1];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output')
    last=n.set(entry,'food_found','bool',False)
    random=n.action(last,'Random Integer',Minimum=0,Maximum=SIZE*SIZE-1)
    each=n.action(random,'For Each Integer',Array=list(range(SIZE*SIZE)))
    index=n.expr('Integer Modulo',A=n.expr('Integer Add',A=(each,'Item'),B=(random,'Value')),B=SIZE*SIZE)
    candidate=n.expr('Make Vector3',X=n.expr('Integer to Float',Value=n.expr('Integer Modulo',A=index,B=SIZE)),
                     Y=.5,Z=n.expr('Integer to Float',Value=n.expr('Integer Divide',A=index,B=SIZE)))
    occupied=n.expr('Vector3 Array Contains',Array=n.get('snake','array<vec3>'),Item=candidate)
    branch=n.branch(each,n.expr('NOT',Value=occupied),'Body')
    last=n.set(branch,'food','vec3',candidate,'True');last=n.set(last,'food_found','bool',True)
    n.action(last,'Break Loop')
    branch=n.branch(each,n.get('food_found','bool'),'Done')
    n.wire(branch,'True',ret,'In')
    won=n.action(branch,'End round','False',Reason='BOARD CLEARED!  R TO RESTART');n.wire(won,'Out',ret,'In');n.finish(f)

    f=FUNCTIONS[2];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output')
    last=n.set(entry,'alive','bool',False);last=n.set(last,'status','string',(entry,'Reason'))
    last=n.set(last,'death_reason','string',(entry,'Reason'))
    last=n.action(last,'Refresh board');n.wire(last,'Out',ret,'In');n.finish(f)

    f=FUNCTIONS[3];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output');last=entry
    for name,kind,value in [('snake','array<vec3>',BODY),('direction','vec3',[1,0,0]),('food','vec3',[6,.5,5]),
                            ('score','int',0),('steps','int',0),('alive','bool',True),('paused','bool',False),
                            ('turn_locked','bool',False),('status','string','RUNNING'),('death_reason','string','')]:last=n.set(last,name,kind,value)
    last=n.action(last,'Set Rotation',Entity='snake_head',Value=[0,0,0])
    last=n.action(last,'Set Random Seed',Seed=20261030)
    last=n.action(last,'Start Timer',Name='snake-tick',Seconds=TICK,Repeat=True)
    last=n.action(last,'Refresh board');n.wire(last,'Out',ret,'In');n.finish(f)

    f=FUNCTIONS[4];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output')
    can_move=n.expr('AND',A=n.get('alive','bool'),B=n.expr('NOT',Value=n.get('paused','bool')))
    check=n.branch(entry,can_move);n.wire(check,'False',ret,'In')
    last=n.set(check,'turn_locked','bool',False,'True')
    last=n.set(last,'steps','int',n.expr('Integer Add',A=n.get('steps','int'),B=1))
    head=n.expr('Get Vector3 Item',Array=n.get('snake','array<vec3>'),Index=0)
    last=n.set(last,'next_head','vec3',n.expr('Vector Add',A=head,B=n.get('direction','vec3')))
    next_head=n.get('next_head','vec3')
    within=n.expr('Point In Bounds',Point=next_head,Min=[0,0,0],Max=[SIZE-1,1,SIZE-1])
    wall=n.branch(last,within)
    dead=n.action(wall,'End round','False',Reason='WALL HIT  /  R TO RESTART');n.wire(dead,'Out',ret,'In')
    ate=n.expr('Less',A=n.expr('Distance',A=next_head,B=n.get('food','vec3')),B=.1)
    last=n.set(wall,'ate','bool',ate,'True')
    keep=n.expr('Integer Subtract',A=n.expr('Vector3 Array Length',Array=n.get('snake','array<vec3>')),
                B=n.expr('Select Integer',Condition=n.get('ate','bool'),**{'True':0,'False':1}))
    last=n.set(last,'trimmed','array<vec3>',n.expr('Slice Vector3 Array',Array=n.get('snake','array<vec3>'),Start=0,End=keep))
    collision=n.expr('Vector3 Array Contains',Array=n.get('trimmed','array<vec3>'),Item=next_head)
    body_check=n.branch(last,collision)
    dead=n.action(body_check,'End round','True',Reason='SELF COLLISION  /  R TO RESTART');n.wire(dead,'Out',ret,'In')
    last=n.set(body_check,'snake','array<vec3>',n.expr('Insert Vector3 Item',Array=n.get('trimmed','array<vec3>'),Index=0,Item=next_head),'False')
    ate_check=n.branch(last,n.get('ate','bool'))
    last=n.set(ate_check,'score','int',n.expr('Integer Add',A=n.get('score','int'),B=1),'True')
    last=n.set(last,'best','int',n.expr('Integer Max',A=n.get('score','int'),B=n.get('best','int')))
    last=n.action(last,'Spawn food');last=n.action(last,'Refresh board');n.wire(last,'Out',ret,'In')
    last=n.action(ate_check,'Refresh board','False');n.wire(last,'Out',ret,'In');n.finish(f)

    f=FUNCTIONS[5];n=Nodes(f['id']);entry=n.node('Function Input');ret=n.node('Function Output')
    ready=n.expr('AND',A=n.get('alive','bool'),B=n.expr('NOT',Value=n.get('paused','bool')))
    ready=n.expr('AND',A=ready,B=n.expr('NOT',Value=n.get('turn_locked','bool')))
    allowed=n.expr('Greater',A=n.expr('Dot Product',A=n.get('direction','vec3'),B=(entry,'Direction')),B=-.5)
    choice=n.branch(entry,n.expr('AND',A=ready,B=allowed));n.wire(choice,'False',ret,'In')
    last=n.set(choice,'direction','vec3',(entry,'Direction'),'True');last=n.set(last,'turn_locked','bool',True)
    last=n.action(last,'Set Rotation',Entity='snake_head',Value=n.expr('Make Vector3',Y=(entry,'Yaw')))
    n.wire(last,'Out',ret,'In');n.finish(f)

    n=Nodes();start=n.node('On Game Start');last=n.action(start,'Create Widget');last=n.action(last,'Camera Look At',Target=[5.5,0,5.5])
    n.action(last,'Reset round')
    timer=n.node('On Timer Finished',Filter='snake-tick');n.action(timer,'Advance snake')
    for keys,direction,yaw in [('RightD',[1,0,0],0),('LeftA',[-1,0,0],180),('UpW',[0,0,-1],90),('DownS',[0,0,1],-90)]:
        key_names={'RightD':['Right','D'],'LeftA':['Left','A'],'UpW':['Up','W'],'DownS':['Down','S']}[keys]
        for key in key_names:
            event=n.node('On Key Pressed',Filter=key);n.action(event,'Request turn',Direction=direction,Yaw=yaw)
    restart=n.node('On Key Pressed',Filter='R')
    last=n.set(restart,'restart_count','int',n.expr('Integer Add',A=n.get('restart_count','int'),B=1))
    n.action(last,'Reset round')
    pause=n.node('On Key Pressed',Filter='P');guard=n.branch(pause,n.get('alive','bool'))
    last=n.set(guard,'paused','bool',n.expr('NOT',Value=n.get('paused','bool')),'True')
    last=n.set(last,'status','string',n.expr('Select String',Condition=n.get('paused','bool'),**{'True':'PAUSED  /  P TO RESUME','False':'RUNNING'}))
    n.action(last,'Refresh board')
    for i,node in enumerate(n.b.graph['nodes']):node['position']=[(i%5)*310,(i//5)*250]
    return n.b.graph


def cube_asset(path):
    vertices=[];normals=[];indices=[]
    for normal,quad in [([1,0,0],[(.5,-.5,-.5),(.5,.5,-.5),(.5,.5,.5),(.5,-.5,.5)]),
      ([-1,0,0],[(-.5,-.5,.5),(-.5,.5,.5),(-.5,.5,-.5),(-.5,-.5,-.5)]),
      ([0,1,0],[(-.5,.5,-.5),(-.5,.5,.5),(.5,.5,.5),(.5,.5,-.5)]),
      ([0,-1,0],[(-.5,-.5,.5),(-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5)]),
      ([0,0,1],[(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5),(-.5,-.5,.5)]),
      ([0,0,-1],[(-.5,-.5,-.5),(-.5,.5,-.5),(.5,.5,-.5),(.5,-.5,-.5)])]:
        first=len(vertices);vertices.extend(quad);normals.extend([normal]*4);indices.extend([first,first+1,first+2,first,first+2,first+3])
    raw=b''.join(struct.pack('<3f',*v) for v in vertices+normals)+struct.pack('<36H',*indices)
    save_json(path,dict(asset=dict(version='2.0',generator='Node_Engine snake template'),scene=0,scenes=[dict(nodes=[0])],
        nodes=[dict(mesh=0)],buffers=[dict(byteLength=len(raw),uri='data:application/octet-stream;base64,'+base64.b64encode(raw).decode())],
        bufferViews=[dict(buffer=0,byteOffset=0,byteLength=288),dict(buffer=0,byteOffset=288,byteLength=288),dict(buffer=0,byteOffset=576,byteLength=72)],
        accessors=[dict(bufferView=0,componentType=5126,count=24,type='VEC3',min=[-.5]*3,max=[.5]*3),
                   dict(bufferView=1,componentType=5126,count=24,type='VEC3'),dict(bufferView=2,componentType=5123,count=36,type='SCALAR')],
        meshes=[dict(primitives=[dict(attributes=dict(POSITION=0,NORMAL=1),indices=2,material=0)])],
        materials=[dict(pbrMetallicRoughness=dict(baseColorFactor=[1,1,1,1],metallicFactor=.05,roughnessFactor=.7))]))


def create(root=ROOT/'templates/games/isometric_snake_3d'):
    root=Path(root);(root/'assets').mkdir(parents=True,exist_ok=True)
    (root/'game.py').unlink(missing_ok=True)  # Superseded standalone Python simulation.
    cube_asset(root/'assets/cube.gltf')
    colors={'head':[.1,.95,.52],'body':[.07,.6,.48],'food':[1,.22,.16],
            'tile_a':[.1,.18,.25],'tile_b':[.13,.23,.3],'rim':[.05,.09,.15],'eye':[.01,.02,.025]}
    materials=[dict(version=1,type='material',id=k,name=k.title(),**dict(default_parameters(),color=v)) for k,v in colors.items()]
    def entity(id,position,scale,material,**extra):
        return dict(id=id,name=id.replace('_',' ').title(),position=position,rotation=[0,0,0],scale=scale,
                    mesh='assets/cube.gltf',material=dict(asset=material,overrides={}),**extra)
    entities=[entity('snake_head',BODY[0],[.84,.65,.84],'head')]
    pool=['snake_head']+[f'segment_{i}' for i in range(1,SIZE*SIZE)]
    for i,id in enumerate(pool[1:],1):entities.append(entity(id,BODY[i] if i<len(BODY) else [0,-5,0],[.8,.58,.8],'body',active=i<len(BODY)))
    entities.extend([entity('eye_left',[.51,.22,-.23],[.06,.17,.16],'eye',parent='snake_head'),
                     entity('eye_right',[.51,.22,.23],[.06,.17,.16],'eye',parent='snake_head'),
                     entity('food',[6,.5,5],[.58,.65,.58],'food')])
    for z in range(SIZE):
        for x in range(SIZE):entities.append(entity(f'tile_{x}_{z}',[x,-.08,z],[.98,.2,.98],'tile_a' if (x+z)%2==0 else 'tile_b'))
    for id,pos,scale in [('north',[5.5,.1,-.65],[12.8,.6,.3]),('south',[5.5,.1,11.65],[12.8,.6,.3]),
                         ('west',[-.65,.1,5.5],[.3,.6,12.8]),('east',[11.65,.1,5.5],[.3,.6,12.8])]:entities.append(entity(id,pos,scale,'rim'))
    entities.append(dict(id='camera',name='Isometric camera',position=[18,20,20],rotation=[0,0,0],scale=[1,1,1],
                         camera=dict(projection='orthographic',size=18,near=.1,far=1000,fov=60)))
    variables={k:dict(type=t,value=v) for k,t,v in [
        ('snake','array<vec3>',BODY),('trimmed','array<vec3>',[]),('direction','vec3',[1,0,0]),
        ('food','vec3',[6,.5,5]),('next_head','vec3',[3,.5,5]),('score','int',0),('best','int',0),('steps','int',0),
        ('alive','bool',True),('paused','bool',False),('turn_locked','bool',False),('ate','bool',False),
        ('food_found','bool',False),('body_entities','array<entity>',pool),('status','string','RUNNING'),
        ('restart_count','int',0),('death_reason','string','')]}
    rml='''<rml><head><title>Isometric Snake</title><style>
body{width:100%;height:100%;font-family:node-ui;color:#e8f8ff;pointer-events:none;font-size:17px;}
#title{position:absolute;left:24px;top:20px;font-size:27px;color:#60efbd;}
#sub{position:absolute;left:26px;top:59px;font-size:13px;color:#9bb5c8;}
#points{position:absolute;right:24px;top:20px;padding:14px 20px;background-color:#142536e8;border-radius:10px;}
#state{position:absolute;left:24px;top:89px;color:#f1cf81;font-size:15px;}
#help{position:absolute;left:24px;bottom:22px;right:24px;background-color:#142536ed;padding:12px 16px;border-radius:8px;font-size:14px;}
@media (max-width:600px){
#title{left:16px;top:16px;font-size:23px;}
#sub{display:none;}
#points{left:16px;right:auto;top:54px;padding:8px 12px;font-size:14px;}
#state{left:16px;top:99px;right:12px;font-size:13px;}
#help{left:12px;right:12px;bottom:12px;padding:10px 12px;font-size:12px;}
}
@media (max-width:400px){
#title{left:12px;top:12px;font-size:20px;}
#points{left:12px;top:46px;padding:7px 10px;font-size:13px;}
#state{left:12px;top:87px;font-size:12px;}
#help{left:8px;right:8px;bottom:8px;padding:8px 10px;font-size:11px;}
}
</style></head><body><div id="title">ISOMETRIC SNAKE</div><div id="sub">A native node graph game</div>
<div id="points">SCORE <span id="score">0</span>   /   BEST <span id="best">0</span></div>
<div id="state"><span id="status">RUNNING</span></div>
<div id="help">WASD / ARROWS: turn &nbsp; | &nbsp; P: pause &nbsp; | &nbsp; R: restart<br/>Eat coral cubes. Avoid the rim and your own body. One turn per tick.</div></body></rml>'''
    scene=dict(version=1,entities=entities,variables=variables,active_camera='camera',material_assets=materials,
               ui_assets=[dict(version=1,type='ui',id='hud',name='Snake HUD',rml=rml)],
               features={'3d':{'pbr':{'metallic':.05,'roughness':.7},'lights':[{'kind':'directional','intensity':1.1,'color':[.93,.97,1]}]}})
    graph=author();compiled=compile_graph(graph,scene)
    save_json(root/'graphs/gameplay.json',graph);save_json(root/'scenes/main.json',scene)
    manifest_path=root/'isometric_snake_3d.nen'
    old=json.loads(manifest_path.read_text('utf-8')) if manifest_path.exists() else {}
    manifest=nen_manifest(dict(version=2,name='Isometric Snake 3D',entry_scene='main',
        scenes=[dict(id='main',name='Snake arena',graph='graphs/gameplay.json',scene='scenes/main.json')],assets=['assets/cube.gltf']))
    if old.get('project_id'):manifest['project_id']=old['project_id']
    save_json(manifest_path,manifest);export(compile_project(project_snapshot(manifest_path)),root/'generated')
    scenarios=[dict(id='start',frames=1,replay=[],expect={'score':0,'alive':True,'steps':0}),
      dict(id='eat',frames=34,replay=[],expect={'score':1,'alive':True}),
      dict(id='wall',frames=110,replay=[],expect={'score':1,'alive':False,'status':'WALL HIT  /  R TO RESTART'}),
      dict(id='restart',frames=112,replay=[dict(frame=110,button='R',down=True),dict(frame=111,button='R',down=False)],
           expect={'score':0,'alive':True,'steps':0,'best':1}),
      dict(id='reverse_rejected',frames=12,replay=[dict(frame=1,button='Left',down=True),dict(frame=2,button='Left',down=False)],
           expect={'alive':True,'direction':[1,0,0],'steps':1}),
      dict(id='pause',frames=90,replay=[dict(frame=1,button='P',down=True),dict(frame=2,button='P',down=False)],
           expect={'paused':True,'steps':0,'score':0,'alive':True}),
      dict(id='self_collision',frames=70,replay=[dict(frame=f,button=k,down=d) for f,k,d in [
          (34,'Down',True),(35,'Down',False),(45,'Left',True),(46,'Left',False),(56,'Up',True),(57,'Up',False)]],
           expect={'score':1,'alive':False,'status':'SELF COLLISION  /  R TO RESTART'})]
    tags={'eat':['scoring','growth'],'wall':['wall_collision'],'self_collision':['self_collision'],'restart':['restart']}
    for s in scenarios:
        trace=s.pop('replay');s['replay']='replays/'+s['id']+'.json'
        save_json(root/s['replay'],dict(version=1,events=trace))
        s['covers']=tags.get(s['id'],[])
        s['assertions']=[dict(path='variables.'+k,op='eq',value=v) for k,v in s.pop('expect').items()]
        if s['id']=='eat':s['assertions'].append(dict(path='variables.snake',op='len_eq',value=5))
        if s['id'] in ('eat','restart'):
            s['before_frames']=22 if s['id']=='eat' else 109
            s['before_assertions']=[dict(path='variables.score',op='eq',value=0 if s['id']=='eat' else 1),
                                    dict(path='variables.alive',op='eq',value=s['id']=='eat')]
    save_json(root/'acceptance.json',dict(version=1,controls='WASD / arrows: turn; P: pause; R: restart',
        state_paths=dict(resets='variables.restart_count'),tick_seconds=TICK,scenarios=scenarios))
    (root/'README.md').write_text('''# Isometric Snake 3D

Open `isometric_snake_3d.nen` in Node_Engine, then Play. Click the game window.
Use WASD or arrows, P to pause/resume, R to restart. Eat coral cubes, avoid the
rim and your body. The initial food is three cells ahead. Best score survives
round restarts during the current session. The game starts immediately.

Every gameplay rule is an editable native graph. Reusable functions in the
graph contain board refresh, bounded food placement, reset, tick, death and
turn validation. The board is 12 by 12 with a 0.18 second native repeating timer.
The 144 body entities share one project-local cube glTF mesh. Inactive pool
entities are activated as the snake grows; no hidden Python gameplay is used.

`acceptance.json` and `replays/*.json` describe native test scenarios. Regenerate
with `tools/create_isometric_snake_template.py --output DIRECTORY`. This writes
only this template's known files and preserves its project UUID.
''',encoding='utf-8')
    from editor.core.game_guides import write_game_guide
    write_game_guide(root, 'snake')
    return root


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'templates/games/isometric_snake_3d')
    print(create(parser.parse_args().output))
