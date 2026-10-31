from copy import deepcopy
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog
import pytest
from editor.core.document import create_project,save_json,load_project
from editor.core.type_edits import edit_type
from editor.core.typed_schema import build_schema
from editor.ui.main_window import MainWindow
from editor.ui.user_types import TypeLibraryDialog,TypeSignatureDialog,apply_type_edit
from tests.test_type_edits import source


def test_field_editor_preserves_origins_and_invalid_text_when_reordering(app):
    b,scene=source(); schema=build_schema(scene['struct_definitions'],scene['enum_definitions'])
    dialog=TypeSignatureDialog('struct',schema,definition=schema.structs['Stats'])
    dialog.table.item(0,0).setText('health')
    dialog.add_row('title','string','Hero')
    dialog.table.item(1,2).setText('invalid JSON'); dialog.table.setCurrentCell(1,0)
    dialog.move(-1)
    assert dialog.table.item(0,2).text()=='invalid JSON'
    dialog.accept(); assert dialog.result()!=QDialog.DialogCode.Accepted
    dialog.table.item(0,2).setText('"Hero"'); dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted
    assert dialog.origins==dict(health='hp')
    assert dialog.definition['fields'][1]['name']=='health'


def test_type_library_cancel_and_failed_deletion_leave_source_untouched(app):
    b,scene=source(); before=deepcopy((b.graph,scene))
    dialog=TypeLibraryDialog(b.graph,scene)
    assert not dialog.apply_definition('struct',None,original='Stats')
    assert dialog.apply_definition('enum',dict(name='Difficulty',values=['Easy','Hard']))
    dialog.reject()
    assert (b.graph,scene)==before


def open_window(tmp_path):
    b,scene=source(); manifest=create_project(tmp_path/'project','Type editing')
    save_json(manifest.parent/'graphs/gameplay.json',b.graph); save_json(manifest.parent/'scenes/main.json',scene)
    window=MainWindow(manifest,settings=QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat))
    window.show()
    return window,manifest


def refactored(window):
    return edit_type(window.adapter.document(),window.scene,'struct',
        dict(name='Vitals',fields=[dict(name='health',type='int',default=10)]),original='Stats',origins=dict(health='hp'))


def test_type_edit_is_one_shared_undo_and_preserves_earlier_graph_history(app,tmp_path):
    window,manifest=open_window(tmp_path)
    make=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='make')
    make.set_property('value_hp',99)
    before=window.adapter.document()
    graph,scene=refactored(window); apply_type_edit(window,graph,scene)
    current=window.adapter.document()
    assert next(n for n in current['nodes'] if n['id']=='make')['values']==dict(health=99)
    window.actions['Undo'].trigger(); assert window.adapter.document()==before
    window.actions['Undo'].trigger()
    assert next(n for n in window.adapter.document()['nodes'] if n['id']=='make')['values']==dict(hp=42)
    window.actions['Redo'].trigger(); window.actions['Redo'].trigger()
    assert window.adapter.document()==current
    assert window.save_project()
    _,saved_graph,saved_scene=load_project(manifest)
    assert saved_scene['variables']['actor']['value']==dict(stats=dict(health=24))
    assert saved_graph==current
    window.open_project(manifest)
    assert window.adapter.document()==current
    assert window.adapter.registry.by_name('Get Vitals Variable')
    window.close()


def test_failed_type_graph_recreation_rolls_back(app,tmp_path,monkeypatch):
    window,_=open_window(tmp_path)
    before=window.signature(); graph,scene=refactored(window)
    original=window.adapter.graph.create_node
    def fail_once(*args,**kwargs):
        monkeypatch.setattr(window.adapter.graph,'create_node',original)
        raise ValueError('Synthetic graph failure')
    monkeypatch.setattr(window.adapter.graph,'create_node',fail_once)
    with pytest.raises(ValueError,match='rolled back'):
        apply_type_edit(window,graph,scene)
    assert window.signature()==before
    window.close()
