"""Pixel evidence for material overrides without losing imported texture/vertex color."""
from copy import deepcopy
import os
import subprocess
import pytest
from PySide6.QtGui import QImage
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.document import load_project, save_json
from editor.core.materials import new_asset
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from tools.create_texture_demo import create
from tests.test_textures import rgb


@pytest.fixture(scope='module')
def material_gpu(tmp_path_factory):
    exe = ROOT / ('build/node_view.exe' if os.name == 'nt' else 'build/node_view')
    if not exe.exists(): pytest.skip('Build the graphical runtime before GPU tests')
    assert current(exe), 'Rebuild the native runtime before GPU tests'
    project = create(tmp_path_factory.mktemp('material-gpu'))
    _, graph, scene = load_project(project / 'project.json')
    scene['material_assets'] = [dict(new_asset('White'), id='white', unlit=True)]
    scene['entities'][0]['material'] = {'asset': 'white', 'overrides': {}}
    def run(overrides=None, nodes=(), mutate=None):
        changed = deepcopy(scene)
        if overrides is not None: changed['entities'][0]['material']['overrides'] = overrides
        if mutate: mutate(changed)
        b = GraphBuilder(); b.add('start', 'On Game Start'); previous = 'start'
        for index, (name, values) in enumerate(nodes):
            nid = f'action_{index}'; b.add(nid, name, Entity='board', **values)
            b.connect(previous, 'Out', nid, 'In'); previous = nid
        ir = compile_graph(b.graph, changed)
        save_json(project / 'generated/material.ir.json', ir)
        capture = project / 'material.bmp'
        result = subprocess.run([str(exe), '--ir', str(project / 'generated/material.ir.json'),
            '--project-root', str(project), '--frames', '2', '--capture', str(capture)],
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        assert result.returncode == 0, result.stderr
        image = QImage(str(capture)); assert not image.isNull()
        return image
    return run


def close(actual, expected):
    assert all(abs(a-b) <= 2 for a, b in zip(actual, expected)), (actual, expected)


def test_instance_factor_replaces_imported_factor_and_preserves_color0_uv_texture(material_gpu):
    image = material_gpu()
    close(rgb(image, 4, 1.5), (255, 137, 255))  # Imported .5 red factor is replaced, COLOR_0 green .25 remains.
    close(rgb(image, -4.4, 1.9), (255, 0, 0)); close(rgb(image, -3.6, 1.1), (128, 128, 128))
    image = material_gpu(nodes=[('Set Material Color', {'Color': [.25, .5, 1]})])
    close(rgb(image, -4.4, 1.9), (137, 0, 0)); close(rgb(image, 4, 1.5), (137, 99, 255))


@pytest.mark.parametrize('mode,opacity,cutoff,expected', [
    ('opaque', 0, .5, (255, 0, 0)), ('blend', .5, .5, (188, 8, 13)),
    ('mask', .4, .5, (11, 15, 21)), ('mask', .6, .5, (255, 0, 0))])
def test_runtime_alpha_modes(material_gpu, mode, opacity, cutoff, expected):
    image = material_gpu(nodes=[('Set Material Alpha Mode', {'Mode': mode}),
        ('Set Material Opacity', {'Opacity': opacity}), ('Set Material Alpha Cutoff', {'Cutoff': cutoff})])
    close(rgb(image, -4.4, 1.9), expected)


def test_unlit_reset_clear_restores_original_imported_material(material_gpu):
    lit = material_gpu(nodes=[('Set Material Unlit', {'Unlit': False})])
    close(rgb(lit, -4.4, 1.9), (215, 0, 0))  # Fixed face light: .35 + .65 * .5 / sqrt(.98).
    reset = material_gpu(nodes=[('Set Material Color', {'Color': [0, 0, 0]}), ('Reset Material Parameters', {})])
    close(rgb(reset, 4, 1.5), (255, 137, 255))
    cleared = material_gpu(nodes=[('Clear Material', {})])
    close(rgb(cleared, 4, 1.5), (188, 137, 255))


def test_shared_mesh_instances_have_independent_materials_on_gpu(material_gpu):
    def two(scene):
        first = scene['entities'][0]; first['scale'] = [.5, .5, 1]; first['position'] = [-3, 0, 0]
        second = deepcopy(first); second['id'] = 'other'; second['position'] = [3, 0, 0]
        scene['entities'].append(second)
    image = material_gpu(nodes=[('Set Material Color', {'Color': [.25, 1, 1]})], mutate=two)
    close(rgb(image, -5.2, .95), (137, 0, 0)); close(rgb(image, .8, .95), (255, 0, 0))
