from editor.core.compiler import GraphError, compile_graph
from editor.core.codegen import CppEmitter, generate_node_code
from editor.core.document import default_scene
import json
import pytest
from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from editor.core.node_code import default_node_code, validate_embedded_code, render_embedded_code, runtime_source_excerpt, parse_compiler_diagnostic
from editor.ui.graph import GraphAdapter
from editor.ui.node_code import NodeCodeDialog


def action_graph(code):
    return {
        'version': 1,
        'name': 'EmbeddedCode',
        'nodes': [
            {'id': 'start', 'type': 1001, 'values': {}},
            {'id': 'scale', 'type': 5030, 'values': {'Scale': 0.5}, 'code': code},
        ],
        'links': [{'from': ['start', 'Out'], 'to': ['scale', 'In']}],
    }


def test_embedded_code_is_validated_lowered_and_exported():
    ir = compile_graph(action_graph('ctx.time_scale = 0.5;'), default_scene())
    assert ir['events']['start'][0]['code'] == 'ctx.time_scale = 0.5;'
    source = generate_node_code(ir)
    assert '// embedded node code:scale' in source
    assert 'ctx.time_scale = 0.5;' in source
    assert 'rt::SetTimeScale(ctx, input_0);' in source
    assert 'rt::RunNodeCode' in CppEmitter().generate(ir)


def test_embedded_code_marker_wraps_generated_call():
    source = generate_node_code(compile_graph(action_graph('{ {{call}} }'), default_scene()))
    assert '{ rt::SetTimeScale(ctx, input_0); }' in source.replace('\n', ' ')


def test_action_result_marker_keeps_result_alive_outside_wrapper():
    graph = {
        'version': 1,
        'nodes': [
            {'id': 'start', 'type': 1001, 'values': {}},
            {'id': 'change', 'type': 7004, 'values': {'Scene': 'main'}, 'code': '{ {{call}} }'},
        ],
        'links': [{'from': ['start', 'Out'], 'to': ['change', 'In']}],
    }
    source = generate_node_code(compile_graph(graph, default_scene()))
    assert 'bool result{};' in source and 'result = rt::ChangeScene' in source


def test_invalid_embedded_code_reports_graph_problem():
    try:
        compile_graph(action_graph('ctx.time_scale = 0.5; }'), default_scene())
    except GraphError as error:
        assert 'Embedded code line 1' in str(error)
    else:
        raise AssertionError('invalid embedded code was accepted')
    assert validate_embedded_code('#include <vector>')


def test_node_code_roundtrips_through_graph_adapter(app):
    adapter = GraphAdapter()
    node = adapter.add(5030)
    custom = 'ctx.time_scale = 0.25;'
    node.set_property('embedded_code', custom)
    document = adapter.document()
    assert document['nodes'][0]['code'] == custom
    reopened = GraphAdapter()
    reopened.load(document)
    restored = reopened.graph.all_nodes()[0]
    assert restored.get_property('embedded_code') == custom
    assert default_node_code(reopened.registry[5030]).startswith('rt::SetTimeScale')


def test_node_code_dialog_edits_actions_and_locks_generated_pure_nodes(app):
    adapter = GraphAdapter()
    action = adapter.add(5030)
    action_dialog = NodeCodeDialog(adapter.registry[5030], action)
    action_dialog.editor.setPlainText('ctx.time_scale = 0.25;')
    action_dialog.accept()
    assert action_dialog.result_code == 'ctx.time_scale = 0.25;'

    pure = adapter.add(9001)
    pure_dialog = NodeCodeDialog(adapter.registry[9001], pure)
    assert pure_dialog.editor.isReadOnly()
    pure_dialog.reject()


@pytest.mark.parametrize('code', [
    '/* comment\n } #include <x>\n */\n{{call}}',
    'const auto s = R"text({ } " #include {{call}})text";\n{{call}}',
    '// {{call}} is only a comment\n{{call}}',
    'const auto count = 1\'000; const auto letter=\'a\';\n{{call}}',
    'const auto text = "using namespace #include {{call}}";\n{{call}}',
])
def test_cpp_comments_literals_and_separators_do_not_change_markers(code):
    assert not validate_embedded_code(code)
    rendered, used_call = render_embedded_code(code, 'actual_call();')
    assert used_call and rendered.endswith('actual_call();')
    assert rendered.count('actual_call();') == 1


def test_marker_only_in_comment_still_appends_default_call():
    ir = compile_graph(action_graph('// {{call}}'), default_scene())
    source = generate_node_code(ir)
    assert '// {{call}}' in source and 'rt::SetTimeScale(ctx, input_0);' in source
    assert validate_embedded_code('/* unfinished')[0].message == 'Unterminated block comment'


