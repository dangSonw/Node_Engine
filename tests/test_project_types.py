"""Whole-project type refactors, legacy identity collisions and multi-file save rollback."""
from copy import deepcopy
import json
import os
import pytest
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication,QDialog
from editor.core.document import create_project,default_scene,empty_graph,save_json,load_project
from editor.core.project_types import synchronize_types,edit_project_type,with_project_types,project_type_library
from editor.core.projects import add_scene,project_snapshot,compile_project,save_project_documents
from editor.core.project_format import load_manifest
from editor.core.builder import GraphBuilder
from editor.core.type_edits import definitions
from editor.core.typed_schema import build_schema
from editor.ui.user_types import TypeLibraryDialog,apply_type_edit
from editor.ui.main_window import MainWindow
from tests.test_type_edits import source
from tests.test_named_ports import root


def snapshot():
    b,_,_=root()
    main=dict(graph=deepcopy(b.graph),scene=default_scene())
    level=deepcopy(main)
    level['scene']['variables']={'stats':{'type':'struct:Stats','value':{'hp':88}}}
    structs,enums=definitions(level['graph'],level['scene'])
    level['scene'].update(struct_definitions=structs,enum_definitions=enums)
    return dict(version=2,entry_scene='main',scenes=dict(main=main,level=level,
        empty=dict(graph=empty_graph(),scene=default_scene())))


def renamed(value):
    return edit_project_type(value,'struct',dict(name='Vitals',fields=[dict(name='health',type='int',default=7)]),
                             original='Stats',origins=dict(health='hp'))


def test_rename_reaches_inactive_scene_function_event_values_and_blank_scene():
    original=snapshot(); before=deepcopy(original); changed=renamed(original)
    assert original==before
    for document in changed['scenes'].values():
        assert {d['name'] for d in document['scene']['struct_definitions']}=={'Vitals'}
        assert document['graph']['struct_definitions']==document['scene']['struct_definitions']
        for f in document['graph'].get('functions',[]):
            assert any(p['type']=='struct:Vitals' for p in f['inputs'])
        for event in document['graph'].get('event_definitions',[]):
            assert event['parameters'][0]['type']=='struct:Vitals'
    assert changed['scenes']['level']['scene']['variables']['stats']==dict(type='struct:Vitals',value=dict(health=88))
    compile_project(changed)


def test_conflict_or_used_type_in_another_scene_rejects_whole_edit():
    value=snapshot(); before=deepcopy(value)
    with pytest.raises(ValueError,match='Scene .*used|referenced'):
        edit_project_type(value,'struct',original='Stats')
    assert value==before
    value['scenes']['level']['graph']['struct_definitions'][0]['fields'][0]['default']=999
    with pytest.raises(ValueError,match='Scene level: conflicting project type: Stats'):
        synchronize_types(value)


def test_distinct_scene_types_with_colliding_legacy_ids_are_remapped_including_functions():
    b,scene=source()
    second=GraphBuilder(enum_definitions=[dict(name='Direction',values=['Left','Right'])])
    second.add('make','Make Direction',Value='Right')
    value=dict(version=2,entry_scene='main',scenes=dict(main=dict(graph=b.graph,scene=scene),
        level=dict(graph=second.graph,scene=default_scene())))
    assert b.graph['nodes'][1]['type']==second.graph['nodes'][0]['type']
    changed=synchronize_types(value)
    schemas=[build_schema(*definitions(d['graph'],d['scene'])) for d in changed['scenes'].values()]
    assert schemas[0].enums==schemas[1].enums
    assert changed['scenes']['main']['graph']['nodes'][1]['type']!=changed['scenes']['level']['graph']['nodes'][0]['type']
    assert synchronize_types(changed)==changed


