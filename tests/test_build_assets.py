from pathlib import Path
import json
import struct
import pytest
from editor.build_worker import stage_assets


def test_rebuild_mirrors_asset_deletions_and_empty_source(tmp_path):
    source=tmp_path/'assets'; build=tmp_path/'build'; source.mkdir(); build.mkdir()
    (source/'keep.bin').write_bytes(b'initial')
    (source/'removed.bin').write_bytes(b'obsolete')
    stage_assets(tmp_path,build)
    (source/'removed.bin').unlink(); (source/'keep.bin').write_bytes(b'updated')
    stage_assets(tmp_path,build)
    assert (build/'assets/keep.bin').read_bytes()==b'updated'
    assert not (build/'assets/removed.bin').exists()
    assert (source/'keep.bin').read_bytes()==b'updated'
    (source/'keep.bin').unlink(); source.rmdir()
    stage_assets(tmp_path,build)
    assert not (build/'assets').exists() and not list(build.glob('.assets-*'))


def test_staging_refuses_external_destination(tmp_path):
    external=tmp_path/'external'; external.mkdir(); (external/'keep').write_text('user data')
    with pytest.raises(RuntimeError,match='project build directory'):
        stage_assets(tmp_path,external)
    assert (external/'keep').read_text()=='user data'


@pytest.mark.parametrize('extension',['gltf','glb'])
def test_staging_models_and_prefab_dependencies_rebuild_without_stale_files(tmp_path,extension):
    build=tmp_path/'build'; build.mkdir()
    model=tmp_path/'models/nhân vật'; model.mkdir(parents=True)
    doc={'asset':{'version':'2.0'},'buffers':[{'uri':'data%20file.bin','byteLength':4}],
         'images':[{'uri':'texture.png'}]}
    encoded=json.dumps(doc).encode(); encoded+=b' '*(-len(encoded)%4)
    contents=(struct.pack('<4sIII4s',b'glTF',2,20+len(encoded),len(encoded),b'JSON')+encoded
              if extension=='glb' else encoded)
    (model/f'robot.{extension}').write_bytes(contents)
    (model/'data file.bin').write_bytes(b'1234'); (model/'texture.png').write_bytes(b'image')
    scene={'prefab_templates':[{'entities':[{'mesh':f'models/nhân vật/robot.{extension}'}]}]}
    stage_assets(tmp_path,build,scene)
    for file in model.iterdir(): assert (build/file.relative_to(tmp_path)).read_bytes()==file.read_bytes()
    (model/'data file.bin').write_bytes(b'5678'); stage_assets(tmp_path,build,scene)
    assert (build/'models/nhân vật/data file.bin').read_bytes()==b'5678'
    stage_assets(tmp_path,build,{'entities':[]})
    assert not list((build/'models').rglob('*.*'))
    assert (model/'data file.bin').read_bytes()==b'5678'


@pytest.mark.parametrize('failure',['missing','escape','collision','edited','link'])
def test_model_staging_failure_preserves_existing_output(tmp_path,failure):
    build=tmp_path/'build'; build.mkdir(); (build/'assets').mkdir()
    (build/'assets/keep').write_bytes(b'previous build')
    model=tmp_path/'robot.gltf'
    model.write_text(json.dumps({'asset':{'version':'2.0'},'buffers':[{'uri':'model.bin'}]}))
    (tmp_path/'model.bin').write_bytes(b'original')
    scene={'entities':[{'mesh':'robot.gltf'}]}
    if failure=='missing': (tmp_path/'model.bin').unlink()
    elif failure=='escape': model.write_text(model.read_text().replace('model.bin','../outside.bin'))
    elif failure=='collision': (build/'model.bin').write_bytes(b'user data')
    elif failure=='link':
        try: (build/'model.bin').symlink_to(tmp_path/'model.bin')
        except OSError: pytest.skip('Symbolic links unavailable')
    else:
        stage_assets(tmp_path,build,scene)
        (build/'assets').mkdir(); (build/'assets/keep').write_bytes(b'previous build')
        (build/'model.bin').write_bytes(b'user data')
    before={p.relative_to(build):p.read_bytes() for p in build.rglob('*') if p.is_file()}
    with pytest.raises((RuntimeError,ValueError,FileNotFoundError)):
        stage_assets(tmp_path,build,scene)
    assert {p.relative_to(build):p.read_bytes() for p in build.rglob('*') if p.is_file()}==before
