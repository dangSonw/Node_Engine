import json
import struct
import time
from copy import deepcopy
from PySide6.QtCore import QSettings, QEvent, Qt
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtTest import QTest
import pytest
from editor.core.document import load_graph, save_json, default_scene, create_project
from editor.core import scene as scene_api
from editor.core.registry import ROOT
from editor.services import RuntimeClient, BuildService
from editor.ui.graph import GraphAdapter
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog, FunctionSignatureDialog, FunctionsCommand


def wait_for(predicate, seconds=3):
    end = time.monotonic() + seconds
    while not predicate() and time.monotonic() < end:
        QTest.qWait(10)
    assert predicate()


def test_entity_hierarchy_inspector_undo_delete_and_reopen(app,tmp_path):
    from PySide6.QtWidgets import QComboBox, QCheckBox
    path=create_project(tmp_path/'hierarchy','Hierarchy')
    window=MainWindow(path,settings=QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    scene,child=scene_api.create_entity(window.scene,'Con rô-bốt')
    window.push_scene('Create child',scene,child)
    combo=next(w for w in window.findChildren(QComboBox) if w.accessibleName()==f'{child} parent')
    window.show(); combo.setFocus()
    QTest.keyClick(combo,Qt.Key.Key_Down)
    from shiboken6 import isValid
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    assert isValid(combo) and combo.currentData()=='player'
    assert scene_api.entity(window.scene,child)['parent']=='player'
    root=window.hierarchy.topLevelItem(0)
    assert root.childCount()==1 and root.child(0).child(0).data(0,Qt.ItemDataRole.UserRole)==child
    window.adapter.graph.undo_stack().undo()
    assert not scene_api.entity(window.scene,child).get('parent')
    window.adapter.graph.undo_stack().redo()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    visible=next(w for w in window.findChildren(QCheckBox) if w.accessibleName()==f'{child} visible' and w.parent() is not None)
    visible.setChecked(False)
    assert scene_api.entity(window.scene,child)['visible'] is False
    window.refresh_hierarchy('player')
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    combo=next(w for w in window.findChildren(QComboBox) if w.accessibleName()=='player parent' and w.parent() is not None)
    assert combo.findData(child)==-1 # Descendants cannot be selected as parents.
    window.push_scene('Delete subtree',scene_api.delete_entity(window.scene,'player'))
    assert window.scene['entities']==[]
    window.adapter.graph.undo_stack().undo()
    assert len(window.scene['entities'])==2
    assert window.save_project()
    before=deepcopy(window.scene)
    window.open_project(path)
    assert window.scene==before
    window.close(); window.deleteLater()


def test_spawn_result_port_can_feed_actions_and_survives_graph_roundtrip(app):
    from editor.core.compiler import compile_graph
    adapter=GraphAdapter()
    start=adapter.add(1001); spawn=adapter.add(8010); move=adapter.add(9002)
    start.outputs()['Out'].connect_to(spawn.inputs()['In'])
    spawn.outputs()['Out'].connect_to(move.inputs()['In'])
    spawn.outputs()['Entity'].connect_to(move.inputs()['Entity'])
    graph=adapter.document(); ir=compile_graph(graph,default_scene())
    assert ir['events']['start'][0]['op']=='action_result'
    assert ir['events']['start'][1]['args'][0]['op']=='local'
    adapter.load(graph); assert adapter.document()==graph
    adapter.deleteLater()


def test_timer_listener_configuration_rejects_wires_and_roundtrips(app):
    adapter=GraphAdapter()
    handler=adapter.add(1003)
    text=adapter.add(3003)
    owner=adapter.add(8001)
    text.outputs()['Value'].connect_to(handler.inputs()['Filter'])
    owner.outputs()['Entity'].connect_to(handler.inputs()['Receiver'])
    assert not handler.inputs()['Filter'].connected_ports()
    assert not handler.inputs()['Receiver'].connected_ports()
    handler.set_property('value_Filter','turn')
    handler.set_property('value_Receiver','player')
    rotate=adapter.add(9004)
    handler.outputs()['Out'].connect_to(rotate.inputs()['In'])
    handler.outputs()['Owner'].connect_to(rotate.inputs()['Entity'])
    before=adapter.document()
    adapter.load(before)
    assert adapter.document()==before
    from editor.core.compiler import compile_graph
    assert compile_graph(before,default_scene())['events']['timers'][0]['filter']=='turn'
    adapter.deleteLater()


def test_persistence_event_ports_undo_and_reopen(app,tmp_path):
    from editor.core.compiler import compile_graph
    import json
    from editor.core.document import save_json
    adapter=GraphAdapter()
    for event in (23101,23102,23103,23104):
        handler=adapter.add(event)
        assert set(handler.outputs())==({'Out','Slot','Error'} if event%2==0 else {'Out','Slot'})
        log=adapter.add(adapter.registry.by_name('Print Log').id)
        handler.outputs()['Out'].connect_to(log.inputs()['In'])
        handler.outputs()['Error' if event%2==0 else 'Slot'].connect_to(log.inputs()['Message'])
    before=adapter.document()
    adapter.graph.undo_stack().undo()
    assert len(adapter.document()['links'])==len(before['links'])-1
    adapter.graph.undo_stack().redo()
    assert adapter.document()==before
    path=tmp_path/'graph.json'; save_json(path,before)
    adapter.load(json.loads(path.read_text('utf-8')))
    assert adapter.document()==before
    assert len(compile_graph(before,default_scene())['events']['persistence'])==4
    adapter.deleteLater()


def test_event_signature_undo_typed_ports_and_project_roundtrip(app,tmp_path):
    from editor.ui.events import EventSignatureDialog, EventsCommand
    from editor.core.events import node_id
    from editor.core.compiler import compile_graph
    path=create_project(tmp_path/'events','Events')
    window=MainWindow(path,settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    dialog=EventSignatureDialog([],window)
    dialog.name_field.setText('Hit')
    dialog.add_port('inputs','Sender','int',7)
    dialog.accept()
    assert dialog.definition is None and 'reserved' in dialog.error.text()
    dialog.tables['inputs'].item(0,0).setText('Damage')
    dialog.accept()
    event=dialog.definition
    assert event['parameters']==[{'name':'Damage','type':'int','default':7}]
    window.adapter.graph.undo_stack().push(EventsCommand(window,[event]))
    assert len([s for s in window.adapter.available_specs() if s.event_id==event['id']])==5
    window.adapter.graph.undo_stack().undo()
    assert window.adapter.event_definitions==[]
    assert not any(s.event_id for s in window.adapter.available_specs())
    window.adapter.graph.undo_stack().redo()
    send=window.adapter.add(node_id(event['id'],'send'))
    handler=window.adapter.add(node_id(event['id'],'on'))
    source=window.adapter.add(3001)
    source.outputs()['Value'].connect_to(send.inputs()['Damage'])
    assert not send.inputs()['Damage'].connected_ports()
    owner=window.adapter.add(8001)
    owner.outputs()['Entity'].connect_to(handler.inputs()['Receiver'])
    assert not handler.inputs()['Receiver'].connected_ports()
    handler.set_property('value_Receiver','player')
    document=window.adapter.document()
    assert compile_graph(document,window.scene)['event_definitions']==[event]
    assert window.save_project()
    window.open_project(path)
    assert window.adapter.document()==document
    other=create_project(tmp_path/'other','Other')
    window.open_project(other)
    assert window.adapter.event_definitions==[]
    assert not any(s.event_id for s in window.adapter.available_specs())
    window.close()
    dialog.deleteLater()


def test_event_clipboard_preserves_types_connections_and_shared_undo(app):
    from editor.core.events import new_event, node_id
    event=new_event('Notice',[{'name':'Count','type':'int','default':7}])
    adapter=GraphAdapter(event_definitions=[event])
    diagnostics=[]
    adapter.diagnostic.connect(diagnostics.append)
    handler=adapter.add(node_id(event['id'],'on'))
    setter=adapter.add(adapter.registry.by_name('Set Integer Variable').id)
    handler.outputs()['Out'].connect_to(setter.inputs()['In'])
    handler.outputs()['Count'].connect_to(setter.inputs()['Value'])
    before=adapter.document()
    old_clipboard=app.clipboard().text()
    try:
        adapter.graph.copy_nodes([handler,setter])
        adapter.paste()
        after=adapter.document()
        assert len(after['nodes'])==4 and len(after['links'])==4, diagnostics
        assert len({n['id'] for n in after['nodes']})==4
        adapter.graph.undo_stack().undo()
        assert adapter.document()==before
        adapter.graph.undo_stack().redo()
        assert adapter.document()==after
    finally:
        app.clipboard().setText(old_clipboard)
        adapter.deleteLater()


@pytest.mark.parametrize('destination',['missing','different_signature','pure_function'])
def test_event_clipboard_rejects_foreign_definitions_atomically(app,destination):
    from copy import deepcopy
    from editor.core.events import new_event, node_id
    from editor.core.functions import new_function
    from editor.core.document import empty_graph
    event=new_event('Notice',[{'name':'Count','type':'int'}])
    adapter=GraphAdapter(event_definitions=[event])
    send=adapter.add(node_id(event['id'],'send')); number=adapter.add(3001)
    old_clipboard=app.clipboard().text()
    target=adapter
    try:
        adapter.graph.copy_nodes([send,number])
        if destination=='missing':
            adapter.load(empty_graph())
        elif destination=='different_signature':
            changed=deepcopy(event); changed['parameters'][0]['type']='float'
            adapter.load({**empty_graph(),'event_definitions':[changed]})
        else:
            pure=new_function('Pure',[],[{'name':'Result','type':'float'}],True)
            target=GraphAdapter(functions=[pure],current_function=pure['id'],event_definitions=[event])
            target.load(pure['graph'])
        before=target.document(); undo_count=target.graph.undo_stack().count()
        errors=[]; target.diagnostic.connect(errors.append)
        target.paste()
        assert errors and 'Cannot paste nodes' in errors[0]
        assert target.document()==before
        assert target.graph.undo_stack().count()==undo_count
    finally:
        app.clipboard().setText(old_clipboard)
        if target is not adapter:
            target.deleteLater()
        adapter.deleteLater()


def test_action_function_editor_knows_project_events_but_pure_functions_cannot_emit(app):
    from editor.core.events import new_event, node_id
    from editor.core.functions import new_function
    event=new_event('Notify',[{'name':'Count','type':'int'}])
    action=new_function('Emit',[],[])
    pure=new_function('Calculate',[],[{'name':'Number','type':'int'}],True)
    dialog=FunctionEditorDialog([action,pure],action['id'],default_scene(),event_definitions=[event])
    assert node_id(event['id'],'send') in {s.id for s in dialog.adapter.available_specs()}
    assert node_id(event['id'],'on') not in {s.id for s in dialog.adapter.available_specs()}
    node=dialog.adapter.add(node_id(event['id'],'send'))
    entry=next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='entry')
    output=next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='return')
    entry.outputs()['Out'].disconnect_from(output.inputs()['In'])
    entry.outputs()['Out'].connect_to(node.inputs()['In'])
    node.outputs()['Out'].connect_to(output.inputs()['In'])
    assert dialog.validate_functions()
    dialog.navigate(pure['id'])
    assert not any(s.event_id for s in dialog.adapter.available_specs())
    dialog.accept()
    assert dialog.result_definitions is not None
    dialog.deleteLater()


