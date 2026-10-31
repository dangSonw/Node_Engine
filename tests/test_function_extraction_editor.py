from copy import deepcopy
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog
from editor.core.document import create_project,load_project,default_scene
from editor.core.function_extraction import extract_function
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog,FunctionExtractionDialog,apply_function_graph_edit
from tests.test_functions import double_function,graph
from tests.test_function_extraction import math_graph
from editor.core.builder import GraphBuilder
from tests.test_physics_scene import chain


def find(adapter,nid): return next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id')==nid)


def test_gameplay_extraction_undo_old_history_and_reopen(app,tmp_path):
    path=create_project(tmp_path/'game','Extraction'); w=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    try:
        w.adapter.load(math_graph()); original=find(w.adapter,'add'); original.set_property('value_A',6)
        before=w.adapter.document(); after,info=extract_function(before,{'add','times'},'Calculate',w.scene)
        stack=w.adapter.graph.undo_stack(); count=stack.count()
        apply_function_graph_edit(w,after,set(info['removed']),{info['call_id']},'Extract function')
        assert w.adapter.document()==after and stack.count()==count+1
        stack.undo(); assert w.adapter.document()==before
        stack.undo(); assert original.get_property('value_A')==3
        stack.redo(); stack.redo(); assert w.adapter.document()==after
        assert w.save_project() and load_project(path)[1]==after
        w.open_project(path); assert w.adapter.document()==after and w.validate_graph()
    finally:
        w.dirty=False; w.close(); w.deleteLater()


def test_nested_extraction_has_shared_undo_across_navigation(app):
    f=double_function(); dialog=FunctionEditorDialog([f],f['id'],default_scene())
    original=find(dialog.adapter,'twice'); original.set_property('value_B',4)
    before=dialog.snapshot(); document=graph([],functions=before)
    after,info=extract_function(document,{'twice'},'Nested double',default_scene(),current_function=f['id'])
    stack=dialog.undo_stack; count=stack.count()
    apply_function_graph_edit(dialog,after,set(info['removed']),{info['call_id']},'Extract function')
    assert len(dialog.snapshot())==2 and stack.count()==count+1
    dialog.navigate(info['function_id']); assert stack.count()==count+1 and dialog.adapter.graph.undo_stack() is stack
    inner=find(dialog.adapter,'twice'); inner.set_property('value_B',9)
    stack.undo(); assert inner.get_property('value_B')==4
    stack.undo(); assert dialog.current_id==f['id'] and dialog.snapshot()==before
    stack.undo(); assert original.get_property('value_B')==2
    stack.redo(); stack.redo(); stack.redo(); dialog.navigate(info['function_id'])
    assert find(dialog.adapter,'twice').get_property('value_B')==9 and dialog.validate_functions()
    dialog.accept(); assert dialog.result()==QDialog.DialogCode.Accepted and len(dialog.result_definitions)==2
    dialog.deleteLater()


def test_extraction_review_cancel_and_name_retry(app):
    document=math_graph(); before=deepcopy(document)
    dialog=FunctionExtractionDialog(document,{'add','times'},default_scene())
    dialog.name_field.setText(''); dialog.accept()
    assert dialog.result()!=QDialog.DialogCode.Accepted and 'nonempty' in dialog.error.text()
    dialog.name_field.setText('Calculated'); dialog.accept()
    assert dialog.result()==QDialog.DialogCode.Accepted and dialog.result_document['functions'][0]['name']=='Calculated'
    assert document==before; dialog.deleteLater()
    dialog=FunctionExtractionDialog(document,{'add','times'},default_scene()); dialog.reject()
    assert document==before; dialog.deleteLater()


def test_guarded_extraction_restores_every_helper_wire_on_undo(app,tmp_path):
    path=create_project(tmp_path/'game','Guard'); w=MainWindow(path,QSettings(str(tmp_path/'ui.ini'),QSettings.IniFormat))
    try:
        b=GraphBuilder(); b.add('start','On Game Start'); chain(b,'start',('branch','Branch',{'Condition':False}))
        b.add('log','Print Log'); b.connect('branch','True','log','In'); w.adapter.load(b.graph)
        before=w.adapter.document(); after,info=extract_function(before,{'branch'},'Maybe',w.scene)
        assert info['guarded']; apply_function_graph_edit(w,after,set(info['removed']),set(info['added']),'Extract function')
        assert w.adapter.document()==after and w.validate_graph()
        w.adapter.graph.undo_stack().undo(); assert w.adapter.document()==before
        w.adapter.graph.undo_stack().redo(); assert w.adapter.document()==after
    finally:
        w.dirty=False; w.close(); w.deleteLater()
