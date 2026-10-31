"""A playable Blockbench robot with collision and trigger graph handlers."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from tools.create_physics_demo import create as create_base

GAME='node-engine-physics-events-demo'


def create(directory=ROOT/'examples/physics_events_demo'):
    directory=create_base(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['entities'].append(dict(id='zone',name='Center trigger zone',position=[0,1,0],rotation=[0,0,0],scale=[1,1,1]))
    scene['ui_assets'][0]['rml']=scene['ui_assets'][0]['rml'].replace('Physics playground','Collision / trigger playground').replace(
        'R: reset; S: save; L: load</div>',
        'R: reset; S: save; L: load<br/>C: load last collision checkpoint<br/>Center trigger: x/z within 1 meter<br/><span id="collision">Collision: waiting</span><br/><span id="trigger">Trigger: waiting</span></div>')
    b=GraphBuilder('Collision and trigger robot'); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='Collision and trigger robot'
    for node in b.graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']=GAME
    b.graph['links'].remove({'from':['ground','Out'],'to':['body','In']})
    b.add('zone_body','Create Box Rigid Body',Entity='zone',Motion='static',Sensor=True,**{'Half Extents':[1,3,1]})
    b.connect('ground','Out','zone_body','In').connect('zone_body','Out','body','In')
    for kind in ('Collision','Trigger'):
        for phase in ('Enter','Stay','Exit'):
            nid=kind.lower()+'_'+phase.lower(); scene['variables'][nid]=0.
            b.add(nid,'On '+kind+' '+phase,Receiver='player')
            b.add(nid+'_count','Get Variable',Name=nid); b.add(nid+'_add','Add',B=1)
            b.connect(nid+'_count','Value',nid+'_add','A')
            b.add(nid+'_set','Set Variable',Name=nid)
            b.connect(nid,'Out',nid+'_set','In').connect(nid+'_add','Value',nid+'_set','Value')
            b.add(nid+'_other','Entity ID'); b.connect(nid,'Other',nid+'_other','Entity')
            b.add(nid+'_label','Concat Strings',A=kind+' '+phase.lower()+': ')
            b.connect(nid+'_other','Value',nid+'_label','B')
            b.add(nid+'_hud','Set Widget Text',Element=kind.lower())
            b.connect(nid+'_set','Out',nid+'_hud','In').connect(nid+'_label','Value',nid+'_hud','Text')
            b.add(nid+'_normal','Set Vector3 Variable',Name=kind.lower()+'_normal')
            b.connect(nid+'_hud','Out',nid+'_normal','In').connect(nid,'Normal',nid+'_normal','Value')
    # A collision callback requests a separate slot; the host saves at its frame boundary.
    b.add('contact_save','Save Game',Slot='first-contact')
    b.connect('collision_enter_normal','Out','contact_save','In')
    b.add('contact_load_event','On Update'); b.add('contact_key','Is Key Pressed',Key='C')
    b.add('contact_if','Branch'); b.add('contact_load','Load Game',Slot='first-contact')
    b.connect('contact_load_event','Out','contact_if','In').connect('contact_key','Value','contact_if','Condition')
    b.connect('contact_if','True','contact_load','In')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%8)*285,(i//8)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Collision and trigger robot'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