def test_invalid_event_load_preserves_live_graph(app):
    from editor.core.events import new_event
    from copy import deepcopy
    adapter=GraphAdapter(event_definitions=[new_event('First')])
    adapter.add(1001)
    before=adapter.document()
    broken=deepcopy(before)
    broken['event_definitions'][0]['parameters']=[{'name':'Sender','type':'int'}]
    with pytest.raises(ValueError): adapter.load(broken)
    assert adapter.document()==before
    adapter.deleteLater()


def test_function_ui_transaction_navigation_undo_and_save(app, tmp_path):
    from tests.test_functions import double_function, action_function
    path = create_project(tmp_path/'functions','Functions')
    window = MainWindow(path,settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    pure = double_function()
    action = action_function(pure)
    window.adapter.graph.undo_stack().push(FunctionsCommand(window,[pure,action]))
    call = window.adapter.add(action['id'])
    call.set_property('value_Number',21)
    before = window.adapter.document()
    dialog = FunctionEditorDialog(window.adapter.functions,action['id'],window.scene,window)
    assert dialog.validate_functions()
    inner = next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='double')
    dialog.adapter.graph.node_double_clicked.emit(inner)
    assert dialog.current_id==pure['id']
    twice = next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='twice')
    twice.set_property('value_B',3)
    dialog.adapter.graph.undo_stack().undo()
    assert twice.get_property('value_B')==2
    dialog.adapter.graph.undo_stack().redo()
    dialog.accept()
    assert dialog.result_definitions is not None
    window.adapter.graph.undo_stack().push(FunctionsCommand(window,dialog.result_definitions))
    after = window.adapter.document()
    window.adapter.graph.undo_stack().undo()
    assert window.adapter.document()==before
    window.adapter.graph.undo_stack().redo()
    assert window.adapter.document()==after
    assert call.get_property('value_Number')==21
    assert window.save_project()
    window.open_project(path)
    assert window.adapter.document()==after
    cancelled = FunctionEditorDialog(window.adapter.functions,pure['id'],window.scene,window)
    cancelled.adapter.add(4001)
    cancelled.reject()
    assert window.adapter.document()==after
    window.close()


