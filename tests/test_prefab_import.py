from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from editor.core.document import create_project, default_scene, load_project, save_json
from editor.core.prefabs import PrefabLibrary, instantiate_scene_prefab
from editor.core.prefab_import import import_project_prefabs, register_prefab_files
from editor.ui.main_window import MainWindow
from tests.test_prefabs import robot, variant


def source_project(tmp_path):
    project = create_project(tmp_path / 'source', 'Source library')
    mesh = project.parent / 'assets/robot.gltf'
    save_json(mesh, {'asset': {'version': '2.0'}, 'buffers': [{'uri': 'geometry.bin', 'byteLength': 4}],
                     'images': [{'uri': 'textures/blue%20image.png'}]})
    (mesh.parent / 'geometry.bin').write_bytes(b'abcd')
    (mesh.parent / 'textures').mkdir(exist_ok=True)
    (mesh.parent / 'textures/blue image.png').write_bytes(b'image')
    base = robot()
    next(e for e in base['entities'] if e['id'] == 'root')['components']['1']['properties']['4'] = 'assets/robot.gltf'
    inherited = variant(overrides={'root': {'mesh': 'assets/robot.gltf'}})
    pair = dict(version=1, type='prefab', id='pair', name='Pair', root='root',
                entities=[dict(default_scene()['entities'][0], id='root')],
                nested=[dict(id='child', prefab='variant', parent='root',
                             overrides={'root': {'mesh': 'assets/robot.gltf'}})])
    library = PrefabLibrary([base, inherited, pair])
    save_json(project.parent / 'scenes/main.json', dict(entities=[], variables={},
        component_definitions=library.component_definitions, prefab_assets=library.assets))
    return project


def test_import_preserves_dependencies_and_typed_references_with_portable_models(tmp_path):
    source = source_project(tmp_path)
    target = create_project(tmp_path / 'target', 'Target')
    original = default_scene()
    before = deepcopy(original)
    source_bytes = (source.parent / 'scenes/main.json').read_bytes()
    scene = import_project_prefabs(original, target.parent, source)
    assert original == before and scene['entities'] == before['entities']
    assert (source.parent / 'scenes/main.json').read_bytes() == source_bytes
    assets = {a['id']: a for a in scene['prefab_assets']}
    assert assets['variant']['base'] == 'robot' and assets['pair']['nested'][0]['prefab'] == 'variant'
    mesh = assets['robot']['entities'][0]['mesh']
    assert mesh.startswith('assets/prefab-library-') and mesh.endswith('/assets/robot.gltf')
    assert assets['variant']['overrides']['root']['mesh'] == mesh
    assert assets['pair']['nested'][0]['overrides']['root']['mesh'] == mesh
    assert next(e for e in assets['robot']['entities'] if e['id'] == 'root')['components']['1']['properties']['4'] == 'assets/robot.gltf'
    assert (target.parent / mesh).read_bytes() == (source.parent / 'assets/robot.gltf').read_bytes()
    assert (target.parent / mesh).with_name('geometry.bin').read_bytes() == b'abcd'
    assert ((target.parent / mesh).parent / 'textures/blue image.png').read_bytes() == b'image'
    assert len(list((target.parent / 'assets').glob('prefab-library-*'))) == 1
    placed, root = instantiate_scene_prefab(scene, 'pair')
    record = placed['prefab_instances'][0]
    child = next(e for e in placed['entities'] if e['id'] == record['mapping']['child'])
    assert child['components']['1']['properties']['1'] == record['mapping']['child/e1']
    assert root == record['root']
    # Portability must not depend on the continued existence of the source project.
    source.parent.rename(source.parent.with_name('source-moved'))
    save_json(target.parent / 'scenes/main.json', placed)
    assert load_project(target)[2] == placed
    PrefabLibrary(placed['prefab_assets'], placed['component_definitions']).resolve('pair')


