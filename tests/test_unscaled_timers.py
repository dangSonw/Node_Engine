"""User-visible mixed timer scheduling through both native host paths."""
import pytest
from editor.core.builder import GraphBuilder
from tests.test_native import native
from tests.test_timers import pair
from tests.test_physics_scene import chain


def timers(scale,entries):
    b=GraphBuilder(); b.add('start','On Game Start')
    end=chain(b,'start',('scale','Set Time Scale',{'Scale':scale}))
    for name,seconds,repeat,unscaled in entries:
        end=chain(b,end,('start_'+name,'Start Timer',dict(Name=name,Seconds=seconds,Repeat=repeat,Unscaled=unscaled)))
    b.add('event','On Timer Finished'); chain(b,'event',('log','Print Log',{}))
    b.connect('event','Name','log','Message')
    return b


@pytest.mark.parametrize('scale,count',[(0,0),(.25,1),(1,4),(2,8)])
def test_clock_domains_and_remaining(native,scale,count):
    b=timers(scale,[('game',.25,True,False),('menu',.25,True,True)])
    state=pair(native,b,frames=8,dt=.125)
    assert state['logs'].count('game')==count
    assert state['logs'].count('menu')==4
    assert all(t['remaining']==.25 for t in state['timers'])
    assert next(t for t in state['timers'] if t['name']=='menu')['unscaled']


def test_mixed_deadlines_interleave_and_break_ties_by_creation(native):
    b=timers(2,[('game',.25,True,False),('menu',.25,True,True)])
    assert pair(native,b,dt=.5)['logs']==['game','game','menu','game','game','menu']
    b=timers(.5,[('menu',.25,True,True),('game',.125,True,False)])
    assert pair(native,b,dt=.5)['logs']==['menu','game','menu','game']


def test_unscaled_zero_callback_can_resume_frozen_game_next_frame(native):
    b=timers(0,[('game',0,False,False),('resume',0,False,True)])
    b.add('resume_event','On Timer Finished',Filter='resume')
    chain(b,'resume_event',('resume','Set Time Scale',{'Scale':1}))
    first=pair(native,b,frames=1,dt=.125)
    assert first['logs']==['resume'] and first['time']==0
    assert first['clock']['scale']==1 and first['clock']['dt']==0
    assert pair(native,b,frames=2,dt=.125)['logs']==['resume','game']


def test_callback_replacement_cancels_old_batch_across_domains(native):
    b=timers(2,[('game',.25,True,False),('menu',.25,True,True)])
    b.add('replace_event','On Timer Finished',Filter='game')
    chain(b,'replace_event',('replace','Start Timer',dict(Name='menu',Seconds=0,Unscaled=False)),
          ('stop','Stop Timer',dict(Name='game')))
    first=pair(native,b,frames=1,dt=.5)
    assert first['logs']==['game'] and len(first['timers'])==1
    assert not first['timers'][0].get('unscaled',False)
    assert pair(native,b,frames=2,dt=.5)['logs']==['game','menu']


def test_inactive_owner_and_manual_pause_preserve_unscaled_countdown(native):
    b=timers(0,[])
    chain(b,'scale',('timer','Start Timer',dict(Name='owned',Seconds=.5,Owner='player',Unscaled=True)),
          ('inactive','Set Entity Active',dict(Entity='player',Active=False)))
    b.add('owned_event','On Timer Finished',Receiver='player')
    chain(b,'owned_event',('owned_log','Print Log',{'Message':'owned'}))
    for frame,name,values in [(2,'Set Entity Active',dict(Entity='player',Active=True)),
                              (3,'Pause Timer',dict(Name='owned',Owner='player')),
                              (5,'Resume Timer',dict(Name='owned',Owner='player'))]:
        nid=str(frame); b.add('update'+nid,'On Update'); b.add('frame'+nid,'Get Frame Count')
        b.add('equal'+nid,'Nearly Equal',B=frame)
        b.connect('frame'+nid,'Value','equal'+nid,'A')
        chain(b,'update'+nid,('if'+nid,'Branch',{}))
        b.connect('equal'+nid,'Value','if'+nid,'Condition')
        b.add('act'+nid,name,**values); b.connect('if'+nid,'True','act'+nid,'In')
    state=pair(native,b,frames=7,dt=.125)
    assert not state['logs'] and state['timers'][0]['remaining']==.125
    state=pair(native,b,frames=8,dt=.125)
    assert state['logs']==['owned'] and state['timers']==[] and state['time']==0


def test_unscaled_pin_accepts_boolean_wire_in_old_timer_node(native):
    b=timers(0,[('menu',0,False,False)])
    b.add('choice','Boolean',Value=True); b.connect('choice','Value','start_menu','Unscaled')
    assert pair(native,b,frames=1)['logs']==['menu']