def test_function_signature_dialog_and_dynamic_port_rejection(app):
    dialog=FunctionSignatureDialog([])
    dialog.name_field.setText('Typed function')
    dialog.pure.setChecked(True)
    dialog.add_port('inputs','Number','int',5)
    dialog.add_port('outputs','Result','int')
    dialog.accept()
    f=dialog.definition
    assert f['inputs']==[{'name':'Number','type':'int','default':5}]
    adapter=GraphAdapter()
    # Existing builtin nodes must reject mismatched newly introduced function ports.
    scalar=adapter.add(4001)
    adapter.configure_functions([f])
    call=adapter.add(f['id'])
    call.outputs()['Result'].connect_to(scalar.inputs()['A'])
    assert not scalar.inputs()['A'].connected_ports()
    integer=adapter.add(4030)
    call.outputs()['Result'].connect_to(integer.inputs()['A'])
    assert integer.inputs()['A'].connected_ports()


def test_enter_commits_function_input_without_closing_dialog(app):
    from PySide6.QtCore import Qt
    from tests.test_functions import double_function
    f=double_function()
    dialog=FunctionEditorDialog([f],f['id'],default_scene())
    dialog.show()
    QTest.qWait(25)
    node=next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id')=='twice')
    dialog.inspect(node)
    field=next(x for x in dialog.findChildren(QLineEdit) if x.property('domain_property')=='value_B')
    field.setFocus()
    field.setText('4')
    QTest.keyClick(field,Qt.Key.Key_Return)
    assert dialog.isVisible()
    assert dialog.result_definitions is None
    assert node.get_property('value_B')==4
    dialog.reject()


