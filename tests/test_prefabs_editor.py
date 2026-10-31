from copy import deepcopy
import pytest
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QInputDialog, QSpinBox, QMessageBox, QLineEdit
from editor.core.document import create_project, default_scene
from editor.core.prefabs import add_scene_prefab, instantiate_scene_prefab
from editor.core.scene import delete_entity, entity, set_entity_property, validate_scene
from editor.ui.main_window import MainWindow, SearchDialog
from tests.test_prefabs import robot


def library_scene():
    asset = robot()
    return {'entities': [], 'variables': {}, 'prefab_assets': [asset],
            'component_definitions': asset['component_definitions']}


def test_nested_child_selection_before_parent_in_scene_order_populates_inspector(app, tmp_path):
    from tests.test_prefab_nested import nested_scene
    project = create_project(tmp_path/'nested-selection', 'Nested selection')
    window = MainWindow(project, QSettings(str(tmp_path/'nested.ini'), QSettings.IniFormat))
    try:
        scene = nested_scene()
        assert [e['id'] for e in scene['entities']].index('c') < [e['id'] for e in scene['entities']].index('r')
        window.push_scene('Nested scene', scene, 'c')
        assert window.selected_entity_id() == 'c'
        assert any(w.accessibleName() == 'c scale' for w in window.inspector.findChildren(QLineEdit))
        assert window.actions['Apply Prefab Overrides'].isEnabled()
    finally:
        window.saved_signature = window.signature(); window.document_changed(); window.close()


def test_equal_value_inspector_edit_is_undoable_and_survives_apply_save_reopen(app, tmp_path):
    project = create_project(tmp_path / 'explicit', 'Explicit overrides')
    window = MainWindow(project, QSettings(str(tmp_path / 'explicit.ini'), QSettings.IniFormat))
    try:
        scene, first = instantiate_scene_prefab(library_scene(), 'robot')
        scene, second = instantiate_scene_prefab(scene, 'robot')
        window.push_scene('Fixture', scene, first)
        initial = window.signature()
        def edit(eid, value):
            window.refresh_hierarchy(eid)
            field = next(w for w in window.inspector.findChildren(QLineEdit)
                         if w.accessibleName() == f'{eid} component 1 property 5')
            field.setText(str(value))
            QTest.keyClick(field, Qt.Key.Key_Return)
        edit(first, 100)
        assert window.scene['prefab_instances'][0]['component_overrides'] == {'root': {'1': {'properties': [5]}}}
        pinned = window.signature()
        assert pinned != initial
        window.actions['Undo'].trigger()
        assert window.signature() == initial
        window.actions['Redo'].trigger()
        assert window.signature() == pinned
        edit(second, 50)
        window.actions['Apply Prefab Overrides'].trigger()
        assert entity(window.scene, first)['components']['1']['properties']['5'] == 100
        assert entity(window.scene, second)['components']['1']['properties']['5'] == 50
        assert window.save_project()
        applied = window.signature()
        window.open_project(project)
        assert window.signature() == applied
        assert window.scene['prefab_instances'][0]['component_overrides'] == {'root': {'1': {'properties': [5]}}}
    finally:
        window.saved_signature = window.signature()
        window.document_changed()
        window.close()


def test_authored_instances_are_independent_and_edits_track_owned_groups():
    initial = library_scene(); original = deepcopy(initial)
    first, root = instantiate_scene_prefab(initial, 'robot')
    second, other = instantiate_scene_prefab(first, 'robot', position=[3, 0, 0])
    assert initial == original
    records = second['prefab_instances']
    assert not set(records[0]['mapping'].values()) & set(records[1]['mapping'].values())
    assert records[0]['owned_components']['root'] == []
    assert records[1]['owned_components']['root'] == ['transform']
    assert entity(second, other)['components']['1']['properties']['1'] == records[1]['mapping']['e1']
    edited = set_entity_property(second, root, 'layer', 0)
    assert edited['prefab_instances'][0]['owned_components']['root'] == ['activity']
    edited = set_entity_property(edited, root, 'position', [7, 8, 9])
    assert edited['prefab_instances'][0]['owned_components']['root'] == ['transform', 'activity']
    assert entity(edited, other)['position'] == [3, 0, 0]


def test_legacy_inferred_override_survives_a_new_authored_write():
    scene, root = instantiate_scene_prefab(library_scene(), 'robot', position=[1, 2, 3])
    del scene['prefab_instances'][0]['owned_components']
    result = set_entity_property(scene, root, 'visible', False)
    assert result['prefab_instances'][0]['owned_components']['root'] == ['transform', 'mesh']


def test_authored_delete_keeps_tombstones_and_root_also_deletes_detached_members():
    scene, root = instantiate_scene_prefab(library_scene(), 'robot')
    child = scene['prefab_instances'][0]['mapping']['e1']
    removed = delete_entity(scene, child)
    assert removed['prefab_instances'][0]['mapping']['e1'] == child
    assert child not in removed['prefab_instances'][0]['owned_components']
    validate_scene(removed)
    detached = set_entity_property(scene, child, 'parent', '')
    other_scene, other = instantiate_scene_prefab(detached, 'robot', parent=child)
    result = delete_entity(other_scene, root)
    assert result['entities'] == [] and result['prefab_instances'] == []
    assert len(other_scene['entities']) == 4


