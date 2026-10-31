"""Native nominal collection operations, callbacks and delayed checkpoint payloads."""
from copy import deepcopy
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.functions import new_function
from editor.core.events import new_event
from editor.core.typed_schema import build_schema
from editor.core.document import default_scene,save_json
from editor.core.projects import compile_project
from tests.test_user_collections import definitions
from tests.test_native import native
from tests.test_physics_scene import chain


def builder(functions=(),event_definitions=()):
    structs,enums=definitions()
    return GraphBuilder(struct_definitions=structs,enum_definitions=enums,functions=functions,event_definitions=event_definitions)


def parity(native,b,**kwargs):
    a,z=native(b.graph,**kwargs)
    assert a.returncode==z.returncode==0,a.stderr+z.stderr
    state=json.loads(a.stdout); assert state==json.loads(z.stdout)
    return state


def test_native_nominal_array_map_set_operations_and_snapshot_loops(native):
    b=builder(); b.add('start','On Game Start')
    chain(b,'start',('array','Set Stats Array Variable',dict(Name='items',Value=[dict(hp=1),dict(hp=2)])),
        ('map','Set Stats Map Variable',dict(Name='lookup',Value={'z':dict(hp=8),'a':dict(hp=3)})),
        ('set','Set Mode Set Variable',dict(Name='modes',Value=['Run','Idle'])))
    b.add('append','Append Stats Item',Array=[dict(hp=4)],Item=dict(hp=9))
    chain(b,'set',('store_append','Set Stats Array Variable',dict(Name='appended')))
    b.connect('append','Value','store_append','Value')
    b.add('mapvalues','Stats Map Values',Map={'z':dict(hp=8),'a':dict(hp=3)})
    chain(b,'store_append',('store_values','Set Stats Array Variable',dict(Name='values')))
    b.connect('mapvalues','Value','store_values','Value')
    b.add('create_set','Create Mode Set',Items=['Idle','Run'])
    b.add('dedup','Add Mode Set Item',Item='Idle')
    b.connect('create_set','Value','dedup','Set')
    chain(b,'store_values',('store_set','Set Mode Set Variable',dict(Name='unique')))
    b.connect('dedup','Value','store_set','Value')
    b.add('each','For Each Stats Map',Map={'z':dict(hp=8),'a':dict(hp=3)})
    b.connect('store_set','Out','each','In')
    b.add('last','Set Stats Variable',Name='last'); b.connect('each','Body','last','In')
    chain(b,'last',('key','Set String Variable',dict(Name='key')))
    b.connect('each','Item','last','Value').connect('each','Key','key','Value')
    state=parity(native,b,frames=0); v=state['variables']
    assert v['items']==dict(type='array<struct:Stats>',value=[dict(hp=1),dict(hp=2)])
    assert v['appended']['value']==[dict(hp=4),dict(hp=9)]
    assert v['values']['value']==[dict(hp=3),dict(hp=8)]
    assert v['unique']==dict(type='set<enum:Mode>',value=['Idle','Run'])
    assert v['last']==dict(type='struct:Stats',value=dict(hp=8)) and v['key']['value']=='z'


def test_native_empty_collections_keep_their_nominal_type(native):
    b=builder(); b.add('start','On Game Start')
    chain(b,'start',('a','Set Stats Array Variable',dict(Name='a',Value=[])),
        ('m','Set Stats Map Variable',dict(Name='m',Value={})),('s','Set Mode Set Variable',dict(Name='s',Value=[])))
    next(node for node in b.graph['nodes'] if node['id']=='a')['code']='{{call}}\nrt::Print(ctx, "Nominal collection hook");'
    b.add('missing','Get Stats Array Variable',Name='missing')
    b.add('select','Select Stats Array',Condition=False,**{'False':[]})
    b.add('selected','Set Stats Array Variable',Name='selected')
    b.connect('s','Out','selected','In').connect('missing','Value','select','True').connect('select','Value','selected','Value')
    state=parity(native,b,frames=0)
    assert state['variables']==dict(a=dict(type='array<struct:Stats>',value=[]),
        m=dict(type='map<struct:Stats>',value={}),s=dict(type='set<enum:Mode>',value=[]),
        selected=dict(type='array<struct:Stats>',value=[]))
    assert state['logs']==['Nominal collection hook']


