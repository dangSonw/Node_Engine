"""Run user values and callback expressions through both native execution paths."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.data_types import SCALARS, default_value, declaration
from editor.core.document import default_scene, save_json
from editor.core.functions import new_function
from tests.test_native import native


def port(name, kind):
    return dict(name=name, type=kind)


def parity(native, b, scene=None, **kwargs):
    a, b = native(b.graph, scene=scene, frames=0, **kwargs)
    assert a.returncode == b.returncode == 0, a.stderr+b.stderr
    left, right = json.loads(a.stdout), json.loads(b.stdout)
    assert left == right
    return left


def test_native_nested_struct_enum_storage_and_checkpoint(native, tmp_path):
    structs = [dict(name='Stats', fields=[dict(name='hp', type='int', default=1)]),
               dict(name='Actor', fields=[dict(name='stats', type='struct:Stats'),
                                         dict(name='mode', type='enum:Mode')])]
    enums = [dict(name='Mode', values=['Idle', 'Run'])]
    b = GraphBuilder(struct_definitions=structs, enum_definitions=enums)
    b.add('start', 'On Game Start'); b.add('stats', 'Make Stats', hp=42)
    b.add('mode', 'Make Mode', Value='Run'); b.add('actor', 'Make Actor')
    b.connect('stats','Value','actor','stats').connect('mode','Value','actor','mode')
    b.add('store', 'Set Actor Variable', Name='actor')
    b.add('read', 'Get Actor Variable', Name='actor')
    b.add('actor_fields', 'Break Actor'); b.add('stats_fields', 'Break Stats')
    b.connect('actor','Value','store','Value').connect('read','Value','actor_fields','Value')
    b.connect('actor_fields','stats','stats_fields','Value')
    b.add('hp', 'Set Integer Variable', Name='hp')
    b.connect('stats_fields','hp','hp','Value')
    b.add('state', 'Set Global Mode Variable', Name='state')
    b.connect('actor_fields','mode','state','Value')
    b.add('open', 'Open Save Storage', **{'Game ID':'user-types'})
    b.add('save', 'Save Game', Slot='user-values')
    b.add('alter', 'Set Actor Variable', Name='actor')
    b.add('load', 'Load Game', Slot='user-values')
    for a,c in zip(['start','store','hp','state','open','save','alter'], ['store','hp','state','open','save','alter','load']):
        b.connect(a,'Out',c,'In')
    # Save requests capture the completed frame; mutate on a later input event.
    b.graph['links'] = [l for l in b.graph['links'] if l['to'] not in (['load','In'],['alter','In'])]
    b.add('K','On Key Pressed',Filter='K'); b.connect('K','Out','alter','In')
    b.add('L','On Key Pressed',Filter='L'); b.connect('L','Out','load','In')
    scene = default_scene()
    replay = tmp_path/'keys.json'; save_json(replay,dict(version=1,events=[
        dict(frame=1,button='K',down=True),dict(frame=2,button='K',down=False),dict(frame=3,button='L',down=True)]))
    a, c = native(b.graph, scene=scene, frames=5, extra=['--save-root',str(tmp_path/'saves'),'--input-replay',str(replay)])
    assert a.returncode == c.returncode == 0, a.stderr+c.stderr
    state = json.loads(a.stdout); assert state == json.loads(c.stdout)
    assert state['variables']['actor'] == declaration('struct:Actor',dict(stats=dict(hp=42),mode='Run'))
    assert state['variables']['hp'] == declaration('int',42)
    assert state['scene']['global_variables']['state'] == declaration('enum:Mode','Run')
    assert state['scene']['struct_definitions'] == structs
    assert state['persistence']['success'], state['persistence']


def callback(name, output, node_name=None, **values):
    f = new_function(name,[port('Item','int')],[port('Result',output)],True)
    if node_name:
        b = GraphBuilder(functions=[f],function=f['id'])
        b.add('entry','Function Input'); b.add('return','Function Output')
        b.add('compute',node_name,**values)
        b.connect('entry','Item','compute','Value' if node_name=='Integer to Float' else 'A')
        b.connect('compute','Value','return','Result'); f['graph'] = b.graph
    else:
        f['graph']['links']=[dict(**{'from':['entry','Item'],'to':['return','Result']})]
    return f


def test_native_sort_filter_map_callbacks(native):
    score=callback('Sort key','float','Integer to Float')
    keep=callback('Positive','bool','Integer Greater or Equal',B=2)
    double=callback('Double','int','Integer Multiply',B=2)
    b=GraphBuilder(functions=[score,keep,double]); b.add('start','On Game Start')
    previous='start'
    for name,mode,f,expected in [('sorted','Sort',score,[-1,2,2,3]),
                                ('filtered','Filter',keep,[3,2,2]),('mapped','Map',double,[6,-2,4,4])]:
        b.add(name,mode+' Integer Array',Array=[3,-1,2,2],Callback=f['id'])
        b.add(name+'_save','Set Integer Array Variable',Name=name)
        b.connect(name,'Value',name+'_save','Value').connect(previous,'Out',name+'_save','In')
        previous=name+'_save'
    state=parity(native,b)
    assert state['variables']['sorted']==declaration('array<int>',[-1,2,2,3])
    assert state['variables']['filtered']==declaration('array<int>',[3,2,2])
    assert state['variables']['mapped']==declaration('array<int>',[6,-2,4,4])


def test_native_callback_map_all_ten_scalar_element_types(native):
    functions=[]
    for kind in SCALARS:
        f=new_function('Identity '+kind,[port('Item',kind)],[port('Result',kind)],True,definitions=functions)
        f['graph']['links']=[{'from':['entry','Item'],'to':['return','Result']}]
        functions.append(f)
    b=GraphBuilder(functions=functions); b.add('start','On Game Start'); previous='start'
    expected={}
    for kind,f in zip(SCALARS,functions):
        label={'float':'Float','int':'Integer','bool':'Boolean','string':'String','vec3':'Vector3',
               'vec2':'Vector2','vec4':'Vector4','quat':'Quaternion','mat4':'Matrix4','entity':'Entity'}[kind]
        value=default_value(kind)
        if kind=='string': value='Tiếng Việt\0語'
        if kind=='int': value=9007199254740993
        items=[value,value]
        b.add(kind,'Map '+label+' Array',Array=items,Callback=f['id'])
        b.add(kind+'_save','Set '+label+' Array Variable',Name=kind)
        b.connect(kind,'Value',kind+'_save','Value').connect(previous,'Out',kind+'_save','In')
        previous=kind+'_save'; expected[kind]=declaration('array<'+kind+'>',items)
    assert parity(native,b)['variables']==expected


def test_native_dynamic_enum_label_is_checked_at_its_node(native):
    b=GraphBuilder(enum_definitions=[dict(name='Mode',values=['Idle','Run'])])
    b.add('start','On Game Start'); b.add('input','String',Value='Invalid')
    b.add('mode','Make Mode'); b.add('save','Set Mode Variable',Name='mode')
    b.connect('input','Value','mode','Value').connect('mode','Value','save','Value')
    b.connect('start','Out','save','In')
    a,c=native(b.graph,frames=0)
    assert a.returncode != 0 and c.returncode != 0
    assert 'Unknown enum:Mode label: Invalid' in a.stderr and 'Unknown enum:Mode label: Invalid' in c.stderr


@pytest.mark.parametrize('corruption',['checkpoint_schema','checkpoint_value','progress_value'])
def test_corrupted_user_values_do_not_commit_on_restore(native,tmp_path,corruption):
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=10)])]
    b=GraphBuilder(struct_definitions=structs)
    b.add('start','On Game Start'); b.add('open','Open Save Storage',**{'Game ID':'corrupt-types'})
    b.connect('start','Out','open','In')
    for key,action in [('S','Save'),('L','Load')]:
        b.add(key,'On Key Pressed',Filter=key)
        name=action+' Variables' if corruption=='progress_value' else action+' Game'
        values=dict(Slot='data')
        if corruption=='progress_value': values['Names']=['stats']
        b.add(key+'action',name,**values); b.connect(key,'Out',key+'action','In')
    scene=default_scene(); scene['variables']=dict(stats=declaration('struct:Stats',dict(hp=10)))
    replay=tmp_path/'replay.json'; root=tmp_path/'saves'
    def run(key):
        save_json(replay,dict(version=1,events=[dict(frame=1,button=key,down=True)]))
        a,c=native(b.graph,scene=scene,frames=3,extra=['--save-root',str(root),'--input-replay',str(replay)])
        assert a.returncode==c.returncode==0,a.stderr+c.stderr
        state=json.loads(a.stdout); assert state==json.loads(c.stdout)
        return state
    assert run('S')['persistence']['success']
    path=next((root/'corrupt-types').glob('slot-*.json'))
    data=json.loads(path.read_text('utf-8'))
    if corruption=='checkpoint_schema':
        data['checkpoint']['scene']['struct_definitions'][0]['fields'][0]['default']=99
    elif corruption=='checkpoint_value':
        data['checkpoint']['scene']['variables']['stats']['value']['hp']='bad'
    else:
        data['variables']['stats']['value']['hp']='bad'
    save_json(path,data)
    restored=run('L')
    assert not restored['persistence']['success']
    assert restored['variables']['stats']==declaration('struct:Stats',dict(hp=10))
    assert ('definitions mismatch' if corruption=='checkpoint_schema' else 'Expected signed 64-bit integer') in restored['persistence']['error']
