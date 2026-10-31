"""Actual Qt dialogs: one project refactor updates active and inactive scenes."""
import argparse
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPushButton
from editor.core.document import create_project,save_json,load_project
from editor.core.projects import add_scene,compile_project,project_snapshot
from editor.core.builder import GraphBuilder
from editor.ui.main_window import MainWindow
from editor.ui.user_types import TypeLibraryDialog,TypeSignatureDialog


def verify(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    path=create_project(output/'Project','Project type authoring')
    manifest=add_scene(path,'level')
    structs=[dict(name='Stats',fields=[dict(name='hp',type='int',default=7)])]
    b=GraphBuilder(struct_definitions=structs)
    b.add('start','On Game Start'); b.add('make','Make Stats',hp=42)
    b.add('read','Break Stats'); b.add('store','Set Integer Variable',Name='seen')
    b.connect('start','Out','store','In').connect('make','Value','read','Value').connect('read','hp','store','Value')
    for entry in manifest['scenes']:
        scene=dict(entities=[],variables={'stats':dict(type='struct:Stats',value=dict(hp=88))},struct_definitions=structs)
        save_json(path.parent/entry['graph'],b.graph); save_json(path.parent/entry['scene'],scene)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    settings=QSettings(str(output/'settings.ini'),QSettings.Format.IniFormat)
    window=MainWindow(path,settings); window.show()
    checks={}; errors=[]
    def capture(widget,name):
        app.processEvents(); assert widget.grab().save(str(output/(name+'.png')))
    def run(callback):
        try: callback()
        except BaseException:
            errors.append(traceback.format_exc())
            dialog=QApplication.activeModalWidget()
            if isinstance(dialog,QDialog): dialog.reject()
            window.dirty=False; window.close(); app.exit(1)
    def later(callback): QTimer.singleShot(100,lambda:run(callback))
    def start():
        checks['original_all_scenes_compile']=bool(compile_project(project_snapshot(path)))
        later(library); window.actions['Structs and Enums…'].trigger()
    def library():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,TypeLibraryDialog)
        assert 'Project' in dialog.windowTitle(); checks['project_library_dialog']=True
        dialog.list.setCurrentRow(0); capture(dialog,'library-before')
        later(signature)
        QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Edit selected'),Qt.MouseButton.LeftButton)
    def signature():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,TypeSignatureDialog)
        dialog.name_field.setText('Vitals'); dialog.table.item(0,0).setText('health')
        capture(dialog,'rename-type-and-field'); later(apply)
        QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    def apply():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,TypeLibraryDialog)
        assert dialog.result_snapshot['scenes']['level']['scene']['variables']['stats']['value']=={'health':88}
        capture(dialog,'library-after'); checks['inactive_scene_migrated_before_commit']=True
        later(editor)
        QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    def editor():
        assert window.dirty and window.adapter.registry.by_name('Make Vitals')
        after=window.signature(); window.actions['Undo'].trigger()
        assert window.adapter.registry.by_name('Make Stats') and not window.dirty
        window.actions['Redo'].trigger(); assert window.signature()==after
        checks['one_undo_redo_across_project']=True
        window.actions['Save'].trigger(); assert not window.dirty
        for entry in manifest['scenes']:
            _,graph,scene=load_project(path,entry['id'])
            assert scene['variables']['stats']['value']=={'health':88}
            assert any(link['from']==['read','health'] for link in graph['links'])
        checks['all_scene_files_saved']=True
        assert window.open_project(path,'level')
        window.library_search.setText('Vitals'); capture(window,'inactive-scene-reopened')
        checks['inactive_scene_reopened']=window.adapter.registry.by_name('Make Vitals').id>=700000
        add_scene(path,'new_level')
        assert load_project(path,'new_level')[2]['struct_definitions'][0]['name']=='Vitals'
        checks['new_scene_inherits_library']=True
        checks['saved_project_compiles']=bool(compile_project(project_snapshot(path)))
        window.close(); app.quit()
    watchdog=QTimer(); watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda:run(lambda:(_ for _ in ()).throw(TimeoutError('Project types proof exceeded 60 seconds'))))
    watchdog.start(60000); later(start); app.exec(); watchdog.stop()
    result=dict(checks=checks,errors=errors,project=str(path)); save_json(output/'checks.json',result)
    assert len(checks)==8 and all(checks.values()) and not errors,result
    print(__import__('json').dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args().output)