def test_play_requests_rebuild_when_no_runtime_matches_sources(app,tmp_path,monkeypatch):
    path=create_project(tmp_path/'stale','Stale runtime')
    window=MainWindow(path,settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr('editor.ui.main_window.runtime_current',lambda *args,**kwargs:False)
    builds=[]
    monkeypatch.setattr(window.builder,'start',lambda *args,**kwargs:builds.append((args,kwargs)))
    window.play()
    assert window.pending_play and len(builds)==1
    assert not window.runtime.active
    window.close()


def test_graph_roundtrip_and_stable_duplicate_undo(app):
    adapter = GraphAdapter()
    adapter.load(load_graph(ROOT / 'examples/blockbench_demo/graphs/gameplay.json'))
    before = adapter.document()
    chosen = next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id') == 'spin')
    chosen.set_selected(True)
    adapter.duplicate()
    after = adapter.document()
    assert len(after['nodes']) == len(before['nodes']) + 1
    assert len({n['id'] for n in after['nodes']}) == len(after['nodes'])
    adapter.graph.undo_stack().undo()
    assert adapter.document() == before
    adapter.graph.undo_stack().redo()
    assert adapter.document() == after
    adapter.load(after)
    assert adapter.document() == after


def test_incompatible_ports_rejected_before_graph_changes(app):
    adapter = GraphAdapter()
    boolean, number = adapter.add(3002), adapter.add(4001)
    boolean.outputs()['Value'].connect_to(number.inputs()['A'])
    assert number.inputs()['A'].connected_ports() == []
    scalar = adapter.add(3001)
    scalar.outputs()['Value'].connect_to(number.inputs()['A'])
    assert len(number.inputs()['A'].connected_ports()) == 1


def test_inspector_validation_dirty_save_and_load(app, tmp_path):
    graph = load_graph(ROOT / 'examples/blockbench_demo/graphs/gameplay.json')
    save_json(tmp_path/'graph.json', graph)
    save_json(tmp_path/'scene.json', default_scene())
    path = tmp_path/'project.json'
    save_json(path, {'version':1, 'name':'Test', 'graph':'graph.json','scene':'scene.json'})
    window = MainWindow(path, QSettings(str(tmp_path/'layout.ini'), QSettings.IniFormat))
    target = next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id') == 'spin')
    window.inspect_node(target)
    field = next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName() == 'Vector Scale Vector')
    field.setText('[0, "bad", 0]')
    field.editingFinished.emit()
    assert target.get_property('value_Vector') == [0,45,0]
    assert not window.dirty
    field.setText('[0, 90, 0]')
    field.editingFinished.emit()
    assert target.get_property('value_Vector') == [0,90,0]
    assert window.dirty
    window.adapter.graph.undo_stack().undo()
    assert not window.dirty
    window.adapter.graph.undo_stack().redo()
    assert window.save_project()
    assert not window.dirty
    saved = window.adapter.document()
    window.open_project(path)
    assert window.adapter.document() == saved
    window.close()