def test_runtime_view_finds_definition_instead_of_declaration():
    adapter = GraphAdapter()
    source = runtime_source_excerpt(adapter.registry[5030])
    assert 'runtime/src/game_time.cpp:' in source
    assert 'c.time_scale=scale;' in source.replace(' ', '')


def test_compiler_diagnostic_and_fragmented_build_output(app):
    from editor.services import BuildService
    line = 'node-code:60001/scale:3:7: error: use of undeclared identifier\r'
    expected = dict(node='60001/scale', line=3, column=7, severity='error', message='use of undeclared identifier')
    assert parse_compiler_diagnostic(line.rstrip()) == expected
    service = BuildService()
    found = []
    service.diagnostic.connect(found.append)
    service._parse_output('noise\n' + line[:32])
    assert not found
    service._parse_output(line[32:])
    service._parse_output('', final=True)
    assert found == [expected]


def test_code_editor_indentation_undo_and_error_navigation(app):
    adapter = GraphAdapter()
    node = adapter.add(5030)
    dialog = NodeCodeDialog(adapter.registry[5030], node)
    dialog.show()
    dialog.editor.setPlainText('if (true) {')
    dialog.editor.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClick(dialog.editor, Qt.Key.Key_Return)
    assert dialog.editor.toPlainText() == 'if (true) {\n    '
    QTest.keyClick(dialog.editor, Qt.Key.Key_Tab)
    assert dialog.editor.toPlainText().endswith('\n        ')
    QTest.keyClick(dialog.editor, Qt.Key.Key_Backtab)
    assert dialog.editor.toPlainText().endswith('\n    ')
    dialog.editor.undo()
    assert dialog.editor.toPlainText().endswith('\n        ')
    dialog.editor.setPlainText('{{call}}\nctx.time_scale = missing;')
    dialog.editor.go_to_line(2, 18)
    assert dialog.editor.textCursor().blockNumber() == 1
    assert dialog.editor.textCursor().positionInBlock() == 17
    dialog.reject()