@pytest.mark.parametrize('component_id',[1000,2000])
def test_project_creation_avoids_component_ids_in_every_scene(component_id):
    value=dict(version=2,entry_scene='main',scenes=dict(main=dict(graph=empty_graph(),scene=default_scene()),
        level=dict(graph=empty_graph(),scene=default_scene())))
    # Components can occupy nominal Make/Break or variable node ID ranges.
    value['scenes']['level']['scene']['component_definitions']=[dict(id=component_id,name='Health',
        properties=[dict(id=1,name='HP',type='int',default=1)])]
    changed=edit_project_type(value,'struct',dict(name='Data',fields=[dict(name='hp',type='int')]))
    assert changed['scenes']['main']['scene']['struct_definitions']==changed['scenes']['level']['scene']['struct_definitions']


def test_loader_rejects_ambiguous_local_ids_instead_of_retargeting_nodes():
    stats=dict(name='Stats',fields=[dict(name='hp',type='int')])
    other=dict(name='Other',fields=[dict(name='hp',type='int')])
    project=dict(type_definitions=project_type_library(dict(type_definitions=dict(structs=[other,stats],enums=[]))))
    b=GraphBuilder(struct_definitions=[stats]); b.add('make','Make Stats')
    with pytest.raises(ValueError,match='identity conflicts'):
        with_project_types(project,b.graph,default_scene())


@pytest.mark.parametrize('library',[None,[],dict(structs=[],enums='bad'),dict(structs=[],enums=[],extra=True)])
def test_project_manifest_rejects_invalid_type_libraries(tmp_path,library):
    path=create_project(tmp_path/'Game','Game'); project=load_manifest(path)
    project['type_definitions']=library; save_json(path,project); before=path.read_bytes()
    with pytest.raises(ValueError): load_project(path)
    assert path.read_bytes()==before


def project(tmp_path):
    path=create_project(tmp_path/'Project','Project types'); project=add_scene(path,'level')
    data=snapshot()
    for sid,document in list(data['scenes'].items())[:2]:
        entry=next(e for e in project['scenes'] if e['id']==sid)
        save_json(path.parent/entry['graph'],document['graph']); save_json(path.parent/entry['scene'],document['scene'])
    return path


def apply_project(window,changed):
    project=deepcopy(window.project); project['type_definitions']=deepcopy(changed['type_definitions'])
    current=changed['scenes'][window.scene_id]
    apply_type_edit(window,current['graph'],current['scene'],project=project,documents=changed['scenes'])


def test_project_edit_undo_redo_save_reopen_new_scene_and_relocation(app,tmp_path):
    path=project(tmp_path); settings=QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat)
    window=MainWindow(path,settings)
    try:
        before=window.signature(); changed=renamed(window.snapshot_project()); apply_project(window,changed)
        after=window.signature(); assert window.dirty
        window.actions['Undo'].trigger(); assert window.signature()==before and not window.dirty
        window.actions['Redo'].trigger(); assert window.signature()==after
        assert window.save_project()
        assert load_project(path,'level')[2]['variables']['stats']['value']==dict(health=88)
        # Undo after Save must stage the original inactive documents again.
        window.actions['Undo'].trigger(); assert window.dirty and window.save_project()
        assert load_project(path,'level')[2]['variables']['stats']['value']==dict(hp=88)
        window.actions['Redo'].trigger(); assert window.save_project()
        add_scene(path,'new_level'); assert load_project(path,'new_level')[2]['struct_definitions'][0]['name']=='Vitals'
        assert window.open_project(path,'level')
        assert window.adapter.registry.by_name('Make Vitals') and not window.dirty
        assert compile_project(project_snapshot(path))['scenes']['new_level']['type_definitions']==changed['type_definitions']
    finally:
        window.dirty=False; window.close(); window.deleteLater()


def test_type_undo_preserves_node_suggestions_and_startup_scene_changes(app,tmp_path):
    path=project(tmp_path)
    window=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat))
    try:
        apply_project(window,renamed(window.snapshot_project()))
        window.node_workflow.setCurrentIndex(window.node_workflow.findData('2d'))
        window.project['entry_scene']='level'; window.document_changed()
        for action in ('Undo','Redo'):
            window.actions[action].trigger()
            assert window.project['editor']['node_workflow']==window.adapter.node_workflow=='2d'
            assert window.project['entry_scene']=='level'
    finally:
        window.dirty=False; window.close(); window.deleteLater()


