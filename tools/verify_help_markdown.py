"""Exercise F1, project Markdown creation, preview, save and reopen in the real editor."""
import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QImage, QPixmap, QTextDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QPushButton
from editor.core.document import create_project, save_json
from editor.ui.main_window import MainWindow
from editor.ui.project_markdown import ProjectMarkdownDialog


def verify(output):
    output = Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    report = dict(passed=False,checks=[])
    save_json(output/'checks.json',report)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    settings = QSettings(str(output/'settings.ini'),QSettings.Format.IniFormat)
    errors = []
    window = MainWindow(ROOT/'templates/games/flappy_bird/flappy_bird.nen',settings)
    def check(label,value):
        assert value,label
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate):
        for _ in range(100):
            if predicate(): return
            QTest.qWait(20)
        assert predicate(),'Timed out waiting for editor action'
    def later(callback):
        def guarded():
            try:callback()
            except BaseException as error:
                errors.append(repr(error))
                dialog = QApplication.activeModalWidget()
                if isinstance(dialog,ProjectMarkdownDialog): dialog.editor.document().setModified(False)
                if dialog:dialog.reject()
        QTimer.singleShot(150,guarded)
    def capture(widget,name):
        app.processEvents();check(name+' screenshot',widget.grab().save(str(output/(name+'.png'))))
    try:
        window.show(); window.raise_(); window.activateWindow(); QTest.qWait(200)
        signature = window.signature()
        node = next(n for n in window.adapter.graph.all_nodes() if n.get_property('type_id')==2001)
        window.adapter.focus(node.get_property('stable_id'))
        window.adapter.graph.widget.setFocus(); QTest.keyClick(window,Qt.Key.Key_F1)
        wait(lambda:getattr(window,'node_help_dialog',None) is not None)
        help_dialog = window.node_help_dialog
        check('F1 opens selected Branch help',help_dialog.current_spec.id==2001)
        help_dialog.search.setText('5010')
        item = next(help_dialog.tree.topLevelItem(i).child(0) for i in range(1,help_dialog.tree.topLevelItemCount())
                    if help_dialog.tree.topLevelItem(i).childCount())
        help_dialog.tree.setCurrentItem(item)
        check('Search selects Start Timer with real IO','Seconds' in help_dialog.browser.toPlainText() and help_dialog.current_spec.id==5010)
        capture(help_dialog,'node-help')
        help_dialog.follow_link(QUrl('guide:flappy'));capture(help_dialog,'template-guide')
        check('Help opens complete game guide','Advance Pipe 3' in help_dialog.browser.toPlainText())
        help_dialog.close();app.processEvents()
        check('Reading Help leaves project unchanged',window.signature()==signature and not window.dirty)
        def inspect_template_markdown():
            dialog=QApplication.activeModalWidget();assert isinstance(dialog,ProjectMarkdownDialog)
            index=next(i for i in range(dialog.files.count()) if dialog.files.item(i).text()=='docs/guide.md')
            QTest.mouseClick(dialog.files.viewport(),Qt.MouseButton.LeftButton,pos=dialog.files.visualItemRect(dialog.files.item(index)).center())
            check('File menu opens template project Markdown',dialog.current_path.name=='guide.md')
            capture(dialog,'template-markdown');dialog.reject()
        later(inspect_template_markdown)
        window.actions['Project Markdown…'].trigger()
        assert not errors,errors
        sandbox=output/'Trò chơi Markdown'
        project=create_project(sandbox,'Trò chơi Markdown')
        shutil.copy2(ROOT/'docs/images/games/flappy.png',sandbox/'assets/example.png')
        check('New projects include README and gitignore',(sandbox/'README.md').exists() and (sandbox/'.gitignore').exists())
        check('Editor opens newly created project',window.open_project(project))
        original=project.read_bytes()
        text='# Hướng dẫn thử thực tế\n\n| IN | OUT |\n| --- | --- |\n| 1 | 2 |\n\n![Ảnh game](../assets/example.png)\n\n```text\nOn Game Start → Branch\n```\n'
        def edit_markdown():
            dialog=QApplication.activeModalWidget();assert isinstance(dialog,ProjectMarkdownDialog)
            def name_file():
                name=QApplication.activeModalWidget();assert isinstance(name,QInputDialog)
                name.setTextValue('docs/hướng dẫn.md');name.accept()
            later(name_file)
            button=next(b for b in dialog.findChildren(QPushButton) if b.text()=='New .md')
            QTest.mouseClick(button,Qt.MouseButton.LeftButton)
            assert not errors,errors
            check('New .md creates a Unicode project document',dialog.current_path.name=='hướng dẫn.md')
            dialog.editor.selectAll();dialog.editor.insertPlainText(text)
            dialog.update_preview();app.processEvents()
            check('Preview renders headings, table and code','OUT' in dialog.preview.toPlainText() and 'On Game Start' in dialog.preview.toPlainText())
            resource=dialog.preview.document().resource(QTextDocument.ResourceType.ImageResource,QUrl.fromLocalFile(str(sandbox/'assets/example.png')))
            check('Preview loads real relative image',isinstance(resource,(QImage,QPixmap)) and not resource.isNull())
            dialog.editor.setFocus();QTest.keyClick(dialog.editor,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
            check('Ctrl+S persists exact Markdown text',(sandbox/'docs/hướng dẫn.md').read_text('utf-8')==text and not dialog.editor.document().isModified())
            capture(dialog,'markdown-edit-preview');dialog.reject()
        later(edit_markdown)
        window.actions['Project Markdown…'].trigger()
        assert not errors,errors
        def reopen_markdown():
            dialog=QApplication.activeModalWidget();assert isinstance(dialog,ProjectMarkdownDialog)
            check('Saved Markdown reopens from disk',dialog.open_document('docs/hướng dẫn.md') and dialog.editor.toPlainText()==text)
            capture(dialog,'markdown-reopened');dialog.reject()
        later(reopen_markdown);window.actions['Project Markdown…'].trigger()
        assert not errors,errors
        check('Writing docs preserves .nen and authored graph',project.read_bytes()==original and not window.dirty)
        report['passed']=True
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        window.dirty=False;window.close();window.deleteLater();app.processEvents()
        save_json(output/'checks.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/validation/template-help/help-ui')
    verify(parser.parse_args().output)
