"""Shared material assets, instance isolation, authoring and native execution parity."""
from copy import deepcopy
import json
import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QPushButton
from editor.core import materials as m
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, create_project, load_project, save_json
from editor.core.scene import entity, set_entity_property, validate_scene
from editor.core.prefabs import add_scene_prefab, instantiate_scene_prefab, PrefabLibrary
from editor.core.prefab_edits import reset_prefab_instance, apply_prefab_overrides
from editor.core.prefab_import import import_project_prefabs
from editor.ui.main_window import MainWindow
from editor.ui.materials import MaterialLibraryDialog, MaterialParametersDialog
from tests.test_entities import pair
from tests.test_native import native


def material_scene():
    scene = default_scene()
    scene['material_assets'] = [dict(m.new_asset('Shared'), id='shared', unlit=True)]
    scene['entities'][0]['material'] = {'asset': 'shared', 'overrides': {}}
    scene['entities'].append(dict(deepcopy(scene['entities'][0]), id='other'))
    return scene


@pytest.mark.parametrize('change', [dict(color=[1, 2, 0]), dict(color=[True, 0, 0]),
    dict(color=[1, 0]), dict(opacity=float('nan')), dict(opacity=-.1), dict(opacity=True),
    dict(alpha_cutoff=1.1), dict(alpha_mode='BLEND'), dict(unlit=1), dict(unknown=1)])
def test_invalid_material_parameters_rejected(change):
    scene = material_scene(); before = deepcopy(scene)
    with pytest.raises(ValueError):
        set_entity_property(scene, 'player', 'material', {'asset': 'shared', 'overrides': change})
    assert scene == before


@pytest.mark.parametrize('change', [dict(version=True), dict(type='shader'), dict(id='bad/id'),
    dict(name=''), dict(name='bad\nname'), dict(name='é'*257)])
def test_invalid_assets_rejected(change):
    scene = material_scene(); scene['material_assets'][0].update(change)
    with pytest.raises(ValueError): validate_scene(scene)


def test_material_asset_reference_conflicts_and_transactional_editing():
    scene = material_scene(); original = deepcopy(scene)
    with pytest.raises(ValueError, match='unknown'): m.remove_asset(scene, 'shared')
    with pytest.raises(ValueError, match='unknown'):
        set_entity_property(scene, 'player', 'material', {'asset': 'missing', 'overrides': {}})
    assert scene == original
    changed = m.put_asset(scene, dict(scene['material_assets'][0], color=[.25, .5, .75]))
    assert m.effective_parameters(changed, entity(changed, 'other')['material'])['color'] == [.25, .5, .75]
    assert scene == original
    changed, aid = add_scene_prefab(changed, 'player', 'Shared prefab')
    assert changed['prefab_assets'][0]['material_assets'] == changed['material_assets']
    changed = m.put_asset(changed, dict(changed['material_assets'][0], opacity=.4))
    assert changed['prefab_assets'][0]['material_assets'] == changed['material_assets']
    lib = PrefabLibrary(changed['prefab_assets'])
    lib.material_assets[0]['name'] = 'mutating returned copies is harmless'
    assert lib.material_assets[0]['name'] == 'Shared'
    with pytest.raises(ValueError, match='Conflicting'):
        PrefabLibrary(changed['prefab_assets'], material_assets=scene['material_assets'])
    for invalid in [[None], {}, None]:
        with pytest.raises(ValueError): validate_scene(dict(scene, prefab_assets=invalid))


def test_portable_prefab_materials_and_import_conflict(tmp_path):
    source = create_project(tmp_path / 'source', 'Source')
    scene, aid = add_scene_prefab(material_scene(), 'player', 'Portable')
    save_json(source.parent / 'scenes/main.json', scene)
    target = create_project(tmp_path / 'target', 'Target')
    imported = import_project_prefabs(default_scene(), target.parent, source)
    placed, root = instantiate_scene_prefab(imported, aid)
    assert m.effective_parameters(placed, entity(placed, root)['material'])['unlit'] is True
    conflict = m.put_asset(default_scene(), dict(scene['material_assets'][0], color=[0, 0, 0]))
    before = deepcopy(conflict)
    with pytest.raises(ValueError, match='Conflicting'): import_project_prefabs(conflict, target.parent, source)
    assert conflict == before
    source.parent.rename(tmp_path / 'source-moved')
    save_json(target.parent / 'scenes/main.json', placed)
    assert load_project(target)[2] == placed


