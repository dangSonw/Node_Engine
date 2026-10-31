"""Two Python-authored scenes sharing assets and a single exported game."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.projects import compile_project,project_snapshot
from editor.core.codegen import export
from editor.core.ui import new_asset
from tools.create_time_demo import create as create_time

GAME='node-engine-scene-demo'; SLOT='scene'

def trace():
    return [dict(frame=f,button=k,down=d) for f,k,d in [(5,'C',True),(6,'C',False),(30,'M',True),(31,'M',False),(40,'C',True),(41,'C',False)]]

def create(directory=ROOT/'examples/scene_session_demo'):
    directory=create_time(directory)
    level=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    level_graph=GraphBuilder('Level'); level_graph.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    next(n for n in level_graph.graph['nodes'] if n['id']=='start')['type']=1019
    next(n for n in level_graph.graph['nodes'] if n['id']=='storage')['values']['Game ID']=GAME
    for n in level_graph.graph['nodes']:
        if n['id'] in ('action_S','action_L'): n['values']['Slot']=SLOT
    menu=default_scene(); menu['entities'][0].update(mesh='assets/robot.gltf',position=[0,0,0],rotation=[0,25,0])
    menu['entities'].append(level['entities'][-1]); menu['active_camera']='camera'
    menu_graph=GraphBuilder('Menu'); menu_graph.add('start','On Scene Loaded')
    def action(b,source,nid,name,**values):
        b.add(nid,name,**values); b.connect(source,'Out',nid,'In'); return nid
    action(menu_graph,'start','hud','Create Widget')
    menu_graph.add('game_start','On Game Start')
    end=action(menu_graph,'game_start','storage','Open Save Storage',**{'Game ID':GAME})
    action(menu_graph,end,'game_log','Print Log',Message='Game started once')
    menu_graph.add('update','On Update')
    for name,b,scene in [('menu',menu_graph,menu),('level',level_graph,level)]:
        if name=='menu':
            for letter,node in [('S','Save Game'),('L','Load Game')]:
                b.add(letter,'On Key Pressed',Filter=letter); action(b,letter,letter+'_action',node,Slot=SLOT)
        for letter,node,values in [('C','Change Scene',{'Scene':'level'}),('M','Change Scene',{'Scene':'menu'}),
            ('R','Reload Scene',{}),('P','Pause World',{}),('U','Resume World',{}),('Q','Quit Application',{}),('X','Change Scene',{'Scene':'missing'})]:
            b.add(letter,'On Key Pressed',Filter=letter); action(b,letter,letter+'_action',node,**values)
        b.add('scene_loaded_log','On Scene Loaded'); action(b,'scene_loaded_log','scene_log','Print Log',Message='Loaded '+name)
        b.add('load_failed','On Scene Load Failed'); action(b,'load_failed','failed_log','Print Log'); b.connect('load_failed','Error','failed_log','Message')
        b.add('late','On Late Update'); end='late'
        for nid,node,setter in [('active_scene','Get Active Scene','Set String Variable'),('scene_ok','Scene Load Succeeded','Set Boolean Variable'),('scene_error','Get Scene Error','Set String Variable')]:
            b.add(nid,node); end=action(b,end,nid+'_store',setter,Name=nid); b.connect(nid,'Value',end,'Value')
        b.add('names','Get Scene Names'); b.add('join','String Join',Separator=', '); b.connect('names','Value','join','Items')
        end=action(b,end,'scene_list','Set String Variable',Name='scene_list'); b.connect('join','Value',end,'Value')
        end=action(b,end,'status','Set Widget Text',Widget='hud',Element='status'); b.connect('scene_error','Value',end,'Text')
        markup=f'''<rml><head><style>body {{width:100%;height:100%;font-family:node-ui;font-size:15px;color:#ffffff;pointer-events:none;}}
        #help {{position:absolute;left:12px;top:12px;padding:12px;width:94%;max-width:440px;box-sizing:border-box;background-color:#171e32dd;}}</style></head>
        <body><div id="help">MULTI-SCENE PLAYGROUND — {name.upper()}<br/>
        C: enter level / M: menu / R: reload current scene<br/>
        S: save whole game / L: load saved scene<br/>
        P: pause world / U: resume / Q: quit<br/>
        X: try unknown scene (world stays intact)<br/>
        {'Three robots: animation, timer, physics. Audio plays.' if name=='level' else 'One Blockbench robot. Audio starts in the level.'}<br/>
        <span id="status"></span></div></body></rml>'''
        scene['ui_assets']=[dict(new_asset(rml=markup),id='hud')]
        for i,n in enumerate(b.graph['nodes']): n['position']=[i%7*280,i//7*220]
        save_json(directory/f'graphs/{name}.json',b.graph); save_json(directory/f'scenes/{name}.json',scene)
    save_json(directory/'project.json',dict(version=2,name='Scene playground',entry_scene='menu',scenes=[
        dict(id=n,name=n.title(),scene=f'scenes/{n}.json',graph=f'graphs/{n}.json') for n in ('menu','level')]))
    save_json(directory/'input-replay.json',dict(version=1,events=trace()))
    export(compile_project(project_snapshot(directory/'project.json')),directory/'generated')
    (directory/'scenes/main.json').unlink()
    (directory/'graphs/gameplay.json').unlink()
    return directory

if __name__=='__main__': print(create())
