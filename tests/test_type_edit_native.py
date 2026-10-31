import json
from editor.core.builder import GraphBuilder
from editor.core.type_edits import stable_definitions, edit_type
from editor.core.document import default_scene
from editor.core.data_types import declaration
from tests.test_native import native


def test_native_stable_type_nodes_work_after_definition_reorder(native):
    structs,enums=stable_definitions([dict(name='Stats',fields=[dict(name='hp',type='int',default=1)]),
                                     dict(name='Other',fields=[dict(name='title',type='string')])],
                                    [dict(name='Mode',values=['Idle','Run'])])
    structs[0]['variable_id']=880000
    b=GraphBuilder(struct_definitions=structs,enum_definitions=enums)
    for nid,name,values in [('start','On Game Start',{}),('stats','Make Stats',dict(hp=42)),
        ('set','Set Global Stats Variable',dict(Name='stats')),('read','Get Global Stats Variable',dict(Name='stats')),
        ('fields','Break Stats',{}),('hp','Set Integer Variable',dict(Name='hp'))]: b.add(nid,name,**values)
    b.connect('start','Out','set','In').connect('set','Out','hp','In')
    b.connect('stats','Value','set','Value').connect('read','Value','fields','Value').connect('fields','hp','hp','Value')
    b.graph['struct_definitions']=list(reversed(structs))
    scene=default_scene()
    a,c=native(b.graph,scene=scene,frames=0)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']['hp']==declaration('int',42)
    assert state['scene']['global_variables']['stats']==declaration('struct:Stats',dict(hp=42))


def test_native_refactored_struct_graph_preserves_behavior(native):
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=1)])]
    b=GraphBuilder(struct_definitions=structs)
    for nid,name,values in [('start','On Game Start',{}),('make','Make Stats',dict(hp=51)),
        ('set','Set Stats Variable',dict(Name='stats')),('read','Get Stats Variable',dict(Name='stats')),
        ('fields','Break Stats',{}),('hp','Set Integer Variable',dict(Name='hp'))]: b.add(nid,name,**values)
    b.connect('start','Out','set','In').connect('set','Out','hp','In').connect('make','Value','set','Value')
    b.connect('read','Value','fields','Value').connect('fields','hp','hp','Value')
    graph,scene=edit_type(b.graph,default_scene(),'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=1)]),
                          original='Stats',origins=dict(health='hp'))
    a,c=native(graph,scene=scene,frames=0)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']['hp']==declaration('int',51)
    assert state['variables']['stats']==declaration('struct:Vitals',dict(health=51))


def test_native_high_component_nodes_are_not_intercepted_by_user_variables(native):
    component=dict(id=2050,name='Health',properties=[dict(id=1,name='Points',type='int',default=100)])
    b=GraphBuilder(component_definitions=[component])
    for nid,name,values in [('start','On Game Start',{}),('add','Add Health Component',{}),
        ('set','Set Health Points',dict(Value=37)),('read','Get Health Points',{}),
        ('store','Set Integer Variable',dict(Name='hp'))]: b.add(nid,name,**values)
    b.connect('start','Out','add','In').connect('add','Out','set','In').connect('set','Out','store','In')
    b.connect('read','Value','store','Value')
    scene=default_scene(); scene['component_definitions']=[component]
    a,c=native(b.graph,scene=scene,frames=0)
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']['hp']==declaration('int',37)
