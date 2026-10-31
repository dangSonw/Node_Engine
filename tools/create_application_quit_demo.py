"""Save the animated Blockbench robot before normal application shutdown."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.document import save_json
from tools.create_input_contexts_demo import create as create_contexts
GAME='node-engine-application-quit-demo'; SLOT='exit'


def trace():
    return [dict(frame=0,button='D',down=True),dict(frame=2,button='Space',down=True),
        dict(frame=3,button='Space',down=False),dict(frame=8,button='D',down=False),
        dict(frame=12,button='Q',down=True)]


def create(directory=ROOT/'examples/application_quit_demo'):
    directory=create_contexts(directory)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['variables'].update(quit_count=dict(type='int',value=0),quit_frame=dict(type='float',value=0),
        after_request=dict(type='bool',value=False),save_completed=dict(type='bool',value=False),load_completed=dict(type='bool',value=False))
    markup=scene['ui_assets'][0]['rml'].replace('Input context: M toggles gameplay controls','Q: save checkpoint and quit / M: gameplay menu')
    markup=markup.replace('</div>','<br/>Last exit count: <span id="quit_count">0</span><br/><span id="exit_status">S/L: save or resume the exit checkpoint</span></div>',1)
    scene['ui_assets'][0]['rml']=markup
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for n in b.graph['nodes']:
        if n['id']=='storage': n['values']['Game ID']=GAME
        if n['id'] in ('save','load'): n['values']['Slot']=SLOT
    def action(source,nid,name,**values):
        b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    b.add('quit_key','On Key Pressed',Filter='Q')
    action(action('quit_key','request_quit','Quit Application'),'after_request','Set Boolean Variable',Name='after_request',Value=True)
    b.add('quitting','On Application Quit'); b.add('quit_count','Get Integer Variable',Name='quit_count'); b.add('quit_inc','Integer Add',B=1)
    b.connect('quit_count','Value','quit_inc','A')
    end=action('quitting','quit_count_set','Set Integer Variable',Name='quit_count'); b.connect('quit_inc','Value',end,'Value')
    b.add('quit_frame','Get Frame Count'); end=action(end,'quit_frame_set','Set Variable',Name='quit_frame'); b.connect('quit_frame','Value',end,'Value')
    end=action(end,'closing_text','Set Widget Text',Element='exit_status',Text='Closing: writing the game checkpoint...')
    end=action(end,'quit_final_count_text','Set Widget Text',Element='quit_count'); b.connect('quit_format','Value',end,'Text')
    end=action(end,'quit_log','Print Log',Message='On Application Quit')
    end=action(end,'save_on_quit','Save Game',Slot=SLOT)
    b.add('exit_error','Get Save Error'); b.add('exit_save_accepted','Branch'); b.connect(end,'Out','exit_save_accepted','In').connect(end,'Accepted','exit_save_accepted','Condition')
    b.add('exit_request_error','Set Widget Text',Element='exit_status'); b.connect('exit_save_accepted','False','exit_request_error','In').connect('exit_error','Value','exit_request_error','Text')
    end=action('exit_request_error','exit_error_log','Print Log'); b.connect('exit_error','Value',end,'Message')
    for nid,event,label,text in [('save_done','On Save Completed','save_completed','Checkpoint saved. Safe to close.'),
                                ('load_done','On Load Completed','load_completed','Checkpoint resumed. Q saves and quits again.')]:
        b.add(nid,event); end=action(nid,nid+'_capture','Set Boolean Variable',Name=label,Value=True)
        end=action(end,nid+'_text','Set Widget Text',Element='exit_status',Text=text)
        action(end,nid+'_log','Print Log',Message=label)
    b.add('save_failed','On Save Failed'); end=action('save_failed','failed_log','Print Log'); b.connect('save_failed','Error',end,'Message')
    end=action(end,'failed_text','Set Widget Text',Element='exit_status'); b.connect('save_failed','Error',end,'Text')
    b.add('exit_hud','On Late Update'); b.add('quit_format','Format Integer'); b.connect('quit_count','Value','quit_format','Value')
    end=action('exit_hud','quit_count_text','Set Widget Text',Element='quit_count'); b.connect('quit_format','Value',end,'Text')
    for i,n in enumerate(b.graph['nodes']): n['position']=[i%6*280,i//6*270]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Save before application quit',scene='scenes/main.json',graph='graphs/gameplay.json'))
    save_json(directory/'input-replay.json',dict(version=3,events=trace())); export(b.compile(scene),directory/'generated'); return directory


if __name__=='__main__': print(create())
