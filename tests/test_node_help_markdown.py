"""Offline help signatures and real project Markdown save/reopen behavior."""
import json
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QPixmap, QTextDocument
from PySide6.QtWidgets import QInputDialog, QMessageBox
from editor.core.document import create_project
from editor.core.registry import Registry, ROOT
from editor.core.node_help import node_markdown, examples, description
from editor.core.project_markdown import markdown_files, markdown_path
from editor.core.functions import new_function, scoped_registry
from editor.ui.node_help import NodeHelpDialog
from editor.ui.project_markdown import ProjectMarkdownDialog


def test_every_builtin_has_current_signature_and_game_examples_match_saved_nodes():
    registry = Registry()
    reference = (ROOT/'docs/node-reference.md').read_text('utf-8')
    for spec in registry.nodes.values():
        page = node_markdown(spec)
        assert description(spec) and f'ID `{spec.id}`' in page
        assert f'id="node-{spec.id}"' in reference
        for side, ports in [('IN',spec.inputs),('OUT',spec.outputs)]:
            for port in ports:
                assert f'| {side} | {port.name} | `{port.type}` |' in page
    assert len(examples()) >= 69
    for tid, example in examples().items():
        graph = json.loads((ROOT/example['graph']).read_text('utf-8'))
        body = graph if example['function']=='Gameplay' else next(f['graph'] for f in graph['functions'] if f['name']==example['function'])
        assert next(n['type'] for n in body['nodes'] if n['id']==example['node']) == int(tid)
        assert not QImage(str(ROOT/f'docs/images/node-examples/{tid}.png')).isNull()


def test_help_filters_nodes_renders_image_and_navigates_offline(app):
    registry = Registry()
    dialog = NodeHelpDialog(registry,spec=registry.by_name('Branch'))
    try:
        dialog.show(); app.processEvents()
        assert 'Condition' in dialog.browser.toPlainText()
        image = dialog.browser.document().resource(QTextDocument.ResourceType.ImageResource,QUrl('help-preview:node'))
        assert isinstance(image,QImage) and not image.isNull()
        dialog.search.setText('9002')
        groups = [dialog.tree.topLevelItem(i) for i in range(1,dialog.tree.topLevelItemCount())]
        assert sum(group.childCount() for group in groups)==1
        assert 'Set Position' in groups[0].child(0).text(0)
        dialog.search.setText('no-node-can-have-this-name')
        assert dialog.empty.isVisible()
        dialog.follow_link(QUrl('node:5010'))
        assert dialog.current_spec.name=='Start Timer'
        dialog.follow_link(QUrl('guide:snake'))
        assert 'Isometric Snake 3D' in dialog.browser.toPlainText()
        dialog.follow_link(QUrl('doc:../../README.md'))
        assert 'Không mở được' in dialog.browser.toPlainText()
    finally:
        dialog.close(); app.processEvents()


def test_help_uses_project_function_signature(app):
    function = new_function('Custom action',inputs=[dict(name='Speed',type='float',default=2.)])
    registry = scoped_registry(Registry(),[function])
    dialog = NodeHelpDialog(registry,spec=registry[function['id']])
    try:
        assert 'Speed' in dialog.browser.toPlainText() and 'Custom action' in dialog.browser.toPlainText()
    finally:
        dialog.close(); app.processEvents()