@pytest.mark.parametrize('remove',['undo_creation','delete'])
def test_inspector_clears_when_node_leaves_graph(app,tmp_path,remove):
    window=MainWindow(settings=QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    try:
        node=window.adapter.add(5113)
        window.inspect_node(node)
        assert window.inspector_form.rowCount()>0
        if remove=='undo_creation': window.adapter.graph.undo_stack().undo()
        else: window.adapter.graph.delete_nodes([node])
        assert window.inspected_node is None and window.inspector_form.rowCount()==0
        # Restoring the node remains editable through the normal selection path.
        if remove=='undo_creation': window.adapter.graph.undo_stack().redo()
        else: window.adapter.graph.undo_stack().undo()
        window.inspect_node(node)
        assert window.inspected_node is node and window.inspector_form.rowCount()>0
    finally:
        window.saved_signature=window.signature(); window.document_changed(); window.close()


def test_ipc_fragmented_and_coalesced_frames(app):
    client = RuntimeClient()
    assert client.server.listen('node-engine-test-' + str(id(client)))
    peer = QLocalSocket()
    messages = []
    client.message.connect(messages.append)
    peer.connectToServer(client.server.fullServerName())
    wait_for(lambda: client.socket is not None)
    def frame(message):
        raw = json.dumps({'protocol_version':1, **message}).encode()
        return struct.pack('<I',len(raw)) + raw
    raw = frame({'event':'hello'}) + frame({'event':'state','state':'paused'})
    peer.write(raw[:2]); peer.flush(); QTest.qWait(20)
    assert not messages
    peer.write(raw[2:9]); peer.flush(); QTest.qWait(20)
    assert not messages
    peer.write(raw[9:]); peer.flush()
    wait_for(lambda: len(messages) == 2)
    assert client.ready and client.state == 'paused'
    client.send('snapshot')
    wait_for(lambda: peer.bytesAvailable() > 4)
    response = bytes(peer.readAll())
    assert json.loads(response[4:])['command'] == 'snapshot'
    peer.abort(); client.server.close()


def test_failed_runtime_start_resets_connection(app, tmp_path):
    client = RuntimeClient()
    exits = []
    client.stopped.connect(exits.append)
    client.start(tmp_path/'missing.exe',tmp_path/'missing.json',tmp_path)
    wait_for(lambda: bool(exits))
    assert not client.active and not client.ready and not client.server.isListening()


def test_failed_build_process_releases_busy_state(app, tmp_path):
    builder = BuildService()
    results = []
    builder.finished.connect(results.append)
    builder.busy = True
    builder.process.start(str(tmp_path/'missing.exe'))
    wait_for(lambda: bool(results))
    assert results == [False] and not builder.busy


def test_shared_scene_graph_undo_and_unicode_entity_inspector(app,tmp_path):
    path = create_project(tmp_path/'new','New')
    window = MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    baseline = window.signature()
    window.actions['Create Entity'].trigger()
    eid = window.selected_entity_id()
    assert eid and len(window.scene['entities']) == 2
    field = next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()==f'{eid} name')
    field.setText('Người chơi thứ hai')
    field.editingFinished.emit()
    assert scene_api.entity(window.scene,eid)['name'] == 'Người chơi thứ hai'
    node = window.adapter.add(3001)
    window.actions['Undo'].trigger()
    assert len(window.adapter.graph.all_nodes()) == 2
    window.actions['Undo'].trigger()
    assert scene_api.entity(window.scene,eid)['name'] == 'Entity'
    window.actions['Undo'].trigger()
    assert window.signature() == baseline and not window.dirty
    for _ in range(3):
        window.actions['Redo'].trigger()
    assert len(window.adapter.graph.all_nodes()) == 3
    assert scene_api.entity(window.scene,eid)['name'] == 'Người chơi thứ hai'
    window.refresh_hierarchy(eid)
    window.actions['Duplicate Entity'].trigger()
    copied = window.selected_entity_id()
    assert copied != eid
    assert scene_api.entity(window.scene,copied)['name'] == 'Người chơi thứ hai 2'
    window.actions['Delete Entity'].trigger()
    assert len(window.scene['entities']) == 2
    window.actions['Undo'].trigger()
    assert window.selected_entity_id() == copied
    assert window.save_project()
    window.open_project(path)
    assert len(window.scene['entities']) == 3 and not window.dirty
    window.close()


