"""Real Qt gestures for design.md Flow B, including cancel and single-step undo."""
from copy import deepcopy
import pytest
from PySide6.QtCore import Qt, QPoint, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import create_project, default_scene
from editor.core.compiler import compile_graph
from editor.core.functions import new_function, ENTRY
from editor.ui.functions import FunctionEditorDialog
from editor.ui.graph import GraphAdapter
from editor.ui.main_window import MainWindow
from editor.ui.search import SearchDialog


def show(adapter, node):
    widget = adapter.graph.widget
    widget.resize(1050, 700)
    widget.show()
    adapter.graph.center_on([node])
    QTest.qWait(30)
    return widget


def drag(adapter, port, target=None):
    viewer = adapter.graph.viewer()
    start = viewer.mapFromScene(port.view.sceneBoundingRect().center())
    end = target or (start + QPoint(210 if port.type_() == 'out' else -210, 145))
    QTest.mousePress(viewer.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewer.viewport(), end, 30)
    QTest.mouseRelease(viewer.viewport(), Qt.MouseButton.LeftButton, pos=end)
    QTest.qWait(20)
    return viewer.mapToScene(end)


def popup():
    dialog = QApplication.activeModalWidget()
    assert isinstance(dialog, SearchDialog)
    return dialog


def choose(dialog, type_id, port):
    row = next(i for i in range(dialog.list.count())
               if tuple(dialog.list.item(i).data(Qt.ItemDataRole.UserRole)) == (type_id, port))
    dialog.list.setCurrentRow(row)
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    QTest.qWait(10)


@pytest.mark.parametrize('source_id,kind,target_id,target_port', [
    (3001, 'float', 4001, 'B'), (3002, 'bool', 2001, 'Condition'),
    (4020, 'vec3', 4021, 'A'), (1001, 'exec', 3005, 'In'),
])
def test_port_drop_filters_connects_selected_port_and_undoes_once(app, source_id, kind, target_id, target_port):
    adapter = GraphAdapter()
    node = adapter.add(source_id)
    origin = next(p for p in node.output_ports())
    widget = show(adapter, node)
    before = adapter.document(); stack = adapter.graph.undo_stack(); index = stack.index()
    position = drag(adapter, origin)
    dialog = popup()
    assert all(p.type == kind for _, p in adapter.compatible_ports(origin))
    assert not any(s.event in ('timer','custom') for s, _ in adapter.compatible_ports(origin))
    assert adapter.document() == before and stack.index() == index
    choose(dialog, target_id, target_port)
    after = adapter.document()
    created = next(n for n in adapter.graph.all_nodes() if n is not node)
    assert created.pos() == [position.x(), position.y()]
    assert created.inputs()[target_port] in origin.connected_ports()
    assert stack.index() == index + 1
    stack.undo(); assert adapter.document() == before
    stack.redo(); assert adapter.document() == after
    adapter.load(after); assert adapter.document() == after
    widget.close(); adapter.deleteLater()


def test_connected_input_cancel_and_replace_preserve_wire_and_undo(app):
    adapter = GraphAdapter()
    source = adapter.add(3001, [-350, -100]); target = adapter.add(4001)
    origin = target.inputs()['B']; source.outputs()['Value'].connect_to(origin)
    widget = show(adapter, target)
    before = adapter.document(); stack = adapter.graph.undo_stack(); index = stack.index()
    drag(adapter, origin); dialog = popup()
    assert adapter.document() == before and len(origin.view.connected_pipes) == 1
    dialog.search.setText('no_such_node')
    assert dialog.list.count() == 0 and dialog.empty.isVisible()
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    assert dialog.isVisible()
    QTest.keyClick(dialog.search, Qt.Key.Key_Escape); QTest.qWait(10)
    assert adapter.document() == before and stack.index() == index and len(origin.view.connected_pipes) == 1
    drag(adapter, origin); choose(popup(), 3001, 'Value')
    after = adapter.document()
    assert len(origin.connected_ports()) == 1 and origin.connected_ports()[0].node() is not source
    assert len(origin.view.connected_pipes) == 1 and not source.outputs()['Value'].view.connected_pipes
    assert stack.index() == index + 1
    stack.undo(); assert adapter.document() == before and len(origin.view.connected_pipes) == 1
    stack.redo(); assert adapter.document() == after and len(origin.view.connected_pipes) == 1
    widget.close(); adapter.deleteLater()