def test_every_nominal_collection_operation_in_both_native_backends(native):
    b=builder(); b.add('start','On Game Start'); previous='start'; expected={}
    for label,element,one,two in [('Stats','struct:Stats',dict(hp=1),dict(hp=2)),('Mode','enum:Mode','Idle','Run')]:
        array='array<'+element+'>'; mapping='map<'+element+'>'; group='set<'+element+'>'
        cases=[
            (f'Create {label} Array',dict(Items=[one,two]),array,[one,two]),
            (f'Append {label} Item',dict(Array=[one],Item=two),array,[one,two]),
            (f'Insert {label} Item',dict(Array=[two],Index=0,Item=one),array,[one,two]),
            (f'Remove {label} Item At',dict(Array=[one,two],Index=0),array,[two]),
            (f'Get {label} Item',dict(Array=[one,two],Index=1),element,two),
            (f'Set {label} Item',dict(Array=[one],Index=0,Item=two),array,[two]),
            (f'{label} Array Length',dict(Array=[one,two]),'int',2),
            (f'{label} Array Contains',dict(Array=[one],Item=two),'bool',False),
            (f'Find {label} Item',dict(Array=[one,two],Item=two),'int',1),
            (f'Reverse {label} Array',dict(Array=[one,two]),array,[two,one]),
            (f'Clear {label} Array',dict(Array=[one]),array,[]),
            (f'Concat {label} Arrays',dict(A=[one],B=[two]),array,[one,two]),
            (f'Slice {label} Array',dict(Array=[one,two],Start=1,End=2),array,[two]),
            (f'Create {label} Map',dict(Items={'a':one}),mapping,{'a':one}),
            (f'Get {label} Map Item',dict(Map={'a':one},Key='a'),element,one),
            (f'Set {label} Map Item',dict(Map={'a':one},Key='b',Item=two),mapping,{'a':one,'b':two}),
            (f'Remove {label} Map Item',dict(Map={'a':one,'b':two},Key='a'),mapping,{'b':two}),
            (f'{label} Map Has Key',dict(Map={'a':one},Key='b'),'bool',False),
            (f'{label} Map Keys',dict(Map={'z':two,'a':one}),'array<string>',['a','z']),
            (f'{label} Map Values',dict(Map={'z':two,'a':one}),array,[one,two]),
            (f'{label} Map Size',dict(Map={'a':one}),'int',1),
            (f'Clear {label} Map',dict(Map={'a':one}),mapping,{}),
            (f'Create {label} Set',dict(Items=[one,two]),group,[one,two]),
            (f'Add {label} Set Item',dict(Set=[one],Item=two),group,[one,two]),
            (f'Remove {label} Set Item',dict(Set=[one,two],Item=one),group,[two]),
            (f'{label} Set Contains',dict(Set=[one,two],Item=one),'bool',True),
            (f'{label} Set Length',dict(Set=[one,two]),'int',2),
            (f'Clear {label} Set',dict(Set=[one,two]),group,[])]
        for name,values,kind,result in cases:
            i=len(expected); expr=f'expr{i}'; store=f'store{i}'
            b.add(expr,name,**values)
            setter=next(s for s in b.registry.nodes.values() if s.variable_type==kind and not s.variable_scope
                        and s.variable_access in ('set','write'))
            b.add(store,setter.name,Name=store); b.connect(previous,'Out',store,'In'); b.connect(expr,'Value',store,'Value')
            previous=store; expected[store]=dict(type=kind,value=result)
    state=parity(native,b,frames=0)
    assert state['variables']==expected


