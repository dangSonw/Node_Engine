"""Project presets guide suggestions while typed graphs remain composable."""
import pytest
from PySide6.QtCore import QSettings
from editor.core.compiler import GraphError
from editor.core.document import create_project, load_project, save_json
from editor.core.project_format import load_manifest
from editor.core.projects import project_snapshot, compile_project
from editor.core.functions import new_function
from editor.ui.graph import GraphAdapter
from editor.ui.functions import FunctionEditorDialog
from editor.ui.main_window import MainWindow
from editor.ui.project_launcher import ProjectLauncher
from tests.test_core import node, link


@pytest.mark.parametrize('workflow,row', [('3d',0), ('2d',1)])
def test_preset_suggestions_ports_and_saved_hybrid_graph(app,tmp_path,workflow,row):
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat)
    browser=ProjectLauncher(settings,start_new=True,project_roots=[])
    browser.recent.setCurrentRow(row)
    browser.directory.setText(str(tmp_path/'Game')); browser.create()
    path=browser.project_path; assert path is not None
    browser.deleteLater()
    window=MainWindow(path,settings)
    try:
        adapter=window.adapter
        assert adapter.node_workflow==workflow
        start=next(n for n in adapter.graph.all_nodes() if n.get_property('type_id')==1001)
        candidates={s.id for s,p in adapter.compatible_ports(start.outputs()['Out'])}
        assert (14104 in candidates)==(workflow=='2d')
        assert (13002 in candidates)==(workflow=='3d')
        assert {9003,15005,15006,14005}.issubset(candidates)
        window.node_workflow.setCurrentIndex(window.node_workflow.findData('all'))
        candidates={s.id for s,p in adapter.compatible_ports(start.outputs()['Out'])}
        assert {14104,13002}.issubset(candidates)
        adapter.add(14104); adapter.add(13002)
        assert window.save_project()
        program=compile_project(project_snapshot(path))
        # The suggestion preference is editorial metadata, never a runtime mode.
        window.node_workflow.setCurrentIndex(window.node_workflow.findData(workflow))
        assert window.save_project() and window.open_project(path)
        assert {14104,13002}.issubset(n['type'] for n in window.adapter.document()['nodes'])
        assert compile_project(project_snapshot(path))==program
        assert load_manifest(path)['editor']['node_workflow']==workflow
    finally:
        window.dirty=False; window.close(); window.deleteLater()


def test_vector_dimensions_and_unavailable_nodes_reject_without_replacing_graph(app):
    adapter=GraphAdapter(); adapter.add(1001)
    before=adapter.document()
    graph=dict(version=1,nodes=[node('vector',4080),node('position',9002)],
               links=[link('vector','Value','position','Value')])
    for workflow in ('2d','3d','all'):
        adapter.node_workflow=workflow
        with pytest.raises(GraphError,match='vec2 -> vec3'):
            adapter.load(graph)
        assert adapter.document()==before
        source=adapter.add(4080)
        assert all(p.type=='vec2' for s,p in adapter.compatible_ports(source.outputs()['Value']))
        adapter.graph.delete_node(source)
        with pytest.raises(ValueError,match='unavailable'):
            adapter.add(99999999)
        assert adapter.document()==before
    adapter.deleteLater()


def test_function_suggestions_inherit_preset_and_preserve_pure_context(app,tmp_path):
    path=create_project(tmp_path/'Game','Game')
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat)
    window=MainWindow(path,settings); window.node_workflow.setCurrentIndex(1)
    action=new_function('Action'); pure=new_function('Pure',outputs=[{'name':'Result','type':'float'}],pure=True,definitions=[action])
    dialog=FunctionEditorDialog([action,pure],action['id'],window.scene,window)
    try:
        ids={s.id for s in dialog.adapter.suggested_specs()}
        assert 14104 in ids and 13002 not in ids and 13018 in ids
        dialog.node_workflow.setCurrentIndex(0)
        assert {14104,13002}.issubset(s.id for s in dialog.adapter.suggested_specs())
        dialog.navigate(pure['id'])
        before=dialog.adapter.document()
        with pytest.raises(ValueError,match='unavailable'):
            dialog.adapter.add(13002)
        with pytest.raises(GraphError,match='unavailable'):
            dialog.adapter.load(dict(version=1,nodes=[node('action',13002)],links=[]))
        assert dialog.adapter.document()==before
    finally:
        dialog.reject(); dialog.deleteLater()
        window.dirty=False; window.close(); window.deleteLater()


@pytest.mark.parametrize('editor',[None,[],{'node_workflow':'unknown'},{'node_workflow':False}])
def test_invalid_project_workflow_fails_before_loading(app,tmp_path,editor):
    path=create_project(tmp_path/'Game','Game')
    manifest=load_manifest(path); manifest['editor']=editor; save_json(path,manifest)
    before=path.read_bytes()
    with pytest.raises(ValueError,match='editor.node_workflow'):
        load_project(path)
    assert path.read_bytes()==before
