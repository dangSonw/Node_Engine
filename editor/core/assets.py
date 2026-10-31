"""Copy standard glTF dependency sets into the project without overwriting files."""
import json
import os
import re
from pathlib import Path, PureWindowsPath
import shutil
import struct
from urllib.parse import unquote, urlsplit


def model_dependencies(source):
    source = Path(source).resolve()
    if source.stat().st_size > 64*1024*1024:
        raise ValueError('Model document exceeds 64 MiB')
    if source.suffix.lower() == '.glb':
        with source.open('rb') as stream:
            header = stream.read(12)
            if len(header) != 12 or struct.unpack('<4sII',header) != (b'glTF',2,source.stat().st_size):
                raise ValueError('Invalid GLB header or file length')
            chunk = stream.read(8)
            if len(chunk) != 8:
                raise ValueError('GLB is missing its JSON chunk')
            length, kind = struct.unpack('<I4s',chunk)
            if kind != b'JSON' or length > source.stat().st_size - 20:
                raise ValueError('Invalid GLB JSON chunk')
            doc = json.loads(stream.read(length))
    elif source.suffix.lower() == '.gltf':
        doc = json.loads(source.read_text('utf-8'))
    else:
        raise ValueError('Choose a glTF or GLB model')
    if not isinstance(doc,dict) or doc.get('asset',{}).get('version') != '2.0':
        raise ValueError('Expected a glTF 2.0 document')
    dependencies = [source]
    for item in doc.get('buffers',[]) + doc.get('images',[]):
        uri = item.get('uri','')
        if not uri or uri.startswith('data:'):
            continue
        parsed = urlsplit(uri)
        if re.search(r'%(?![0-9a-fA-F]{2})',uri):
            raise ValueError(f'Invalid model dependency URI escape: {uri}')
        relative = unquote(parsed.path,errors='strict')
        if (parsed.scheme or parsed.netloc or any(c in uri for c in ':?#\\') or
                any(c in relative for c in '\0\\:') or PureWindowsPath(relative).drive):
            raise ValueError(f'Only local relative asset dependencies are supported: {uri}')
        # Keep an internal symlink's URI name when copying, while checking its target.
        path = Path(os.path.abspath(source.parent / relative))
        if not path.is_relative_to(source.parent) or not path.resolve().is_relative_to(source.parent):
            raise ValueError(f'Asset dependency escapes its source directory: {uri}')
        if not path.is_file():
            raise ValueError(f'Missing model dependency: {uri}')
        if path not in dependencies:
            dependencies.append(path)
    return dependencies


def import_model(source, project_root):
    source, root = Path(source).resolve(), Path(project_root).resolve()
    dependencies = model_dependencies(source)
    assets = root/'assets'
    assets.mkdir(exist_ok=True)
    if source.is_relative_to(assets):
        return source.relative_to(root).as_posix()
    destination = assets/source.stem
    index = 2
    while destination.exists():
        destination = assets/f'{source.stem}-{index}'
        index += 1
    destination.mkdir(exist_ok=False)
    for dependency in dependencies:
        target = destination/dependency.relative_to(source.parent)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(dependency,target)
    return (destination/source.name).relative_to(root).as_posix()
