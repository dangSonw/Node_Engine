"""Whole-game save example using the same public nodes as the editor."""
from pathlib import Path
import shutil
import struct
import sys
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.codegen import export
from editor.core.document import default_scene,save_json
from editor.core.registry import ROOT
from editor.core.ui import new_asset

GAME='node-engine-game-save-demo'
SLOT='slot-1'
MARKUP='''<rml><head><style>
body {font-family:node-ui;font-size:18px;color:#edf1ff;}
#panel {position:absolute;left:24px;top:24px;width:320px;height:240px;background-color:#171e32ee;}
p {position:absolute;left:16px;width:285px;}
#title {top:10px;} #score {top:44px;} #hint {top:145px;font-size:15px;} #status {top:177px;font-size:14px;}
input {position:absolute;top:102px;font-family:node-ui;font-size:18px;color:#ffffff;height:34px;width:130px;background-color:#30446e;border:1px #7489ce;}
input:hover {background-color:#486397;} #save {left:16px;} #load {left:172px;}
</style></head><body><div id="panel"><p id="title">Whole-game checkpoint</p><p id="score">0</p>
<input id="save" type="button" value="Save"/><input id="load" type="button" value="Load"/>
<p id="hint">S: save / L: load</p><p id="status">Ready</p></div></body></rml>'''


def create(directory=ROOT/'examples/game_save_demo',game_id=GAME):
    directory=Path(directory); assets=directory/'assets'; assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',assets/'robot.gltf')
    with wave.open(str(assets/'tone.wav'),'wb') as wav:
        wav.setparams((2,2,44100,0,'NONE','not compressed'))
        wav.writeframes(b''.join(struct.pack('<hh',i*97%24000-12000,i*131%16000-8000) for i in range(7000)))
    scene=default_scene(); scene['entities'][0].update(name='Checkpoint robot',mesh='assets/robot.gltf')
    scene['entities'].append(dict(id='camera',name='Game camera',position=[2.,1.8,4.],rotation=[0.,0.,0.],scale=[1.,1.,1.],camera=default_camera()))
    scene['active_camera']='camera'
    scene['variables']={'score':0.,'ticks':0.,'accepted':dict(type='bool',value=False),
        'pending':dict(type='bool',value=False),'completed':dict(type='bool',value=False)}
    scene['audio_assets']=[dict(version=1,type='sound',id='tone',name='Checkpoint tone',file='assets/tone.wav')]
    scene['ui_assets']=[dict(new_asset(rml=MARKUP),id='hud')]
    b=GraphBuilder('Whole-game save and restore')
    def add(id,label,**values): b.add(id,label,**values); return id
    def wire(a,out,z,input): b.connect(a,out,z,input)
    def then(a,z): wire(a,'Out',z,'In')
    def branch(source,condition,id,port='Out'):
        add(id,'Branch'); wire(source,port,id,'In'); wire(condition,'Value',id,'Condition'); return id
    def game_request(source,prefix,load=False,port='Out'):
        add(prefix,'Load Game' if load else 'Save Game'); wire(source,port,prefix,'In')
        add(prefix+'_accepted','Set Boolean Variable',Name='accepted'); then(prefix,prefix+'_accepted')
        wire(prefix,'Accepted',prefix+'_accepted','Value')
        add(prefix+'_pending','Set Boolean Variable',Name='pending'); then(prefix+'_accepted',prefix+'_pending')
        wire('pending','Value',prefix+'_pending','Value')
    add('pending','Game Save Pending'); add('success','Save Operation Succeeded'); add('error','Get Save Error')
    add('start','On Game Start'); add('open','Open Save Storage',**{'Game ID':game_id}); then('start','open')
    add('aim','Camera Look At',Target=[0.,.7,0.]); then('open','aim')
    add('widget','Create Widget'); then('aim','widget')
    add('sound','Play Sound',Sound='tone',Voice='music',Loop=True,Volume=.05); then('widget','sound')
    add('timer','Start Timer',Name='pulse',Seconds=.019,Repeat=True); then('sound','timer')
    add('exists','Save Slot Exists'); then('timer','exists')
    branch('exists','exists','restore'); game_request('restore','startup_load',True,'True')
    add('tick','On Timer Finished',Filter='pulse')
    add('ticks','Get Variable',Name='ticks'); add('add_tick','Add',B=1.); wire('ticks','Value','add_tick','A')
    add('set_tick','Set Variable',Name='ticks'); then('tick','set_tick'); wire('add_tick','Value','set_tick','Value')
    add('update','On Update'); add('sequence','Sequence'); then('update','sequence')
    add('keys','Sequence'); wire('sequence','Then','keys','In')
    add('score','Get Variable',Name='score'); add('increment','Add',B=1.); wire('score','Value','increment','A')
    add('store_score','Set Variable',Name='score'); wire('sequence','First','store_score','In'); wire('increment','Value','store_score','Value')
    add('rotate','Rotate',Degrees=[0.,1.,0.]); then('store_score','rotate')
    add('format','Format Float'); wire('score','Value','format','Value')
    add('show_score','Set Widget Text',Element='score'); then('rotate','show_score'); wire('format','Value','show_score','Text')
    add('record_status','Set Boolean Variable',Name='completed'); then('show_score','record_status'); wire('success','Value','record_status','Value')
    branch('record_status','success','status')
    add('ok','Set Widget Text',Element='status',Text='Ready / last operation succeeded'); wire('status','True','ok','In')
    add('failed','Set Widget Text',Element='status'); wire('status','False','failed','In'); wire('error','Value','failed','Text')
    for prefix,key,load,port in [('save_key','S',False,'First'),('load_key','L',True,'Then')]:
        add(prefix+'_pressed','Is Key Pressed',Key=key)
        branch('keys',prefix+'_pressed',prefix+'_check',port)
        game_request(prefix+'_check',prefix,load,'True')
    for prefix,load in [('save',False),('load',True)]:
        add(prefix+'_click','On Button Click',**{'Widget Filter':'hud','Element Filter':prefix})
        game_request(prefix+'_click',prefix+'_button',load)
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%7)*270,(i//7)*230]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Whole-game checkpoint robot',graph='graphs/gameplay.json',
        scene='scenes/main.json',assets=['assets/robot.gltf','assets/tone.wav']))
    export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
