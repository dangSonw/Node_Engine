import json
from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QLineEdit, QCheckBox, QPushButton, QDialogButtonBox
from editor.core.document import create_project
from editor.core.components import node_id
from editor.ui.components import ComponentSignatureDialog
from editor.ui.main_window import MainWindow, SearchDialog
from editor.ui.graph import GraphAdapter
from tests.test_components import health


def test_component_authoring_inspector_undo_and_project_isolation(app, tmp_path):
    path = create_project(tmp_path/'health', 'Health')
    window = MainWindow(path, QSettings(str(tmp_path/'layout.ini'), QSettings.IniFormat))
    window.refresh_hierarchy('player')
    baseline = window.signature()
    def define():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, ComponentSignatureDialog)
        dialog.name_field.setText('Health')
        dialog.add_port('inputs', 'Points', 'int', 100)
        QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    QTimer.singleShot(10, define)
    window.actions['Define Component…'].trigger()
    cid = window.scene['component_definitions'][0]['id']
    assert window.adapter.registry.by_name('Set Health Points').id == node_id(cid, 'set', 1)
    window.actions['Undo'].trigger()
    assert window.signature() == baseline
    assert not any(s.component_id for s in window.adapter.registry.nodes.values())
    window.actions['Redo'].trigger()
    assert window.actions['Add Component…'].isEnabled()
    def attach():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, SearchDialog)
        QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    QTimer.singleShot(10, attach)
    window.actions['Add Component…'].trigger()
    assert not window.actions['Add Component…'].isEnabled()
    def instance():
        return window.scene['entities'][0]['components'][str(cid)]
    def widget(cls, suffix):
        return next(w for w in window.inspector.findChildren(cls)
                    if w.accessibleName() == f'player component {cid} {suffix}')
    field = widget(QLineEdit, 'property 1')
    field.setText('false'); field.editingFinished.emit()
    assert instance()['properties']['1'] == 100
    assert field.styleSheet()
    field.setText('75'); QTest.keyClick(field, Qt.Key.Key_Return)
    assert instance()['properties']['1'] == 75 and not field.styleSheet()
    QTest.keyClick(widget(QCheckBox, 'enabled'), Qt.Key.Key_Space)
    assert instance()['enabled'] is False
    window.actions['Undo'].trigger()
    assert instance()['enabled'] is True
    window.actions['Undo'].trigger()
    assert instance()['properties']['1'] == 100
    window.actions['Redo'].trigger(); window.actions['Redo'].trigger()
    QTest.mouseClick(widget(QPushButton, 'remove'), Qt.MouseButton.LeftButton)
    assert not window.scene['entities'][0]['components']
    window.actions['Undo'].trigger()
    assert instance() == {'enabled': False, 'properties': {'1': 75}}
    window.adapter.add(node_id(cid, 'get', 1))
    assert window.save_project()
    saved = window.signature()
    window.open_project(path)
    assert window.signature() == saved and not window.dirty
    second = create_project(tmp_path/'empty', 'Empty')
    window.open_project(second)
    assert not any(s.component_id for s in window.adapter.registry.nodes.values())
    assert not window.actions['Add Component…'].isEnabled()
    window.close()


def test_component_dialog_rejects_duplicate_names_and_bad_types(app):
    dialog = ComponentSignatureDialog([health()])
    dialog.name_field.setText('HEALTH'); dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert 'unique' in dialog.error.text()
    dialog.name_field.setText('Inventory')
    dialog.add_port('inputs', 'Items', 'array<int>', [1, 2])
    dialog.tables['inputs'].item(0, 2).setText('[true]')
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.tables['inputs'].item(0, 2).setText('[1, 2]')
    dialog.accept()
    assert dialog.definition['properties'][0]['default'] == [1, 2]


def test_component_clipboard_rejects_foreign_schema(app):
    source = GraphAdapter(component_definitions=[health()])
    target = GraphAdapter()
    node = source.add(node_id(1, 'get', 1)); node.set_selected(True)
    old_clipboard = app.clipboard().text()
    try:
        assert source.graph.copy_nodes([node])
        copied = json.loads(app.clipboard().text())
        assert next(iter(copied['nodes'].values()))['custom']['type_id'] == node_id(1, 'get', 1)
        diagnostics = []
        target.diagnostic.connect(diagnostics.append)
        before = target.document()
        target.paste()
        assert target.document() == before
        assert any('unavailable' in message for message in diagnostics)
    finally:
        source.deleteLater()
        target.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        app.clipboard().setText(old_clipboard)
