"""Actual SDL_GPU pixels, image formats, sampler behavior and asset failures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import struct
import subprocess
import pytest
from PySide6.QtGui import QImage
from editor.core.registry import ROOT
from editor.core.compiler import compile_graph
from editor.core.document import load_project, save_json
from editor.core.runtime_build import current
from tools.create_texture_demo import create


@pytest.fixture(scope='module')
def gpu(tmp_path_factory):
    executable = ROOT / ('build/node_view.exe' if os.name == 'nt' else 'build/node_view')
    if not executable.exists(): pytest.skip('Build the graphical runtime before these tests')
    assert current(executable), 'Rebuild the native runtime before GPU tests'
    project = create(tmp_path_factory.mktemp('textures'))
    _, graph, scene = load_project(project / 'project.json')
    original = json.loads((project / 'assets/board.gltf').read_text('utf-8'))
    def run(document=None, mesh='assets/board.gltf', label='capture'):
        if document is not None: save_json(project / mesh, document)
        changed = deepcopy(scene); changed['entities'][0]['mesh'] = mesh
        save_json(project / 'generated/test.ir.json', compile_graph(graph, changed))
        capture = project / (label + '.bmp')
        result = subprocess.run([str(executable), '--ir', str(project / 'generated/test.ir.json'),
            '--project-root', str(project), '--frames', '2', '--capture', str(capture)],
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        return result, QImage(str(capture))
    result, image = run()
    assert result.returncode == 0 and not image.isNull(), result.stderr
    return project, original, run, image


def rgb(image, x, y):
    pixels = image.height() / 8
    px, py = round(image.width()/2+x*pixels), round(image.height()/2-y*pixels)
    assert 0 <= px < image.width() and 0 <= py < image.height(), 'Sample is outside the current camera frustum'
    return image.pixelColor(px, py).getRgb()[:3]


@pytest.mark.parametrize('label,x,y,expected', [
    ('external PNG top left', -4.4, 1.9, (255, 0, 0)),
    ('opaque ignores zero alpha', -3.6, 1.9, (0, 255, 0)),
    ('UV bottom left', -4.4, 1.1, (0, 0, 255)),
    ('sRGB roundtrip', -3.6, 1.1, (128, 128, 128)),
    ('data URI mask solid', -2.4, 1.9, (255, 0, 0)),
    ('mask discarded hole', -1.6, 1.9, (11, 15, 21)),
    ('mask cutoff just above half', -2.4, 1.1, (0, 0, 255)),
    ('bufferView alpha blend linear', -.4, 1.1, (187, 187, 255)),
    ('transparent hole reveals opaque background', .4, 1.9, (255, 255, 255)),
    ('JPEG with percent-encoded filename', 2, 1.5, (32, 160, 225)),
    ('linear factor times COLOR_0', 4, 1.5, (188, 137, 255)),
    ('repeat red at u=.25', -4.6, -.9, (255, 0, 0)),
    ('repeat red again at u=1.25', -3.8, -.9, (255, 0, 0)),
    ('mirrored repeat at u=1.25', -1.8, -.9, (0, 255, 0)),
    ('clamp u above one', .2, -.9, (0, 255, 0)),
    ('UV1 plus transform scale and offset', 2, -1.5, (0, 255, 0)),
    ('mipmap minification averaged in linear space', 4, -1.5, (188, 188, 188)),
])
def test_gpu_reference_colors(gpu, label, x, y, expected):
    actual = rgb(gpu[3], x, y)
    assert all(abs(a-b) <= 2 for a, b in zip(actual, expected)), (label, actual, expected)


def test_glb_buffer_view_matches_gltf_pixels(gpu):
    result, image = gpu[2](mesh='assets/board.glb', label='glb')
    assert result.returncode == 0, result.stderr
    assert image == gpu[3]


@pytest.mark.parametrize('kind,expected', [('uv', 'TEXCOORD'), ('png', 'PNG or JPEG'),
    ('large', 'Texture header exceeds'), ('escape', 'escapes'), ('missing', 'cannot find'),
    ('count', 'TEXCOORD'), ('filter', 'minification filter')])
def test_invalid_texture_fails_explicitly(gpu, kind, expected):
    project, original, run, _ = gpu
    doc = deepcopy(original)
    primitive = doc['meshes'][0]['primitives'][0]
    if kind == 'uv': primitive['attributes'].pop('TEXCOORD_0')
    elif kind == 'filter': doc['samplers'][0]['minFilter'] = 42
    elif kind == 'count': doc['accessors'][primitive['attributes']['TEXCOORD_0']]['count'] = 3
    elif kind in ('png', 'large'):
        data = b'not an image' if kind == 'png' else b'\x89PNG\r\n\x1a\n' + struct.pack('>I4sII', 13, b'IHDR', 100000, 100000)
        (project / 'assets/invalid.png').write_bytes(data)
        doc['images'][0] = {'uri': 'invalid.png'}
    elif kind == 'escape':
        (project / 'outside.png').write_bytes((project / 'assets/images/quadrants.png').read_bytes())
        doc['images'][0] = {'uri': '../outside.png'}
    else: doc['images'][0] = {'uri': 'missing.png'}
    result, _ = run(doc, mesh='assets/invalid.gltf', label='invalid-' + kind)
    assert result.returncode != 0
    # Filesystem diagnostics are localized; only the explicit error exit is portable here.
    if kind != 'missing': assert expected.lower() in result.stderr.lower(), result.stderr


def test_untextured_default_material_is_white(gpu):
    doc = deepcopy(gpu[1])
    primitive = doc['meshes'][0]['primitives'][0]
    primitive.pop('material')
    result, image = gpu[2](doc, mesh='assets/default.gltf', label='default')
    assert result.returncode == 0, result.stderr
    color = rgb(image, -4, 1.5)
    assert max(color) - min(color) <= 1 and min(color) > 100


def test_transparent_primitives_sorted_across_entities(gpu):
    doc = deepcopy(gpu[1])
    primitive = deepcopy(doc['meshes'][0]['primitives'][0])
    doc['materials'] = [{'pbrMetallicRoughness': {'baseColorFactor': c}, 'alphaMode': 'BLEND',
                         'extensions': {'KHR_materials_unlit': {}}} for c in ([1,0,0,.5],[0,0,1,.5])]
    doc['meshes'] = [{'primitives': [dict(primitive, material=i)]} for i in range(2)]
    doc['nodes'] = [{'mesh': 0}, {'mesh': 1, 'translation': [0,0,-.5]}]
    doc['scenes'][0]['nodes'] = [0,1]  # Near red is authored before distant blue.
    result, first = gpu[2](doc, mesh='assets/layers.gltf', label='layers')
    assert result.returncode == 0, result.stderr
    color = rgb(first, -4.4, 1.9)
    assert all(abs(a-b)<=2 for a,b in zip(color, (188,4,138))), color
    doc['scenes'][0]['nodes'] = [1,0]
    result, second = gpu[2](doc, mesh='assets/layers-reversed.gltf', label='layers-reversed')
    assert result.returncode == 0, result.stderr
    assert first == second


def test_texture_transform_rotation(gpu):
    doc = deepcopy(gpu[1])
    material = doc['materials'][doc['meshes'][0]['primitives'][-2]['material']]
    material['pbrMetallicRoughness']['baseColorTexture']['extensions']['KHR_texture_transform'] = {
        'texCoord': 1, 'offset': [1,0], 'rotation': 1.5707963267948966}
    result, image = gpu[2](doc, mesh='assets/rotated.gltf', label='rotated')
    assert result.returncode == 0, result.stderr
    assert rgb(image, 2.4, -1.9) == (0,0,255)


def test_embedded_jpeg_matches_external(gpu):
    import base64
    doc = deepcopy(gpu[1])
    data = (gpu[0] / 'assets/images/solid color.jpg').read_bytes()
    doc['images'][3] = {'uri': 'data:image/jpeg;base64,' + base64.b64encode(data).decode()}
    result, image = gpu[2](doc, mesh='assets/embedded-jpeg.gltf', label='embedded-jpeg')
    assert result.returncode == 0, result.stderr
    assert image == gpu[3]
