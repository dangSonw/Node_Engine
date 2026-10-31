"""Camera authoring, native lens/lifetime behavior and hierarchy invariants."""
from copy import deepcopy
import json
import math
import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QPushButton
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera, create_camera, set_active_camera
from editor.core.document import default_scene, create_project, load_project
from editor.core.scene import validate_scene, entity, set_entity_property, delete_entity
from editor.core.prefabs import add_scene_prefab, instantiate_scene_prefab
from editor.core.prefab_edits import reconcile_prefab_assets, reset_prefab_instance
from editor.ui.camera import CameraDialog
from editor.ui.main_window import MainWindow
from tests.test_entities import pair
from tests.test_native import native


def camera_scene():
    scene = default_scene()
    scene['entities'].append(dict(id='camera', name='Camera', position=[0, 2, 6],
                                 rotation=[0, 0, 0], scale=[1, 1, 1], camera=default_camera()))
    scene['active_camera'] = 'camera'
    return scene


@pytest.mark.parametrize('edit', [{'fov': 0}, {'fov': 180}, {'fov': True}, {'size': 0},
    {'size': float('inf')}, {'near': 0}, {'near': 1000}, {'far': 1e10}, {'projection': 'unknown'}])
def test_camera_boundary_validation(edit):
    scene = camera_scene()
    entity(scene, 'camera')['camera'].update(edit)
    with pytest.raises(ValueError):
        validate_scene(scene)


def test_camera_authoring_undo_dialog_and_save(app, tmp_path):
    path = create_project(tmp_path / 'project', 'Camera authoring')
    window = MainWindow(path, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    try:
        window.actions['Create Camera'].trigger()
        eid = window.selected_entity_id()
        assert window.scene['active_camera'] == eid
        assert entity(window.scene, eid)['camera'] == default_camera()
        def edit():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, CameraDialog)
            dialog.projection.setCurrentText('orthographic')
            dialog.fields['size'].setText('8')
            dialog.fields['near'].setText('1001')
            dialog.accept()
            assert dialog.result() != QDialog.DialogCode.Accepted and dialog.error.text()
            dialog.fields['far'].setText('2000')
            dialog.accept()
        QTimer.singleShot(10, edit)
        next(b for b in window.inspector.findChildren(QPushButton) if b.text() == 'Edit Camera…').click()
        assert entity(window.scene, eid)['camera']['size'] == 8
        window.actions['Undo'].trigger()
        assert entity(window.scene, eid)['camera'] == default_camera()
        window.actions['Redo'].trigger()
        window.actions['Duplicate Entity'].trigger()
        copy = window.selected_entity_id()
        assert entity(window.scene, copy)['camera'] == entity(window.scene, eid)['camera']
        assert window.scene['active_camera'] == eid
        next(b for b in window.inspector.findChildren(QPushButton) if b.text() == 'Use as Game Camera').click()
        assert window.scene['active_camera'] == copy
        window.actions['Delete Entity'].trigger()
        assert 'active_camera' not in window.scene
        window.actions['Undo'].trigger()
        assert window.scene['active_camera'] == copy
        assert window.save_project()
        assert load_project(path)[2] == window.scene
    finally:
        window.saved_signature = window.signature()
        window.close()


def test_native_create_lens_queries_clone_destroy_and_roundtrip(native):
    b = GraphBuilder(); b.add('start', 'On Game Start'); last = 'start'
    def action(nid, name, **values):
        nonlocal last
        b.add(nid, name, **values); b.connect(last, 'Out', nid, 'In'); last = nid
    action('create', 'Create Camera')
    for nid, name, values in [
        ('activate', 'Set Active Camera', {}), ('perspective', 'Set Camera Perspective', {'FOV': 75}),
        ('fov', 'Set Camera FOV', {'Value': 80}), ('orthographic', 'Set Camera Orthographic', {'Height': 12}),
        ('size', 'Set Camera Orthographic Size', {'Value': 8}),
        ('clip', 'Set Camera Clipping Planes', {'Near': .25, 'Far': 400}),
    ]:
        action(nid, name, **values); b.connect('create', 'Camera', nid, 'Camera')
    for nid, name, target, kind in [('has', 'Has Camera', 'Entity', 'Boolean'),
        ('fov_value', 'Get Camera FOV', 'Camera', ''), ('size_value', 'Get Camera Orthographic Size', 'Camera', '')]:
        b.add(nid, name); b.connect('create', 'Camera', nid, target)
        action(nid + '_save', f'Set {kind} Variable'.replace('  ', ' '), Name=nid)
        b.connect(nid, 'Value', nid + '_save', 'Value')
    b.add('selected', 'Get Active Camera')
    action('save_selected', 'Set Entity Variable', Name='selected')
    b.connect('selected', 'Value', 'save_selected', 'Value')
    action('clone', 'Clone Entity'); b.connect('create', 'Camera', 'clone', 'Source')
    result = pair(native, b)
    assert result['variables']['has']['value'] is True
    assert result['variables']['fov_value'] == 80 and result['variables']['size_value'] == 8
    assert result['variables']['selected']['value'] == result['scene']['active_camera'] == 'spawned_1'
    lens = entity(result['scene'], 'spawned_1')['camera']
    assert lens == dict(default_camera(), projection='orthographic', fov=80, size=8, near=.25, far=400)
    assert entity(result['scene'], 'spawned_2')['camera'] == lens
    assert pair(native, GraphBuilder(), result['scene'])['scene'] == result['scene']
    d = GraphBuilder(); d.add('start', 'On Game Start'); d.add('destroy', 'Destroy Entity', Entity='spawned_1')
    d.connect('start', 'Out', 'destroy', 'In')
    assert 'active_camera' not in pair(native, d, result['scene'])['scene']


