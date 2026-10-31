import json
from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog,QDialog
from editor.core.document import create_project,save_json,load_project
from editor.core.project_history import discover_projects,read_history,merge_history
from editor.ui.project_launcher import (ProjectLauncher,history_path,recent_projects,remember_project,history_entries)


def settings(path):
    return QSettings(str(path),QSettings.Format.IniFormat)


def test_history_persists_across_processes_and_migrates_single_string(tmp_path):
    path=create_project(tmp_path/'Game','Game')
    config=tmp_path/'user.ini'; first=settings(config)
    first.setValue('projects/recent',str(path)); first.sync()
    assert recent_projects(first)==[str(path)]
    assert remember_project(first,path)
    result=subprocess.run([sys.executable,'-c',
        'import json,sys; from PySide6.QtCore import QSettings; from editor.ui.project_launcher import history_entries; '
        'print(json.dumps(history_entries(QSettings(sys.argv[1],QSettings.Format.IniFormat))))',str(config)],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr
    entries=json.loads(result.stdout)
    assert entries[0]['path']==str(path) and entries[0]['opened_at']


def test_history_keeps_more_than_ten_projects_order_and_missing_entries(tmp_path):
    config=settings(tmp_path/'user.ini')
    paths=[tmp_path/f'Project {i}'/f'Game{i}.nen' for i in range(15)]
    config.setValue('projects/recent',[str(p) for p in paths])
    assert remember_project(config,paths[4])
    stored=read_history(history_path(config))
    assert len(stored)==15 and stored[0]['path']==str(paths[4])
    assert len({entry['path'] for entry in stored})==15 and len(recent_projects(config))==15
    assert all(entry['opened_at']=='' for entry in stored[1:])


def test_history_bad_record_and_corrupt_json_fall_back_to_legacy(tmp_path):
    config=settings(tmp_path/'user.ini'); path=tmp_path/'Game.nen'
    config.setValue('recentProjects',json.dumps([str(path)]))
    store=history_path(config); store.write_text('broken')
    assert recent_projects(config)==[str(path)]
    save_json(store,dict(version=1,projects=[{},dict(path=''),dict(path=5),dict(path=str(path),opened_at='')]))
    assert len(read_history(store))==1
    assert len(merge_history(store,[str(path),str(path)]))==1


def test_discovery_prefers_nen_and_excludes_generated_assets_and_deep_trees(tmp_path):
    root=tmp_path/'workspace'
    a=create_project(root/'first','First'); b=create_project(root/'sub'/'second','Second')
    save_json(a.with_name('project.json'),dict(version=1,graph='graphs/gameplay.json',scene='scenes/main.json'))
    create_project(root/'build'/'ignored','Ignored')
    create_project(root/'one'/'two'/'three','Too deep')
    found=discover_projects([root])
    assert set(found)=={a,b}


def test_conversion_history_collapses_legacy_backup_of_same_project(tmp_path):
    path=create_project(tmp_path/'Game','Game'); legacy=path.with_name('project.json')
    save_json(legacy,dict(version=1,name='Game',graph='graphs/gameplay.json',scene='scenes/main.json'))
    config=settings(tmp_path/'user.ini'); assert remember_project(config,legacy)
    assert remember_project(config,path)
    assert recent_projects(config)==[str(path)] and legacy.is_file()


def test_browser_restores_known_projects_without_inventing_history(app,tmp_path):
    path=create_project(tmp_path/'workspace'/'Old game','Old game')
    config=settings(tmp_path/'user.ini')
    browser=ProjectLauncher(config,project_roots=[path.parent.parent])
    assert browser.recent.count()==1 and recent_projects(config)==[]
    data=browser.recent.item(0).data(Qt.ItemDataRole.UserRole+1)
    assert data['source']=='existing' and not data['opened_at']
    assert 'Discovered' in browser.detail_fields.text()
    browser.search.setText('not found')
    assert browser.recent.count()==0 and not browser.open_button.isEnabled() and not browser.path.text()
    browser.new_project(); assert browser.mode=='new' and browser.open_button.isEnabled()
    browser.search.setText('not found'); assert not browser.open_button.isEnabled()
    browser.reject(); browser.deleteLater()


def test_browser_legacy_recent_order_version_preview_and_search(app,tmp_path):
    first=create_project(tmp_path/'Zed','Zed'); second=create_project(tmp_path/'Alpha','Alpha')
    config=settings(tmp_path/'user.ini'); config.setValue('projects/recent',[str(first),str(second)])
    browser=ProjectLauncher(config,project_roots=[])
    assert browser.recent.item(0).data(Qt.ItemDataRole.UserRole)==str(first)
    browser.sort.setCurrentText('Name')
    assert browser.recent.item(0).data(Qt.ItemDataRole.UserRole)==str(second)
    assert browser.recent.currentItem().data(Qt.ItemDataRole.UserRole)==str(first)
    browser.recent.setCurrentRow(0)
    assert '0.1.0' in browser.detail_fields.text() and str(second.parent) in browser.detail_fields.text()
    browser.search.setText('Zed'); assert browser.recent.count()==1 and browser.path.text()==str(first)
    browser.reject(); browser.deleteLater()


def test_browser_creates_real_2d_template_and_double_click_only_selects(app,tmp_path):
    config=settings(tmp_path/'user.ini')
    browser=ProjectLauncher(config,start_new=True,project_roots=[])
    browser.directory.setText(str(tmp_path/'New game')); browser.name.setText('Trò chơi 2D')
    browser.show(); app.processEvents(); item=browser.recent.item(1)
    browser.recent.setCurrentItem(item)
    QTest.mouseDClick(browser.recent.viewport(),Qt.MouseButton.LeftButton,pos=browser.recent.visualItemRect(item).center())
    browser.recent.itemActivated.emit(item)
    assert browser.project_path is None and not (tmp_path/'New game').exists()
    QTest.mouseClick(browser.open_button,Qt.MouseButton.LeftButton)
    manifest,graph,scene=load_project(browser.project_path)
    assert manifest['name']=='Trò chơi 2D' and scene['active_camera']=='camera'
    assert manifest['editor']['node_workflow']=='2d'
    camera=next(e for e in scene['entities'] if e['id']=='camera')
    assert camera['camera']['projection']=='orthographic'
    browser.deleteLater()


def test_added_search_folder_survives_restart_and_keyboard_opens_legacy(app,tmp_path,monkeypatch):
    path=create_project(tmp_path/'older-projects'/'Game','Older project')
    config=settings(tmp_path/'user.ini')
    browser=ProjectLauncher(config,project_roots=[])
    assert browser.recent.count()==0
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(path.parent.parent))
    browser.add_folder(); assert browser.recent.count()==1
    browser.reject(); browser.deleteLater()
    restored=ProjectLauncher(settings(tmp_path/'user.ini'),project_roots=[])
    assert restored.recent.count()==1 and not recent_projects(config)
    restored.show(); app.processEvents(); restored.recent.setFocus()
    QTest.keyClick(restored.recent,Qt.Key.Key_Return)
    assert restored.result()==QDialog.DialogCode.Accepted and restored.project_path==path
    restored.deleteLater()


def test_small_browser_keeps_primary_controls_inside_window(app,tmp_path):
    browser=ProjectLauncher(settings(tmp_path/'user.ini'),project_roots=[])
    browser.resize(960,570); browser.show(); app.processEvents()
    assert browser.width()==960 and browser.height()==570
    for mode in ('recent','new'):
        browser.change_mode(mode); browser.resize(1180,720); app.processEvents()
        browser.resize(960,570); app.processEvents()
        assert browser.size().width()==960 and browser.size().height()==570
        for widget in (browser.open_button,browser.search,browser.browse_button if mode=='recent' else browser.name):
            bounds=widget.rect().translated(widget.mapTo(browser,widget.rect().topLeft()))
            assert browser.rect().contains(bounds),(mode,widget,bounds)
    browser.reject(); browser.deleteLater()