def test_library_cancel_and_inactive_failure_leave_all_files_unchanged(app,tmp_path):
    path=project(tmp_path); before={file:file.read_bytes() for file in path.parent.rglob('*.json')}
    data=project_snapshot(path); active=data['scenes']['main']
    dialog=TypeLibraryDialog(active['graph'],active['scene'],snapshot=data)
    assert not dialog.apply_definition('struct',None,original='Stats')
    assert dialog.apply_definition('enum',dict(name='Difficulty',values=['Easy','Hard']))
    dialog.reject(); dialog.deleteLater()
    assert all(file.read_bytes()==content for file,content in before.items())


def test_legacy_conflicting_types_can_be_renamed_in_editor_before_project_sync(app,tmp_path):
    path=project(tmp_path); manifest=load_manifest(path)
    entry=next(e for e in manifest['scenes'] if e['id']=='level')
    graph_path=path.parent/entry['graph']; graph=json.loads(graph_path.read_text('utf-8'))
    graph['struct_definitions'][0]['fields'][0]['default']=999; save_json(graph_path,graph)
    scene_path=path.parent/entry['scene']; scene=json.loads(scene_path.read_text('utf-8'))
    scene['struct_definitions'][0]['fields'][0]['default']=999; save_json(scene_path,scene)
    window=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat))
    checks=[]
    def resolve():
        dialog=QApplication.activeModalWidget()
        try:
            assert isinstance(dialog,TypeLibraryDialog) and dialog.result_snapshot is None
            assert 'conflicting project type: Stats' in dialog.error.text()
            assert dialog.apply_definition('struct',dict(name='AvatarStats',fields=[dict(name='hp',type='int',default=7)]),original='Stats')
            checks.append(True); dialog.accept()
        finally:
            if isinstance(dialog,QDialog) and not checks: dialog.reject()
    try:
        QTimer.singleShot(0,resolve); window.edit_user_types()
        assert checks and window.save_project()
        changed=synchronize_types(window.snapshot_project())
        assert {d['name'] for d in changed['type_definitions']['structs']}=={'Stats','AvatarStats'}
    finally:
        window.dirty=False; window.close(); window.deleteLater()


@pytest.mark.parametrize('failure_call',[3,5])
def test_batch_save_failure_rolls_back_committed_documents_and_external_edits_are_preserved(tmp_path,monkeypatch,failure_call):
    path=project(tmp_path); data=renamed(project_snapshot(path)); manifest=load_manifest(path)
    manifest['type_definitions']=data['type_definitions']
    files=[path]+list((path.parent/'graphs').glob('*.json'))+list((path.parent/'scenes').glob('*.json'))
    before={file:file.read_bytes() for file in files}; replace=os.replace; calls=0
    def fail_once(source,target):
        nonlocal calls
        calls+=1
        if calls==failure_call: raise OSError('Synthetic disk write failure')
        return replace(source,target)
    monkeypatch.setattr(os,'replace',fail_once)
    with pytest.raises(OSError,match='Synthetic'):
        save_project_documents(path,manifest,data['scenes'])
    assert all(file.read_bytes()==content for file,content in before.items())
    assert not list(path.parent.rglob('*.tmp'))
    monkeypatch.setattr(os,'replace',replace)
    target=path.parent/'scenes/level.json'; target.write_text('{"external":"edit"}',encoding='utf-8')
    with pytest.raises(ValueError,match='changed on disk'):
        save_project_documents(path,manifest,data['scenes'],expected=before)
    assert json.loads(target.read_text('utf-8'))=={'external':'edit'}
    assert all(file.read_bytes()==content for file,content in before.items() if file!=target)
