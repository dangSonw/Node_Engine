import json
import subprocess
from copy import deepcopy
import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QDialog, QApplication
from editor.core.input import empty_input, validate_input
from editor.core.document import default_scene, create_project, load_project, save_json
from editor.core.compiler import compile_graph, GraphError
from editor.core.builder import GraphBuilder
from editor.ui.input import InputDialog
from editor.ui.main_window import MainWindow
from tests.test_native import native


def bindings():
    return {'version': 1, 'actions': {'jump': ['Space', 'MouseLeft']},
            'axes': {'horizontal': {'negative': ['A', 'Left'], 'positive': ['D', 'Right']}}}


def gamepad_bindings():
    result = bindings(); result['version'] = 2
    result['actions']['jump'].append(dict(button='South', controller=0))
    result['axes']['horizontal']['gamepads'] = [dict(axis='LeftX', controller=0, dead_zone=.2, invert=False)]
    result['axes']['trigger'] = dict(negative=[], positive=[], gamepads=[dict(axis='RightTrigger', controller=7, dead_zone=0, invert=True)])
    return result


def invalid_gamepad_bindings():
    base = gamepad_bindings(); result = []
    for field, values in [('button', ['A', 1]), ('controller', [-1, True, 4294967296, 1.5])]:
        for value in values:
            bad = deepcopy(base); bad['actions']['jump'][-1][field] = value; result.append(bad)
    for field, values in [('axis', ['Bad', False]), ('controller', [True, -1]),
                          ('dead_zone', [-.1, 1, True, float('nan')]), ('invert', [0, 'false'])]:
        for value in values:
            bad = deepcopy(base); bad['axes']['horizontal']['gamepads'][0][field] = value; result.append(bad)
    bad = deepcopy(base); bad['version'] = 1; result.append(bad)
    bad = deepcopy(base); bad['actions']['jump'].append(deepcopy(bad['actions']['jump'][-1])); result.append(bad)
    bad = deepcopy(base); bad['axes']['horizontal']['gamepads'] *= 2; result.append(bad)
    bad = deepcopy(base); bad['axes']['trigger']['gamepads'] = []; result.append(bad)
    bad = deepcopy(base); bad['axes']['trigger'].pop('gamepads'); result.append(bad)
    bad = deepcopy(base); bad['axes']['trigger']['extra'] = 0; result.append(bad)
    return result


@pytest.mark.parametrize('bad', invalid_gamepad_bindings())
def test_reject_invalid_gamepad_bindings(bad):
    with pytest.raises(ValueError): validate_input(bad)


def test_gamepad_binding_dialog_roundtrip_and_errors(app, tmp_path):
    source = gamepad_bindings(); assert validate_input(source) == source
    dialog = InputDialog(source); dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted and dialog.result_input == source
    dialog = InputDialog(bindings()); dialog.add_gamepad_row('Action', 'jump', positive='South')
    row = dialog.add_gamepad_row('Analog axis', 'horizontal', positive='LeftX', dead_zone=.2)
    dialog.gamepad_table.cellWidget(row, 5).setText('nan'); dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted and dialog.error.text()
    dialog.gamepad_table.cellWidget(row, 5).setText('0.2')
    dialog.gamepad_table.cellWidget(row, 4).setText('4294967296'); dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted and dialog.error.text()
    dialog.gamepad_table.cellWidget(row, 4).setText('0')
    dialog.add_gamepad_row('Analog axis', 'trigger', positive='RightTrigger', controller=7, dead_zone=0, invert=True)
    dialog.accept(); assert dialog.result_input == source
    dialog = InputDialog(empty_input())
    row = dialog.add_gamepad_row('Axis buttons', 'dpad', negative='DpadLeft', positive='DpadRight', controller=4294967295)
    dialog.accept(); result = dialog.result_input
    assert result['axes']['dpad']['negative'] == [dict(button='DpadLeft', controller=4294967295)]
    reopened = InputDialog(result); reopened.accept(); assert reopened.result_input == result
    path = create_project(tmp_path/'pads', 'Controller authoring')
    window = MainWindow(path, QSettings(str(tmp_path/'pads.ini'), QSettings.IniFormat))
    def edit():
        active=QApplication.activeModalWidget(); assert isinstance(active, InputDialog)
        active.add_gamepad_row('Action','jump',positive='South')
        active.add_gamepad_row('Analog axis','horizontal',positive='LeftX'); active.accept()
    try:
        QTimer.singleShot(10,edit); window.actions['Input Actions and Axes…'].trigger()
        expected=deepcopy(window.scene['input']); assert expected['version']==2
        window.actions['Undo'].trigger(); assert 'input' not in window.scene
        window.actions['Redo'].trigger(); assert window.scene['input']==expected
        assert window.save_project() and load_project(path)[2]['input']==expected
    finally:
        window.saved_signature=window.signature(); window.close()