def callbacks():
    structs,enums=definitions(); schema=build_schema(structs,enums); functions=[]
    for label,result in [('Rank','float'),('Keep','bool'),('Upgrade','struct:Stats')]:
        f=new_function(label,[dict(name='Item',type='struct:Stats')],[dict(name='Result',type=result)],True,functions,schema=schema)
        body=GraphBuilder(functions=[*functions,f],function=f['id'],struct_definitions=structs,enum_definitions=enums)
        body.add('entry','Function Input'); body.add('fields','Break Stats'); body.add('return','Function Output')
        body.connect('entry','Item','fields','Value')
        if label=='Rank':
            body.add('result','Integer to Float'); body.connect('fields','hp','result','Value')
        elif label=='Keep':
            body.add('result','Integer Less',B=4); body.connect('fields','hp','result','A')
        else:
            body.add('plus','Integer Add',B=10); body.add('result','Make Stats')
            body.connect('fields','hp','plus','A').connect('plus','Value','result','hp')
        body.connect('result','Value','return','Result'); f['graph']=body.graph; functions.append(f)
    return functions


def test_native_sort_filter_map_callbacks_and_nominal_collection_function_ports(native):
    functions=callbacks(); structs,enums=definitions(); schema=build_schema(structs,enums)
    f=new_function('Values',[dict(name='Items',type='map<struct:Stats>')],
        [dict(name='Result',type='array<struct:Stats>')],True,functions,schema=schema)
    body=GraphBuilder(functions=[*functions,f],function=f['id'],struct_definitions=structs,enum_definitions=enums)
    body.add('entry','Function Input'); body.add('values','Stats Map Values'); body.add('return','Function Output')
    body.connect('entry','Items','values','Map').connect('values','Value','return','Result'); f['graph']=body.graph
    b=builder([*functions,f]); b.add('start','On Game Start'); previous='start'
    for mode,callback in zip(('Sort','Filter','Map'),functions):
        b.add(mode,mode+' Stats Array',Array=[dict(hp=8),dict(hp=1),dict(hp=3)],Callback=callback['id'])
        store=mode+'_store'; b.add(store,'Set Stats Array Variable',Name=mode)
        b.connect(previous,'Out',store,'In').connect(mode,'Value',store,'Value'); previous=store
    b.add('call','Values',Items={'z':dict(hp=9),'a':dict(hp=2)})
    b.add('saved','Set Stats Array Variable',Name='function')
    b.connect(previous,'Out','saved','In').connect('call','Result','saved','Value')
    state=parity(native,b,frames=0); values=state['variables']
    for name,expected in [('Sort',[1,3,8]),('Filter',[1,3]),('Map',[18,11,13]),('function',[2,9])]:
        assert values[name]==dict(type='array<struct:Stats>',value=[dict(hp=n) for n in expected])


def test_native_enum_array_callback_signatures_and_stable_order(native):
    schema=build_schema(*definitions()); functions=[]
    for mode,result in [('Sort','float'),('Filter','bool'),('Map','enum:Mode')]:
        f=new_function(mode+' Mode',[dict(name='Item',type='enum:Mode')],[dict(name='Result',type=result)],True,functions,schema=schema)
        if mode=='Map': f['graph']['links']=[{'from':['entry','Item'],'to':['return','Result']}]
        else: f['graph']['nodes'][1]['values']={'Result':1.0 if mode=='Sort' else True}
        functions.append(f)
    b=builder(functions);b.add('start','On Game Start');previous='start'
    for mode,f in zip(('Sort','Filter','Map'),functions):
        b.add(mode,mode+' Mode Array',Array=['Run','Idle'],Callback=f['id'])
        target=mode+'saved';b.add(target,'Set Mode Array Variable',Name=mode)
        b.connect(previous,'Out',target,'In').connect(mode,'Value',target,'Value');previous=target
    state=parity(native,b,frames=0)
    for mode in ('Sort','Filter','Map'): assert state['variables'][mode]==dict(type='array<enum:Mode>',value=['Run','Idle'])


