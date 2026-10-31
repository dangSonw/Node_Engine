"""Real C++ build and execution tests; no Python runtime impersonation."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from editor.core.registry import ROOT
from editor.core.compiler import compile_graph
from editor.core.document import default_scene, save_json, write_text_if_changed
from editor.core.codegen import export, generate_adapters
from tests.test_core import sample, node, link


def tool(name):
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".local/bin" / (name + ".exe")
    if local.exists():
        return str(local)
    if name == "clang++":
        candidates = sorted((Path.home() / "AppData/Local/Programs").glob("llvm-mingw-*/bin/clang++.exe"))
        if candidates:
            return str(candidates[-1])
    return None


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    cmake, ninja, compiler = tool("cmake"), tool("ninja"), tool("clang++")
    if not all((cmake, ninja, compiler)):
        pytest.skip("Native build tools not installed")
    reusable = os.environ.get('NODE_ENGINE_NATIVE_TEST_BUILD')
    build = Path(reusable).resolve() if reusable else tmp_path_factory.mktemp("native")
    build.mkdir(parents=True, exist_ok=True)
    c_compiler = Path(compiler).with_name('clang' + Path(compiler).suffix)
    cache = build/'CMakeCache.txt'
    if reusable and cache.exists():
        for line in cache.read_text('utf-8').splitlines():
            if line.startswith(('CMAKE_CXX_COMPILER:STRING=', 'CMAKE_CXX_COMPILER:FILEPATH=')):
                compiler = line.split('=',1)[1]
            elif line.startswith(('CMAKE_C_COMPILER:STRING=', 'CMAKE_C_COMPILER:FILEPATH=')):
                c_compiler = line.split('=',1)[1]
    generated = build / "generated"
    write_text_if_changed(ROOT / "runtime/generated/adapters.generated.cpp", generate_adapters())
    # Configure once; subsequent tests only rebuild the generated translation unit.
    export(compile_graph(sample(), default_scene()), generated)
    env = os.environ.copy()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    def checked(args):
        # A clean Windows fixture may compile the bundled SDL/RmlUi/Jolt/ozz
        # dependencies before the actual runtime; allow that first build to
        # finish instead of reporting an infrastructure timeout.
        result = subprocess.run(args, env=env, text=True, encoding='utf-8', capture_output=True, timeout=1200)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    checked([cmake, "-S", str(ROOT), "-B", str(build), "-G", "Ninja",
             f"-DCMAKE_MAKE_PROGRAM={ninja}", f"-DCMAKE_CXX_COMPILER={compiler}",
             f"-DCMAKE_C_COMPILER={c_compiler}",
             "-DNODE_ENGINE_SDL=OFF",
             "-DCMAKE_BUILD_TYPE=Release", f"-DNODE_ENGINE_GENERATED={generated / 'game.generated.cpp'}"])
    def run(graph=None, frames=120, extra=(), scene=None, program=None):
        export(program if program is not None else compile_graph(graph, default_scene() if scene is None else scene), generated)
        checked([cmake, "--build", str(build), "--parallel", "2"])
        suffix = ".exe" if os.name == "nt" else ""
        def launch(name, args):
            return subprocess.run([str(build / (name + suffix)), *args, "--frames", str(frames), *extra],
                                  env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
        return launch("node_preview", ["--ir", str(generated / "game.ir.json")]), launch("node_game", [])
    return run


@pytest.mark.parametrize("keys,expected_x", [([], 0.0), (["--key", "D"], 6.0)])
def test_interpreter_export_parity(native, keys, expected_x):
    a, b = native(sample(), extra=keys)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    left, right = json.loads(a.stdout), json.loads(b.stdout)
    assert left == right
    assert left["variables"]["score"] == 3
    assert left["entities"]["player"]["position"][0] == pytest.approx(expected_x)
    assert left["entities"]["player"]["rotation"][1] == 120
    assert left["frame"] == 120


def test_general_math_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    b = GraphBuilder('General math foundation')
    b.add('start', 'On Game Start')
    for nid, name, values in [
        ('mod', 'Modulo', {'A': 7.5, 'B': 2.0}),
        ('pow', 'Power', {'Base': 2.0, 'Exponent': 3.0}),
        ('sqrt', 'Sqrt', {'Value': 81.0}),
        ('floor', 'Floor', {'Value': -1.25}),
        ('ceil', 'Ceil', {'Value': -1.25}),
        ('round', 'Round', {'Value': -1.5}),
        ('tan', 'Tan', {'Radians': math.pi / 4}),
        ('atan2', 'Atan2', {'Y': 1.0, 'X': 1.0}),
        ('inverse', 'Inverse Lerp', {'A': 10.0, 'B': 20.0, 'Value': 15.0}),
        ('smooth', 'SmoothStep', {'A': 0.0, 'B': 10.0, 'Value': 5.0}),
        ('remap', 'Remap Range', {'Value': 5.0, 'Input Min': 0.0, 'Input Max': 10.0,
                                  'Output Min': 100.0, 'Output Max': 200.0}),
        ('equal', 'Equal', {'A': 1.0, 'B': 1.0}),
        ('notequal', 'Not Equal', {'A': 1.0, 'B': 2.0}),
        ('lessequal', 'Less or Equal', {'A': 1.0, 'B': 1.0}),
        ('greaterequal', 'Greater or Equal', {'A': 2.0, 'B': 1.0}),
        ('xor', 'XOR', {'A': True, 'B': False}),
        ('band', 'Bitwise AND', {'A': 12, 'B': 10}),
        ('bor', 'Bitwise OR', {'A': 12, 'B': 10}),
        ('bxor', 'Bitwise XOR', {'A': 12, 'B': 10}),
        ('idiv', 'Integer Divide', {'A': -7, 'B': 3}),
        ('imod', 'Integer Modulo', {'A': -7, 'B': 3}),
        ('iabs', 'Integer Abs', {'Value': -9}),
        ('imin', 'Integer Min', {'A': -3, 'B': 5}),
        ('imax', 'Integer Max', {'A': -3, 'B': 5}),
        ('ilessequal', 'Integer Less or Equal', {'A': 3, 'B': 3}),
        ('igreaterequal', 'Integer Greater or Equal', {'A': 5, 'B': 3}),
        ('inotequal', 'Integer Not Equal', {'A': 5, 'B': 3}),
    ]:
        b.add(nid, name, **values)

    stores = [
        ('mod', 'modulo', 'Set Variable'), ('pow', 'power', 'Set Variable'),
        ('sqrt', 'sqrt', 'Set Variable'), ('floor', 'floor', 'Set Variable'),
        ('ceil', 'ceil', 'Set Variable'), ('round', 'round', 'Set Variable'),
        ('tan', 'tan', 'Set Variable'), ('atan2', 'atan2', 'Set Variable'),
        ('inverse', 'inverse_lerp', 'Set Variable'), ('smooth', 'smooth_step', 'Set Variable'),
        ('remap', 'remap', 'Set Variable'), ('equal', 'equal', 'Set Boolean Variable'),
        ('notequal', 'not_equal', 'Set Boolean Variable'),
        ('lessequal', 'less_equal', 'Set Boolean Variable'),
        ('greaterequal', 'greater_equal', 'Set Boolean Variable'),
        ('xor', 'xor', 'Set Boolean Variable'), ('band', 'bit_and', 'Set Integer Variable'),
        ('bor', 'bit_or', 'Set Integer Variable'), ('bxor', 'bit_xor', 'Set Integer Variable'),
        ('idiv', 'integer_divide', 'Set Integer Variable'), ('imod', 'integer_modulo', 'Set Integer Variable'),
        ('iabs', 'integer_abs', 'Set Integer Variable'), ('imin', 'integer_min', 'Set Integer Variable'),
        ('imax', 'integer_max', 'Set Integer Variable'),
        ('ilessequal', 'integer_less_equal', 'Set Boolean Variable'),
        ('igreaterequal', 'integer_greater_equal', 'Set Boolean Variable'),
        ('inotequal', 'integer_not_equal', 'Set Boolean Variable'),
    ]
    previous = 'start'
    for index, (source, variable, setter) in enumerate(stores):
        target = f'store_{index}'
        b.add(target, setter, Name=variable)
        b.connect(previous, 'Out', target, 'In')
        b.connect(source, 'Value', target, 'Value')
        previous = target

    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    values = left['variables']
    expected = {
        'modulo': 1.5, 'power': 8.0, 'sqrt': 9.0, 'floor': -2.0, 'ceil': -1.0,
        'round': -2.0, 'tan': 1.0, 'atan2': math.pi / 4, 'inverse_lerp': .5,
        'smooth_step': .5, 'remap': 150.0, 'equal': True, 'not_equal': True,
        'less_equal': True, 'greater_equal': True, 'xor': True, 'bit_and': 8,
        'bit_or': 14, 'bit_xor': 6, 'integer_divide': -2, 'integer_modulo': -1,
        'integer_abs': 9, 'integer_min': -3, 'integer_max': 5,
        'integer_less_equal': True, 'integer_greater_equal': True, 'integer_not_equal': True,
    }
    for name, expected_value in expected.items():
        actual = values[name]
        if isinstance(actual, dict):
            actual = actual['value']
        assert actual == pytest.approx(expected_value)


@pytest.mark.parametrize('node_name,values,setter,error_text', [
    ('Modulo', {'A': 1.0, 'B': 0.0}, 'Set Variable', 'modulo by zero'),
    ('Sqrt', {'Value': -1.0}, 'Set Variable', 'negative'),
    ('Integer Divide', {'A': 1, 'B': 0}, 'Set Integer Variable', 'division by zero'),
    ('Integer Modulo', {'A': 1, 'B': 0}, 'Set Integer Variable', 'modulo by zero'),
])
def test_general_math_domain_errors_report_the_math_node(native, node_name, values, setter, error_text):
    from editor.core.builder import GraphBuilder
    b = GraphBuilder('Math domain errors')
    b.add('start', 'On Game Start')
    b.add('math', node_name, **values)
    b.add('store', setter, Name='result')
    b.connect('start', 'Out', 'store', 'In').connect('math', 'Value', 'store', 'Value')
    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 1
    assert json.loads(preview.stderr) == json.loads(game.stderr)
    error = json.loads(preview.stderr)
    assert error['node'] == 'math'
    assert error_text in error['message'].lower()


def test_vector_geometry_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    b = GraphBuilder('Vector geometry foundation')
    b.add('start', 'On Game Start')
    for nid, name, values in [
        ('x', 'Vector X', {'Vector': [1, 2, 3]}),
        ('y', 'Vector Y', {'Vector': [1, 2, 3]}),
        ('z', 'Vector Z', {'Vector': [1, 2, 3]}),
        ('angle', 'Angle Between', {'A': [1, 0, 0], 'B': [0, 1, 0]}),
        ('project', 'Project Vector', {'Vector': [2, 3, 0], 'On': [1, 0, 0]}),
        ('reflect', 'Reflect Vector', {'Vector': [1, -2, 0], 'Normal': [0, 1, 0]}),
        ('rotate', 'Rotate Vector', {'Vector': [1, 0, 0], 'Rotation': [0, 0, 90]}),
    ]:
        b.add(nid, name, **values)
    stores = [
        ('x', 'x', 'Set Variable'), ('y', 'y', 'Set Variable'), ('z', 'z', 'Set Variable'),
        ('angle', 'angle', 'Set Variable'), ('project', 'projected', 'Set Vector3 Variable'),
        ('reflect', 'reflected', 'Set Vector3 Variable'), ('rotate', 'rotated', 'Set Vector3 Variable'),
    ]
    previous = 'start'
    for index, (source, variable, setter) in enumerate(stores):
        target = f'store_{index}'
        b.add(target, setter, Name=variable)
        b.connect(previous, 'Out', target, 'In')
        b.connect(source, 'Value', target, 'Value')
        previous = target

    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['x'] == pytest.approx(1.0)
    assert left['variables']['y'] == pytest.approx(2.0)
    assert left['variables']['z'] == pytest.approx(3.0)
    assert left['variables']['angle'] == pytest.approx(math.pi / 2)
    assert left['variables']['projected']['value'] == pytest.approx([2.0, 0.0, 0.0])
    assert left['variables']['reflected']['value'] == pytest.approx([1.0, 2.0, 0.0])
    assert left['variables']['rotated']['value'] == pytest.approx([0.0, 1.0, 0.0])


@pytest.mark.parametrize('node_name,values,error_text', [
    ('Angle Between', {'A': [0, 0, 0], 'B': [1, 0, 0]}, 'nonzero vectors'),
    ('Reflect Vector', {'Vector': [1, 0, 0], 'Normal': [0, 0, 0]}, 'nonzero normal'),
])
def test_vector_geometry_domain_errors_report_the_math_node(native, node_name, values, error_text):
    from editor.core.builder import GraphBuilder
    b = GraphBuilder('Vector geometry domain errors')
    b.add('start', 'On Game Start')
    b.add('math', node_name, **values)
    setter = 'Set Vector3 Variable' if node_name == 'Reflect Vector' else 'Set Variable'
    b.add('store', setter, Name='result')
    b.connect('start', 'Out', 'store', 'In').connect('math', 'Value', 'store', 'Value')
    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 1
    assert json.loads(preview.stderr) == json.loads(game.stderr)
    error = json.loads(preview.stderr)
    assert error['node'] == 'math'
    assert error_text in error['message'].lower()


def test_vector2_and_vector4_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    b = GraphBuilder('Vector2 and Vector4 foundation')
    b.add('start', 'On Game Start')
    for nid, name, values in [
        ('make2', 'Make Vector2', {'X': 1.5, 'Y': -2.0}),
        ('add2', 'Vector2 Add', {'A': [1, 2], 'B': [3, 4]}),
        ('norm2', 'Vector2 Normalize', {'Vector': [3, 4]}),
        ('dot2', 'Vector2 Dot', {'A': [1, 2], 'B': [3, 4]}),
        ('make4', 'Make Vector4', {'X': 1, 'Y': 2, 'Z': 3, 'W': 4}),
        ('add4', 'Vector4 Add', {'A': [1, 2, 3, 4], 'B': [4, 3, 2, 1]}),
        ('norm4', 'Vector4 Normalize', {'Vector': [1, 2, 2, 4]}),
        ('dot4', 'Vector4 Dot', {'A': [1, 2, 3, 4], 'B': [4, 3, 2, 1]}),
    ]:
        b.add(nid, name, **values)
    stores = [
        ('make2', 'make2', 'Set Vector2 Variable'),
        ('add2', 'add2', 'Set Vector2 Variable'),
        ('norm2', 'norm2', 'Set Vector2 Variable'),
        ('dot2', 'dot2', 'Set Variable'),
        ('make4', 'make4', 'Set Vector4 Variable'),
        ('add4', 'add4', 'Set Vector4 Variable'),
        ('norm4', 'norm4', 'Set Vector4 Variable'),
        ('dot4', 'dot4', 'Set Variable'),
    ]
    previous = 'start'
    for index, (source, variable_name, setter) in enumerate(stores):
        target = f'store_{index}'
        b.add(target, setter, Name=variable_name)
        b.connect(previous, 'Out', target, 'In')
        b.connect(source, 'Value', target, 'Value')
        previous = target

    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    values = left['variables']
    assert values['make2']['value'] == pytest.approx([1.5, -2.0])
    assert values['add2']['value'] == pytest.approx([4.0, 6.0])
    assert values['norm2']['value'] == pytest.approx([0.6, 0.8])
    assert values['dot2'] == pytest.approx(11.0)
    assert values['make4']['value'] == pytest.approx([1.0, 2.0, 3.0, 4.0])
    assert values['add4']['value'] == pytest.approx([5.0, 5.0, 5.0, 5.0])
    assert values['norm4']['value'] == pytest.approx([0.2, 0.4, 0.4, 0.8])
    assert values['dot4'] == pytest.approx(20.0)


def test_quaternion_and_matrix_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    half = math.sqrt(0.5)
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    b = GraphBuilder('Quaternion and matrix foundation')
    b.add('start', 'On Game Start')
    b.add('make', 'Make Quaternion', Euler=[0, 0, 90])
    b.add('axis', 'Quaternion From Axis Angle', Axis=[0, 1, 0], Degrees=90)
    b.add('multiply', 'Quaternion Multiply', A=[0, 0, 0, 1])
    b.connect('axis', 'Value', 'multiply', 'B')
    b.add('norm', 'Quaternion Normalize', Value=[0, 0, 0, 2])
    b.add('inverse', 'Quaternion Inverse')
    b.connect('make', 'Value', 'inverse', 'Value')
    b.add('slerp', 'Quaternion Slerp', A=[0, 0, 0, 1], T=0.5)
    b.connect('make', 'Value', 'slerp', 'B')
    b.add('rotate', 'Quaternion Rotate Vector', Vector=[1, 0, 0])
    b.connect('make', 'Value', 'rotate', 'Rotation')
    b.add('identity', 'Identity Matrix')
    b.add('trs', 'Make Transform Matrix', Position=[10, 20, 0], Rotation=[0, 0, 0, 1], Scale=[2, 3, 1])
    b.add('point', 'Transform Point', Point=[1, 1, 0])
    b.connect('trs', 'Value', 'point', 'Matrix')
    b.add('direction', 'Transform Direction', Direction=[1, 1, 0])
    b.connect('trs', 'Value', 'direction', 'Matrix')
    b.add('matrix_inverse', 'Matrix Inverse')
    b.connect('trs', 'Value', 'matrix_inverse', 'Value')
    b.add('matrix_check', 'Matrix Multiply')
    b.connect('trs', 'Value', 'matrix_check', 'A')
    b.connect('matrix_inverse', 'Value', 'matrix_check', 'B')

    stores = [
        ('make', 'make', 'Set Quaternion Variable'),
        ('axis', 'axis', 'Set Quaternion Variable'),
        ('multiply', 'multiply', 'Set Quaternion Variable'),
        ('norm', 'norm', 'Set Quaternion Variable'),
        ('inverse', 'inverse', 'Set Quaternion Variable'),
        ('slerp', 'slerp', 'Set Quaternion Variable'),
        ('rotate', 'rotate', 'Set Vector3 Variable'),
        ('identity', 'identity', 'Set Matrix4 Variable'),
        ('trs', 'trs', 'Set Matrix4 Variable'),
        ('point', 'point', 'Set Vector3 Variable'),
        ('direction', 'direction', 'Set Vector3 Variable'),
        ('matrix_inverse', 'matrix_inverse', 'Set Matrix4 Variable'),
        ('matrix_check', 'matrix_check', 'Set Matrix4 Variable'),
    ]
    previous = 'start'
    for index, (source, variable_name, setter) in enumerate(stores):
        target = f'store_{index}'
        b.add(target, setter, Name=variable_name)
        b.connect(previous, 'Out', target, 'In')
        b.connect(source, 'Value', target, 'Value')
        previous = target

    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    values = left['variables']
    expected_z90 = [0.0, 0.0, half, half]
    assert values['make']['value'] == pytest.approx(expected_z90)
    assert values['axis']['value'] == pytest.approx([0.0, half, 0.0, half])
    assert values['multiply']['value'] == pytest.approx([0.0, half, 0.0, half])
    assert values['norm']['value'] == pytest.approx([0.0, 0.0, 0.0, 1.0])
    assert values['slerp']['value'] == pytest.approx([0.0, 0.0, math.sin(math.pi / 8), math.cos(math.pi / 8)])
    assert values['rotate']['value'] == pytest.approx([0.0, 1.0, 0.0])
    assert values['identity']['value'] == pytest.approx(identity)
    assert values['point']['value'] == pytest.approx([12.0, 23.0, 0.0])
    assert values['direction']['value'] == pytest.approx([2.0, 3.0, 0.0])
    assert values['matrix_check']['value'] == pytest.approx(identity)


def test_general_geometry_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    b = GraphBuilder('General geometry foundation')
    b.add('start', 'On Game Start')
    for nid, name, values in [
        ('inside', 'Point In Bounds', {'Point': [0.5, 0, -0.5], 'Min': [-1, -1, -1], 'Max': [1, 1, 1]}),
        ('outside', 'Point In Bounds', {'Point': [2, 0, 0], 'Min': [-1, -1, -1], 'Max': [1, 1, 1]}),
        ('segment', 'Closest Point On Segment', {'Point': [3, 2, 0], 'A': [0, 0, 0], 'B': [4, 0, 0]}),
        ('clamp', 'Closest Point On Bounds', {'Point': [2, -3, 0.5], 'Min': [-1, -1, -1], 'Max': [1, 1, 1]}),
        ('plane', 'Ray Plane Intersection', {'Origin': [0, 2, 0], 'Direction': [0, -1, 0], 'Plane Point': [0, 0, 0], 'Plane Normal': [0, 1, 0]}),
        ('sphere', 'Ray Sphere Intersection Distance', {'Origin': [0, 0, -5], 'Direction': [0, 0, 1], 'Center': [0, 0, 0], 'Radius': 1}),
        ('lines', 'Line Segments Intersect 2D', {'A1': [-1, 0, 0], 'A2': [1, 0, 0], 'B1': [0, -1, 0], 'B2': [0, 1, 0]}),
        ('minimum', 'Bounds Min', {'Points': [[2, 3, 4], [-1, 5, 0], [3, -2, 1]]}),
        ('maximum', 'Bounds Max', {'Points': [[2, 3, 4], [-1, 5, 0], [3, -2, 1]]}),
        ('ray_bounds', 'Ray Bounds Intersection Distance', {'Origin': [0, 0, -5], 'Direction': [0, 0, 1], 'Min': [-1, -1, -1], 'Max': [1, 1, 1]}),
        ('triangle', 'Closest Point On Triangle', {'Point': [0.25, 0.25, 1], 'A': [0, 0, 0], 'B': [1, 0, 0], 'C': [0, 1, 0]}),
        ('overlap', 'Sphere Overlaps Bounds', {'Center': [2, 0, 0], 'Radius': 1, 'Min': [-1, -1, -1], 'Max': [1, 1, 1]}),
        ('plane_distance', 'Distance To Plane', {'Point': [0, 3, 0], 'Plane Point': [0, 1, 0], 'Plane Normal': [0, 1, 0]}),
    ]:
        b.add(nid, name, **values)
    stores = [
        ('inside', 'inside', 'Set Boolean Variable'),
        ('outside', 'outside', 'Set Boolean Variable'),
        ('segment', 'segment', 'Set Vector3 Variable'),
        ('clamp', 'clamp', 'Set Vector3 Variable'),
        ('plane', 'plane', 'Set Vector3 Variable'),
        ('sphere', 'sphere', 'Set Variable'),
        ('lines', 'lines', 'Set Boolean Variable'),
        ('minimum', 'minimum', 'Set Vector3 Variable'),
        ('maximum', 'maximum', 'Set Vector3 Variable'),
        ('ray_bounds', 'ray_bounds', 'Set Variable'),
        ('triangle', 'triangle', 'Set Vector3 Variable'),
        ('overlap', 'overlap', 'Set Boolean Variable'),
        ('plane_distance', 'plane_distance', 'Set Variable'),
    ]
    previous = 'start'
    for index, (source, variable_name, setter) in enumerate(stores):
        target = f'store_{index}'
        b.add(target, setter, Name=variable_name)
        b.connect(previous, 'Out', target, 'In')
        b.connect(source, 'Value', target, 'Value')
        previous = target

    preview, game = native(b.graph, frames=0)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    values = left['variables']
    assert values['inside']['value'] is True
    assert values['outside']['value'] is False
    assert values['segment']['value'] == pytest.approx([3.0, 0.0, 0.0])
    assert values['clamp']['value'] == pytest.approx([1.0, -1.0, 0.5])
    assert values['plane']['value'] == pytest.approx([0.0, 0.0, 0.0])
    assert values['sphere'] == pytest.approx(4.0)
    assert values['lines']['value'] is True
    assert values['minimum']['value'] == pytest.approx([-1.0, -2.0, 0.0])
    assert values['maximum']['value'] == pytest.approx([3.0, 5.0, 4.0])
    assert values['ray_bounds'] == pytest.approx(4.0)
    assert values['triangle']['value'] == pytest.approx([0.25, 0.25, 0.0])
    assert values['overlap']['value'] is True
    assert values['plane_distance'] == pytest.approx(2.0)


def test_camera_projection_nodes_have_native_interpreter_parity(native):
    from editor.core.builder import GraphBuilder

    scene = {
        'active_camera': 'camera',
        'entities': [{
            'id': 'camera', 'name': 'Camera', 'position': [0, 2, 6],
            'rotation': [0, 0, 0], 'scale': [1, 1, 1],
            'camera': {'projection': 'perspective', 'fov': 60, 'size': 10,
                       'near': 0.1, 'far': 1000},
        }],
        'variables': {},
    }
    b = GraphBuilder('Camera projection foundation')
    b.add('start', 'On Game Start')
    b.add('set', 'Set Camera Orthographic', Camera='camera', Height=10.0, Near=0.1, Far=1000.0)
    b.connect('start', 'Out', 'set', 'In')
    b.add('world', 'World To Screen', Camera='camera', World=[0, 2, 0], Viewport=[960, 640])
    b.add('screen_store', 'Set Vector2 Variable', Name='screen')
    b.connect('set', 'Out', 'screen_store', 'In').connect('world', 'Value', 'screen_store', 'Value')
    b.add('back', 'Screen To World', Camera='camera', Screen=[480, 320],
          Depth=5.9 / 999.9, Viewport=[960, 640])
    b.add('world_store', 'Set Vector3 Variable', Name='world')
    b.connect('screen_store', 'Out', 'world_store', 'In').connect('back', 'Value', 'world_store', 'Value')

    preview, game = native(b.graph, frames=0, scene=scene)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['screen']['value'] == pytest.approx([480.0, 320.0])
    assert left['variables']['world']['value'] == pytest.approx([0.0, 2.0, 0.0])


def test_while_reevaluates_mutable_inputs(native):
    graph = {"version": 1, "nodes": [
        node("start", 1001), node("set", 3005, Value=0),
        node("loop", 2004), node("get", 3004), node("less", 4012, B=5),
        node("add", 4001, B=1), node("inc", 3005)],
        "links": [link("start", "Out", "set", "In"), link("set", "Out", "loop", "In"),
                  link("get", "Value", "less", "A"), link("less", "Value", "loop", "Condition"),
                  link("loop", "Body", "inc", "In"), link("get", "Value", "add", "A"),
                  link("add", "Value", "inc", "Value")]}
    a, b = native(graph, frames=0)
    assert a.returncode == b.returncode == 0, a.stderr+b.stderr
    assert json.loads(a.stdout) == json.loads(b.stdout)
    assert json.loads(a.stdout)["variables"]["score"] == 5


def test_infinite_loop_stops_and_reports_node(native):
    graph = {"version": 1, "nodes": [node("start", 1001), node("loop", 2004, Condition=True)],
             "links": [link("start", "Out", "loop", "In")]}
    a, b = native(graph, extra=["--budget", "100"])
    assert a.returncode == b.returncode == 1
    assert json.loads(a.stderr) == json.loads(b.stderr)
    assert json.loads(a.stderr)["node"] == "loop"
    assert "budget" in json.loads(a.stderr)["message"]


def test_runtime_error_at_original_node(native):
    graph = {"version": 1, "nodes": [
        node("start", 1001), node("divide", 4004, A=1, B=0), node("set", 3005)],
        "links": [link("start", "Out", "set", "In"), link("divide", "Value", "set", "Value")]}
    a, b = native(graph)
    assert a.returncode == b.returncode == 1
    assert json.loads(a.stderr) == json.loads(b.stderr)
    assert json.loads(a.stderr)["node"] == "divide"


def test_entity_transform_and_vector_nodes_share_native_semantics(native):
    from editor.core.builder import GraphBuilder
    b = GraphBuilder('Spatial foundation')
    for nid, name, values in [
        ('start','On Game Start',{}), ('rotate','Set Rotation',{'Value':[10,20,30]}),
        ('rotation','Get Rotation',{}), ('subtract','Vector Subtract',{'B':[1,2,3]}),
        ('position','Set Position',{}), ('lerp','Vector Lerp',{'B':[2,4,6],'T':.5}),
        ('scale','Set Scale',{}), ('getscale','Get Scale',{}), ('distance','Distance',{'B':[1,1,1]}),
        ('set','Set Variable',{}), ('exists','Entity Exists',{}), ('assert','Assert',{}),
        ('missing','Entity Exists',{'Entity':'missing'}), ('branch','Branch',{}),
        ('log','Print Log',{'Message':'missing handled'}),
    ]:
        b.add(nid,name,**values)
    for args in [('start','Out','rotate','In'),('rotate','Out','position','In'),
                 ('position','Out','scale','In'),('scale','Out','set','In'),
                 ('set','Out','assert','In'),('assert','Out','branch','In'),
                 ('rotation','Value','subtract','A'),('subtract','Value','position','Value'),
                 ('lerp','Value','scale','Value'),('getscale','Value','distance','A'),
                 ('distance','Value','set','Value'),('exists','Value','assert','Condition'),
                 ('missing','Value','branch','Condition'),('branch','False','log','In')]:
        b.connect(*args)
    a,b = native(b.graph,frames=0)
    assert a.returncode == b.returncode == 0, a.stderr+b.stderr
    result=json.loads(a.stdout)
    assert result == json.loads(b.stdout)
    assert result['entities']['player'] == {'position':[9,18,27],'rotation':[10,20,30],'scale':[1,2,3]}
    assert result['variables']['score'] == pytest.approx(5**.5)
    assert result['logs'] == ['missing handled']


def test_typed_collections_and_variables_are_values_not_aliases(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration, INT_MIN, INT_MAX
    b=GraphBuilder('Typed collection behavior')
    b.add('start','On Game Start')
    previous='start'
    scene=default_scene()
    expected={}
    def action(nid,name,**values):
        nonlocal previous
        b.add(nid,name,**values)
        b.connect(previous,'Out',nid,'In')
        previous=nid
        return nid
    for t,label,samples in [
        ('float','Float',[1.5,-2.25,3.75,4.5]),
        ('int','Integer',[2**60+1,-(2**60)+3,INT_MAX,INT_MIN]),
        ('bool','Boolean',[False,True,True,False]),
        ('string','String',['A\0Z','Xin chào','β','']),
        ('vec3','Vector3',[[1,2,3],[4,5,6],[7,8,9],[10,11,12]]),
        ('entity','Entity',['player','enemy','npc',''])]:
        a,bb,c,d=samples
        source=f'{t}_source'
        scene['variables'][source]=declaration(f'array<{t}>',[a,bb])
        expected[source]=scene['variables'][source]
        for suffix,name,values in [
            ('source',f'Get {label} Array Variable',{'Name':source}),
            ('append',f'Append {label} Item',{'Item':c}),
            ('insert',f'Insert {label} Item',{'Index':0,'Item':d}),
            ('setitem',f'Set {label} Item',{'Index':2,'Item':a}),
            ('remove',f'Remove {label} Item At',{'Index':1}),
            ('reverse',f'Reverse {label} Array',{})]:
            b.add(f'{t}_{suffix}',name,**values)
        order=['source','append','insert','setitem','remove','reverse']
        for src,dst in zip(order,order[1:]):
            b.connect(f'{t}_{src}','Value',f'{t}_{dst}','Array')
        out=action(f'{t}_save',f'Set {label} Array Variable',Name=f'{t}_result')
        b.connect(f'{t}_reverse','Value',out,'Value')
        expected[f'{t}_result']=declaration(f'array<{t}>',[c,a,d])
        scalar_set='Set Variable' if t=='float' else f'Set {label} Variable'
        for suffix,operation,values,target_type,target_label,result in [
            ('item',f'Get {label} Item',{'Index':1},t,scalar_set,a),
            ('length',f'{label} Array Length',{},'int','Set Integer Variable',3),
            ('found',f'Find {label} Item',{'Item':a},'int','Set Integer Variable',1),
            ('contains',f'{label} Array Contains',{'Item':a},'bool','Set Boolean Variable',True),
            ('clear',f'Clear {label} Array',{},f'array<{t}>',f'Set {label} Array Variable',[])]:
            key=f'{t}_{suffix}'
            b.add(key,operation,**values)
            b.connect(f'{t}_reverse','Value',key,'Array')
            target=action(key+'_save',target_label,Name=key)
            b.connect(key,'Value',target,'Value')
            expected[key]=declaration(target_type,result)
        b.add(t+'_map','Create '+label+' Map',Items={'z':a,'a':bb})
        b.add(t+'_mapset','Set '+label+' Map Item',Key='m',Item=c)
        b.add(t+'_mapremove','Remove '+label+' Map Item',Key='a')
        b.connect(t+'_map','Value',t+'_mapset','Map').connect(t+'_mapset','Value',t+'_mapremove','Map')
        target=action(t+'_mapsave','Set '+label+' Map Variable',Name=t+'_map')
        b.connect(t+'_mapremove','Value',target,'Value')
        expected[t+'_map']=declaration(f'map<{t}>',{'m':c,'z':a})
        for suffix,name,values,result_type,setter,result in [
            ('mapitem',f'Get {label} Map Item',{'Key':'z'},t,scalar_set,a),
            ('keys',f'{label} Map Keys',{},'array<string>','Set String Array Variable',['m','z']),
            ('values',f'{label} Map Values',{},f'array<{t}>',f'Set {label} Array Variable',[c,a]),
            ('size',f'{label} Map Size',{},'int','Set Integer Variable',2),
            ('has',f'{label} Map Has Key',{'Key':'a'},'bool','Set Boolean Variable',False),
            ('mapclear',f'Clear {label} Map',{},f'map<{t}>',f'Set {label} Map Variable',{})]:
            key=f'{t}_{suffix}'
            b.add(key,name,**values)
            b.connect(t+'_mapremove','Value',key,'Map')
            target=action(key+'_save',setter,Name=key)
            b.connect(key,'Value',target,'Value')
            expected[key]=declaration(result_type,result)
    a,b=native(b.graph,frames=0,scene=scene)
    assert a.returncode == b.returncode == 0,a.stderr+b.stderr
    result=json.loads(a.stdout)
    assert result == json.loads(b.stdout)
    assert result['variables'] == expected


def test_typed_sets_are_unique_ordered_and_native_parity(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder('Typed set behavior')
    b.add('start','On Game Start')
    b.add('create','Create Integer Set',Items=[1,2,3])
    b.add('duplicate','Add Integer Set Item',Item=2)
    b.add('append','Add Integer Set Item',Item=4)
    b.add('remove','Remove Integer Set Item',Item=1)
    b.add('contains','Integer Set Contains',Item=3)
    b.add('length','Integer Set Length')
    b.add('clear','Clear Integer Set')
    b.add('save_items','Set Integer Set Variable',Name='items')
    b.add('save_contains','Set Boolean Variable',Name='contains')
    b.add('save_length','Set Integer Variable',Name='length')
    b.add('save_clear','Set Integer Set Variable',Name='cleared')
    for source,target in [('create','duplicate'),('duplicate','append'),('append','remove')]:
        b.connect(source,'Value',target,'Set')
    for target in ('contains','length','clear'):
        b.connect('remove','Value',target,'Set')
    b.connect('start','Out','save_items','In').connect('save_items','Out','save_contains','In')
    b.connect('save_contains','Out','save_length','In').connect('save_length','Out','save_clear','In')
    b.connect('remove','Value','save_items','Value').connect('contains','Value','save_contains','Value')
    b.connect('length','Value','save_length','Value').connect('clear','Value','save_clear','Value')
    preview,game=native(b.graph,frames=0)
    assert preview.returncode==game.returncode==0,preview.stderr+game.stderr
    left,right=json.loads(preview.stdout),json.loads(game.stdout)
    assert left==right
    assert left['variables']=={
        'items':declaration('set<int>',[2,3,4]),
        'contains':declaration('bool',True),
        'length':declaration('int',3),
        'cleared':declaration('set<int>',[]),
    }


def test_foreach_sets_preserve_insertion_order_and_native_parity(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder('For Each set behavior')
    b.add('start','On Game Start')
    b.add('loop','For Each Integer Set',Set=[3,1,2])
    b.add('visited','Get Integer Array Variable',Name='visited')
    b.add('append','Append Integer Item')
    b.add('save','Set Integer Array Variable',Name='visited')
    b.connect('start','Out','loop','In')
    b.connect('loop','Body','save','In')
    b.connect('visited','Value','append','Array')
    b.connect('loop','Item','append','Item')
    b.connect('append','Value','save','Value')
    scene=default_scene()
    scene['variables']={'visited':declaration('array<int>',[])}
    preview,game=native(b.graph,frames=0,scene=scene)
    assert preview.returncode==game.returncode==0,preview.stderr+game.stderr
    left,right=json.loads(preview.stdout),json.loads(game.stdout)
    assert left==right
    assert left['variables']['visited']==declaration('array<int>',[3,1,2])


def test_array_concat_and_slice_preserve_order_and_native_parity(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder('Array concat and slice behavior')
    b.add('start','On Game Start')
    b.add('concat','Concat Integer Arrays',A=[1,2],B=[3,4])
    b.add('slice','Slice Integer Array',Start=1,End=4)
    b.add('save','Set Integer Array Variable',Name='result')
    b.connect('concat','Value','slice','Array')
    b.connect('slice','Value','save','Value')
    b.connect('start','Out','save','In')
    scene=default_scene()
    scene['variables']={'result':declaration('array<int>',[])}
    preview,game=native(b.graph,frames=0,scene=scene)
    assert preview.returncode==game.returncode==0,preview.stderr+game.stderr
    left,right=json.loads(preview.stdout),json.loads(game.stdout)
    assert left==right
    assert left['variables']['result']==declaration('array<int>',[2,3,4])


def test_foreach_maps_bind_sorted_keys_items_and_native_parity(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder('For Each map behavior')
    b.add('start','On Game Start')
    b.add('loop','For Each Integer Map',Map={'z':3,'a':1,'m':2})
    b.add('keys','Get String Array Variable',Name='keys')
    b.add('append_key','Append String Item')
    b.add('save_keys','Set String Array Variable',Name='keys')
    b.add('values','Get Integer Array Variable',Name='values')
    b.add('append_value','Append Integer Item')
    b.add('save_values','Set Integer Array Variable',Name='values')
    b.connect('start','Out','loop','In')
    b.connect('loop','Body','save_keys','In')
    b.connect('save_keys','Out','save_values','In')
    b.connect('keys','Value','append_key','Array')
    b.connect('loop','Key','append_key','Item')
    b.connect('append_key','Value','save_keys','Value')
    b.connect('values','Value','append_value','Array')
    b.connect('loop','Item','append_value','Item')
    b.connect('append_value','Value','save_values','Value')
    scene=default_scene()
    scene['variables']={'keys':declaration('array<string>',[]),'values':declaration('array<int>',[])}
    preview,game=native(b.graph,frames=0,scene=scene)
    assert preview.returncode==game.returncode==0,preview.stderr+game.stderr
    left,right=json.loads(preview.stdout),json.loads(game.stdout)
    assert left==right
    assert left['variables']=={
        'keys':declaration('array<string>',['a','m','z']),
        'values':declaration('array<int>',[1,2,3]),
    }


def test_nested_foreach_snapshots_source_and_binds_item_index(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder('Nested iteration')
    for nid,name,values in [
        ('start','On Game Start',{}),('source','Get Integer Array Variable',{'Name':'source'}),
        ('outer','For Each Integer',{}),('inner','For Each Integer',{'Array':[1,2,3]}),
        ('product','Integer Multiply',{}),('sum','Get Integer Variable',{'Name':'sum'}),
        ('add','Integer Add',{}),('store','Set Integer Variable',{'Name':'sum'}),
        ('ten','Integer Multiply',{'B':10}),('index','Integer Add',{}),
        ('visited','Get Integer Array Variable',{'Name':'visited'}),('append','Append Integer Item',{}),
        ('save','Set Integer Array Variable',{'Name':'visited'}),
        ('clear','Set Integer Array Variable',{'Name':'source','Value':[]})]:
        b.add(nid,name,**values)
    for edge in [('start','Out','outer','In'),('source','Value','outer','Array'),
        ('outer','Body','inner','In'),('inner','Body','store','In'),('store','Out','save','In'),
        ('save','Out','clear','In'),('outer','Item','product','A'),('inner','Item','product','B'),
        ('product','Value','add','A'),('sum','Value','add','B'),('add','Value','store','Value'),
        ('outer','Index','ten','A'),('ten','Value','index','A'),('inner','Index','index','B'),
        ('index','Value','append','Item'),('visited','Value','append','Array'),('append','Value','save','Value')]:
        b.connect(*edge)
    scene=default_scene()
    scene['variables']={'source':declaration('array<int>',[10,20]),'sum':declaration('int',0),
                        'visited':declaration('array<int>',[])}
    a,b=native(b.graph,frames=0,scene=scene)
    assert a.returncode == b.returncode == 0,a.stderr+b.stderr
    result=json.loads(a.stdout)
    assert result == json.loads(b.stdout)
    assert result['variables'] == {'source':declaration('array<int>',[]),'sum':declaration('int',180),
                                  'visited':declaration('array<int>',[0,1,2,10,11,12])}


@pytest.mark.parametrize('name,values,setter,message',[
    ('Get Integer Item',{'Array':[1,2],'Index':-1},'Set Integer Variable','out of range'),
    ('Get String Map Item',{'Map':{'a':'b'},'Key':'missing'},'Set String Variable','key not found'),
    ('Integer Add',{'A':2**63-1,'B':1},'Set Integer Variable','overflow'),
    ('Integer Subtract',{'A':-(2**63),'B':1},'Set Integer Variable','overflow'),
    ('Integer Multiply',{'A':-(2**63),'B':-1},'Set Integer Variable','overflow'),
    ('Truncate to Integer',{'Value':1e30},'Set Integer Variable','range'),
    ('String Split',{'Text':'abc','Separator':''},'Set String Array Variable','empty'),
])
def test_collection_and_integer_failures_match_at_source_node(native,name,values,setter,message):
    from editor.core.builder import GraphBuilder
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('bad',name,**values)
    b.add('store',setter)
    b.connect('start','Out','store','In').connect('bad','Value','store','Value')
    a,b=native(b.graph,frames=0)
    assert a.returncode == b.returncode == 1
    result=json.loads(a.stderr)
    assert result == json.loads(b.stderr)
    assert result['node'] == 'bad' and message in result['message']


def test_dynamic_variable_names_still_enforce_types_at_runtime(native):
    from editor.core.builder import GraphBuilder
    from editor.core.data_types import declaration
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('name','String',Value='ready')
    b.add('bad','Get Variable')
    b.add('store','Set Variable',Name='result')
    b.connect('name','Value','bad','Name').connect('bad','Value','store','Value').connect('start','Out','store','In')
    scene=default_scene()
    scene['variables']['ready']=declaration('bool',True)
    a,b=native(b.graph,frames=0,scene=scene)
    assert a.returncode == b.returncode == 1
    result=json.loads(a.stderr)
    assert result == json.loads(b.stderr)
    assert result['node'] == 'bad' and 'not float' in result['message']


def test_string_operations_preserve_unicode_nul_and_integer_precision(native):
    from editor.core.builder import GraphBuilder
    b=GraphBuilder()
    for nid,name,values in [
        ('start','On Game Start',{}),('split','String Split',{'Text':'Xin chào||β|','Separator':'|'}),
        ('join','String Join',{'Separator':' / '}),('replace','String Replace',{'Find':'β','Replacement':'robot\0X'}),
        ('print','Print Log',{}),('number','Format Integer',{'Value':2**63-1}),('nlog','Print Log',{}),
        ('same','Compare References',{'A':'player','B':'player'}),('assert','Assert',{}),
        ('id','Entity ID',{'Entity':'Nhân vật'}),('idlog','Print Log',{}),
        ('bools','For Each Boolean',{'Array':[True,False]}),('formatbool','Format Boolean',{}),
        ('blog','Print Log',{})]:
        b.add(nid,name,**values)
    for edge in [('start','Out','print','In'),('split','Value','join','Items'),('join','Value','replace','Text'),
        ('replace','Value','print','Message'),('print','Out','nlog','In'),('number','Value','nlog','Message'),
        ('nlog','Out','assert','In'),('same','Value','assert','Condition'),('assert','Out','idlog','In'),
        ('id','Value','idlog','Message'),('idlog','Out','bools','In'),('bools','Body','blog','In'),
        ('bools','Item','formatbool','Value'),('formatbool','Value','blog','Message')]:
        b.connect(*edge)
    a,b=native(b.graph,frames=0)
    assert a.returncode == b.returncode == 0,a.stderr+b.stderr
    result=json.loads(a.stdout)
    assert result == json.loads(b.stdout)
    assert result['logs'] == ['Xin chào /  / robot\0X / ','9223372036854775807','Nhân vật','true','false']


@pytest.mark.parametrize('items,budget', [([],100),([1,2,3],5)])
def test_foreach_empty_done_and_instruction_budget(native,items,budget):
    from editor.core.builder import GraphBuilder
    b=GraphBuilder()
    b.add('start','On Game Start')
    b.add('loop','For Each Integer',Array=items)
    b.add('body','Print Log',Message='item')
    b.add('done','Print Log',Message='done')
    b.connect('start','Out','loop','In').connect('loop','Body','body','In').connect('loop','Done','done','In')
    a,b=native(b.graph,frames=0,extra=['--budget',str(budget)])
    if items:
        assert a.returncode == b.returncode == 1
        result=json.loads(a.stderr)
        assert result == json.loads(b.stderr)
        assert result['node']=='loop' and 'budget' in result['message']
    else:
        assert a.returncode == b.returncode == 0,a.stderr+b.stderr
        result=json.loads(a.stdout)
        assert result == json.loads(b.stdout) and result['logs']==['done']