def test_scene_transform_undo_updates_inspector_without_mutating_old_scene(app,tmp_path):
    path = create_project(tmp_path/'new','New')
    window = MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    window.refresh_hierarchy('player')
    original = json.dumps(window.scene,sort_keys=True)
    field = next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()=='player position')
    field.setText('[2, 3, 4]')
    field.editingFinished.emit()
    assert window.scene['entities'][0]['position'] == [2,3,4]
    window.actions['Undo'].trigger()
    assert json.dumps(window.scene,sort_keys=True) == original
    field = next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()=='player position')
    assert json.loads(field.text()) == [0,0,0]
    assert not window.dirty
    window.close()


def test_import_assigns_selected_entity_and_undo_keeps_resource(app,tmp_path,monkeypatch):
    path = create_project(tmp_path/'new','New')
    window = MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    window.create_entity()
    eid = window.selected_entity_id()
    source = str(ROOT/'examples/blockbench_demo/assets/robot.gltf')
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(source,''))
    window.import_model()
    assert 'mesh' not in window.scene['entities'][0]
    mesh = scene_api.entity(window.scene,eid)['mesh']
    assert (path.parent/mesh).is_file()
    window.actions['Undo'].trigger()
    assert 'mesh' not in scene_api.entity(window.scene,eid)
    assert (path.parent/mesh).is_file()
    window.save_project()
    window.close()