def test_native_mixed_gamepad_action_and_analog_bindings(native, tmp_path):
    graph,scene=trace_graph(); scene['input']=gamepad_bindings()
    def pad(f,id,button,down): return dict(frame=f,type='gamepad_button',controller=id,button=button,down=down)
    def connect(f,id,on=True): return dict(frame=f,type='gamepad_connection',controller=id,connected=on)
    def axis(f,id,value): return dict(frame=f,type='gamepad_axis',controller=id,axis='LeftX',value=value)
    def key(f,button,down): return dict(frame=f,button=button,down=down)
    events=[connect(0,7),connect(0,9),axis(0,7,.6),axis(0,9,-.9),key(0,'Space',True),pad(0,7,'South',True),
        key(1,'Space',False),pad(1,9,'South',True),pad(1,7,'South',False),axis(1,9,0),
        connect(2,9,False),key(2,'D',True),pad(3,7,'South',True),pad(3,7,'South',False),pad(3,7,'South',True),key(3,'A',True),
        dict(frame=4,release_all=True),pad(5,7,'South',True),key(5,'Space',True),connect(5,7,False),key(6,'Space',False),
        connect(7,8),pad(7,8,'South',True),axis(7,8,-1)]
    replay=tmp_path/'mapped.json'; save_json(replay,dict(version=3,events=events))
    a,b=native(graph,frames=8,scene=scene,extra=['--input-replay',str(replay)])
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    state=json.loads(a.stdout); assert state==json.loads(b.stdout) and state['scene']['input']==scene['input']
    expected=dict(held=[1,1,0,1,0,1,0,1],pressed=[1,0,0,1,0,1,0,1],released=[0,0,1,1,1,0,1,0],
        pressed_again=[1,0,0,1,0,1,0,1],key_down=[1,0,0,0,0,1,0,0],key_up=[0,1,0,0,0,0,1,0],axis=[-.875,.5,1,.5,0,0,0,-1])
    for k,v in expected.items(): assert state['variables'][k]['value']==pytest.approx(v),k


@pytest.mark.parametrize('bad', [None, [], {}, {'version': True, 'actions': {}, 'axes': {}},
    {'version': 1, 'actions': {'x': ['space']}, 'axes': {}},
    {'version': 1, 'actions': {'x': ['Space', 'Space']}, 'axes': {}},
    {'version': 1, 'actions': {'x\x00': ['Space']}, 'axes': {}},
    {'version': 1, 'actions': {}, 'axes': {'x': {'negative': ['A'], 'positive': ['A']}}},
    {'version': 1, 'actions': {}, 'axes': {'x': {'negative': [], 'positive': ['D']}}}])
def test_reject_invalid_bindings(bad):
    with pytest.raises(ValueError):
        validate_input(bad)


