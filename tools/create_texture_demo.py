"""Reproducible glTF/GLB texture conformance board; no external art required."""
from copy import deepcopy
import base64
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QImage, QColor
from editor.core.document import save_json, empty_graph
from editor.core.camera import default_camera
from editor.core.compiler import compile_graph
from editor.core.codegen import export
from editor.core.registry import ROOT


def create(directory=ROOT / 'examples/texture_demo'):
    directory = Path(directory)
    assets = directory / 'assets'
    (assets / 'images').mkdir(parents=True, exist_ok=True)
    checker = QImage(32, 32, QImage.Format_RGBA8888)
    for y in range(32):
        for x in range(32):
            checker.setPixelColor(x, y, QColor(*[(255, 0, 0, 255), (0, 255, 0, 0),
                (0, 0, 255, 128), (128, 128, 128, 255)][(y >= 16) * 2 + (x >= 16)]))
    assert checker.save(str(assets / 'images/quadrants.png'))
    jpeg = QImage(32, 32, QImage.Format_RGB888); jpeg.fill(QColor(32, 160, 224))
    assert jpeg.save(str(assets / 'images/solid color.jpg'), quality=100)
    mip = QImage(32, 32, QImage.Format_RGBA8888)
    for y in range(32):
        for x in range(32):
            value = 255 * ((x + y) % 2)
            mip.setPixelColor(x, y, QColor(value, value, value))
    assert mip.save(str(assets / 'images/mip.png'))
    png = (assets / 'images/quadrants.png').read_bytes()
    binary = bytearray()
    doc = dict(asset={'version': '2.0', 'generator': 'Node_Engine texture test board'}, scene=0,
        scenes=[{'nodes': [0]}], nodes=[{'mesh': 0}], meshes=[{'primitives': []}],
        accessors=[], bufferViews=[], buffers=[], materials=[], images=[], textures=[],
        samplers=[{'magFilter': 9728, 'minFilter': 9728, 'wrapS': w, 'wrapT': w}
                  for w in (33071, 10497, 33648)] + [{'magFilter': 9729, 'minFilter': 9987}],
        extensionsUsed=['KHR_materials_unlit', 'KHR_texture_transform'])
    def view(data):
        binary.extend(b'\0' * (-len(binary) % 4))
        offset = len(binary); binary.extend(data)
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data)})
        return len(doc['bufferViews']) - 1
    def accessor(values, kind, components, code='f', component=5126):
        data = struct.pack('<' + code * len(values) * components, *(n for row in values for n in row))
        entry = dict(bufferView=view(data), componentType=component, count=len(values), type=kind)
        if kind == 'VEC3':
            entry.update(min=[min(v[i] for v in values) for i in range(3)],
                         max=[max(v[i] for v in values) for i in range(3)])
        doc['accessors'].append(entry)
        return len(doc['accessors']) - 1
    doc['images'] = [{'uri': 'images/quadrants.png'},
        {'uri': 'data:image/png;base64,' + base64.b64encode(png).decode()},
        {'bufferView': view(png), 'mimeType': 'image/png'},
        {'uri': 'images/solid%20color.jpg'}, {'uri': 'images/mip.png'}]
    doc['textures'] = [{'source': i, 'sampler': 0} for i in range(4)] + [
        {'source': 0, 'sampler': 1}, {'source': 0, 'sampler': 2}, {'source': 4, 'sampler': 3}]
    def material(texture=None, mode='OPAQUE', factor=None, transform=None):
        pbr = {'baseColorFactor': factor or [1, 1, 1, 1]}
        if texture is not None:
            pbr['baseColorTexture'] = {'index': texture}
            if transform:
                pbr['baseColorTexture']['extensions'] = {'KHR_texture_transform': transform}
        doc['materials'].append({'pbrMetallicRoughness': pbr, 'alphaMode': mode,
                                'extensions': {'KHR_materials_unlit': {}}})
        return len(doc['materials']) - 1
    def quad(x, y, mat, uv=None, colors=None, channel=0, z=0):
        attrs = {'POSITION': accessor([(x-.8, y-.8, z), (x+.8, y-.8, z),
            (x+.8, y+.8, z), (x-.8, y+.8, z)], 'VEC3', 3)}
        attrs['TEXCOORD_' + str(channel)] = accessor(uv or [(0, 1), (1, 1), (1, 0), (0, 0)], 'VEC2', 2)
        if colors:
            attrs['COLOR_0'] = accessor([colors] * 4, 'VEC4', 4)
        primitive = {'attributes': attrs, 'indices': accessor([(0,), (1,), (2,), (0,), (2,), (3,)],
                                                              'SCALAR', 1, 'H', 5123)}
        if mat is not None: primitive['material'] = mat
        doc['meshes'][0]['primitives'].append(primitive)
    quad(-4, 1.5, material(0))
    quad(-2, 1.5, material(1, 'MASK'))
    # Reverse authoring order: renderer must draw the opaque background first.
    quad(0, 1.5, material(2, 'BLEND'))
    quad(0, 1.5, material(), z=-.25)
    quad(2, 1.5, material(3))
    quad(4, 1.5, material(factor=[.5, 1, 1, 1]), colors=[1, .25, 1, 1])
    repeat_uv = [(0, 2), (2, 2), (2, 0), (0, 0)]
    quad(-4, -1.5, material(4), repeat_uv)
    quad(-2, -1.5, material(5), repeat_uv)
    quad(0, -1.5, material(0), repeat_uv)
    quad(2, -1.5, material(0, transform={'texCoord': 1, 'offset': [.5, 0], 'scale': [.5, .5]}), channel=1)
    quad(4, -1.5, material(6), [(0, 128), (128, 128), (128, 0), (0, 0)])
    doc['buffers'] = [{'byteLength': len(binary), 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(binary).decode()}]
    save_json(assets / 'board.gltf', doc)
    glb = deepcopy(doc); glb['buffers'][0].pop('uri')
    data = json.dumps(glb, separators=(',', ':')).encode()
    data += b' ' * (-len(data) % 4); binary.extend(b'\0' * (-len(binary) % 4))
    content = struct.pack('<I4s', len(data), b'JSON') + data + struct.pack('<I4s', len(binary), b'BIN\0') + binary
    (assets / 'board.glb').write_bytes(struct.pack('<4sII', b'glTF', 2, 12 + len(content)) + content)
    scene = {'entities': [dict(id='board', name='Texture conformance board', position=[0, 0, 0],
        rotation=[0, 0, 0], scale=[1, 1, 1], mesh='assets/board.gltf'),
        dict(id='camera', name='Board camera', position=[0, 0, 8], rotation=[0, 0, 0], scale=[1, 1, 1],
             camera=dict(default_camera(), projection='orthographic', size=8))], 'variables': {}, 'active_camera': 'camera'}
    graph = empty_graph()
    save_json(directory / 'project.json', dict(version=1, name='Texture conformance board',
        graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/board.gltf']))
    save_json(directory / 'scenes/main.json', scene)
    save_json(directory / 'graphs/gameplay.json', graph)
    export(compile_graph(graph, scene), directory / 'generated')
    return directory


if __name__ == '__main__':
    print(create())
