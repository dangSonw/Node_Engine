"""Sprite authoring, image validation, prefab portability and native node parity."""
from copy import deepcopy
import json
import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QSpinBox, QCheckBox
from editor.core import sprites as s
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, create_project, load_project, save_json
from editor.core.scene import entity, set_entity_property, validate_scene
from editor.core.prefabs import add_scene_prefab, instantiate_scene_prefab, PrefabLibrary
from editor.core.prefab_edits import reset_prefab_instance, apply_prefab_overrides
from editor.core.prefab_import import import_project_prefabs, register_prefab_files
from editor.ui.main_window import MainWindow
from editor.ui.sprites import SpriteLibraryDialog, SpriteAssetDialog
from tests.test_entities import pair
from tests.test_native import native
from tools.create_sprite_demo import create


def sprite_scene():
    scene = default_scene()
    scene['sprite_assets'] = [dict(s.new_asset('assets/atlas.png'), id='atlas', columns=2, rows=2)]
    scene['entities'][0]['sprite'] = s.binding('atlas')
    scene['entities'].append(dict(deepcopy(scene['entities'][0]), id='other'))
    return scene


@pytest.mark.parametrize('change', [dict(version=True), dict(id='bad/id'), dict(name=''), dict(columns=True),
    dict(rows=0), dict(columns=8193), dict(columns=8192, rows=9), dict(width=0), dict(height=float('nan')),
    dict(pivot=[0, 2]), dict(pivot=[0]), dict(filter='mips'), dict(texture='../atlas.png'),
    dict(texture='assets/../atlas.png'), dict(texture='image.png'), dict(texture='assets/a.svg'),
    dict(texture='assets//atlas.png'), dict(texture='assets/./atlas.png'), dict(texture='assets/a:atlas.png')])
def test_invalid_sprite_assets(change):
    scene = sprite_scene(); scene['sprite_assets'][0].update(change)
    with pytest.raises(ValueError): validate_scene(scene)


@pytest.mark.parametrize('change', [dict(asset='missing'), dict(frame=-1), dict(frame=4), dict(frame=True),
                                  dict(flip_x=1), dict(flip_y='false'), dict(unknown=0)])
def test_binding_validation_is_transactional(change):
    scene = sprite_scene(); before = deepcopy(scene)
    with pytest.raises(ValueError): set_entity_property(scene, 'player', 'sprite', dict(s.binding('atlas'), **change))
    assert scene == before


def test_assets_prefab_dependencies_edits_and_relocation(tmp_path):
    source = create(tmp_path / 'source'); path = source / 'project.json'
    _, _, scene = load_project(path)
    scene, aid = add_scene_prefab(scene, 'player', 'Sprite prefab')
    assert scene['prefab_assets'][0]['sprite_assets'] == scene['sprite_assets']
    scene, first = instantiate_scene_prefab(scene, aid)
    scene = set_entity_property(scene, first, 'sprite', dict(s.binding('atlas'), frame=3))
    applied = apply_prefab_overrides(scene, first)
    assert PrefabLibrary(applied['prefab_assets']).resolve(aid)['entities'][0]['sprite']['frame'] == 3
    assert entity(reset_prefab_instance(scene, first), first)['sprite']['frame'] == 0
    with pytest.raises(ValueError, match='unknown'): s.remove_asset(scene, 'atlas')
    with pytest.raises(ValueError, match='outside'): s.put_asset(scene, dict(scene['sprite_assets'][0], columns=1, rows=1))
    save_json(source / 'scenes/main.json', applied)
    destination = tmp_path / 'destination'; destination.mkdir()
    imported = import_project_prefabs(default_scene(), destination, path)
    copied = s.texture_file(destination, imported['sprite_assets'][0])
    assert copied.read_bytes() == (source / 'assets/atlas.png').read_bytes()
    assert imported['prefab_assets'][0]['sprite_assets'] == imported['sprite_assets']
    source.rename(tmp_path / 'source-moved')
    imported, root = instantiate_scene_prefab(imported, aid)
    assert entity(imported, root)['sprite']['frame'] == 3
    assert s.texture_file(destination, imported['sprite_assets'][0]) == copied


def test_image_import_and_grid_rejection(tmp_path):
    source = create(tmp_path / 'source')
    root = tmp_path / 'project'; root.mkdir()
    scene, sid = s.import_texture(default_scene(), root, source / 'assets/atlas.png')
    asset = scene['sprite_assets'][0]
    assert sid == asset['id'] and s.inspect_texture(root / asset['texture']) == (64, 64)
    with pytest.raises(ValueError, match='divide'): s.texture_file(root, dict(asset, columns=3))
    broken = root / 'broken.png'; broken.write_bytes(b'not an image')
    with pytest.raises(ValueError): s.import_texture(scene, root, broken)


