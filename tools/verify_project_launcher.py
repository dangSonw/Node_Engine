"""Exercise the actual startup entry point and project manager in a fresh Qt process."""
import argparse
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QDialogButtonBox
from editor.main import main
from editor.ui.main_window import MainWindow
from editor.ui.project_launcher import ProjectLauncher, recent_projects
from editor.core.document import create_project, save_json
from editor.core.project_format import load_manifest
from editor.core.projects import compile_project, project_snapshot


def verify(output):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    project_root=output/'Game project'
    if project_root.exists():
        raise ValueError('Choose a fresh output directory; existing proof projects are preserved')
    app=QApplication.instance() or QApplication([])
    checks={}; errors=[]
    path=project_root/'Game project.nen'

    def capture(widget,name):
        app.processEvents()
        assert widget.grab().save(str(output/(name+'.png')))

    def run(callback):
        try:
            callback()
        except BaseException:
            errors.append(traceback.format_exc())
            modal=QApplication.activeModalWidget()
            if modal: modal.reject()
            for widget in app.topLevelWidgets():
                if isinstance(widget,MainWindow):
                    widget.dirty=False; widget.close()
            app.exit(1)

    def schedule(callback):
        QTimer.singleShot(180,lambda:run(callback))

    def welcome():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,ProjectLauncher)
        assert not any(isinstance(w,MainWindow) for w in app.topLevelWidgets())
        checks['welcome_before_editor']=True
        capture(dialog,'welcome')
        QTest.mouseClick(dialog.new_button,Qt.MouseButton.LeftButton)
        schedule(new_project)

    def new_project():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,ProjectLauncher) and dialog.mode=='new'
        dialog.name.setText('Trò chơi thử nghiệm')
        dialog.directory.setText(str(project_root))
        capture(dialog,'new-project')
        schedule(editor)
        QTest.mouseClick(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)

    def editor():
        window=next(w for w in app.topLevelWidgets() if isinstance(w,MainWindow) and w.isVisible())
        assert window.project_path==path and path.is_file()
        manifest=load_manifest(path)
        assert manifest['name']=='Trò chơi thử nghiệm' and manifest['entry_scene']=='main'
        assert all((path.parent/folder).is_dir() for folder in ('scenes','graphs','assets/models','assets/textures','assets/audio','assets/ui','assets/prefabs'))
        checks['new_project_nen_and_structure']=True
        window.actions['Create Entity'].trigger()
        entity=window.selected_entity_id()
        field=next(f for f in window.inspector.findChildren(QLineEdit) if f.accessibleName()==f'{entity} name')
        field.setText('Nhân vật mới'); field.editingFinished.emit()
        assert window.dirty
        window.actions['Save'].trigger()
        assert not window.dirty
        checks['unicode_inspector_save']=True
        capture(window,'editor-created')
        schedule(manager)
        window.actions['Project Manager…'].trigger()

    def manager():
        dialog=QApplication.activeModalWidget()
        assert isinstance(dialog,ProjectLauncher)
        assert str(path) in recent_projects(dialog.settings)
        checks['project_manager_and_recent_history']=True
        incompatible=create_project(output/'Future project','Future version')
        raw=load_manifest(incompatible); raw['engine']['minimum_version']='99.0.0'; save_json(incompatible,raw)
        before=incompatible.read_bytes()
        dialog.path.setText(str(incompatible))
        QTest.mouseClick(dialog.open_button,Qt.MouseButton.LeftButton)
        assert dialog.isVisible() and 'requires Node_Engine 99.0.0' in dialog.message.text()
        assert incompatible.read_bytes()==before
        checks['future_engine_rejected_without_writes']=True
        capture(dialog,'incompatible-version')
        dialog.path.setText(str(path))
        schedule(reopened)
        QTest.mouseClick(dialog.open_button,Qt.MouseButton.LeftButton)

    def reopened():
        window=next(w for w in app.topLevelWidgets() if isinstance(w,MainWindow) and w.isVisible())
        assert window.project_path==path and not window.dirty
        assert any(e['name']=='Nhân vật mới' for e in window.scene['entities'])
        assert compile_project(project_snapshot(path))['entry_scene']=='main'
        checks['saved_project_reopened_and_compiled']=True
        capture(window,'editor-reopened')
        window.close()

    watchdog=QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda:run(lambda:(_ for _ in ()).throw(TimeoutError('Startup proof exceeded 30 seconds'))))
    watchdog.start(30000)
    schedule(welcome)
    code=main([],settings=QSettings(str(output/'settings/browser.ini'),QSettings.Format.IniFormat))
    watchdog.stop()
    result={'checks':checks,'errors':errors,'project':str(path),'exit_code':code}
    save_json(output/'checks.json',result)
    assert not errors and len(checks)==6 and code==0,result
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args().output)
