"""Pixel tests of atlas frames, alpha, transforms and sampler isolation in SDL_GPU."""
from copy import deepcopy
import subprocess
import pytest
from PySide6.QtGui import QImage
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.document import load_project, save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.materials import new_asset
from tools.create_sprite_demo import create
from tests.test_textures import rgb
from tests.test_material_gpu import close


@pytest.fixture(scope='module')
def sprite_gpu(tmp_path_factory):
    exe = ROOT / 'build/node_view.exe'
    assert current(exe), 'Rebuild the native runtime before GPU checks'
    project = create(tmp_path_factory.mktemp('sprite-gpu'))
    assert QImage(str(project / 'assets/atlas.png')).save(str(project / 'assets/atlas.jpg'), quality=100)
    _, _, scene = load_project(project / 'project.json')
    def run(nodes=(), mutate=None, success=True, raw=False):
        changed = deepcopy(scene)
        if mutate and not raw: mutate(changed)
        b = GraphBuilder(); b.add('start', 'On Game Start'); previous = 'start'
        for i, (name, values) in enumerate(nodes):
            nid = f'action_{i}'; b.add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
        ir = compile_graph(b.graph, changed)
        if mutate and raw: mutate(ir['scene'])
        save_json(project / 'generated/pixels.ir.json', ir)
        capture = project / 'capture.bmp'
        result = subprocess.run([str(exe), '--ir', str(project / 'generated/pixels.ir.json'), '--project-root',
            str(project), '--frames', '2', '--capture', str(capture)], text=True, encoding='utf-8', capture_output=True, timeout=20)
        if not success: return result
        assert result.returncode == 0, result.stdout + result.stderr
        image = QImage(str(capture)); assert not image.isNull()
        return image
    return run


def test_atlas_orientation_transparent_pixels_and_shared_instances(sprite_gpu):
    image = sprite_gpu()
    for x, y, color in [(-2, 2, (255, 0, 0)), (-1, 2, (0, 255, 0)), (-2, 1, (0, 0, 255)),
        (-1, 1, (11, 15, 21)), (1, 2, (255, 255, 0)), (2, 2, (255, 0, 255)),
        (1, 1, (0, 255, 255)), (2, 1, (255, 255, 255)), (-1.5, -1.5, (255, 128, 0)), (1.5, -1.5, (128, 0, 255))]:
        close(rgb(image, x, y), color)


@pytest.mark.parametrize('frame,flip_x,flip_y,expected', [(0, True, False, (0, 255, 0)),
    (0, False, True, (0, 0, 255)), (0, True, True, (11, 15, 21)), (1, False, False, (255, 255, 0)),
    (2, False, False, (255, 128, 0)), (3, False, False, (128, 0, 255))])
def test_frame_and_flip_nodes_only_change_target(sprite_gpu, frame, flip_x, flip_y, expected):
    image = sprite_gpu([('Set Sprite Frame', {'Frame': frame}), ('Set Sprite Flip', {'Flip X': flip_x, 'Flip Y': flip_y})])
    close(rgb(image, -2, 2), expected); close(rgb(image, 1, 2), (255, 255, 0))


def test_linear_filter_does_not_bleed_into_neighbour_frames(sprite_gpu):
    def linear(scene): scene['sprite_assets'][0]['filter'] = 'linear'
    image = sprite_gpu(mutate=linear)
    close(rgb(image, -.5125, 2), (0, 255, 0))  # Last column of frame 0 borders yellow frame 1.
    close(rgb(image, -2, .5125), (0, 0, 255))  # Last row borders orange frame 2.


def test_pivot_hierarchy_transform_and_visibility(sprite_gpu):
    def pivot(scene):
        scene['sprite_assets'][0]['pivot'] = [0, 0]
        player = scene['entities'][0]; player['position'] = [0, 0, 0]; player['parent'] = 'group'
        scene['entities'].append(dict(id='group', name='Group', position=[-3, 0, 0], rotation=[0, 0, 0], scale=[.5, .5, 1]))
    image = sprite_gpu(mutate=pivot)
    close(rgb(image, -2.75, .75), (255, 0, 0)); close(rgb(image, -3.25, .75), (11, 15, 21))
    hidden = sprite_gpu([('Set Entity Visibility', {'Entity': 'group', 'Visible': False})], mutate=pivot)
    close(rgb(hidden, -2.75, .75), (11, 15, 21))


def test_material_color_and_opacity_apply_to_sprite(sprite_gpu):
    def material(scene):
        scene['material_assets'] = [dict(new_asset(), id='tint', color=[.25, 1, 1], opacity=.5, alpha_mode='blend', unlit=True)]
        scene['entities'][0]['material'] = {'asset': 'tint', 'overrides': {}}
    image = sprite_gpu(mutate=material)
    close(rgb(image, -2, 2), (100, 8, 13)); close(rgb(image, 1, 2), (255, 255, 0))


def test_grid_mismatch_fails_before_render(sprite_gpu):
    result = sprite_gpu(mutate=lambda scene: scene['sprite_assets'][0].update(columns=3), success=False)
    assert result.returncode != 0 and 'divide texture' in result.stdout + result.stderr


@pytest.mark.parametrize('texture', ['assets//atlas.png', 'assets/./atlas.png', 'assets/a:atlas.png', 'assets/../atlas.png'])
def test_native_rejects_noncanonical_texture_paths(sprite_gpu, texture):
    result = sprite_gpu(mutate=lambda scene: scene['sprite_assets'][0].update(texture=texture), success=False, raw=True)
    assert result.returncode != 0 and 'Sprite texture' in result.stdout + result.stderr


def test_jpeg_sprite_atlas(sprite_gpu):
    image = sprite_gpu(mutate=lambda scene: scene['sprite_assets'][0].update(texture='assets/atlas.jpg'))
    close(rgb(image, -2, 2), (254, 0, 0)); close(rgb(image, -1, 2), (0, 255, 1))
