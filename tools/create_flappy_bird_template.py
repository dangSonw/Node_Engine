"""Author a complete Flappy Bird using editable native gameplay graphs."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.functions import new_function
from editor.core.project_format import nen_manifest
from editor.core.ui import new_asset
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QColor,QImage,QPainter,QPen


class Author:
    def __init__(self,builder): self.b=builder;self.i=0;self.tail=('entry','Out')
    def node(self,label,**args):
        self.i+=1;n='n'+str(self.i)
        self.b.add(n,label,**{k:v for k,v in args.items() if not isinstance(v,tuple)})
        for k,v in args.items():
            if isinstance(v,tuple):self.b.connect(v[0],v[1],n,k)
        return n
    def expr(self,label,**args):return (self.node(label,**args),'Value')
    def act(self,label,**args):
        n=self.node(label,**args);self.b.connect(*self.tail,n,'In');self.tail=(n,'Out');return n
    def get(self,name,kind=''):
        return self.expr('Get '+(kind+' ' if kind else '')+'Variable',Name=name)
    def set(self,name,value,kind=''):
        return self.act('Set '+(kind+' ' if kind else '')+'Variable',Name=name,Value=value)
    def end(self):self.b.connect(*self.tail,'return','In')
    def finish(self):
        for i,n in enumerate(self.b.graph['nodes']):
            n.setdefault('position',[(i//8)*360,(i%8)*180])
        return self.b.graph


HUD='''<rml><head><title>Flappy Bird</title><style>
body { width: 100%; height: 100%; margin: 0px; font-family: node-ui; color: #f9ffff; font-size: 19px; }
div { display: block; }
#title { position: absolute; width: 320px; left: 28px; top: 20px; color: #103d58; font-size: 28px; }
#score { position: absolute; width: 320px; left: 30px; top: 64px; color: #103d58; font-size: 25px; }
#best { position: absolute; width: 180px; right: 30px; top: 26px; color: #103d58; text-align: right; }
#status { position: absolute; left: 25%; top: 37%; width: 50%; text-align: center;
 padding: 15px; background-color: #12394cdd; border-radius: 12px; font-size: 23px; }
#help { position: absolute; bottom: 18px; left: 25%; width: 50%; text-align: center;
 padding: 8px; background-color: #113d50d8; border-radius: 8px; font-size: 16px; }
</style></head><body><div id="title">FLAPPY BIRD</div><div id="score">SCORE 0</div>
<div id="best">BEST 0</div><div id="status">SPACE / CLICK to fly</div>
<div id="help">SPACE / CLICK: flap | P: pause | R: restart</div></body></rml>'''


def graphs():
    functions=[]
    def begin(name,fid,inputs=()):
        f=new_function(name,inputs=inputs,definitions=functions);f['id']=fid
        b=GraphBuilder(functions=functions+[f],function=fid)
        b.add('entry','Function Input');b.add('return','Function Output')
        return f,Author(b)
    def done(f,a):f['graph']=a.finish();functions.append(f)

    f,a=begin('Refresh HUD',1000100)
    for variable,prefix in [('score','SCORE '),('best','BEST ')]:
        text=a.expr('Concat Strings',A=prefix,B=a.expr('Format Integer',Value=a.get(variable,'Integer')))
        a.act('Set Widget Text',Element=variable,Text=text)
    dead=a.expr('NOT',Value=a.get('alive','Boolean'))
    pause=a.expr('Select String',Condition=a.get('paused','Boolean'),**{'True':'PAUSED - P to resume','False':''})
    ready=a.expr('Select String',Condition=a.get('started','Boolean'),**{'True':pause,'False':'SPACE / CLICK to fly'})
    status=a.expr('Select String',Condition=dead,**{'True':'GAME OVER - R to restart','False':ready})
    a.act('Set Widget Text',Element='status',Text=status)
    visible=a.expr('Select String',Condition=a.expr('String Equal',A=status,B=''),**{'True':'none','False':'block'})
    a.act('Set Widget Style',Element='status',Property='display',Value=visible);a.end();done(f,a)

    f,a=begin('Game Over',1000101,[dict(name='Reason',type='string',default='boundary')])
    a.set('alive',False,'Boolean');a.set('velocity',0.)
    a.set('death_reason',('entry','Reason'),'String')
    a.set('best',a.expr('Integer Max',A=a.get('best','Integer'),B=a.get('score','Integer')),'Integer')
    a.act('Refresh HUD');a.end();done(f,a)

    f,a=begin('Reset Round',1000102)
    a.act('Set Random Seed',Seed=42017)
    for name,value,kind in [('score',0,'Integer'),('bird_y',0.,''),('velocity',0.,''),
                            ('alive',True,'Boolean'),('started',False,'Boolean'),('paused',False,'Boolean')]:a.set(name,value,kind)
    a.set('death_reason','','String');a.set('steps',0,'Integer')
    a.act('Set Position',Entity='bird',Value=[-2.,0.,.1]);a.act('Set Sprite State',Entity='bird',State='idle')
    for i in range(3):
        a.set(f'pipe_{i}_x',4.+i*4.);a.set(f'pipe_{i}_gap',0.);a.set(f'pipe_{i}_passed',False,'Boolean')
        for side,offset in [('top',5.),('bottom',-5.)]:
            a.act('Set Position',Entity=f'pipe_{i}_{side}',Value=[4.+i*4.,offset,0.])
    a.act('Refresh HUD');a.end();done(f,a)

    f,a=begin('Flap',1000103)
    allowed=a.expr('AND',A=a.get('alive','Boolean'),B=a.expr('NOT',Value=a.get('paused','Boolean')))
    branch=a.node('Branch',Condition=allowed);a.b.connect('entry','Out',branch,'In');a.b.connect(branch,'False','return','In')
    a.tail=(branch,'True');a.set('started',True,'Boolean');a.set('velocity',5.5)
    a.act('Set Sprite State',Entity='bird',State='flap');a.act('Refresh HUD');a.end();done(f,a)

    for i in range(3):
        f,a=begin(f'Advance Pipe {i+1}',1000110+i)
        x=f'pipe_{i}_x';gap=f'pipe_{i}_gap';passed=f'pipe_{i}_passed'
        a.set(x,a.expr('Subtract',A=a.get(x),B=a.expr('Multiply',A=2.6,B=a.expr('Get Delta Time'))))
        branch=a.node('Branch',Condition=a.expr('Less',A=a.get(x),B=-8.))
        a.b.connect(*a.tail,branch,'In');a.tail=(branch,'True')
        a.set(x,a.expr('Add',A=a.get(x),B=12.))
        random=a.act('Random Float',Minimum=-1.35,Maximum=1.35);a.set(gap,(random,'Value'));a.set(passed,False,'Boolean')
        join=a.node('Sequence');a.b.connect(*a.tail,join,'In');a.b.connect(branch,'False',join,'In')
        a.tail=(join,'First')
        crossed=a.expr('AND',A=a.expr('Less',A=a.get(x),B=-2.6),B=a.expr('NOT',Value=a.get(passed,'Boolean')))
        score=a.node('Branch',Condition=crossed);a.b.connect(*a.tail,score,'In');a.tail=(score,'True')
        a.set('score',a.expr('Integer Add',A=a.get('score','Integer'),B=1),'Integer');a.set(passed,True,'Boolean')
        a.set('best',a.expr('Integer Max',A=a.get('best','Integer'),B=a.get('score','Integer')),'Integer')
        a.tail=(join,'Then')
        for side,offset in [('top',5.),('bottom',-5.)]:
            pos=a.expr('Make Vector3',X=a.get(x),Y=a.expr('Add',A=a.get(gap),B=offset))
            a.act('Set Position',Entity=f'pipe_{i}_{side}',Value=pos)
        overlap=a.expr('Less',A=a.expr('Abs',Value=a.expr('Add',A=a.get(x),B=2.)),B=.825)
        outside=a.expr('Greater',A=a.expr('Abs',Value=a.expr('Subtract',A=a.get('bird_y'),B=a.get(gap))),B=1.175)
        collision=a.node('Branch',Condition=a.expr('AND',A=overlap,B=outside))
        a.b.connect(*a.tail,collision,'In');a.tail=(collision,'True');a.act('Game Over',Reason='pipe');a.end()
        a.b.connect(collision,'False','return','In');done(f,a)

    f,a=begin('Simulate Bird',1000120)
    a.set('steps',a.expr('Integer Add',A=a.get('steps','Integer'),B=1),'Integer')
    a.set('velocity',a.expr('Subtract',A=a.get('velocity'),B=a.expr('Multiply',A=15.,B=a.expr('Get Delta Time'))))
    a.set('bird_y',a.expr('Add',A=a.get('bird_y'),B=a.expr('Multiply',A=a.get('velocity'),B=a.expr('Get Delta Time'))))
    a.act('Set Position',Entity='bird',Value=a.expr('Make Vector3',X=-2.,Y=a.get('bird_y'),Z=.1))
    for i in range(3):a.act(f'Advance Pipe {i+1}')
    boundary=a.expr('OR',A=a.expr('Less',A=a.get('bird_y'),B=-3.175),B=a.expr('Greater',A=a.get('bird_y'),B=3.925))
    branch=a.node('Branch',Condition=boundary)
    a.b.connect(*a.tail,branch,'In');a.tail=(branch,'True')
    reason=a.expr('Select String',Condition=a.expr('Less',A=a.get('bird_y'),B=0.),**{'True':'ground','False':'ceiling'})
    a.act('Game Over',Reason=reason);a.end()
    a.b.connect(branch,'False','return','In');done(f,a)

    b=GraphBuilder('Flappy Bird - native editable gameplay',functions=functions);a=Author(b)
    b.add('start','On Game Start');a.tail=('start','Out');a.act('Create Widget',Template='hud',Widget='hud');a.act('Reset Round')
    b.add('space','On Key Pressed',Filter='Space');a.tail=('space','Out');a.act('Flap')
    b.add('click','On Mouse Button',Filter='MouseLeft')
    down=a.node('Branch',Condition=('click','Down'));b.connect('click','Out',down,'In');a.tail=(down,'True');a.act('Flap')
    b.add('restart','On Key Pressed',Filter='R');a.tail=('restart','Out')
    a.set('restart_count',a.expr('Integer Add',A=a.get('restart_count','Integer'),B=1),'Integer');a.act('Reset Round')
    b.add('pause','On Key Pressed',Filter='P');a.tail=('pause','Out');a.set('paused',a.expr('NOT',Value=a.get('paused','Boolean')),'Boolean')
    a.act('Refresh HUD')
    b.add('update','On Update');a.tail=('update','Out')
    ready=a.expr('AND',A=a.get('started','Boolean'),B=a.get('alive','Boolean'))
    ready=a.expr('AND',A=ready,B=a.expr('NOT',Value=a.get('paused','Boolean')))
    branch=a.node('Branch',Condition=ready);a.b.connect(*a.tail,branch,'In');a.tail=(branch,'True')
    a.act('Simulate Bird');a.act('Refresh HUD')
    return a.finish()


def artwork(root):
    def painter(name,w,h):
        image=QImage(w,h,QImage.Format.Format_RGBA8888);image.fill(Qt.GlobalColor.transparent)
        return image,QPainter(image),root/'assets'/name
    image,p,path=painter('bird.png',128,64)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i in range(2):
        x=i*64;p.setPen(QPen(QColor('#9a6615'),3));p.setBrush(QColor('#ffdc48'));p.drawEllipse(QRectF(x+8,12,44,39))
        p.setBrush(QColor('#fff4a1'));p.drawEllipse(QRectF(x+8,27 if i else 18,24,20))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#ffffff'));p.drawEllipse(QRectF(x+36,16,15,18))
        p.setBrush(QColor('#18384a'));p.drawEllipse(QRectF(x+44,20,5,8));p.setBrush(QColor('#ee7842'));p.drawRect(x+47,31,16,9)
    p.end();assert image.save(str(path))
    image,p,path=painter('pipe.png',64,256);p.fillRect(8,0,48,256,QColor('#42ad61'));p.fillRect(12,0,9,256,QColor('#8edb77'))
    p.fillRect(49,0,7,256,QColor('#237f54'));p.fillRect(0,0,64,20,QColor('#277f51'));p.fillRect(4,3,56,13,QColor('#70ce70'))
    p.fillRect(0,236,64,20,QColor('#277f51'));p.fillRect(4,240,56,13,QColor('#70ce70'))
    p.end();assert image.save(str(path))
    image,p,path=painter('sky.png',320,180);image.fill(QColor('#8bd6e4'))
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#e9f8ee'))
    for x,y in [(30,55),(150,38),(260,70)]:
        p.drawEllipse(x,y,65,17);p.drawEllipse(x+14,y-12,29,30)
    p.fillRect(0,155,320,25,QColor('#75b798'));p.fillRect(0,170,320,10,QColor('#4b9f84'));p.end();assert image.save(str(path))
    image,p,path=painter('ground.png',128,32);image.fill(QColor('#dfc88b'));p.fillRect(0,0,128,8,QColor('#80bd61'))
    p.fillRect(0,8,128,3,QColor('#4c8e55'));p.setPen(QColor('#c6ab72'))
    for x in range(0,128,16):p.drawLine(x,15,x+7,21)
    p.end();assert image.save(str(path))


def create(root):
    root=Path(root);(root/'assets').mkdir(parents=True,exist_ok=True)
    artwork(root);graph=graphs()
    def entity(eid,pos,scale=(1,1,1),sprite=None,layer=0):
        result=dict(id=eid,name=eid.replace('_',' ').title(),position=list(pos),rotation=[0,0,0],scale=list(scale),sorting_order=layer)
        if sprite:result['sprite']=dict(asset=sprite,frame=0,flip_x=False,flip_y=False)
        return result
    bird=entity('bird',[-2,0,.1],sprite='bird',layer=10);bird['sprite_state']=dict(asset='bird_states',state='idle')
    entities=[entity('sky',[0,0,-2],sprite='sky',layer=-20),entity('ground',[0,-3.9,.3],sprite='ground',layer=20),bird]
    for i in range(3):
        for side,y in [('top',5),('bottom',-5)]:
            item=entity(f'pipe_{i}_{side}',[4+i*4,y,0],sprite='pipe',layer=0)
            item['sprite']['flip_y']=side=='bottom';entities.append(item)
    camera=entity('camera',[0,0,12]);camera['camera']=dict(projection='orthographic',size=8.5,near=.1,far=100.,fov=60.);entities.append(camera)
    variables={'score':dict(type='int',value=0),'best':dict(type='int',value=0),'restart_count':dict(type='int',value=0),
        'death_reason':dict(type='string',value=''),'steps':dict(type='int',value=0),'bird_y':0.,'velocity':0.,
        'alive':dict(type='bool',value=True),'started':dict(type='bool',value=False),'paused':dict(type='bool',value=False)}
    for i in range(3):variables.update({f'pipe_{i}_x':4.+i*4.,f'pipe_{i}_gap':0.,f'pipe_{i}_passed':dict(type='bool',value=False)})
    def sprite(sid,width,height,columns=1):
        return dict(version=1,type='sprite',id=sid,name=sid.title(),texture=f'assets/{sid}.png',width=width,height=height,
                    columns=columns,rows=1,pivot=[.5,.5],filter='nearest')
    scene=dict(version=1,entities=entities,active_camera='camera',variables=variables,
        sprite_assets=[sprite('bird',.65,.65,2),sprite('pipe',1.,7.),sprite('sky',16.,9.),sprite('ground',16.,.8)],
        sprite_state_assets=[dict(version=1,type='sprite_state_machine',id='bird_states',name='Bird wings',sprite='bird',
            states=dict(idle=[0,1],flap=[1,0]),initial='idle',fps=10.,loop=True)],
        ui_assets=[dict(new_asset(rml=HUD),id='hud')])
    save_json(root/'graphs/gameplay.json',graph);save_json(root/'scenes/main.json',scene)
    path=root/'flappy_bird.nen';old=json.loads(path.read_text('utf-8')) if path.exists() else None
    manifest=nen_manifest(dict(version=2,name='Flappy Bird',entry_scene='main',scenes=[dict(id='main',name='Main',
        graph='graphs/gameplay.json',scene='scenes/main.json')],assets=[f'assets/{n}.png' for n in ('bird','pipe','sky','ground')]))
    if old and old.get('project_id'):manifest['project_id']=old['project_id']
    manifest['editor']=dict(node_workflow='2d');save_json(path,manifest)
    from editor.core.projects import compile_project,project_snapshot
    export(compile_project(project_snapshot(path)),root/'generated')
    save_json(root/'replays/death.json',dict(version=1,events=[dict(frame=0,button='Space',down=True),dict(frame=1,button='Space',down=False)]))
    scoring=[]
    for frame in range(0,250,44):
        scoring.extend([dict(frame=frame,button='Space',down=True),dict(frame=frame+1,button='Space',down=False)])
    save_json(root/'replays/score.json',dict(version=1,events=scoring))
    save_json(root/'replays/ready.json',dict(version=1,events=[]))
    save_json(root/'replays/restart_scored.json',dict(version=1,events=scoring+[
        dict(frame=300,button='R',down=True),dict(frame=301,button='R',down=False)]))
    save_json(root/'replays/pause.json',dict(version=1,events=[dict(frame=0,button='Space',down=True),
        dict(frame=1,button='Space',down=False),dict(frame=15,button='P',down=True),dict(frame=16,button='P',down=False)]))
    save_json(root/'replays/pipe_death.json',dict(version=1,events=[dict(frame=f+d,button='Space',down=d==0)
        for f in range(0,170,40) for d in (0,1)]))
    save_json(root/'replays/recycle.json',dict(version=1,events=[dict(frame=f+d,button='Space',down=d==0)
        for f in range(0,310,44) for d in (0,1)]))
    def assertion(name,value,op='eq'):return dict(path='variables.'+name,op=op,value=value)
    save_json(root/'acceptance.json',dict(version=1,controls='Space/click flap; P pause; R restart',
        state_paths=dict(ticks='variables.steps',resets='variables.restart_count',reason='variables.death_reason'),scenarios=[
        dict(id='ready',frames=30,replay='replays/ready.json',covers=['ready'],assertions=[assertion('started',False),assertion('alive',True),assertion('score',0)]),
        dict(id='score',frames=250,before_frames=1,replay='replays/score.json',covers=['scoring'],assertions=[assertion('score',1,'ge'),assertion('alive',True),assertion('best',1,'ge')]),
        dict(id='death',frames=120,replay='replays/death.json',covers=['death'],assertions=[assertion('alive',False),assertion('score',0),assertion('death_reason','ground')]),
        dict(id='pipe_death',frames=170,replay='replays/pipe_death.json',covers=['death','pipe_collision'],
            assertions=[assertion('alive',False),assertion('death_reason','pipe'),assertion('bird_y',-3.,'gt'),assertion('bird_y',3.,'lt')]),
        dict(id='restart',frames=310,before_frames=299,replay='replays/restart_scored.json',covers=['restart'],
            before_assertions=[assertion('alive',False),assertion('score',1,'ge')],
            assertions=[assertion('alive',True),assertion('started',False),assertion('score',0),assertion('best',1,'ge'),assertion('bird_y',0.),assertion('restart_count',1)]),
        dict(id='pause',frames=90,replay='replays/pause.json',covers=['pause'],assertions=[assertion('paused',True),assertion('alive',True),assertion('score',0),assertion('steps',15),assertion('bird_y',.875)]),
        dict(id='recycle',frames=300,replay='replays/recycle.json',covers=['pipe_recycling'],
            assertions=[assertion('alive',True),assertion('steps',300),assertion('pipe_0_gap',0.,'ne'),assertion('pipe_0_x',0.,'gt'),assertion('score',2)])]))
    (root/'README.md').write_text('''# Flappy Bird

Open flappy_bird.nen in Node_Engine. Space or left click starts/flaps; P pauses;
R resets the round. Fly through gaps and score once per pipe pair. Ground,
ceiling and pipe collisions end the round. Best score survives round resets
within this game process. Restart uses the same seed for reproducible practice.

All gameplay is authored as ordinary nodes and named reusable functions in
graphs/gameplay.json. Select a function to inspect Reset Round, Flap, each pipe,
Simulate Bird, Game Over and HUD updates. No embedded C++ gameplay is used.
Read or edit docs/guide.md with File > Project Markdown (Ctrl+Shift+M).
Native acceptance is described in acceptance.json and replays/.
''',encoding='utf-8')
    from editor.core.game_guides import write_game_guide
    write_game_guide(root, 'flappy')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'templates/games/flappy_bird')
    print(create(parser.parse_args().output))
