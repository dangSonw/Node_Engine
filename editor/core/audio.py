"""Scene sound assets; decoding is validated by the native SDL_mixer at preview/build runtime."""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import re
import shutil
import uuid
from .scene import asset_path, entity_text

EXTENSIONS = ('.wav', '.ogg', '.mp3', '.flac')


def new_asset(file, name='Sound'):
    return dict(version=1, type='sound', id=uuid.uuid4().hex, name=name, file=file)


def validate_assets(values):
    if not isinstance(values, list) or len(values)>1024:
        raise ValueError('At most 1024 sound assets are allowed')
    result = {}
    for a in values:
        if not isinstance(a, dict) or set(a) != {'version','type','id','name','file'}:
            raise ValueError('Invalid sound asset fields')
        if type(a['version']) is not int or a['version']!=1 or a['type']!='sound':
            raise ValueError('Unsupported sound version/type')
        sid = a['id']
        if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',sid) or sid in result:
            raise ValueError('Invalid or duplicate sound ID')
        if not entity_text(a['name'],512): raise ValueError('Invalid sound name')
        path = PurePosixPath(asset_path(a['file']))
        if (not entity_text(a['file'],4096) or ':' in a['file'] or path.as_posix()!=a['file'] or
                path.parts[0]!='assets' or path.suffix.lower() not in EXTENSIONS):
            raise ValueError('Sound requires a WAV, Ogg, MP3 or FLAC file inside project assets')
        result[sid] = a
    return result


def scene_assets(scene):
    return list(validate_assets(scene.get('audio_assets',[])).values())


def put_asset(scene, asset):
    from .scene import validate_scene
    validate_assets([asset]); result=deepcopy(scene)
    values={a['id']:a for a in scene_assets(result)}; values[asset['id']]=deepcopy(asset)
    result['audio_assets']=list(values.values())
    return validate_scene(result)


def import_sound(scene, project_root, source):
    root, source = Path(project_root).resolve(), Path(source).resolve()
    if source.suffix.lower() not in EXTENSIONS or not source.is_file() or not 0<source.stat().st_size<=64*1024*1024:
        raise ValueError('Sound requires WAV, Ogg, MP3 or FLAC of at most 64 MiB')
    asset = new_asset('',source.stem)
    relative=Path('assets/audio')/(asset['id']+source.suffix.lower())
    target=root/relative
    if not target.resolve().is_relative_to(root/'assets'):
        raise ValueError('Sound destination escapes project assets')
    asset['file']=relative.as_posix(); result=put_asset(scene,asset)
    target.parent.mkdir(parents=True,exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst: shutil.copyfileobj(src,dst)
    return result,asset['id']