def delayed_collections():
    schema=build_schema(*definitions())
    event=new_event('Batch',[dict(name='Items',type='array<struct:Stats>'),
        dict(name='Lookup',type='map<struct:Stats>'),dict(name='Modes',type='set<enum:Mode>')],schema=schema)
    b=builder(event_definitions=[event]); b.add('start','On Game Start')
    chain(b,'start',('open','Open Save Storage',{'Game ID':'user-collection-checkpoint'}),
        ('send','Broadcast Batch',dict(Lookup={'z':dict(hp=8),'a':dict(hp=3)},Modes=['Run','Idle'])),
        ('mutate','Set Stats Array Variable',dict(Name='source',Value=[dict(hp=99)])))
    b.add('source','Get Stats Array Variable',Name='source'); b.connect('source','Value','send','Items')
    b.add('event','On Batch'); b.add('each','For Each Stats Map')
    b.connect('event','Out','each','In').connect('event','Lookup','each','Map')
    b.add('delay','Delay',Seconds=.3); b.connect('each','Body','delay','In')
    chain(b,'delay',('last','Set Stats Variable',dict(Name='last')),('key','Set String Variable',dict(Name='key')))
    b.connect('each','Item','last','Value').connect('each','Key','key','Value')
    b.add('received','Set Stats Array Variable',Name='received'); b.connect('each','Done','received','In')
    b.connect('event','Items','received','Value')
    chain(b,'received',('modes','Set Mode Set Variable',dict(Name='modes'))); b.connect('event','Modes','modes','Value')
    for key,label in [('S','Save Game'),('L','Load Game')]:
        b.add(key,'On Key Pressed',Filter=key); chain(b,key,(key+'action',label,dict(Slot='waiting')))
    scene=default_scene(); scene['struct_definitions'],scene['enum_definitions']=definitions()
    scene['variables']={'source':dict(type='array<struct:Stats>',value=[dict(hp=8),dict(hp=3)])}
    return b,scene


