import json
import shutil
import pytest
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QMessageBox
from editor import __version__
from editor.core.document import create_project, load_project, save_json
from editor.core.project_format import load_manifest, nen_manifest
from editor.core.projects import add_scene, compile_project, convert_to_nen, project_snapshot
from editor.ui.project_launcher import NewProjectDialog, ProjectLauncher, recent_projects, remember_project
from editor.ui.main_window import MainWindow


def legacy_project(tmp_path,version=1):
    path=create_project(tmp_path/'legacy','Legacy')
    raw=load_manifest(path)
    for key in ('format','format_version','project_id','engine'):
        raw.pop(key)
    if version==1:
        entry=raw.pop('scenes')[0]
        raw.pop('entry_scene')
        raw.update(version=1,graph=entry['graph'],scene=entry['scene'])
    result=path.with_name('project.json')
    save_json(result,raw)
    path.unlink()
    return result


def test_nen_structure_unicode_identity_multiscene_and_relocation(tmp_path):
    path=create_project(tmp_path/'Trò chơi mới','Rắn 3D')
    assert path.name=='Trò chơi mới.nen' and not path.with_name('project.json').exists()
    manifest,graph,scene=load_project(path)
    assert manifest['format']=='NodeEngine.Project' and manifest['version']==2
    assert manifest['engine']['created_with']==__version__ and manifest['entry_scene']=='main'
    for directory in ('graphs','scenes','assets/models','assets/textures','assets/audio','assets/ui','assets/prefabs'):
        assert (path.parent/directory).is_dir()
    with pytest.raises(FileExistsError):
        create_project(path.parent,'Overwrite')
    assert load_project(path)==(manifest,graph,scene)
    add_scene(path,'level')
    original=compile_project(project_snapshot(path))
    shutil.copytree(path.parent,tmp_path/'relocated')
    moved=tmp_path/'relocated'/path.name
    assert compile_project(project_snapshot(moved))==original
    assert load_manifest(moved)['project_id']==manifest['project_id']


@pytest.mark.parametrize('version',[1,2])
def test_legacy_conversion_retains_documents_original_and_compiled_behavior(tmp_path,version):
    path=legacy_project(tmp_path,version)
    before={p:p.read_bytes() for p in path.parent.rglob('*') if p.is_file()}
    old=compile_project(project_snapshot(path))
    target,data=convert_to_nen(path)
    assert target.name=='legacy.nen' and data['version']==2
    assert load_manifest(target)==data and all(p.read_bytes()==contents for p,contents in before.items())
    result=compile_project(project_snapshot(target))
    assert (old if version==1 else old['scenes']['main'])==result['scenes']['main']
    with pytest.raises(FileExistsError):
        convert_to_nen(path)
    with pytest.raises(ValueError,match='already uses'):
        convert_to_nen(target)


@pytest.mark.parametrize('damage,message',[
    (lambda p:p.update(format='Other.Project'),'not a Node_Engine'),
    (lambda p:p.update(format_version=999),'format version'),
    (lambda p:p.update(format_version=True),'format version'),
    (lambda p:p.update(project_id='bad'),'project_id'),
    (lambda p:p.pop('engine'),'engine versions'),
    (lambda p:p['engine'].update(minimum_version='99.0.0'),'requires Node_Engine'),
    (lambda p:p['engine'].update(created_with=1),'major.minor.patch'),
    (lambda p:p['scenes'][0].update(graph='../outside.json'),'relative'),
])
def test_incompatible_nen_is_rejected_without_writing_files(tmp_path,damage,message):
    path=create_project(tmp_path/'game','Game')
    raw=load_manifest(path); damage(raw); save_json(path,raw)
    before=path.read_bytes()
    with pytest.raises(ValueError,match=message):
        project_snapshot(path)
    with pytest.raises(ValueError,match=message):
        load_project(path)
    with pytest.raises(ValueError,match=message):
        add_scene(path,'level')
    assert path.read_bytes()==before and not (path.parent/'graphs/level.json').exists()


def test_nen_cannot_be_a_renamed_legacy_json_and_conversion_checks_inactive_scenes(tmp_path):
    path=legacy_project(tmp_path,2)
    forged=path.with_name('forged.nen'); forged.write_bytes(path.read_bytes())
    with pytest.raises(ValueError,match='not a Node_Engine'):
        load_project(forged)
    add_scene(path,'level')
    (path.parent/'scenes/level.json').unlink()
    with pytest.raises(FileNotFoundError):
        convert_to_nen(path)
    assert not path.with_name('legacy.nen').exists()


