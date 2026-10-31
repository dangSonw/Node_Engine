"""Native resource identity includes scene and unspawned prefab dependencies."""
import hashlib
import json
import os
import shutil
import struct
import subprocess

import pytest
from editor.core.registry import ROOT
from editor.core.runtime_build import current


@pytest.fixture(scope='module',autouse=True)
def current_probe():
    from editor.build_worker import find_tool
    assert current(ROOT/'build/node_view.exe'),'Rebuild the native runtime first'
    env=dict(os.environ,PATH=str(find_tool('clang++').parent)+os.pathsep+os.environ.get('PATH',''))
    result=subprocess.run([str(find_tool('cmake')),'--build',str(ROOT/'build'),
        '--target','node_game_checkpoint_probe','--parallel','2'],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=180)
    assert result.returncode==0,result.stdout+result.stderr


def identity(project):
    assert current(ROOT/'build/node_view.exe'),'Rebuild the native runtime first'
    return subprocess.run([str(ROOT/'build/node_game_checkpoint_probe.exe'),'--identity',str(project)],
                          capture_output=True,text=True,encoding='utf-8',timeout=20)


def model_fixture(project,extension='gltf',uri='buffer%20data.bin'):
    directory=project/'models/robot'; directory.mkdir(parents=True)
    document={'asset':{'version':'2.0','generator':'fixture-1'},'buffers':[{'uri':uri,'byteLength':4}],
              'images':[{'uri':'texture.png'},{'uri':'data:image/png;base64,AA=='}]}
    encoded=json.dumps(document).encode(); encoded+=b' '*(-len(encoded)%4)
    if extension=='glb': encoded=struct.pack('<4sIII4s',b'glTF',2,20+len(encoded),len(encoded),b'JSON')+encoded
    (directory/f'robot.{extension}').write_bytes(encoded)
    (directory/'buffer data.bin').write_bytes(b'1234')
    (directory/'texture.png').write_bytes(b'image')
    (project/'unused.bin').write_bytes(b'not a resource')
    return f'models/robot/robot.{extension}'


@pytest.mark.parametrize('extension',['gltf','glb'])
@pytest.mark.parametrize('prefab',[False,True])
def test_native_model_closure_and_relocation(tmp_path,extension,prefab):
    project=tmp_path/'project'; mesh=model_fixture(project,extension)
    scene={'entities':[{'mesh':mesh}]}
    if prefab: scene={'prefab_templates':[scene]}
    (project/'program.json').write_text(json.dumps({'scene':scene,'events':{}}))
    result=identity(project); assert result.returncode==0,result.stderr
    baseline=json.loads(result.stdout); files=baseline['assets']
    assert set(files)=={mesh,'models/robot/buffer data.bin','models/robot/texture.png'}
    for name,record in files.items():
        data=(project/name).read_bytes()
        assert record=={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    relocated=tmp_path/'relocated'; shutil.copytree(project,relocated)
    assert json.loads(identity(relocated).stdout)==baseline
    for name in files:
        file=relocated/name; raw=file.read_bytes()
        if name==mesh: changed=raw.replace(b'fixture-1',b'fixture-2')
        else: changed=bytes([raw[0]^1])+raw[1:]
        file.write_bytes(changed)
        result=identity(relocated); assert result.returncode==0,result.stderr
        assert json.loads(result.stdout)!=baseline
        file.write_bytes(raw)


@pytest.mark.parametrize('uri',['../outside.bin','/absolute.bin','https://example.org/file.bin',
    'file:///file.bin','buffer%20data.bin?','buffer%20data.bin#','bad%GG.bin','%00.bin',
    '..%2Foutside.bin','C%3A/file.bin','missing.bin'])
def test_native_rejects_unavailable_or_nonlocal_dependencies(tmp_path,uri):
    mesh=model_fixture(tmp_path,uri=uri)
    (tmp_path/'models/outside.bin').write_bytes(b'outside model directory')
    (tmp_path/'program.json').write_text(json.dumps({'scene':{'entities':[{'mesh':mesh}]},'events':{}}))
    result=identity(tmp_path)
    assert result.returncode!=0


@pytest.mark.parametrize('extension',['gltf','glb'])
def test_staged_external_textured_model_renders_identically(tmp_path,extension):
    from PySide6.QtGui import QImage
    from editor.build_worker import stage_assets
    from editor.core.document import load_project,save_json
    from editor.core.compiler import compile_graph
    from tools.create_texture_demo import create
    project=create(tmp_path/'Trò chơi')
    shutil.copytree(project/'assets',project/'models/nhân vật')
    _,graph,scene=load_project(project/'project.json')
    scene['entities'][0]['mesh']=f'models/nhân vật/board.{extension}'
    ir=compile_graph(graph,scene)
    build=project/'build'; build.mkdir(); stage_assets(project,build,ir['scene'])
    captures=[]
    for root in (project,build):
        save_json(root/'program.json',ir); capture=root/'hình ảnh.bmp'
        result=subprocess.run([str(ROOT/'build/node_view.exe'),'--ir',str(root/'program.json'),
            '--project-root',str(root),'--frames','2','--capture',str(capture)],
            capture_output=True,text=True,encoding='utf-8',timeout=25)
        assert result.returncode==0,result.stderr
        image=QImage(str(capture)); assert not image.isNull(); captures.append(image)
    assert captures[0]==captures[1]
