"""Real interpreted/generated graph playback, entity lifecycle and diagnostics."""
import json
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene
from editor.core.registry import ROOT
from tests.test_native import native
from tests.test_physics_scene import chain,run

ASSET='examples/animation_assets/robot.glb'
def scene():
    s=default_scene(); s['variables']={}; s['entities'][0]['mesh']=ASSET
    return s
def start():
    b=GraphBuilder(); b.add('start','On Game Start'); return b
def save_query(b,source,nid,label,type='Float',**values):
    b.add(nid,label,**values)
    end=chain(b,source,(nid+'_store','Set Variable' if type=='Float' else 'Set '+type+' Variable',{'Name':nid}))
    b.connect(nid,'Value',end,'Value'); return end

def test_all_playback_controls_and_queries(native):
    b=start(); end=chain(b,'start',('play','Play Animation',{'Clip':'Wave'}),
        ('pause','Pause Animation',{}),('seek','Set Animation Time',{'Time':1.25}),
        ('speed','Set Animation Speed',{'Speed':-.5}),('loop','Set Animation Loop',{'Loop':False}))
    for nid,label,type,values in [('clips','Get Animation Clips','String Array',{}),
            ('time','Get Animation Time','Float',{}),('progress','Get Animation Progress','Float',{}),
            ('duration','Get Animation Duration','Float',{'Clip':'Wave'}),
            ('paused','Is Animation Paused','Boolean',{}),('playing','Is Animation Playing','Boolean',{})]:
        end=save_query(b,end,nid,label,type,**values)
    chain(b,end,('resume','Resume Animation',{}))
    result=run(native,b,scene(),60,extra=['--project-root',str(ROOT)])
    v=result['variables']; p=result['animation']['player']
    assert v['clips']['value']==['Idle','Wave','Walk'] and v['duration']==2
    assert v['time']==1.25 and v['progress']==.625
    assert v['paused']['value'] and not v['playing']['value']
    assert p['time']==pytest.approx(.75) and p['playing'] and not p['paused'] and not p['loop']

@pytest.mark.parametrize('speed,loop,frames,expected,playing',[(1,False,150,2,False),(-1,False,150,0,False),
    (1,True,150,.5,True),(-1,True,150,1.5,True),(0,False,150,0,True)])
def test_endpoints_reverse_loop_and_zero_speed(native,speed,loop,frames,expected,playing):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave','Loop':loop,'Speed':speed}))
    p=run(native,b,scene(),frames,extra=['--project-root',str(ROOT)])['animation']['player']
    assert p['time']==pytest.approx(expected,abs=1e-10) and p['playing']==playing

def test_clone_independent_clock_activity_and_visibility(native):
    b=start(); end=chain(b,'start',('play','Play Animation',{'Clip':'Wave'}),
        ('seek','Set Animation Time',{'Time':.75}),('clone','Clone Entity',{}),
        ('inactive','Set Entity Active',{'Active':False}),('hidden','Set Entity Visibility',{'Visible':False}))
    b.connect('clone','Entity','hidden','Entity')
    result=run(native,b,scene(),60,extra=['--project-root',str(ROOT)])
    assert result['animation']['player']['time']==.75
    assert result['animation']['spawned_1']['time']==pytest.approx(1.75)
    assert not next(e for e in result['scene']['entities'] if e['id']=='spawned_1')['visible']

def test_stop_and_destroy_remove_players(native):
    b=start(); chain(b,'start',('play','Play Animation',{'Clip':'Wave'}),('clone','Clone Entity',{}),
        ('stop','Stop Animation',{}),('destroy','Destroy Entity',{'Entity':'spawned_1'}))
    end=save_query(b,'destroy','playing','Is Animation Playing','Boolean')
    save_query(b,end,'time','Get Animation Time')
    result=run(native,b,scene(),1,extra=['--project-root',str(ROOT)])
    assert 'animation' not in result and result['variables']['time']==0
    assert not result['variables']['playing']['value']

@pytest.mark.parametrize('label,values,fragment',[
    ('Play Animation',{'Clip':'Missing'},'Unknown animation clip'),
    ('Play Animation',{'Clip':'Wave','Speed':101},'speed'),
    ('Set Animation Time',{'Time':1},'Play Animation first'),
    ('Play Animation',{'Entity':'missing','Clip':'Wave'},'entity')])
def test_invalid_playback_reports_original_node(native,label,values,fragment):
    b=start(); chain(b,'start',('invalid',label,values))
    a,z=native(b.graph,scene=scene(),frames=0,extra=['--project-root',str(ROOT)])
    assert a.returncode==z.returncode==1 and json.loads(a.stderr)==json.loads(z.stderr)
    error=json.loads(a.stderr); assert error['node']=='invalid' and fragment.lower() in error['message'].lower()