def test_older_engine_metadata_and_unknown_fields_survive_save(app,tmp_path):
    path=create_project(tmp_path/'game','Game')
    raw=load_manifest(path)
    raw['engine'].update(created_with='0.0.1',last_saved_with='0.0.2',minimum_version='0.0.1',custom='retain')
    raw['extensions']={'example.plugin':{'enabled':True}}
    save_json(path,raw)
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat)
    window=MainWindow(path,settings)
    try:
        window.scene['variables']['score']=5; window.document_changed()
        assert window.save_project()
        saved=load_manifest(path)
        assert saved['project_id']==raw['project_id'] and saved['extensions']==raw['extensions']
        assert saved['engine']=={**raw['engine'],'last_saved_with':__version__,'minimum_version':__version__}
        window.open_project(path)
        assert window.scene['variables']['score']==5 and not window.dirty
    finally:
        window.dirty=False; window.close(); window.deleteLater()


def test_new_dialog_validation_cancel_and_success(app,tmp_path):
    dialog=NewProjectDialog()
    dialog.directory.setText('')
    dialog.create()
    assert dialog.project_path is None and 'Choose' in dialog.message.text()
    dialog.directory.setText(str(tmp_path)); dialog.create()
    assert dialog.project_path is None and not list(tmp_path.glob('*.nen'))
    dialog.directory.setText(str(tmp_path/'new')); dialog.name.setText('')
    dialog.create(); assert not (tmp_path/'new').exists()
    dialog.name.setText('Người chơi'); dialog.show(); app.processEvents()
    QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    assert dialog.result()==QDialog.DialogCode.Accepted and dialog.project_path.suffix=='.nen'
    dialog.deleteLater()


def test_launcher_validation_recent_cancel_and_open(app,tmp_path):
    path=create_project(tmp_path/'game','Game')
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat)
    for _ in range(2): remember_project(settings,path)
    remember_project(settings,tmp_path/'missing.nen')
    assert len(recent_projects(settings))==2
    dialog=ProjectLauncher(settings,initial_project=path)
    assert dialog.project_path is None
    dialog.path.setText(str(tmp_path/'missing.nen')); dialog.open_project()
    assert dialog.result()!=QDialog.DialogCode.Accepted and 'Cannot open' in dialog.message.text()
    graph_path=path.parent/'graphs/gameplay.json'
    contents=graph_path.read_bytes(); save_json(graph_path,[])
    dialog.path.setText(str(path)); dialog.open_project()
    assert 'Graph document must be an object' in dialog.message.text() and dialog.project_path is None
    graph_path.write_bytes(contents)
    dialog.recent.setCurrentRow(1)
    assert dialog.path.text()==str(path.resolve())
    dialog.show(); app.processEvents()
    QTest.mouseClick(dialog.open_button,Qt.MouseButton.LeftButton)
    assert dialog.project_path==path and dialog.result()==QDialog.DialogCode.Accepted
    cancelled=ProjectLauncher(settings,initial_project=path)
    cancelled.reject(); assert cancelled.project_path is None
    dialog.deleteLater(); cancelled.deleteLater()


def test_entry_point_requires_welcome_even_with_project_argument(app,tmp_path,monkeypatch):
    import editor.main as entry
    path=create_project(tmp_path/'game','Game')
    observed=[]
    def close_welcome():
        dialog=QApplication.activeModalWidget()
        observed.append(isinstance(dialog,ProjectLauncher) and dialog.path.text()==str(path))
        if dialog: dialog.reject()
    def no_editor(*a,**kw):
        pytest.fail('Editor constructed before choosing a project')
    monkeypatch.setattr(entry,'MainWindow',no_editor)
    QTimer.singleShot(0,close_welcome)
    assert entry.main([str(path)],settings=QSettings(str(tmp_path/'entry.ini'),QSettings.Format.IniFormat))==0 and observed==[True]


def test_editor_conversion_respects_discard_and_preserves_backup(app,tmp_path,monkeypatch):
    path=legacy_project(tmp_path)
    original=path.read_bytes()
    settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat)
    window=MainWindow(path,settings)
    try:
        window.scene['variables']['draft']=9; window.document_changed()
        monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.StandardButton.Cancel)
        window.convert_project()
        assert window.project_path==path and window.dirty
        monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.StandardButton.Discard)
        window.convert_project()
        assert window.project_path.suffix=='.nen' and not window.dirty
        assert 'draft' not in window.scene['variables'] and path.read_bytes()==original
        assert not window.actions['Convert to .nen…'].isEnabled()
    finally:
        window.dirty=False; window.close(); window.deleteLater()