def test_escape_during_detached_drag_restores_visual_and_model(app):
    adapter = GraphAdapter(); source = adapter.add(3001, [-330, 0]); target = adapter.add(4001)
    origin = target.inputs()['A']; source.outputs()['Value'].connect_to(origin)
    widget = show(adapter, target); before = adapter.document(); index = adapter.graph.undo_stack().index()
    viewer = adapter.graph.viewer(); start = viewer.mapFromScene(origin.view.sceneBoundingRect().center())
    QTest.mousePress(viewer.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(viewer.viewport(), start+QPoint(-150,120), 20)
    QTest.keyClick(viewer, Qt.Key.Key_Escape)
    QTest.mouseRelease(viewer.viewport(), Qt.MouseButton.LeftButton, pos=start+QPoint(-150,120))
    QTest.qWait(10)
    assert QApplication.activeModalWidget() is None
    assert adapter.document() == before and adapter.graph.undo_stack().index() == index
    assert len(origin.view.connected_pipes) == 1 and not viewer._LIVE_PIPE.isVisible()
    widget.close(); adapter.deleteLater()


def test_normal_port_connections_and_incompatible_targets_keep_existing_behavior(app):
    adapter = GraphAdapter(); source = adapter.add(3001, [-300,0]); target = adapter.add(4001, [150,0])
    boolean = adapter.add(3002, [150,200]); widget = show(adapter, source)
    adapter.graph.fit_to_selection(); QTest.qWait(10)
    viewer = adapter.graph.viewer(); origin = source.outputs()['Value']
    drag(adapter, origin, viewer.mapFromScene(target.inputs()['A'].view.sceneBoundingRect().center()))
    assert origin.connected_ports() == [target.inputs()['A']]
    before = adapter.document()
    drag(adapter, boolean.outputs()['Value'], viewer.mapFromScene(target.inputs()['B'].view.sceneBoundingRect().center()))
    assert adapter.document() == before and QApplication.activeModalWidget() is None
    widget.close(); adapter.deleteLater()


def test_candidates_respect_functions_constants_and_removed_origins(app):
    pure = new_function('Double', [{'name':'X','type':'float','default':0.}], [{'name':'Y','type':'float'}], pure=True)
    adapter = GraphAdapter(functions=[pure], current_function=pure['id']); adapter.load(pure['graph'])
    source = next(n for n in adapter.graph.all_nodes() if n.get_property('type_id') == ENTRY)
    origin = source.outputs()['X']; candidates = adapter.compatible_ports(origin)
    assert candidates and all(s.kind in ('pure','select','pure_call','struct_make','struct_break','enum_value','collection_callback','return') and not s.context for s,p in candidates)
    assert not any(s.id == pure['id'] for s,p in candidates)
    assert any(s.kind == 'return' for s,p in candidates)
    before = adapter.document(); index = adapter.graph.undo_stack().index()
    with pytest.raises(ValueError): adapter.add_connected(3005, 'Value', origin, [0,0])
    assert adapter.document() == before and adapter.graph.undo_stack().index() == index
    adapter.deleteLater()
    adapter = GraphAdapter(); handler = adapter.add(1003)
    assert not adapter.compatible_ports(handler.inputs()['Filter'])
    source = adapter.add(3001); origin = source.outputs()['Value']
    origin.set_locked(True); assert not adapter.compatible_ports(origin)
    origin.set_locked(False); adapter.graph.delete_nodes([source]); before = adapter.document()
    with pytest.raises(ValueError): adapter.add_connected(4001, 'A', origin, [0,0])
    assert adapter.document() == before
    adapter.deleteLater()


def test_search_keyboard_navigation_and_no_match_cancel(app):
    dialog = SearchDialog([('Alpha',1), ('Beta',2)], 'Search', None); dialog.open(); QTest.qWait(10)
    QTest.keyClick(dialog.search, Qt.Key.Key_Down); assert dialog.list.currentRow() == 1
    QTest.keyClick(dialog.search, Qt.Key.Key_Up); assert dialog.list.currentRow() == 0
    QTest.keyClicks(dialog.search, 'BETA'); assert dialog.list.count() == 1
    QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    assert dialog.result_value == 2
    dialog.deleteLater()


def test_every_event_configuration_input_is_excluded_and_rejects_wires(app):
    adapter = GraphAdapter()
    sources = {kind: adapter.add(tid).output_ports()[0] for kind,tid in [('entity',8001),('string',3003),('bool',3002)]}
    for spec in adapter.registry.nodes.values():
        if spec.kind != 'event' or not spec.inputs:
            continue
        handler = adapter.add(spec.id)
        for p in spec.inputs:
            origin = sources[p.type]; target = handler.inputs()[p.name]
            assert not adapter.compatible_ports(target), spec.name
            assert not any(s.id == spec.id for s, _ in adapter.compatible_ports(origin)), spec.name
            origin.connect_to(target)
            assert not target.connected_ports(), spec.name
    adapter.deleteLater()


def test_dynamic_collection_signature_and_function_dialog_search(app):
    f = new_function('Collection', [{'name':'Items','type':'array<float>','default':[]}],
                     [{'name':'Result','type':'array<float>'}], pure=True)
    dialog = FunctionEditorDialog([f], f['id'], default_scene())
    adapter = dialog.adapter
    source = next(n for n in adapter.graph.all_nodes() if n.get_property('type_id') == ENTRY)
    origin = source.outputs()['Items']
    dialog.show(); adapter.graph.center_on([source]); QTest.qWait(30)
    matches = adapter.compatible_ports(origin)
    assert matches and all(p.type == 'array<float>' for s,p in matches)
    target_spec, target_port = next((s,p) for s,p in matches if s.kind == 'return')
    before = adapter.document()
    drag(adapter, origin)
    search = popup(); choose(search, target_spec.id, target_port.name)
    assert dialog.isVisible() and dialog.result_definitions is None
    after = adapter.document(); adapter.graph.undo_stack().undo(); assert adapter.document() == before
    adapter.graph.undo_stack().redo(); assert adapter.document() == after
    dialog.reject(); dialog.deleteLater()


def test_occupied_exec_output_replaces_and_undo_restores_previous_handler(app):
    adapter = GraphAdapter(); start = adapter.add(1001); old = adapter.add(3005, [300,0])
    origin = start.outputs()['Out']; origin.connect_to(old.inputs()['In'])
    before = adapter.document(); index = adapter.graph.undo_stack().index()
    widget = show(adapter, start); drag(adapter, origin); choose(popup(), 2001, 'In')
    assert len(origin.connected_ports()) == 1 and origin.connected_ports()[0].node().get_property('type_id') == 2001
    assert not old.inputs()['In'].connected_ports()
    assert adapter.graph.undo_stack().index() == index+1
    adapter.graph.undo_stack().undo(); assert adapter.document() == before
    assert len(origin.view.connected_pipes) == 1
    widget.close(); adapter.deleteLater()


def test_main_window_port_search_save_reopen_and_shared_undo(app, tmp_path):
    path = create_project(tmp_path/'port-search', 'Port Search')
    window = MainWindow(path, settings=QSettings(str(tmp_path/'settings.ini'), QSettings.Format.IniFormat))
    adapter = window.adapter; adapter.load({'version':1,'name':'Search','nodes':[],'links':[]})
    source = adapter.add(3001); source.set_property('value_Value', 2.5)
    window.show(); adapter.graph.center_on([source]); QTest.qWait(30)
    before = adapter.document(); index = adapter.graph.undo_stack().index()
    drag(adapter, source.outputs()['Value']); choose(popup(), 3005, 'Value')
    created = next(n for n in adapter.graph.all_nodes() if n.get_property('type_id') == 3005)
    after = adapter.document()
    window.actions['Undo'].trigger(); assert adapter.document() == before
    window.actions['Redo'].trigger(); assert adapter.document() == after
    assert adapter.graph.undo_stack().index() == index+1
    start = adapter.add(1001); start.outputs()['Out'].connect_to(created.inputs()['In'])
    assert compile_graph(adapter.document(), window.scene)['events']['start']
    assert window.save_project(); saved = deepcopy(adapter.document())
    window.open_project(path); assert window.adapter.document() == saved
    window.close(); window.deleteLater()
