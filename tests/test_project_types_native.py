"""Project-wide nominal types through real scene transitions and checkpoint restore."""
from copy import deepcopy
import json
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json,create_project
from editor.core.project_types import edit_project_type
from editor.core.projects import compile_project,add_scene,save_project_documents,project_snapshot
from tests.test_named_ports import root
from tests.test_native import native
from tests.test_physics_scene import chain


def authored_project():
    main,_,_=root()
    # Complete the queued function/event result before entering the other scene.
    chain(main,'save',('global','Set Global Stats Variable',dict(Name='shared')))
    main.connect('event','Data','global','Value')
    main.add('C','On Key Pressed',Filter='C')
    chain(main,'C',('change','Change Scene',dict(Scene='level')))
    main_scene=default_scene()
    main_scene['variables']={'shared':dict(type='struct:Stats',value=dict(hp=7))}
    main_scene['variable_scopes']={'shared':'global'}
    main_scene['struct_definitions']=deepcopy(main.graph['struct_definitions'])
    main_scene['enum_definitions']=deepcopy(main.graph['enum_definitions'])
    level=GraphBuilder(struct_definitions=main.graph['struct_definitions'],enum_definitions=main.graph['enum_definitions'])
    level.add('loaded','On Scene Loaded'); level.add('shared','Get Global Stats Variable',Name='shared')
    level.add('fields','Break Stats'); level.add('seen','Set Integer Variable',Name='seen')
    level.connect('loaded','Out','seen','In').connect('shared','Value','fields','Value').connect('fields','hp','seen','Value')
    chain(level,'seen',('open','Open Save Storage',{'Game ID':'project-types'}))
    for key,label,values in [('S','Save Game',{'Slot':'typed'}),('L','Load Game',{'Slot':'typed'}),
        ('D','Set Global Stats Variable',dict(Name='shared',Value=dict(hp=99)))]:
        level.add(key,'On Key Pressed',Filter=key); chain(level,key,(key+'action',label,values))
    return dict(version=2,entry_scene='main',scenes=dict(main=dict(graph=main.graph,scene=main_scene),
        level=dict(graph=level.graph,scene=default_scene())))


def test_refactored_project_globals_transition_and_checkpoint_match_native_hosts(native,tmp_path):
    value=authored_project()
    changed=edit_project_type(value,'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=7)]),
                              original='Stats',origins=dict(health='hp'))
    path=create_project(tmp_path/'Native project','Shared nominal values')
    project=add_scene(path,'level'); project['type_definitions']=changed['type_definitions']
    save_project_documents(path,project,changed['scenes'])
    replay=tmp_path/'replay.json'
    save_json(replay,dict(version=1,events=[dict(frame=frame+released,button=key,down=not released)
        for frame,key in [(1,'C'),(3,'S'),(5,'D'),(7,'L')] for released in (0,1)]))
    # Stop at Load: later replay frames would intentionally execute D again.
    a,b=native(program=compile_project(project_snapshot(path)),frames=8,
               extra=['--input-replay',str(replay),'--save-root',str(tmp_path/'saves')])
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    state=json.loads(a.stdout); assert state==json.loads(b.stdout)
    assert state['scene_session']['active']=='level'
    assert state['variables']['seen']==dict(type='int',value=42)
    assert state['scene']['global_variables']['shared']==dict(type='struct:Vitals',value=dict(health=42))
    assert state['scene']['struct_definitions'][0]['fields'][0]['name']=='health'
    assert state['persistence']['success'] and state['frame']<8