def test_native_queued_collections_loop_delay_and_fresh_checkpoint_resume(native,tmp_path):
    b,scene=delayed_collections(); saves=tmp_path/'saves'; replay=tmp_path/'replay.json'
    save_json(replay,dict(version=1,events=[dict(frame=1,button='S',down=True)]))
    waiting=parity(native,b,scene=scene,frames=2,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert waiting['persistence']['success'] and len(waiting['continuations']['tasks'])==1
    save_json(replay,dict(version=1,events=[dict(frame=0,button='L',down=True)]))
    resumed=parity(native,b,scene=scene,frames=10,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert resumed['persistence']['success'] and not resumed['continuations']['tasks']
    assert resumed['variables']['received']==dict(type='array<struct:Stats>',value=[dict(hp=8),dict(hp=3)])
    assert resumed['variables']['source']['value']==[dict(hp=99)]
    assert resumed['variables']['last']['value']==dict(hp=8) and resumed['variables']['key']['value']=='z'
    assert resumed['variables']['modes']==dict(type='set<enum:Mode>',value=['Run','Idle'])


@pytest.mark.parametrize('damage',['element','identity'])
def test_corrupt_nominal_collection_checkpoint_rejects_before_commit(native,tmp_path,damage):
    b,scene=delayed_collections(); saves=tmp_path/'saves'; replay=tmp_path/'replay.json'
    save_json(replay,dict(version=1,events=[dict(frame=1,button='S',down=True)]))
    parity(native,b,scene=scene,frames=2,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    path=next(saves.rglob('*.json')); saved=json.loads(path.read_text('utf-8'))
    def find(value):
        if isinstance(value,dict):
            if value.get('type')=='map<struct:Stats>' and 'value' in value: return value
            for item in value.values():
                result=find(item)
                if result is not None: return result
        elif isinstance(value,list):
            for item in value:
                result=find(item)
                if result is not None: return result
    item=find(saved['checkpoint']['continuations']); assert item is not None
    if damage=='element': item['value']['a']['hp']='invalid'
    else: item['type']='map<struct:Missing>'
    save_json(path,saved); before=path.read_bytes()
    save_json(replay,dict(version=1,events=[dict(frame=0,button='L',down=True)]))
    state=parity(native,b,scene=scene,frames=1,extra=['--dt','.1','--save-root',str(saves),'--input-replay',str(replay)])
    assert not state['persistence']['success'] and state['persistence']['error']
    assert 'received' not in state['variables'] and len(state['continuations']['tasks'])==1
    assert path.read_bytes()==before


@pytest.mark.parametrize('key,node_id',[('A','bad_array'),('B','bad_map'),('C','bad_slice'),('D','bad_insert')])
def test_native_collection_errors_keep_source_node_identity(native,tmp_path,key,node_id):
    b=builder()
    for key_,source,label,values,kind in [
        ('A','bad_array','Get Stats Item',dict(Array=[],Index=0),'Set Stats Variable'),
        ('B','bad_map','Get Stats Map Item',dict(Map={},Key='missing'),'Set Stats Variable'),
        ('C','bad_slice','Slice Stats Array',dict(Array=[],Start=0,End=1),'Set Stats Array Variable'),
        ('D','bad_insert','Insert Stats Item',dict(Array=[],Index=-1,Item=dict(hp=1)),'Set Stats Array Variable')]:
        b.add(key_,'On Key Pressed',Filter=key_); b.add(source,label,**values); b.add(key_+'save',kind,Name=source)
        b.connect(key_,'Out',key_+'save','In').connect(source,'Value',key_+'save','Value')
    replay=tmp_path/'error.json';save_json(replay,dict(version=1,events=[dict(frame=0,button=key,down=True)]))
    a,z=native(b.graph,frames=1,extra=['--input-replay',str(replay)])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    assert json.loads(a.stderr)['node']==node_id


def test_nominal_global_and_entity_collections_clone_and_scene_transition(native,tmp_path):
    b=builder();b.add('start','On Game Start')
    chain(b,'start',('shared','Set Global Stats Array Variable',dict(Name='shared',Value=[dict(hp=7)])),
        ('owner','Set Entity Stats Map Variable',dict(Entity='player',Name='stash',Value={'a':dict(hp=1)})),
        ('clone','Clone Entity',dict(Source='player')),
        ('edit_clone','Set Entity Stats Map Variable',dict(Entity='spawned_1',Name='stash',Value={'a':dict(hp=2)})),
        ('original','Set Global Stats Map Variable',dict(Name='original')),
        ('copy','Set Global Stats Map Variable',dict(Name='copy')))
    for node_id,owner,store in [('read_original','player','original'),('read_copy','spawned_1','copy')]:
        b.add(node_id,'Get Entity Stats Map Variable',Entity=owner,Name='stash');b.connect(node_id,'Value',store,'Value')
    b.add('C','On Key Pressed',Filter='C');chain(b,'C',('change','Change Scene',dict(Scene='level')))
    level=builder();level.add('loaded','On Scene Loaded');level.add('read','Get Global Stats Array Variable',Name='shared')
    chain(level,'loaded',('seen','Set Scene Stats Array Variable',dict(Name='seen')));level.connect('read','Value','seen','Value')
    scene=default_scene();scene['variables']={'shared':dict(type='array<struct:Stats>',value=[])}
    scene['variable_scopes']={'shared':'global'};scene['struct_definitions'],scene['enum_definitions']=definitions()
    program=compile_project(dict(version=2,entry_scene='main',scenes=dict(main=dict(graph=b.graph,scene=scene),
        level=dict(graph=level.graph,scene=default_scene()))))
    replay=tmp_path/'transition.json';save_json(replay,dict(version=1,events=[dict(frame=1,button='C',down=True)]))
    a,z=native(program=program,frames=3,extra=['--input-replay',str(replay)])
    assert a.returncode==z.returncode==0,a.stderr+z.stderr
    state=json.loads(a.stdout);assert state==json.loads(z.stdout)
    assert state['scene_session']['active']=='level'
    assert state['variables']['seen']==dict(type='array<struct:Stats>',value=[dict(hp=7)])
    globals_=state['scene']['global_variables']
    assert globals_['original']['value']=={'a':dict(hp=1)} and globals_['copy']['value']=={'a':dict(hp=2)}