@pytest.mark.parametrize('failure', ['duplicate', 'schema', 'missing_model', 'missing_buffer', 'escape', 'dependency'])
def test_invalid_import_preserves_scene_and_files(tmp_path, failure):
    source = source_project(tmp_path)
    target = create_project(tmp_path / 'target', 'Target')
    original_files=sorted((target.parent/'assets').rglob('*'))
    scene = default_scene()
    source_scene = load_project(source)[2]
    if failure == 'duplicate':
        scene.update(prefab_assets=[robot()], component_definitions=robot()['component_definitions'])
    elif failure == 'schema':
        scene['component_definitions'] = deepcopy(robot()['component_definitions'])
        scene['component_definitions'][0]['properties'][0]['type'] = 'string'
    elif failure == 'missing_model':
        (source.parent / 'assets/robot.gltf').unlink()
    elif failure == 'missing_buffer':
        (source.parent / 'assets/geometry.bin').unlink()
    elif failure == 'escape':
        model = json.loads((source.parent / 'assets/robot.gltf').read_text('utf-8'))
        model['buffers'][0]['uri'] = '../../outside.bin'
        save_json(source.parent / 'assets/robot.gltf', model)
    else:
        source_scene['prefab_assets'] = [a for a in source_scene['prefab_assets'] if a['id'] != 'robot']
        save_json(source.parent / 'scenes/main.json', source_scene)
    before = deepcopy(scene)
    with pytest.raises((ValueError, OSError)):
        import_project_prefabs(scene, target.parent, source)
    assert scene == before
    assert sorted((target.parent/'assets').rglob('*'))==original_files


def test_failed_copy_rolls_back_all_staged_files(tmp_path, monkeypatch):
    source = source_project(tmp_path)
    target = create_project(tmp_path / 'target', 'Target')
    original_files=sorted((target.parent/'assets').rglob('*'))
    original_copy, calls = shutil.copy2, []
    def fail(source, target):
        calls.append(source)
        if len(calls) == 2:
            raise OSError('Simulated disk error')
        return original_copy(source, target)
    monkeypatch.setattr('editor.core.prefab_import.shutil.copy2', fail)
    with pytest.raises(OSError, match='Simulated'):
        import_project_prefabs(default_scene(), target.parent, source)
    assert len(calls) == 2 and sorted((target.parent/'assets').rglob('*'))==original_files


def test_internal_dependency_symlink_keeps_uri_and_external_target_is_rejected(tmp_path):
    source = source_project(tmp_path)
    target = create_project(tmp_path / 'target', 'Target')
    alias = source.parent / 'assets/alias.bin'
    try:
        alias.symlink_to('geometry.bin')
    except OSError as error:
        pytest.skip(f'This Windows account cannot create symlinks: {error}')
    model = json.loads((source.parent / 'assets/robot.gltf').read_text('utf-8'))
    model['buffers'][0]['uri'] = 'alias.bin'
    save_json(source.parent / 'assets/robot.gltf', model)
    imported = import_project_prefabs(default_scene(), target.parent, source)
    mesh = next(a for a in imported['prefab_assets'] if a['id'] == 'robot')['entities'][0]['mesh']
    assert (target.parent / mesh).with_name('alias.bin').read_bytes() == b'abcd'
    alias.unlink()
    outside = tmp_path / 'outside.bin'; outside.write_bytes(b'outside')
    alias.symlink_to(outside)
    before = sorted((target.parent / 'assets').iterdir())
    with pytest.raises(ValueError, match='escapes'):
        import_project_prefabs(default_scene(), target.parent, source)
    assert sorted((target.parent / 'assets').iterdir()) == before


def test_registration_resolves_selected_files_and_existing_library(tmp_path):
    source = source_project(tmp_path)
    root = source.parent
    paths = []
    for asset in load_project(source)[2]['prefab_assets']:
        path = root / 'assets/prefabs' / (asset['id'] + '.prefab.json')
        save_json(path, asset); paths.append(path)
    before = default_scene()
    scene = register_prefab_files(before, root, paths)
    assert len(scene['prefab_assets']) == 3 and 'prefab_assets' not in before
    only_robot = register_prefab_files(before, root, [p for p in paths if p.stem == 'robot.prefab'])
    rest = register_prefab_files(only_robot, root, [p for p in paths if p.stem != 'robot.prefab'])
    assert rest == scene
    assert not list((root / 'assets').glob('prefab-library-*'))
    with pytest.raises(ValueError, match='Duplicate prefab ID'):
        register_prefab_files(scene, root, paths)
    with pytest.raises(ValueError, match='Missing prefab dependency'):
        register_prefab_files(before, root, [p for p in paths if p.stem == 'variant.prefab'])
    with pytest.raises(ValueError, match='inside this project'):
        register_prefab_files(before, tmp_path / 'elsewhere', paths)
    broken = root / 'assets/broken.prefab.json'
    broken.write_text('{"id":"one","id":"two"}', 'utf-8')
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        register_prefab_files(before, root, [broken])