def test_real_modal_save_undo_redo_and_project_reopen(app, tmp_path):
    from editor.ui.main_window import MainWindow
    from editor.core.document import create_project, load_project
    project = create_project(tmp_path / 'code-project', 'Node code proof')
    window = MainWindow(project, settings=QSettings(str(tmp_path/'settings.ini'), QSettings.Format.IniFormat))
    window.show()
    app.processEvents()
    window.adapter.load(action_graph(''))
    node = next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id') == 'scale')
    code = '{{call}}\nctx.time_scale = input_0 * 0.5; // tiếng Việt'
    def save_code():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, NodeCodeDialog)
        dialog.editor.setPlainText(code)
        QTest.keyClick(dialog.editor, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    QTimer.singleShot(100, save_code)
    assert window.edit_node_code(node)
    assert node.get_property('embedded_code') == code
    window.adapter.graph.undo_stack().undo()
    assert node.get_property('embedded_code') == ''
    window.adapter.graph.undo_stack().redo()
    assert node.get_property('embedded_code') == code
    window.save_project()
    _, saved_graph, _ = load_project(project)
    assert next(n for n in saved_graph['nodes'] if n['id'] == 'scale')['code'] == code
    window.close()


def test_compiler_problem_opens_code_at_reported_line(app, tmp_path):
    from editor.ui.main_window import MainWindow
    from editor.core.document import create_project
    path = create_project(tmp_path/'diagnostic-project', 'Compiler problem proof')
    window = MainWindow(path, settings=QSettings(str(tmp_path/'ui.ini'), QSettings.Format.IniFormat))
    window.show()
    app.processEvents()
    window.adapter.load(action_graph('{{call}}\nctx.time_scale = missing;'))
    diagnostic = dict(node='scale', line=2, column=18, severity='error', message='Unknown symbol: missing')
    window.build_diagnostic(diagnostic)
    visited = []
    def inspect_error():
        dialog = QApplication.activeModalWidget()
        visited.append((dialog.editor.textCursor().blockNumber(), dialog.editor.textCursor().positionInBlock()))
        assert 'Unknown symbol' in dialog.error.text()
        dialog.reject()
    QTimer.singleShot(100, inspect_error)
    window.activate_problem(window.problems.item(0))
    assert visited == [(1, 17)]
    window.dirty = False
    window.close()


def test_function_graph_code_editor_uses_function_undo_and_save(app):
    from editor.core.functions import new_function, ENTRY, RETURN
    from editor.ui.functions import FunctionEditorDialog
    f = new_function('Authored code', [], [])
    f['graph'] = {'version':1, 'nodes':[
        {'id':'entry', 'type':ENTRY, 'values':{}},
        {'id':'code', 'type':27006, 'values':{}},
        {'id':'return', 'type':RETURN, 'values':{}},
    ], 'links':[
        {'from':['entry','Out'], 'to':['code','In']},
        {'from':['code','Out'], 'to':['return','In']},
    ]}
    dialog = FunctionEditorDialog([f], f['id'], default_scene())
    node = next(n for n in dialog.adapter.graph.all_nodes() if n.get_property('stable_id') == 'code')
    dialog.inspect(node)
    def save_code():
        editor = QApplication.activeModalWidget()
        editor.editor.setPlainText('rt::SetTimeScale(ctx, 0.75);')
        editor.accept()
    QTimer.singleShot(100, save_code)
    assert dialog.edit_node_code()
    dialog.adapter.graph.undo_stack().undo()
    assert node.get_property('embedded_code') == ''
    dialog.adapter.graph.undo_stack().redo()
    dialog.accept()
    saved = next(n for n in dialog.result_definitions[0]['graph']['nodes'] if n['id'] == 'code')
    assert saved['code'] == 'rt::SetTimeScale(ctx, 0.75);'


def test_embedded_robot_example_exports_shared_hooks():
    from editor.core.document import load_project
    from editor.core.registry import ROOT
    _, graph, scene = load_project(ROOT / 'examples/embedded_code_demo/project.json')
    ir = compile_graph(graph, scene)
    source = generate_node_code(ir)
    assert graph['nodes'][1]['type'] == 27006
    assert 'input_0' in source and 'rt::Translate' in source
    assert 'rt::Rotate' in source and 'Embedded C++ is running' in source
    assert scene['active_camera'] == 'camera'


def test_code_survives_duplicate_paste_and_undo(app):
    adapter = GraphAdapter()
    node = adapter.add(27006)
    node.set_property('embedded_code', 'rt::SetTimeScale(ctx, 0.5);')
    node.set_selected(True)
    adapter.duplicate()
    assert len(adapter.graph.all_nodes()) == 2
    assert all(n.get_property('embedded_code') == 'rt::SetTimeScale(ctx, 0.5);' for n in adapter.graph.all_nodes())
    adapter.graph.undo_stack().undo()
    assert len(adapter.graph.all_nodes()) == 1
    adapter.graph.copy_nodes([node])
    adapter.paste()
    assert len(adapter.graph.all_nodes()) == 2
    assert all(n.get_property('embedded_code') == 'rt::SetTimeScale(ctx, 0.5);' for n in adapter.graph.all_nodes())


def test_preview_requires_project_specific_hook_stamp(app, tmp_path, monkeypatch):
    from editor.ui.main_window import MainWindow
    from editor.core.document import create_project
    from editor.core.registry import ROOT
    path = create_project(tmp_path/'stamp-project', 'Hook fingerprint')
    window = MainWindow(path, settings=QSettings(str(tmp_path/'stamp.ini'), QSettings.Format.IniFormat))
    seen = []
    def current(executable, expected, *, node_code=None):
        seen.append((executable, node_code))
        return True
    monkeypatch.setattr('editor.ui.main_window.runtime_current', current)
    first = compile_graph(action_graph('{{call}}\nctx.time_scale = 0.25;'), default_scene())
    assert window.preview_executable(first).parent == path.parent/'build'
    original_hash = seen[-1][1]
    assert original_hash
    assert not any(exe.parent == ROOT/'build' for exe, _ in seen)
    second = compile_graph(action_graph('{{call}}\nctx.time_scale = 0.75;'), default_scene())
    window.preview_executable(second)
    assert seen[-1][1] != original_hash
    window.close()


def test_generated_view_shows_actual_arguments_events_and_flow():
    from editor.core.node_code import generated_node_code
    from editor.core.builder import GraphBuilder
    b = GraphBuilder('Generated code view')
    b.add('start', 'On Game Start')
    b.add('branch', 'Branch', Condition=True)
    b.add('scale', 'Set Time Scale', Scale=0.5)
    b.connect('start', 'Out', 'branch', 'In').connect('branch', 'True', 'scale', 'In')
    ir = b.compile()
    for node_id, name in [('start', 'On Game Start'), ('branch', 'Branch'), ('scale', 'Set Time Scale')]:
        text, line = generated_node_code(ir, node_id, b.registry.by_name(name))
        assert 'rt::SetTimeScale(ctx, 0.5);' in text
        assert 'if (true)' in text
        assert 'CompiledProgram JSON omitted' in text
        expected = 'void OnStart(' if node_id == 'start' else f'rt::Tick(ctx, "{node_id}");'
        assert expected in text.splitlines()[line - 1]