def test_inspector_library_undo_save_and_node_picker(app, tmp_path):
    source = create(tmp_path / 'source')
    path = create_project(tmp_path / 'editor', 'Sprite authoring')
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    window = MainWindow(path, settings); window.show()
    try:
        def library():
            dialog = QApplication.activeModalWidget(); assert isinstance(dialog, SpriteLibraryDialog)
            dialog.import_image(source / 'assets/atlas.png')
            def atlas():
                edit = QApplication.activeModalWidget(); assert isinstance(edit, SpriteAssetDialog)
                edit.fields['columns'].setText('2'); edit.fields['rows'].setText('2'); edit.accept()
            QTimer.singleShot(10, atlas); dialog.edit(); dialog.accept()
        QTimer.singleShot(10, library); window.actions['Sprites…'].trigger()
        sid = window.scene['sprite_assets'][0]['id']; window.refresh_hierarchy('player')
        picker = next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName() == 'player sprite')
        picker.setCurrentIndex(picker.findData(sid)); picker.activated.emit(picker.currentIndex()); app.processEvents()
        frame = next(w for w in window.inspector.findChildren(QSpinBox) if w.accessibleName() == 'player sprite frame')
        frame.setValue(3); frame.editingFinished.emit(); app.processEvents()
        assert entity(window.scene, 'player')['sprite']['frame'] == 3
        window.actions['Undo'].trigger(); assert entity(window.scene, 'player')['sprite']['frame'] == 0
        window.actions['Redo'].trigger(); assert entity(window.scene, 'player')['sprite']['frame'] == 3
        flip = next(w for w in window.inspector.findChildren(QCheckBox) if w.accessibleName() == 'player sprite flip_x')
        flip.click(); app.processEvents(); assert entity(window.scene, 'player')['sprite']['flip_x']
        assert window.save_project() and load_project(path)[2] == window.scene
        b = GraphBuilder(); b.add('set', 'Set Sprite', Sprite=sid); window.adapter.load(b.graph)
        window.inspect_node(window.adapter.graph.all_nodes()[0])
        picker = next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName() == 'Set Sprite Sprite')
        assert picker.currentData() == sid
    finally:
        window.saved_signature = window.signature(); window.document_changed(); window.close()


def test_native_nodes_clone_isolation_and_roundtrip(native):
    scene = sprite_scene(); b = GraphBuilder(); b.add('start', 'On Game Start'); last = 'start'
    def action(nid, name, **values):
        nonlocal last
        b.add(nid, name, **values); b.connect(last, 'Out', nid, 'In'); last = nid
    action('assign', 'Set Sprite', Sprite='atlas'); action('frame', 'Set Sprite Frame', Frame=3)
    action('flip', 'Set Sprite Flip', **{'Flip X': True, 'Flip Y': True})
    for nid, name, kind in [('id', 'Get Sprite', 'String'), ('frame_value', 'Get Sprite Frame', 'Integer'),
        ('count', 'Get Sprite Frame Count', 'Integer'), ('flip_x', 'Get Sprite Flip X', 'Boolean'),
        ('flip_y', 'Get Sprite Flip Y', 'Boolean'), ('exists', 'Sprite Exists', 'Boolean')]:
        b.add(nid, name, **({'Sprite': 'atlas'} if nid == 'exists' else {}))
        action('save_'+nid, f'Set {kind} Variable', Name=nid); b.connect(nid, 'Value', 'save_'+nid, 'Value')
    action('clone', 'Clone Entity', Source='player'); action('clear', 'Clear Sprite')
    result = pair(native, b, scene)
    assert {k: v['value'] for k, v in result['variables'].items()} == dict(id='atlas', frame_value=3, count=4, flip_x=True, flip_y=True, exists=True)
    assert entity(result['scene'], 'other')['sprite'] == s.binding('atlas')
    assert entity(result['scene'], 'player').get('sprite') is None
    assert entity(result['scene'], 'spawned_1')['sprite'] == dict(s.binding('atlas'), frame=3, flip_x=True, flip_y=True)
    assert pair(native, GraphBuilder(), result['scene'])['scene'] == result['scene']


def test_native_prefab_apply_and_reset(native):
    scene, aid = add_scene_prefab(sprite_scene(), 'player', 'Sprite prefab')
    scene, first = instantiate_scene_prefab(scene, aid); scene, second = instantiate_scene_prefab(scene, aid)
    scene = set_entity_property(scene, second, 'sprite', dict(s.binding('atlas'), frame=2))
    b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('frame', 'Set Sprite Frame', Entity=first, Frame=3)
    b.add('apply', 'Apply Prefab Overrides', Instance=first)
    b.connect('start', 'Out', 'frame', 'In'); b.connect('frame', 'Out', 'apply', 'In')
    result = pair(native, b, scene)
    assert entity(result['scene'], second)['sprite']['frame'] == 2
    expected = apply_prefab_overrides(set_entity_property(scene, first, 'sprite', dict(s.binding('atlas'), frame=3)), first)
    assert result['scene']['prefab_assets'] == expected['prefab_assets']
    reset = GraphBuilder(); reset.add('start', 'On Game Start'); reset.add('reset', 'Reset Prefab Instance', Instance=second)
    reset.connect('start', 'Out', 'reset', 'In'); result = pair(native, reset, result['scene'])
    assert entity(result['scene'], second)['sprite']['frame'] == 3
    cleared = set_entity_property(result['scene'], first, 'sprite', None)
    assert entity(pair(native, GraphBuilder(), cleared)['scene'], first).get('sprite') is None


def test_invalid_nodes_report_source(native):
    for name, values in [('Set Sprite', {'Sprite': 'missing'}), ('Set Sprite Frame', {'Frame': -1}),
                         ('Set Sprite Frame', {'Frame': 4}), ('Set Sprite Flip', {'Entity': 'missing'})]:
        b = GraphBuilder(); b.add('start', 'On Game Start'); b.add('bad', name, **values); b.connect('start', 'Out', 'bad', 'In')
        a, c = native(b.graph, scene=sprite_scene(), frames=0)
        assert a.returncode == c.returncode == 1 and json.loads(a.stderr) == json.loads(c.stderr)
        assert json.loads(a.stderr)['node'] == 'bad'
