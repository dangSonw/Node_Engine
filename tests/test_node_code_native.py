"""Embedded code must affect real Preview and Game state identically."""
import json
from pathlib import Path
import subprocess

import pytest

from editor.core.builder import GraphBuilder
from editor.core.document import default_scene, save_json
from editor.core.data_types import declaration
from tests.test_native import native, tool


def test_embedded_code_executes_after_call_in_both_hosts(native):
    b = GraphBuilder('Embedded ordering')
    b.add('start', 'On Game Start')
    b.add('scale', 'Set Time Scale', Scale=0.5)
    b.graph['nodes'][-1]['code'] = '{{call}}\nctx.time_scale = input_0 * 0.5;'
    b.connect('start', 'Out', 'scale', 'In')
    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['clock']['scale'] == 0.25


def test_embedded_action_result_and_local_output(native):
    b = GraphBuilder('Embedded result')
    b.add('start', 'On Game Start')
    b.add('item', 'Add Inventory Item', Entity='player', Item='apple', Count=2)
    b.graph['nodes'][-1]['code'] = '{ {{call}} }\nresult = false;'
    b.add('store', 'Set Boolean Variable', Name='accepted')
    b.connect('start', 'Out', 'item', 'In').connect('item', 'Out', 'store', 'In')
    b.connect('item', 'Accepted', 'store', 'Value')
    scene = default_scene()
    scene['variables']['accepted'] = declaration('bool', True)
    preview, game = native(b.graph, scene=scene, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['accepted'] == {'type': 'bool', 'value': False}
    assert left['scene']['inventories']['player']['apple'] == 2


def test_embedded_code_after_delay_keeps_post_call_statements(native):
    b = GraphBuilder('Embedded continuation')
    b.add('start', 'On Game Start')
    b.add('wait', 'Delay', Seconds=0.01)
    b.add('scale', 'Set Time Scale', Scale=0.5)
    b.graph['nodes'][-1]['code'] = '{{call}}\nctx.time_scale = 0.125;'
    b.connect('start', 'Out', 'wait', 'In').connect('wait', 'Out', 'scale', 'In')
    preview, game = native(b.graph, frames=2)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['clock']['scale'] == 0.125


def test_preview_rejects_changed_code_until_rebuilt(native):
    b = GraphBuilder('Stale embedded code')
    b.add('start', 'On Game Start')
    b.add('scale', 'Set Time Scale', Scale=0.5)
    b.graph['nodes'][-1]['code'] = '{{call}}\nctx.time_scale = 0.25;'
    b.connect('start', 'Out', 'scale', 'In')
    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    path = Path(preview.args[preview.args.index('--ir') + 1])
    changed = json.loads(path.read_text('utf-8'))
    changed['events']['start'][0]['code'] = '{{call}}\nctx.time_scale = 0.75;'
    save_json(path, changed)
    stale = subprocess.run(preview.args, capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert stale.returncode != 0
    assert 'not compiled' in stale.stderr and 'scale' in stale.stderr


def test_dedicated_cpp_node_and_scene_scoped_handlers(native):
    scenes = {}
    for name, value in [('menu', 3.0), ('level', 7.0)]:
        b = GraphBuilder(name)
        b.add('loaded', 'On Scene Loaded')
        b.add('code', 'C++ Code')
        b.graph['nodes'][-1]['code'] = f'rt::SetVariable(ctx, "result", {value});'
        b.connect('loaded', 'Out', 'code', 'In')
        if name == 'menu':
            b.add('start', 'On Game Start')
            b.add('change', 'Change Scene', Scene='level')
            b.connect('start', 'Out', 'change', 'In')
        scenes[name] = b.compile()
    program = dict(version=1, entry_scene='menu', scenes=scenes)
    preview, game = native(program=program, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['scene_session']['active'] == 'level'
    assert left['variables']['result'] == 7.0


def test_real_compiler_error_retains_node_and_code_line(tmp_path):
    from editor.core.codegen import generate_node_code
    from editor.core.node_code import parse_compiler_diagnostic
    from editor.core.registry import ROOT
    compiler = tool('clang++')
    if not compiler:
        pytest.skip('Native compiler not installed')
    b = GraphBuilder('Compiler error origin')
    b.add('start', 'On Game Start')
    b.add('bad-code', 'C++ Code')
    b.graph['nodes'][-1]['code'] = '// intentional compiler error\nctx.time_scale = missing_symbol;'
    b.connect('start', 'Out', 'bad-code', 'In')
    program = dict(version=1, entry_scene='level', scenes={'level': b.compile()})
    source = tmp_path / 'bad.generated.cpp'
    source.write_text(generate_node_code(program), encoding='utf-8')
    includes = ['runtime/include', 'deps/include', 'deps/glm-1.0.1', 'deps/flecs-4.1.6']
    command = [compiler, '-std=c++20', '-fsyntax-only', '-fno-color-diagnostics',
               '-DFLECS_CUSTOM_BUILD', '-DFLECS_OS_API_IMPL', *[f'-I{ROOT/p}' for p in includes], str(source)]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode != 0
    errors = [parse_compiler_diagnostic(line) for line in result.stderr.splitlines()]
    assert any(d and d['node'] == 'level/bad-code' and d['line'] == 2 and 'missing_symbol' in d['message'] for d in errors), result.stderr