def test_markdown_create_edit_preview_save_reopen_and_relative_image(app,tmp_path,monkeypatch):
    project = create_project(tmp_path/'Trò chơi mới','Trò chơi mới')
    assert (project.parent/'README.md').exists()
    image = QImage(1000,200,QImage.Format.Format_RGB32); image.fill(0xff42ad61)
    assert image.save(str(project.parent/'assets/example.png'))
    dialog = ProjectMarkdownDialog(project)
    try:
        dialog.show(); app.processEvents()
        monkeypatch.setattr(QInputDialog,'getText',lambda *_args,**_kwargs:('docs/hướng dẫn.md',True))
        dialog.new_document()
        assert dialog.current_path.name=='hướng dẫn.md'
        text = '# Tiếng Việt\n\n| IN | OUT |\n| --- | --- |\n| 2 | 3 |\n\n![Ảnh](../assets/example.png)\n\n[README](../README.md)\n'
        dialog.editor.selectAll(); dialog.editor.insertPlainText(text)
        dialog.update_preview(); app.processEvents()
        assert 'Tiếng Việt' in dialog.preview.toPlainText() and 'OUT' in dialog.preview.toPlainText()
        loaded = dialog.preview.document().resource(QTextDocument.ResourceType.ImageResource,QUrl.fromLocalFile(str(project.parent/'assets/example.png')))
        assert isinstance(loaded,(QImage,QPixmap)) and not loaded.isNull()
        assert dialog.save_document()
        path = dialog.current_path
        assert path.read_text('utf-8')==text
        dialog.follow_link(QUrl('../README.md'))
        assert dialog.current_path.name=='README.md'
        assert dialog.open_document(path)
        assert dialog.editor.toPlainText()==text
        dialog.search.setText('hướng')
        assert sum(not dialog.files.item(i).isHidden() for i in range(dialog.files.count()))==1
    finally:
        dialog.editor.document().setModified(False); dialog.close(); app.processEvents()
    reopened = ProjectMarkdownDialog(project)
    try:
        assert reopened.open_document(path) and reopened.editor.toPlainText()==text
    finally:
        reopened.close(); app.processEvents()


def test_markdown_cancel_discard_and_external_change_never_lose_data(app,tmp_path,monkeypatch):
    project = create_project(tmp_path/'safe','Safe')
    other = project.parent/'other.md'; other.write_text('# Other\n',encoding='utf-8')
    dialog = ProjectMarkdownDialog(project)
    try:
        original = dialog.current_path
        dialog.editor.insertPlainText('unsaved ')
        monkeypatch.setattr(QMessageBox,'question',lambda *_a,**_k:QMessageBox.StandardButton.Cancel)
        assert not dialog.open_document(other) and dialog.current_path==original
        assert 'unsaved' in dialog.editor.toPlainText()
        monkeypatch.setattr(QMessageBox,'question',lambda *_a,**_k:QMessageBox.StandardButton.Discard)
        assert dialog.open_document(other)
        dialog.editor.insertPlainText('my edit ')
        other.write_text('# External change\n',encoding='utf-8')
        assert not dialog.save_document()
        assert other.read_text('utf-8')=='# External change\n'
        assert 'my edit' in dialog.editor.toPlainText()
        assert dialog.editor.document().isModified()
    finally:
        dialog.editor.document().setModified(False); dialog.close(); app.processEvents()


def test_markdown_files_keep_sources_and_reject_outputs_and_escape(tmp_path):
    project = create_project(tmp_path/'game','Game')
    for name in ('generated/trace.md','build/output.md','dist/README.md','docs/note.md'):
        path = project.parent/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('# Test',encoding='utf-8')
    assert {p.relative_to(project.parent).as_posix() for p in markdown_files(project.parent)}=={'README.md','docs/note.md'}
    for name in ('../outside.md','generated/trace.md','docs/notes.txt'):
        with pytest.raises(ValueError):markdown_path(project.parent,name)


@pytest.mark.parametrize('folder',['flappy_bird','isometric_snake_3d'])
def test_template_guide_covers_every_node_and_wire_and_has_project_local_image(folder):
    root = ROOT/'templates/games'/folder
    guide = (root/'docs/guide.md').read_text('utf-8')
    graph = json.loads((root/'graphs/gameplay.json').read_text('utf-8'))
    for label,body in [('Gameplay',graph)]+[(f['name'],f['graph']) for f in graph['functions']]:
        assert f'## {label} — {len(body["nodes"])} node' in guide
        for node in body['nodes']:
            assert f'· `{node["id"]}`' in guide
        for link in body['links']:
            assert '.'.join(map(str,link['from'])) in guide
            assert '.'.join(map(str,link['to'])) in guide
    assert not QImage(str(root/'docs/images/game.png')).isNull()
