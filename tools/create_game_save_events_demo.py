"""Extend the checkpoint robot with completion/failure graph handlers."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from editor.core.registry import ROOT
from tools.create_game_save_demo import create as create_base

GAME='node-engine-game-save-events-demo'


def create(directory=ROOT/'examples/game_save_events_demo',game_id=GAME):
    directory=create_base(directory,game_id)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['ui_assets'][0]['rml']=scene['ui_assets'][0]['rml'].replace('Whole-game checkpoint','Save / load events').replace(
        'S: save / L: load','S/L: save/load; F/M: failures')
    scene['variables'].pop('completed')
    b=GraphBuilder('Save/load result events')
    b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    b.graph['name']='Save/load result events'
    removed={'record_status','status','ok','failed','success','error'}
    b.graph['nodes']=[n for n in b.graph['nodes'] if n['id'] not in removed]
    b.graph['links']=[e for e in b.graph['links'] if e['from'][0] not in removed and e['to'][0] not in removed]
    for prefix,label,message in [('saved','On Save Completed','Saved: '),('save_failed','On Save Failed','Save failed: '),
                                 ('loaded','On Load Completed','Loaded: '),('load_failed','On Load Failed','Load failed: ')]:
        b.add(prefix,label)
        b.add(prefix+'_text','Concat Strings',A=message)
        b.connect(prefix,'Error' if 'Failed' in label else 'Slot',prefix+'_text','B')
        b.add(prefix+'_status','Set Widget Text',Element='status')
        b.connect(prefix,'Out',prefix+'_status','In').connect(prefix+'_text','Value',prefix+'_status','Text')
        b.add(prefix+'_log','Print Log')
        b.connect(prefix+'_status','Out',prefix+'_log','In').connect(prefix+'_text','Value',prefix+'_log','Message')
    b.add('failures','Sequence'); b.connect('show_score','Out','failures','In')
    for prefix,key,operation,slot,port in [('invalid','F','Save Game','','First'),('missing','M','Load Game','missing','Then')]:
        b.add(prefix+'_key','Is Key Pressed',Key=key); b.add(prefix+'_if','Branch')
        b.connect('failures',port,prefix+'_if','In').connect(prefix+'_key','Value',prefix+'_if','Condition')
        b.add(prefix,operation,Slot=slot); b.connect(prefix+'_if','True',prefix,'In')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%7)*270,(i//7)*230]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    project=json.loads((directory/'project.json').read_text('utf-8')); project['name']='Checkpoint robot with result events'
    save_json(directory/'project.json',project); export(b.compile(scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