def test_authored_capture_and_failed_placement_are_transactional():
    scene = default_scene(); before = deepcopy(scene)
    with_asset, aid = add_scene_prefab(scene, 'player', 'Player asset')
    assert scene == before
    placed, root = instantiate_scene_prefab(with_asset, aid, parent='player')
    assert entity(placed, root)['parent'] == 'player'
    with pytest.raises(ValueError, match='does not exist'):
        instantiate_scene_prefab(with_asset, aid, parent='absent')
    assert len(with_asset['entities']) == 1


def test_prefab_menu_dialogs_inspector_undo_redo_save_reopen_and_isolation(app, tmp_path):
    project = create_project(tmp_path / 'prefabs', 'Prefabs')
    window = MainWindow(project, QSettings(str(tmp_path / 'layout.ini'), QSettings.IniFormat))
    window.refresh_hierarchy('player'); original = window.signature()
    assert not window.actions['Instantiate Prefab…'].isEnabled()
    def capture():
        dialog = app.activeModalWidget(); assert isinstance(dialog, QInputDialog)
        dialog.setTextValue('Reusable player'); dialog.accept()
    QTimer.singleShot(20, capture); window.actions['Create Prefab from Entity…'].trigger()
    assert window.actions['Instantiate Prefab…'].isEnabled()
    window.actions['Undo'].trigger(); assert window.signature() == original
    window.actions['Redo'].trigger()
    def choose():
        dialog = app.activeModalWidget(); assert isinstance(dialog, SearchDialog)
        QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for _ in range(2):
        QTimer.singleShot(20, choose); window.actions['Instantiate Prefab…'].trigger()
    root = window.selected_entity_id()
    records = deepcopy(window.scene['prefab_instances'])
    assert len(records) == 2 and len(window.scene['entities']) == 3
    layer = next(w for w in window.inspector.findChildren(QSpinBox) if w.accessibleName() == root + ' layer')
    layer.setValue(12)
    assert window.scene['prefab_instances'][1]['owned_components']['root'] == ['activity']
    window.actions['Undo'].trigger()
    assert window.scene['prefab_instances'] == records
    window.actions['Undo'].trigger(); assert len(window.scene['prefab_instances']) == 1
    window.actions['Redo'].trigger(); assert window.scene['prefab_instances'] == records
    window.refresh_hierarchy(root); window.actions['Delete Entity'].trigger()
    assert len(window.scene['prefab_instances']) == 1
    window.actions['Undo'].trigger(); assert window.scene['prefab_instances'] == records
    assert window.save_project()
    saved = window.signature(); window.open_project(project)
    assert window.signature() == saved and not window.dirty
    window.open_project(create_project(tmp_path / 'empty', 'Empty'))
    assert not window.actions['Instantiate Prefab…'].isEnabled()
    window.close()


def test_apply_reset_dialog_cancel_undo_and_save_reopen(app, tmp_path):
    project = create_project(tmp_path / 'editing', 'Editing')
    window = MainWindow(project, QSettings(str(tmp_path / 'edits.ini'), QSettings.IniFormat))
    try:
        initial, first = instantiate_scene_prefab(library_scene(), 'robot')
        initial, second = instantiate_scene_prefab(initial, 'robot')
        window.push_scene('Fixture', initial, first)
        assert window.actions['Apply Prefab Overrides'].isEnabled()
        edited = set_entity_property(window.scene, first, 'layer', 11)
        window.push_scene('Change source layer', edited, first)
        before = window.signature()
        window.actions['Apply Prefab Overrides'].trigger()
        applied = window.signature()
        assert entity(window.scene, second)['layer'] == 11
        window.actions['Undo'].trigger(); assert window.signature() == before
        window.actions['Redo'].trigger(); assert window.signature() == applied
        edited = set_entity_property(window.scene, second, 'layer', 3)
        window.push_scene('Local override', edited, second)
        before_reset = window.signature()
        def respond(button):
            dialog = app.activeModalWidget(); assert isinstance(dialog, QMessageBox)
            dialog.button(button).click()
        QTimer.singleShot(20, lambda: respond(QMessageBox.StandardButton.Cancel))
        window.actions['Reset Prefab Instance…'].trigger()
        assert window.signature() == before_reset
        QTimer.singleShot(20, lambda: respond(QMessageBox.StandardButton.Yes))
        window.actions['Reset Prefab Instance…'].trigger()
        assert entity(window.scene, second)['layer'] == 11
        reset = window.signature()
        window.actions['Undo'].trigger(); assert window.signature() == before_reset
        window.actions['Redo'].trigger(); assert window.signature() == reset
        assert window.save_project()
        window.open_project(project)
        assert window.signature() == reset and not window.dirty
    finally:
        window.saved_signature = window.signature(); window.document_changed(); window.close()