def test_input_dialog_and_scene_undo_save(app, tmp_path):
    dialog = InputDialog(bindings())
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.result_input == bindings()
    dialog = InputDialog(empty_input())
    dialog.add_row('Action', 'jump', '', 'Space')
    dialog.add_row('Action', 'jump', '', 'Space')
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted and dialog.error.text()
    dialog.table.cellWidget(1, 3).setCurrentText('MouseLeft')
    dialog.accept()
    assert dialog.result_input['actions']['jump'] == ['Space', 'MouseLeft']
    path = create_project(tmp_path / 'project', 'Input authoring')
    window = MainWindow(path, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    def edit():
        active = QApplication.activeModalWidget()
        assert isinstance(active, InputDialog)
        active.add_row('Action', 'jump', '', 'Space')
        active.add_row('Axis', 'horizontal', 'A', 'D')
        active.accept()
    try:
        QTimer.singleShot(10, edit)
        window.actions['Input Actions and Axes…'].trigger()
        assert window.scene['input']['axes']['horizontal']['positive'] == ['D']
        assert window.dirty
        window.actions['Undo'].trigger()
        assert 'input' not in window.scene
        window.actions['Redo'].trigger()
        assert window.save_project()
        assert load_project(path)[2]['input'] == window.scene['input']
    finally:
        window.saved_signature = window.signature()
        window.close()


def trace_graph():
    b = GraphBuilder('Input transitions')
    b.add('update', 'On Update')
    scene = default_scene()
    scene['input'] = bindings()
    previous = 'update'
    for key, name, values, label in [
        ('held', 'Is Action Held', {}, 'Boolean'),
        ('pressed', 'Is Action Pressed', {}, 'Boolean'),
        ('released', 'Is Action Released', {}, 'Boolean'),
        ('pressed_again', 'Is Action Pressed', {}, 'Boolean'),
        ('key_down', 'Is Key Pressed', {}, 'Boolean'),
        ('key_up', 'Is Key Released', {}, 'Boolean'),
        ('axis', 'Get Input Axis', {}, 'Float'),
    ]:
        kind = 'float' if label == 'Float' else 'bool'
        scene['variables'][key] = {'type': f'array<{kind}>', 'value': []}
        b.add(key, name, **values)
        b.add(key + '_get', f'Get {label} Array Variable', Name=key)
        b.add(key + '_append', f'Append {label} Item')
        b.add(key + '_save', f'Set {label} Array Variable', Name=key)
        b.connect(key + '_get', 'Value', key + '_append', 'Array')
        b.connect(key, 'Value', key + '_append', 'Item')
        b.connect(key + '_append', 'Value', key + '_save', 'Value')
        b.connect(previous, 'Out', key + '_save', 'In')
        previous = key + '_save'
    return b.graph, scene


def test_native_input_replay_edges_axes_and_compiled_parity(native, tmp_path):
    graph, scene = trace_graph()
    sequence = [(0, 'D', True), (0, 'Space', True), (1, 'D', True),
                (1, 'MouseLeft', True), (1, 'Space', False), (2, 'MouseLeft', False),
                (2, 'D', False), (2, 'A', True), (2, 'D', True), (3, 'A', False),
                (4, 'Space', True), (4, 'Space', False), (5, 'Space', True)]
    events = [dict(frame=f, button=k, down=d) for f, k, d in sequence]
    events += [{'frame': 5, 'release_all': True}, {'frame': 7, 'button': 'A', 'down': True}]
    replay = tmp_path / 'input.json'
    save_json(replay, {'version': 1, 'events': events})
    left, right = native(graph, frames=8, scene=scene, extra=['--input-replay', str(replay)])
    assert left.returncode == right.returncode == 0, left.stderr + right.stderr
    state = json.loads(left.stdout)
    assert state == json.loads(right.stdout)
    assert state['scene']['input'] == bindings()
    expected = {
        'held': [1,1,0,0,0,0,0,0], 'pressed': [1,0,0,0,1,1,0,0],
        'released': [0,0,1,0,1,1,0,0], 'pressed_again': [1,0,0,0,1,1,0,0],
        'key_down': [1,0,0,0,1,1,0,0], 'key_up': [0,1,0,0,1,1,0,0],
        'axis': [1,1,0,1,1,0,0,-1],
    }
    assert {k: v['value'] for k, v in state['variables'].items()} == expected
    # Invalid replay input must fail before the graph runs in either binary.
    for events in [
        [{'frame': 0, 'button': 'Typo', 'down': True}],
        [{'frame': -1, 'button': 'D', 'down': True}],
        [{'frame': 1.5, 'button': 'D', 'down': True}],
        [{'frame': True, 'button': 'D', 'down': True}],
        [{'frame': 0, 'button': 'D', 'down': 1}],
        [{'frame': 0, 'release_all': False}],
        [{'frame': 1, 'release_all': True}, {'frame': 0, 'release_all': True}],
    ]:
        save_json(replay, {'version': 1, 'events': events})
        runs = [subprocess.run(r.args, capture_output=True, text=True, timeout=10) for r in (left, right)]
        assert all(r.returncode == 1 for r in runs)
        assert json.loads(runs[0].stderr) == json.loads(runs[1].stderr)
    # Preview loads untrusted scene JSON, independently of Python compilation.
    save_json(replay, {'version': 1, 'events': []})
    from pathlib import Path
    ir_path = Path(left.args[left.args.index('--ir') + 1])
    ir = json.loads(ir_path.read_text('utf-8'))
    for invalid in (None, {'version': True, 'actions': {}, 'axes': {}},
                    {'version': 1, 'actions': {'jump': ['Typo']}, 'axes': {}}):
        ir['scene']['input'] = invalid
        save_json(ir_path, ir)
        run = subprocess.run(left.args, capture_output=True, text=True, timeout=10)
        assert run.returncode == 1 and json.loads(run.stderr)['event'] == 'node_error'


def test_dynamic_missing_action_reports_runtime_node_in_both_paths(native):
    b = GraphBuilder('Dynamic action error')
    for nid, name, values in [('start', 'On Game Start', {}),
                               ('name', 'String', {'Value': 'missing'}),
                               ('query', 'Is Action Pressed', {}), ('assert', 'Assert', {})]:
        b.add(nid, name, **values)
    b.connect('start', 'Out', 'assert', 'In')
    b.connect('name', 'Value', 'query', 'Action')
    b.connect('query', 'Value', 'assert', 'Condition')
    left, right = native(b.graph, frames=0)
    assert left.returncode == right.returncode == 1
    assert json.loads(left.stderr) == json.loads(right.stderr)
    assert json.loads(left.stderr)['node'] == 'query'


def test_unknown_static_input_names_are_attached_to_node():
    b = GraphBuilder('Missing action')
    b.add('start', 'On Game Start')
    b.add('missing', 'Is Action Held', Action='missing')
    b.add('assert', 'Assert')
    b.connect('start', 'Out', 'assert', 'In')
    b.connect('missing', 'Value', 'assert', 'Condition')
    with pytest.raises(GraphError) as error:
        compile_graph(b.graph, default_scene())
    assert error.value.problems[0].node == 'missing'
