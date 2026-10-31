"""A Blockbench robot whose score, name and rotation survive process restarts."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.registry import ROOT
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.codegen import export
from editor.core.ui import new_asset


GAME='node-engine-robot-save-demo'
NAMES=['score','player_name','robot_rotation']
MARKUP='''<rml><head><title>Robot save playground</title><style>
body { font-family:node-ui; font-size:17px; color:#edf1ff; }
#panel { position:absolute; left:24px; top:24px; width:340px; height:340px; background-color:#171e32ee; border:1px #6276b0; }
h2 { position:absolute; left:18px; top:0px; font-size:21px; }
#score { position:absolute; left:18px; top:45px; }
input { font-family:node-ui; font-size:17px; color:#ffffff; border:1px #7489ce; background-color:#30446e; height:30px; }
input:hover { background-color:#486397; }
#name { position:absolute; left:18px; top:100px; width:290px; background-color:#101829; }
#add { position:absolute; left:18px; top:155px; width:290px; }
#save { position:absolute; left:18px; top:208px; width:132px; }
#load { position:absolute; left:174px; top:208px; width:134px; }
#status { position:absolute; left:18px; top:248px; width:300px; font-size:14px; }
</style></head><body><div id="panel"><h2>Robot save playground</h2>
<p id="score">Score: 0</p><input id="name" type="text" value="Player"/>
<input id="add" type="button" value="Add point / turn robot"/>
<input id="save" type="button" value="Save"/><input id="load" type="button" value="Load"/>
<p id="status">Add points, enter a name, then Save.</p></div></body></rml>'''


def create(directory=ROOT/'examples/persistence_demo',game_id=GAME):
    directory=Path(directory); (directory/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf',directory/'assets/robot.gltf')
    scene=default_scene(); scene['entities'][0].update(name='Saved robot',mesh='assets/robot.gltf')
    scene['variables']={'score':0.,'player_name':dict(type='string',value='Player'),
                        'robot_rotation':dict(type='vec3',value=[0.,0.,0.])}
    scene['ui_assets']=[dict(new_asset(rml=MARKUP),id='hud')]
    b=GraphBuilder('Save and restore progress across game restarts')
    def add(nid,label,**values): b.add(nid,label,**values); return nid
    def wire(a,out,z,input): b.connect(a,out,z,input)
    def then(a,z): wire(a,'Out',z,'In')
    def status(nid,text): return add(nid,'Set Widget Text',Element='status',Text=text)
    add('error','Get Save Error')
    def check(operation,prefix):
        add(prefix+'_check','Branch'); then(operation,prefix+'_check'); wire(operation,'Value',prefix+'_check','Condition')
        status(prefix+'_error',''); wire(prefix+'_check','False',prefix+'_error','In'); wire('error','Value',prefix+'_error','Text')
        return prefix+'_check'
    def hud(prefix,source,port='Out',message='Loaded saved progress.'):
        add(prefix+'_turn','Set Rotation'); wire(source,port,prefix+'_turn','In'); wire('rotation','Value',prefix+'_turn','Value')
        add(prefix+'_score','Set Widget Text',Element='score'); then(prefix+'_turn',prefix+'_score'); wire('label','Value',prefix+'_score','Text')
        add(prefix+'_name','Set Widget Text',Element='name'); then(prefix+'_score',prefix+'_name'); wire('name','Value',prefix+'_name','Text')
        status(prefix+'_status',message); then(prefix+'_name',prefix+'_status')
    def load(prefix,source,port='Out'):
        add(prefix+'_load','Load Variables',Names=NAMES); wire(source,port,prefix+'_load','In')
        branch=check(prefix+'_load',prefix); hud(prefix,branch,'True')

    add('score','Get Variable',Name='score'); add('format','Format Float'); wire('score','Value','format','Value')
    add('label','Concat Strings',A='Score: '); wire('format','Value','label','B')
    add('name','Get String Variable',Name='player_name'); add('rotation','Get Vector3 Variable',Name='robot_rotation')
    add('start','On Game Start'); add('widget','Create Widget',Template='hud'); then('start','widget')
    add('open','Open Save Storage',**{'Game ID':game_id}); then('widget','open')
    opened=check('open','storage'); add('exists','Save Slot Exists'); wire(opened,'True','exists','In')
    add('exists_ok','Save Operation Succeeded'); add('exists_check','Branch'); then('exists','exists_check'); wire('exists_ok','Value','exists_check','Condition')
    status('exists_error',''); wire('exists_check','False','exists_error','In'); wire('error','Value','exists_error','Text')
    add('has_save','Branch'); wire('exists_check','True','has_save','In'); wire('exists','Value','has_save','Condition')
    load('startup','has_save','True')
    for nid,element in [('clicked','add'),('save_clicked','save'),('load_clicked','load')]:
        add(nid,'On Button Click',**{'Widget Filter':'hud','Element Filter':element})
    add('increment','Add',B=1.); wire('score','Value','increment','A')
    add('store_score','Set Variable',Name='score'); then('clicked','store_score'); wire('increment','Value','store_score','Value')
    add('rotate','Rotate',Degrees=[0,30,0]); then('store_score','rotate')
    add('show_score','Set Widget Text',Element='score'); then('rotate','show_score'); wire('label','Value','show_score','Text')
    status('unsaved','Progress changed. Press Save.'); then('show_score','unsaved')
    add('submitted','On UI Text Submitted',**{'Widget Filter':'hud','Element Filter':'name'})
    add('set_name','Set String Variable',Name='player_name'); then('submitted','set_name'); wire('submitted','Value','set_name','Value')
    status('name_changed','Name changed. Press Save.'); then('set_name','name_changed')
    # Read the text on Save as well, so a player need not press Enter first.
    add('input_name','Get Widget Text',Element='name'); add('save_name','Set String Variable',Name='player_name')
    then('save_clicked','save_name'); wire('input_name','Value','save_name','Value')
    add('actual_rotation','Get Rotation'); add('store_rotation','Set Vector3 Variable',Name='robot_rotation')
    then('save_name','store_rotation'); wire('actual_rotation','Value','store_rotation','Value')
    add('save','Save Variables',Names=NAMES); then('store_rotation','save'); saved=check('save','saved')
    status('saved_status','Saved. You can close and reopen the game.'); wire(saved,'True','saved_status','In')
    load('manual','load_clicked')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%7)*270,(i//7)*230]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Robot save playground',graph='graphs/gameplay.json',
        scene='scenes/main.json',assets=['assets/robot.gltf']))
    export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