def test_typed_ports_and_collection_document_roundtrip(app):
    from editor.core.registry import Registry
    r=Registry()
    adapter=GraphAdapter()
    array=adapter.add(r.by_name('Create Integer Array').id)
    getter=adapter.add(r.by_name('Get Integer Item').id)
    wrong=adapter.add(r.by_name('Get Float Item').id)
    array.outputs()['Value'].connect_to(wrong.inputs()['Array'])
    assert wrong.inputs()['Array'].connected_ports() == []
    array.outputs()['Value'].connect_to(getter.inputs()['Array'])
    array.set_property('value_Items',[2**60+1,4])
    saved=adapter.document()
    adapter.load(saved)
    assert adapter.document() == saved
    assert len(saved['links']) == 1


def test_validate_ui_reports_type_and_loop_scope_errors(app,tmp_path):
    from editor.core.builder import GraphBuilder
    path=create_project(tmp_path/'invalid','Invalid')
    window=MainWindow(path,QSettings(str(tmp_path/'invalid.ini'),QSettings.IniFormat))
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('loop','For Each Integer',Array=[1])
    b.add('store','Set Integer Variable')
    b.connect('start','Out','loop','In').connect('loop','Done','store','In').connect('loop','Item','store','Value')
    window.adapter.load(b.graph)
    assert not window.validate_graph()
    assert 'only available inside' in window.problems.item(0).text()
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()


def test_variables_dialog_validation_and_shared_undo(app,tmp_path):
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QDialogButtonBox, QDialog
    from editor.ui.variables import VariablesDialog
    from editor.core.data_types import declaration
    dialog=VariablesDialog({'score':2})
    dialog.add_row('score','bool',True)
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert 'Duplicate' in dialog.error.text()
    assert dialog.result_variables == {'score':2}
    dialog.table.item(1,0).setText('ready')
    dialog.table.item(1,2).setText('12')
    dialog.accept()
    assert 'Expected bool' in dialog.error.text()
    dialog.table.item(1,2).setText('true')
    dialog.accept()
    assert dialog.result_variables == {'score':2,'ready':declaration('bool',True)}
    path=create_project(tmp_path/'variables','Variables')
    window=MainWindow(path,QSettings(str(tmp_path/'variables.ini'),QSettings.IniFormat))
    window.show()
    assert QTest.qWaitForWindowExposed(window)
    baseline=window.signature()
    def populate():
        active=app.activeModalWidget()
        assert isinstance(active,VariablesDialog)
        active.add_row('tên','string','Nhân vật')
        active.add_row('items','array<int>',[1,2**60+1])
        active.add_row('targets','map<entity>',{'main':'player'})
        button=active.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    QTimer.singleShot(50,populate)
    window.actions['Scene Variables…'].trigger()
    expected={'tên':declaration('string','Nhân vật'),'items':declaration('array<int>',[1,2**60+1]),
              'targets':declaration('map<entity>',{'main':'player'})}
    assert window.scene['variables'] == expected and window.dirty
    window.actions['Undo'].trigger()
    assert window.signature() == baseline and not window.dirty
    window.actions['Redo'].trigger()
    assert window.scene['variables'] == expected
    assert window.save_project()
    window.open_project(path)
    assert window.scene['variables'] == expected and not window.dirty
    window.close()
