import copy
import json
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QInputDialog, QMessageBox
from editor.core.document import create_project, load_project, save_json
from editor.core.projects import add_scene, scene_entries, project_snapshot, compile_project
from editor.core.compiler import GraphError
from editor.ui.main_window import MainWindow


def test_legacy_upgrade_snapshot_and_unsaved_preview(tmp_path):
    path=create_project(tmp_path/'game','Game')
    # Exercise the original version-1 layout explicitly; new projects now use .nen/version 2.
    legacy=path.with_name('project.json')
    save_json(legacy,dict(version=1,name='Game',graph='graphs/gameplay.json',scene='scenes/main.json'))
    path=legacy
    original=load_project(path)
    assert 'scenes' not in compile_project(project_snapshot(path))
    p=add_scene(path,'level','Level')
    assert p['entry_scene']=='main' and load_project(path)[1:]==original[1:]
    _,graph,scene=load_project(path,'level'); scene['variables']['unsaved']=7
    snapshot=project_snapshot(path,p,'level',graph,scene,preview=True)
    scene['variables']['unsaved']=99
    save_json(path.parent/'graphs/level.json',{'invalid':True})
    ir=compile_project(snapshot)
    assert ir['entry_scene']=='level' and ir['scenes']['level']['scene']['variables']['unsaved']==7
    assert 'unsaved' not in ir['scenes']['main']['scene']['variables']
    with pytest.raises(ValueError): project_snapshot(path)


@pytest.mark.parametrize('damage',[
    lambda p:p.pop('entry_scene'), lambda p:p.update(entry_scene='absent'),
    lambda p:p['scenes'].append(copy.deepcopy(p['scenes'][0])),
    lambda p:p['scenes'][1].update(graph='./graphs/gameplay.json'),
    lambda p:p['scenes'][1].update(scene='../outside.json'),
    lambda p:p['scenes'][1].update(id='1bad'),
])
def test_manifest_rejects_ambiguous_or_escaping_documents(tmp_path,damage):
    path=create_project(tmp_path/'game','Game'); p=add_scene(path,'level'); damage(p)
    with pytest.raises(ValueError): scene_entries(p)


def test_new_scene_never_overwrites_existing_files(tmp_path):
    path=create_project(tmp_path/'game','Game'); before=path.read_bytes()
    occupied=path.parent/'graphs/level.json'; occupied.write_text('keep')
    with pytest.raises(ValueError): add_scene(path,'level')
    assert path.read_bytes()==before and occupied.read_text()=='keep'
    assert not (path.parent/'scenes/level.json').exists()


def test_editor_reports_missing_inactive_scene_document(app,tmp_path):
    path=create_project(tmp_path/'game','Game'); add_scene(path,'level')
    w=MainWindow(path,QSettings(str(tmp_path/'settings.ini'),QSettings.IniFormat))
    try:
        (path.parent/'graphs/level.json').unlink()
        assert not w.validate_graph() and w.problems.count()==1
        assert 'level.json' in w.problems.item(0).text()
    finally:
        w.dirty=False; w.close(); w.deleteLater()


def test_errors_identify_scene_and_node(tmp_path):
    path=create_project(tmp_path/'game','Game'); add_scene(path,'level')
    snap=project_snapshot(path); snap['scenes']['level']['graph']['nodes'][0]['type']=99999
    with pytest.raises(GraphError) as caught: compile_project(snap)
    assert caught.value.problems[0].node=='level/loaded'


def test_editor_creates_switches_and_persists_startup_and_build_snapshot(app,tmp_path,monkeypatch):
    path=create_project(tmp_path/'game','Game')
    w=MainWindow(path,QSettings(str(tmp_path/'settings.ini'),QSettings.IniFormat))
    try:
        monkeypatch.setattr(QInputDialog,'getText',lambda *a:('level',True))
        w.actions['New Scene…'].trigger()
        assert w.scene_id=='level' and not w.dirty and w.project['version']==2
        w.actions['Use as Startup Scene'].trigger(); assert w.dirty
        assert w.save_project() and json.loads(path.read_text())['entry_scene']=='level'
        w.switch_scene('main'); assert w.scene_id=='main'
        w.scene['variables']['draft']=3; w.document_changed()
        captured=[]; monkeypatch.setattr(w.builder,'start',lambda *a,**kw:captured.append(kw['snapshot']))
        w.build_game(); assert captured[0]['entry_scene']=='level'
        assert captured[0]['scenes']['main']['scene']['variables']['draft']==3
        assert w.snapshot_project(preview=True)['entry_scene']=='main'
        monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.StandardButton.Cancel)
        assert not w.switch_scene('level') and w.scene_id=='main'
        monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.StandardButton.Discard)
        assert w.switch_scene('level') and w.scene_id=='level' and not w.dirty
        w.switch_scene('main'); assert 'draft' not in w.scene['variables']
        w.focus_problem('level/loaded'); assert w.scene_id=='level'
        assert w.validate_graph()
    finally:
        w.dirty=False; w.close(); w.deleteLater()