def test_empty_and_no_mesh_libraries(tmp_path):
    source = create_project(tmp_path / 'source', 'Source')
    target = create_project(tmp_path / 'target', 'Target')
    original_files=sorted((target.parent/'assets').rglob('*'))
    with pytest.raises(ValueError, match='no registered prefabs'):
        import_project_prefabs(default_scene(), target.parent, source)
    from editor.core.prefabs import add_scene_prefab
    scene, aid = add_scene_prefab(default_scene(), 'player', 'Empty object')
    save_json(source.parent / 'scenes/main.json', scene)
    imported = import_project_prefabs(default_scene(), target.parent, source)
    assert imported['prefab_assets'][0]['id'] == aid and sorted((target.parent/'assets').rglob('*'))==original_files


def test_import_menu_undo_redo_save_reopen_and_rejection(app, tmp_path, monkeypatch):
    source = source_project(tmp_path)
    target = create_project(tmp_path / 'target', 'Target')
    window = MainWindow(target, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(source), ''))
        original = window.signature()
        window.actions['Import Prefab Library…'].trigger()
        imported = window.signature()
        assert imported != original and window.dirty
        assert window.actions['Instantiate Prefab…'].isEnabled()
        assert any(spec.component_id == 1 for spec in window.adapter.available_specs())
        window.actions['Undo'].trigger()
        assert window.signature() == original and not window.actions['Instantiate Prefab…'].isEnabled()
        assert not any(spec.component_id == 1 for spec in window.adapter.available_specs())
        window.actions['Redo'].trigger()
        assert window.signature() == imported
        assert window.save_project()
        window.open_project(target)
        assert window.signature() == imported and not window.dirty
        count = window.adapter.graph.undo_stack().count()
        window.actions['Import Prefab Library…'].trigger()
        assert window.signature() == imported and window.adapter.graph.undo_stack().count() == count
        assert 'Duplicate prefab ID' in window.console.toPlainText()
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: ('', ''))
        window.actions['Import Prefab Library…'].trigger()
        assert window.signature() == imported
        save_json(source, [])
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (str(source), ''))
        window.actions['Import Prefab Library…'].trigger()
        assert window.signature() == imported and window.adapter.graph.undo_stack().count() == count
        assert 'Project manifest must be an object' in window.console.toPlainText()
    finally:
        window.saved_signature = window.signature(); window.document_changed(); window.close()


def test_registration_menu_is_one_undoable_scene_edit(app, tmp_path, monkeypatch):
    source = source_project(tmp_path)
    paths = []
    for asset in load_project(source)[2]['prefab_assets']:
        path = source.parent / 'assets/prefabs' / (asset['id'] + '.prefab.json')
        save_json(path, asset); paths.append(str(path))
    save_json(source.parent / 'scenes/main.json', default_scene())
    window = MainWindow(source, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    try:
        monkeypatch.setattr(QFileDialog, 'getOpenFileNames', lambda *args, **kwargs: (paths, ''))
        original = window.signature()
        window.actions['Register Prefab Files…'].trigger()
        registered = window.signature()
        assert len(window.scene['prefab_assets']) == 3
        window.actions['Undo'].trigger(); assert window.signature() == original
        window.actions['Redo'].trigger(); assert window.signature() == registered
        assert window.save_project()
        window.open_project(source); assert window.signature() == registered
    finally:
        window.saved_signature = window.signature(); window.document_changed(); window.close()