def rotate(rotation, vector):
    # Independent Y*X*Z basis, applied in reverse order to a column vector.
    x, y, z = map(math.radians, rotation)
    a, b, c = vector
    a, b = math.cos(z)*a-math.sin(z)*b, math.sin(z)*a+math.cos(z)*b
    b, c = math.cos(x)*b-math.sin(x)*c, math.sin(x)*b+math.cos(x)*c
    return [math.cos(y)*a+math.sin(y)*c, b, -math.sin(y)*a+math.cos(y)*c]


def test_native_follow_look_at_scaled_rotated_parent_and_smoothing(native):
    scene = camera_scene()
    entity(scene, 'player')['position'] = [2, 1, -3]
    parent = dict(id='rig', name='Rig', position=[3, -2, 1], rotation=[15, 35, -10], scale=[2, 3, 4])
    scene['entities'].append(parent)
    entity(scene, 'camera')['parent'] = 'rig'
    b = GraphBuilder(); b.add('update', 'On Update'); b.add('follow', 'Camera Follow', Offset=[0, 3, 8])
    b.add('look', 'Camera Look At', Target=[2, 1, -3]); b.add('world', 'Get World Position', Entity='camera')
    b.add('save', 'Set Vector3 Variable', Name='world')
    for a, c in [('update', 'follow'), ('follow', 'look'), ('look', 'save')]: b.connect(a, 'Out', c, 'In')
    b.connect('world', 'Value', 'save', 'Value')
    result = pair(native, b, scene, frames=1)
    assert result['variables']['world']['value'] == pytest.approx([2, 4, 5])
    forward = rotate(parent['rotation'], rotate(result['entities']['camera']['rotation'], [0, 0, -1]))
    assert forward == pytest.approx([0, -3/math.sqrt(73), -8/math.sqrt(73)])
    scene = camera_scene()
    entity(scene, 'camera')['position'] = [0, 0, 0]
    smooth = GraphBuilder(); smooth.add('update', 'On Update'); smooth.add('follow', 'Camera Follow', Offset=[10, 0, 0], Rate=2)
    smooth.connect('update', 'Out', 'follow', 'In')
    result = pair(native, smooth, scene, frames=60)
    assert result['entities']['camera']['position'] == pytest.approx([10*(1-math.exp(-2)), 0, 0])


def test_native_invalid_camera_actions_report_source_nodes(native):
    for name, values in [('Set Camera FOV', {'Value': 180}), ('Set Camera Clipping Planes', {'Near': 1000}),
                         ('Camera Look At', {'Target': [0, 2, 6]}), ('Camera Look At', {'Up': [0, 0, 0]}),
                         ('Camera Follow', {'Rate': -1}), ('Set Active Camera', {'Camera': 'player'})]:
        b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('bad', name, **values)
        b.connect('start', 'Out', 'bad', 'In')
        a, c = native(b.graph, scene=camera_scene(), frames=0)
        assert a.returncode == c.returncode == 1
        assert json.loads(a.stderr) == json.loads(c.stderr)
        assert json.loads(a.stderr)['node'] == 'bad'


def test_camera_prefab_override_propagation_reset_apply_and_removal(native):
    scene = camera_scene()
    scene, aid = add_scene_prefab(scene, 'camera', 'Camera rig')
    scene, first = instantiate_scene_prefab(scene, aid)
    scene, second = instantiate_scene_prefab(scene, aid)
    scene = set_active_camera(scene, first)
    scene = set_entity_property(scene, second, 'camera', dict(default_camera(), fov=90))
    b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('fov', 'Set Camera FOV', Camera=first, Value=70)
    b.add('apply', 'Apply Prefab Overrides', Instance=first)
    b.connect('start', 'Out', 'fov', 'In'); b.connect('fov', 'Out', 'apply', 'In')
    result = pair(native, b, scene)
    assert result['scene']['active_camera'] == first
    assert entity(result['scene'], first)['camera']['fov'] == 70
    assert entity(result['scene'], second)['camera']['fov'] == 90
    assert 'camera' in result['prefab_state']['entities'][second]['owned_components']
    reset = GraphBuilder(); reset.add('start', 'On Game Start'); reset.add('reset', 'Reset Prefab Instance', Instance=second)
    reset.connect('start', 'Out', 'reset', 'In')
    result = pair(native, reset, result['scene'])
    assert entity(result['scene'], second)['camera']['fov'] == 70
    absent = set_entity_property(result['scene'], first, 'camera', None)
    assert 'active_camera' not in absent
    absent = pair(native, GraphBuilder(), absent)['scene']
    assert entity(absent, first).get('camera') is None
    assert 'camera' in next(r for r in absent['prefab_instances'] if r['root'] == first)['owned_components']['root']
    assert entity(reset_prefab_instance(absent, first), first)['camera']['fov'] == 70
    assets = deepcopy(result['scene']['prefab_assets'])
    next(a for a in assets if a['id'] == aid)['overrides']['root']['camera'] = None
    removed = reconcile_prefab_assets(result['scene'], assets)
    assert 'active_camera' not in removed
    assert 'active_camera' not in pair(native, GraphBuilder(), removed)['scene']
