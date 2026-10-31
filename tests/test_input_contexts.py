import json
from copy import deepcopy
import pytest
from PySide6.QtCore import QSettings,QTimer,Qt
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QListWidget
from PySide6.QtTest import QTest
from editor.core.input import validate_input
from editor.core.builder import GraphBuilder
from editor.core.compiler import GraphError
from editor.core.document import default_scene,create_project,load_project,save_json
from editor.ui.input import InputDialog
from editor.ui.main_window import MainWindow
from tests.test_native import native
from tests.test_input import gamepad_bindings

def bindings():
    b=gamepad_bindings(); b['version']=3
    b['contexts']={'gameplay':dict(enabled=True,actions=['jump'],axes=['horizontal']),
        'secondary':dict(enabled=False,actions=['jump'],axes=[])}
    return b

def invalid():
    base=bindings(); result=[]
    for value in (None,[],True):
        bad=deepcopy(base); bad['contexts']=value; result.append(bad)
    for field,values in [('enabled',[0,'true',None]),('actions',[['missing'],['jump','jump'],[1],'jump']),('axes',[['missing'],['horizontal','horizontal'],None])]:
        for value in values:
            bad=deepcopy(base); bad['contexts']['gameplay'][field]=value; result.append(bad)
    bad=deepcopy(base); bad['contexts']['gameplay']=dict(enabled=True,actions=[],axes=[]); result.append(bad)
    bad=deepcopy(base); bad['contexts']['gameplay']['extra']=True; result.append(bad)
    bad=deepcopy(base); bad['contexts']['']=bad['contexts'].pop('gameplay'); result.append(bad)
    bad=deepcopy(base); bad['contexts']['bad\x00']=bad['contexts'].pop('gameplay'); result.append(bad)
    bad=deepcopy(base); bad['version']=2; result.append(bad)
    bad=deepcopy(base); bad.pop('contexts'); result.append(bad)
    bad=deepcopy(base); bad['contexts']={str(i):dict(enabled=True,actions=['jump'],axes=[]) for i in range(65)}; result.append(bad)
    return result

@pytest.mark.parametrize('bad',invalid())
def test_invalid_context_schema(bad):
    with pytest.raises(ValueError): validate_input(bad)