def test_material_authoring_dialogs_undo_save_and_node_picker(app, tmp_path):
    path = create_project(tmp_path / 'project', 'Materials')
    window = MainWindow(path, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    try:
        def parameters():
            dialog = QApplication.activeModalWidget(); assert isinstance(dialog, MaterialParametersDialog)
            dialog.name.setText('Shared blue'); dialog.color[0].setText('invalid'); dialog.accept()
            assert dialog.result() != QDialog.DialogCode.Accepted and dialog.error.text()
            dialog.color[0].setText('.25'); dialog.unlit.setChecked(True); dialog.accept()
        def library():
            dialog = QApplication.activeModalWidget(); assert isinstance(dialog, MaterialLibraryDialog)
            QTimer.singleShot(10, parameters); dialog.create(); dialog.accept()
        QTimer.singleShot(10, library); window.actions['Materials…'].trigger()
        asset = window.scene['material_assets'][0]; mid = asset['id']
        window.refresh_hierarchy('player')
        combo = next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName() == 'player material')
        combo.setCurrentIndex(combo.findData(mid)); combo.activated.emit(combo.currentIndex()); app.processEvents()
        assert entity(window.scene, 'player')['material'] == {'asset': mid, 'overrides': {}}
        def instance():
            dialog = QApplication.activeModalWidget(); assert isinstance(dialog, MaterialParametersDialog)
            dialog.fields['opacity'].setText('.5'); dialog.mode.setCurrentText('blend'); dialog.accept()
        QTimer.singleShot(10, instance)
        next(w for w in window.inspector.findChildren(QPushButton) if w.text() == 'Edit Material Instance…').click()
        assert entity(window.scene, 'player')['material']['overrides'] == {'opacity': .5, 'alpha_mode': 'blend'}
        window.actions['Undo'].trigger(); assert not entity(window.scene, 'player')['material']['overrides']
        window.actions['Redo'].trigger(); assert entity(window.scene, 'player')['material']['overrides']['opacity'] == .5
        next(w for w in window.inspector.findChildren(QPushButton) if w.text() == 'Reset Material Parameters').click()
        assert not entity(window.scene, 'player')['material']['overrides']
        assert window.save_project() and load_project(path)[2] == window.scene
        b = GraphBuilder(); b.add('set', 'Set Material', Material=mid)
        window.adapter.load(b.graph)
        node = window.adapter.graph.all_nodes()[0]; window.inspect_node(node)
        picker = next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName() == 'Set Material Material')
        assert picker.currentData() == mid and picker.currentText() == 'Shared blue'
    finally:
        window.saved_signature = window.signature(); window.close()


