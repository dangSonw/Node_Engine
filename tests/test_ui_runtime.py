"""Exercise UI event lifetime and faults in the actual native interpreter."""
import json
import subprocess
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.ui import new_asset


CLICK = [dict(frame=0,type='move',x=40,y=20),
         dict(frame=0,type='button',button=0,down=True),
         dict(frame=0,type='button',button=0,down=False)]
MARKUP = '''<rml><head><style>
body { font-family:node-ui; font-size:16px; }
#add { position:absolute; left:10px; top:10px; width:100px; height:30px; }
</style></head><body><input id="add" type="button" value="Add"/>
<div id="panel"><p id="score">Default</p></div><progress id="progress" value="0"/>
</body></rml>'''


def run_ui(tmp_path, graph, replay=CLICK, extra=()):
    assert current(ROOT/'build/node_view.exe'), 'Rebuild native runtime first'
    scene=default_scene(); scene['ui_assets']=[dict(new_asset(rml=MARKUP),id='hud')]
    scene['variables']['delivered']=0.
    save_json(tmp_path/'game.ir.json',graph.compile(scene))
    save_json(tmp_path/'replay.json',dict(version=1,events=replay))
    return subprocess.run([str(ROOT/'build/node_preview.exe'),'--ir',str(tmp_path/'game.ir.json'),
        '--project-root',str(tmp_path),'--ui-replay',str(tmp_path/'replay.json'),
        '--frames','1',*extra],capture_output=True,text=True,encoding='utf-8',timeout=15)


def graph_with_widget():
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('create','Create Widget',Template='hud')
    b.connect('start','Out','create','In')
    return b


@pytest.mark.parametrize('operation', ['recreate','hide','disable'])
def test_invalidated_control_cancels_remaining_listeners(tmp_path,operation):
    b=graph_with_widget()
    for name in ('a_handler','b_handler'):
        b.add(name,'On Button Click',**{'Widget Filter':'hud','Element Filter':'add'})
    if operation=='recreate':
        b.add('invalidate','Destroy Widget'); b.add('restore','Create Widget',Template='hud')
    elif operation=='hide':
        b.add('invalidate','Show Widget',Visible=False); b.add('restore','Show Widget',Visible=True)
    else:
        b.add('invalidate','Set Widget Enabled',Element='add',Enabled=False)
    b.connect('a_handler','Out','invalidate','In')
    if operation!='disable': b.connect('invalidate','Out','restore','In')
    b.add('stale','Set Variable',Name='delivered',Value=1.)
    b.connect('b_handler','Out','stale','In')
    result=run_ui(tmp_path,b)
    assert result.returncode==0,result.stderr
    state=json.loads(result.stdout)
    assert state['variables']['delivered']==0
    assert state['ui']['widgets']['hud']['elements']['add']['enabled']==(operation!='disable')


def test_ui_handler_shares_instruction_budget_and_reports_origin(tmp_path):
    b=graph_with_widget(); b.add('click','On Button Click')
    b.add('loop','While Loop',Condition=True); b.connect('click','Out','loop','In')
    result=run_ui(tmp_path,b,extra=['--budget','30'])
    assert result.returncode==1
    error=json.loads(result.stderr)
    assert error['node']=='loop' and 'budget' in error['message']


@pytest.mark.parametrize('label,values,message',[
    ('Set Widget Value',dict(Element='progress',Value=2.),'between 0 and 1'),
    ('Set Widget Text',dict(Element='panel',Text='remove children'),'plain text element'),
    ('Set Widget Size',dict(Element='panel',Width=-1.),'Invalid UI size'),
])
def test_ui_faults_report_the_original_graph_node(tmp_path,label,values,message):
    b=graph_with_widget(); b.add('bad_widget_change',label,**values)
    b.connect('create','Out','bad_widget_change','In')
    result=run_ui(tmp_path,b,replay=[])
    assert result.returncode==1
    error=json.loads(result.stderr)
    assert error['node']=='bad_widget_change' and message in error['message']
