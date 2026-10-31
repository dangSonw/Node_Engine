"""Export an unrotated, untextured Blockbench cube fixture as embedded glTF.

This intentionally small converter is not Blockbench's desktop glTF exporter.
Unsupported geometry is rejected instead of silently producing a different model.
"""
import argparse
import base64
import json
from pathlib import Path
import struct


def convert(source, output):
    doc = json.loads(Path(source).read_text('utf-8'))
    if doc.get('textures') or doc.get('animations'):
        raise ValueError('Fixture exporter accepts only untextured static cubes')
    for item in doc.get('groups', []) + doc['elements']:
        if any(item.get('rotation', [0, 0, 0])) or item.get('inflate', 0):
            raise ValueError('Fixture exporter does not support rotation or inflation')
    binary = bytearray()
    views, accessors, meshes, nodes = [], [], [], []
    materials = [
        {'name': name, 'pbrMetallicRoughness': {'baseColorFactor': color,
          'metallicFactor': 0, 'roughnessFactor': 1}, 'doubleSided': True}
        for name, color in [('Lavender', [.58, .43, .91, 1]), ('Cyan', [.16, .78, .85, 1]),
                            ('Ink', [.025, .045, .09, 1])]
    ]
    def accessor(values, components, component_type, target):
        fmt = 'f' if component_type == 5126 else 'I'
        flat = [v for row in values for v in row] if components > 1 else values
        raw = struct.pack('<' + fmt * len(flat), *flat)
        views.append({'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(raw), 'target': target})
        binary.extend(raw)
        entry = {'bufferView': len(views)-1, 'componentType': component_type,
                 'count': len(values), 'type': 'VEC3' if components == 3 else 'SCALAR'}
        if components == 3:
            entry.update(min=[min(p[i] for p in values) for i in range(3)],
                         max=[max(p[i] for p in values) for i in range(3)])
        accessors.append(entry)
        return len(accessors)-1
    for item in doc['elements']:
        if item.get('type', 'cube') != 'cube':
            raise ValueError('Fixture exporter accepts only cubes')
        lo, hi = item['from'], item['to']
        if any(lo[i] >= hi[i] for i in range(3)):
            raise ValueError('Invalid cube extent')
        vertices = [[x/16, y/16, z/16] for x, y, z in [
            (lo[0],lo[1],lo[2]), (hi[0],lo[1],lo[2]), (hi[0],hi[1],lo[2]), (lo[0],hi[1],lo[2]),
            (lo[0],lo[1],hi[2]), (hi[0],lo[1],hi[2]), (hi[0],hi[1],hi[2]), (lo[0],hi[1],hi[2])]]
        # Outward winding for all six faces; native importer bakes flat lighting.
        indices = [0,2,1,0,3,2, 4,5,6,4,6,7, 0,4,7,0,7,3,
                   1,2,6,1,6,5, 0,1,5,0,5,4, 3,7,6,3,6,2]
        material = 2 if 'Eye' in item['name'] else 1 if any(s in item['name'] for s in ('Arm','Light')) else 0
        meshes.append({'name': item['name'], 'primitives': [{'attributes': {'POSITION': accessor(vertices,3,5126,34962)},
            'indices': accessor(indices,1,5125,34963), 'material': material, 'mode': 4}]})
        nodes.append({'name': item['name'], 'mesh': len(meshes)-1})
    result = {'asset': {'version': '2.0', 'generator': 'Node_Engine cube fixture exporter'},
              'scene': 0, 'scenes': [{'nodes': list(range(len(nodes)))}], 'nodes': nodes,
              'meshes': meshes, 'materials': materials, 'bufferViews': views, 'accessors': accessors,
              'buffers': [{'byteLength': len(binary), 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(binary).decode('ascii')}]}
    Path(output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return {'cubes': len(meshes), 'triangles': len(meshes)*12, 'bytes': len(binary)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    args = parser.parse_args()
    print(convert(args.source, args.output))