def test_native_material_nodes_all_parameters_isolation_clone_and_roundtrip(native):
    scene = material_scene()
    b = GraphBuilder(); b.add('start', 'On Game Start'); last = 'start'
    def action(nid, name, **values):
        nonlocal last
        b.add(nid, name, **values); b.connect(last, 'Out', nid, 'In'); last = nid
    for nid, name, values in [('assign', 'Set Material', {'Material': 'shared'}),
        ('color', 'Set Material Color', {'Color': [.2, .4, .6]}), ('opacity', 'Set Material Opacity', {'Opacity': .3}),
        ('mode', 'Set Material Alpha Mode', {'Mode': 'blend'}), ('cutoff', 'Set Material Alpha Cutoff', {'Cutoff': .7}),
        ('unlit', 'Set Material Unlit', {'Unlit': False})]: action(nid, name, **values)
    for nid, name, kind in [('id', 'Get Material', 'String'), ('rgb', 'Get Material Color', 'Vector3'),
        ('alpha', 'Get Material Opacity', ''), ('alpha_mode', 'Get Material Alpha Mode', 'String'),
        ('alpha_cutoff', 'Get Material Alpha Cutoff', ''), ('unlit_value', 'Is Material Unlit', 'Boolean'),
        ('exists', 'Material Exists', 'Boolean')]:
        b.add(nid, name, **({'Material': 'shared'} if nid == 'exists' else {}))
        action('save_' + nid, f'Set {kind} Variable'.replace('  ', ' '), Name=nid)
        b.connect(nid, 'Value', 'save_' + nid, 'Value')
    action('clone', 'Clone Entity', Source='player')
    action('reset', 'Reset Material Parameters')
    result = pair(native, b, scene)
    values = result['variables']
    assert values['id']['value'] == 'shared' and values['rgb']['value'] == [.2, .4, .6]
    assert values['alpha'] == .3 and values['alpha_cutoff'] == .7
    assert values['alpha_mode']['value'] == 'blend' and values['unlit_value']['value'] is False
    assert values['exists']['value'] is True
    assert entity(result['scene'], 'other')['material']['overrides'] == {}
    assert entity(result['scene'], 'player')['material']['overrides'] == {}
    assert entity(result['scene'], 'spawned_1')['material']['overrides']['color'] == [.2, .4, .6]
    assert pair(native, GraphBuilder(), result['scene'])['scene'] == result['scene']
    clear = GraphBuilder(); clear.add('start', 'On Game Start'); clear.add('clear', 'Clear Material')
    clear.connect('start', 'Out', 'clear', 'In')
    assert entity(pair(native, clear, result['scene'])['scene'], 'player').get('material') is None


def test_native_material_prefab_apply_reset_clear(native):
    scene, aid = add_scene_prefab(material_scene(), 'player', 'Material prefab')
    scene, first = instantiate_scene_prefab(scene, aid); scene, second = instantiate_scene_prefab(scene, aid)
    scene = set_entity_property(scene, second, 'material', {'asset': 'shared', 'overrides': {'color': [0, 1, 0]}})
    b = GraphBuilder(); b.add('start', 'On Game Start')
    b.add('color', 'Set Material Color', Entity=first, Color=[1, 0, 0])
    b.add('apply', 'Apply Prefab Overrides', Instance=first)
    b.connect('start', 'Out', 'color', 'In'); b.connect('color', 'Out', 'apply', 'In')
    result = pair(native, b, scene)
    assert m.effective_parameters(result['scene'], entity(result['scene'], first)['material'])['color'] == [1, 0, 0]
    assert m.effective_parameters(result['scene'], entity(result['scene'], second)['material'])['color'] == [0, 1, 0]
    expected = apply_prefab_overrides(set_entity_property(scene, first, 'material', {'asset': 'shared', 'overrides': {'color': [1, 0, 0]}}), first)
    assert entity(expected, second)['material'] == entity(result['scene'], second)['material']
    reset = GraphBuilder(); reset.add('start', 'On Game Start'); reset.add('reset', 'Reset Prefab Instance', Instance=second)
    reset.connect('start', 'Out', 'reset', 'In')
    result = pair(native, reset, result['scene'])
    assert entity(result['scene'], second)['material']['overrides']['color'] == [1, 0, 0]
    absent = set_entity_property(result['scene'], first, 'material', None)
    absent = pair(native, GraphBuilder(), absent)['scene']
    assert entity(absent, first).get('material') is None
    assert 'material' in next(r for r in absent['prefab_instances'] if r['root'] == first)['owned_components']['root']
    assert entity(reset_prefab_instance(absent, first), first)['material']['overrides']['color'] == [1, 0, 0]


def test_native_invalid_material_nodes_report_source(native):
    for name, values in [('Set Material', {'Material': 'missing'}), ('Set Material Opacity', {'Opacity': -1}),
        ('Set Material Color', {'Color': [0, 2, 0]}), ('Set Material Alpha Mode', {'Mode': 'typo'}),
        ('Set Material Alpha Cutoff', {'Cutoff': 2}), ('Reset Material Parameters', {'Entity': 'missing'})]:
        b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('bad', name, **values)
        b.connect('start', 'Out', 'bad', 'In')
        a, c = native(b.graph, scene=material_scene(), frames=0)
        assert a.returncode == c.returncode == 1
        assert json.loads(a.stderr) == json.loads(c.stderr)
        assert json.loads(a.stderr)['node'] == 'bad'