def test_context_dialog_members_roundtrip_and_scene_history(app,tmp_path):
    source=bindings(); assert validate_input(source)==source
    dialog=InputDialog(source); dialog.accept(); assert dialog.result_input==source
    dialog=InputDialog(gamepad_bindings()); row=dialog.add_context('gameplay')
    dialog.accept(); assert dialog.result()!=QDialog.DialogCode.Accepted and dialog.error.text()
    def choose():
        modal=QApplication.activeModalWidget(); assert isinstance(modal,QDialog)
        for widget in modal.findChildren(QListWidget):
            target='jump' if widget.accessibleName()=='Context actions' else 'horizontal'
            for i in range(widget.count()):
                if widget.item(i).data(Qt.ItemDataRole.UserRole)==target: widget.item(i).setCheckState(Qt.CheckState.Checked)
        QTest.mouseClick(modal.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    dialog.show(); app.processEvents(); QTest.qWait(40)
    QTimer.singleShot(30,choose); dialog.context_table.cellWidget(row,2).click(); QTest.qWait(100)
    dialog.accept(); expected=deepcopy(source); expected['contexts'].pop('secondary')
    assert dialog.result_input==expected
    dialog=InputDialog(expected); dialog.add_context('gameplay',expected['contexts']['gameplay']); dialog.accept()
    assert dialog.result()!=QDialog.DialogCode.Accepted and 'Duplicate' in dialog.error.text()
    path=create_project(tmp_path/'project','Context authoring'); scene=load_project(path)[2]; scene['input']=gamepad_bindings(); save_json(path.parent/'scenes/main.json',scene)
    window=MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    def edit():
        active=QApplication.activeModalWidget(); active.add_context('gameplay',expected['contexts']['gameplay']); active.accept()
    try:
        QTimer.singleShot(20,edit); window.actions['Input Actions and Axes…'].trigger(); assert window.scene['input']==expected
        window.actions['Undo'].trigger(); assert window.scene['input']==gamepad_bindings()
        window.actions['Redo'].trigger(); assert window.scene['input']==expected
        assert window.save_project() and load_project(path)[2]['input']==expected
    finally: window.saved_signature=window.signature(); window.close()

@pytest.mark.parametrize('name',['Set Input Context Enabled','Is Input Context Enabled'])
def test_literal_unknown_context_reports_node(name):
    b=GraphBuilder(); b.add('bad',name,Context='missing')
    with pytest.raises(GraphError) as e: b.compile(default_scene())
    assert e.value.problems[0].node=='bad'

def context_graph():
    b=GraphBuilder(); scene=default_scene(); scene['input']=bindings()
    b.add('toggle','On Key Pressed',Filter='M'); b.add('enabled','Is Input Context Enabled'); b.add('not','NOT'); b.add('set','Set Input Context Enabled')
    b.connect('toggle','Out','set','In').connect('enabled','Value','not','Value').connect('not','Value','set','Enabled')
    for nid,event in [('press','On Action Pressed'),('release','On Action Released')]:
        b.add(nid,event,Filter='jump'); b.add(nid+'_log','Print Log',Message=nid); b.connect(nid,'Out',nid+'_log','In')
    b.add('update','On Update'); end='update'
    for nid,label,node,port,values in [('enabled_values','Boolean','Is Input Context Enabled','Value',{}),
        ('held','Boolean','Is Action Held','Value',{}),('pressed','Boolean','Is Action Pressed','Value',{}),
        ('released','Boolean','Is Action Released','Value',{}),('axis','Float','Get Input Axis','Value',{})]:
        scene['variables'][nid]=dict(type='array<bool>' if label=='Boolean' else 'array<float>',value=[])
        b.add(nid,node,**values); b.add(nid+'_get',f'Get {label} Array Variable',Name=nid)
        b.add(nid+'_append',f'Append {label} Item'); b.add(nid+'_save',f'Set {label} Array Variable',Name=nid)
        b.connect(nid,port,nid+'_append','Item').connect(nid+'_get','Value',nid+'_append','Array').connect(nid+'_append','Value',nid+'_save','Value')
        b.connect(end,'Out',nid+'_save','In'); end=nid+'_save'
    return b,scene

def test_native_contexts_gate_edges_axes_and_held_reactivation(native,tmp_path):
    b,scene=context_graph()
    def key(f,k,down): return dict(frame=f,button=k,down=down)
    def pad(f,down): return dict(frame=f,type='gamepad_button',controller=7,button='South',down=down)
    events=[key(0,'D',True),key(0,'Space',True),key(1,'M',True),key(2,'M',False),key(3,'M',True),key(4,'M',False),
        dict(frame=4,type='gamepad_connection',controller=7,connected=True),pad(4,True),key(4,'Space',False),pad(5,False),pad(6,True),
        key(7,'M',True),key(8,'M',False),pad(8,False),key(9,'M',True),key(9,'Space',True),key(10,'M',False),key(10,'Space',False),key(11,'Space',True),dict(frame=12,release_all=True)]
    path=tmp_path/'input.json'; save_json(path,dict(version=3,events=events))
    a,c=native(b.graph,scene=scene,frames=13,extra=['--input-replay',str(path)])
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    expected=dict(enabled_values=[1,0,0,1,1,1,1,0,0,1,1,1,1],held=[1,0,0,0,0,0,1,0,0,0,0,1,0],
        pressed=[1,0,0,0,0,0,1,0,0,0,0,1,0],released=[0,1,0,0,0,0,0,1,0,0,0,0,1],axis=[1,0,0,1,1,1,1,0,0,1,1,1,0])
    for k,v in expected.items(): assert state['variables'][k]['value']==v,k
    assert state['logs']==['press','release']*3

def test_native_dynamic_context_error_origin(native):
    b=GraphBuilder(); b.add('start','On Game Start'); b.add('name','String',Value='missing'); b.add('set','Set Input Context Enabled')
    b.connect('start','Out','set','In').connect('name','Value','set','Context')
    a,c=native(b.graph,frames=0)
    assert a.returncode==c.returncode==1 and json.loads(a.stderr)==json.loads(c.stderr)
    assert json.loads(a.stderr)['node']=='set'
