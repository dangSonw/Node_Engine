from copy import deepcopy
import json
from pathlib import Path
import struct
import pytest
from editor.core import scene as api
from editor.core.document import create_project, load_project, default_scene, save_json
from editor.core.compiler import compile_graph
from editor.core.assets import import_model, model_dependencies


def test_new_project_is_valid_and_never_overwrites_existing_folder(tmp_path):
    path = create_project(tmp_path/'Game','Trò chơi mới')
    project, graph, scene = load_project(path)
    assert project['name'] == 'Trò chơi mới'
    assert len(graph['nodes']) == 2
    assert compile_graph(graph,scene)['events'] == {'start':[],'update':[]}
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        create_project(path.parent,'Overwrite')
    assert path.read_bytes() == original


def test_entity_operations_are_immutable_and_ids_survive_name_changes():
    scene = default_scene()
    before = deepcopy(scene)
    created, eid = api.create_entity(scene,'Player')
    assert api.entity(created,eid)['name'] == 'Player 2'
    copy, second = api.duplicate_entity(created,eid)
    assert second != eid
    renamed = api.set_entity_property(copy,second,'name','Nhân vật 2')
    assert api.entity(renamed,second)['id'] == second
    removed = api.delete_entity(renamed,eid)
    assert [e['id'] for e in removed['entities']] == ['player',second]
    assert scene == before


@pytest.mark.parametrize('prop,value', [('name',''),('position',[0,True,0]),('rotation',[0,float('nan'),0]),
                                         ('scale',[1,1]),('mesh','../escape.gltf'),('mesh','C:/outside.gltf')])
def test_invalid_scene_values_rejected(prop,value):
    with pytest.raises(ValueError):
        api.set_entity_property(default_scene(),'player',prop,value)


def test_scene_duplicate_ids_rejected_before_compile():
    scene = default_scene()
    scene['entities'] *= 2
    with pytest.raises(ValueError,match='unique'):
        compile_graph({'version':1,'nodes':[],'links':[]},scene)


def test_import_copies_nested_gltf_dependencies_without_collisions(tmp_path):
    source = tmp_path/'source'
    (source/'bin').mkdir(parents=True)
    (source/'tex').mkdir()
    (source/'bin/data.bin').write_bytes(b'geometry')
    (source/'tex/my image.png').write_bytes(b'fixture-image')
    save_json(source/'model.gltf', {'asset':{'version':'2.0'},'buffers':[{'uri':'bin/data.bin'}],
                                  'images':[{'uri':'tex/my%20image.png'},{'uri':'data:image/png;base64,AA=='}]})
    root = tmp_path/'game'
    root.mkdir()
    result = import_model(source/'model.gltf',root)
    assert result == 'assets/model/model.gltf'
    assert (root/'assets/model/bin/data.bin').read_bytes() == b'geometry'
    assert (root/'assets/model/tex/my image.png').read_bytes() == b'fixture-image'
    assert import_model(source/'model.gltf',root) == 'assets/model-2/model.gltf'
    assert import_model(root/result,root) == result


@pytest.mark.parametrize('uri',['missing.bin','../outside.bin','https://example.com/data.bin','%2e%2e/outside.bin',
    'data.bin?','data.bin#','bad%GG.bin','%00.bin','C%3A/file.bin'])
def test_missing_or_external_dependencies_fail_before_copy(tmp_path,uri):
    source = tmp_path/'source'
    source.mkdir()
    (tmp_path/'outside.bin').write_bytes(b'outside')
    save_json(source/'model.gltf',{'asset':{'version':'2.0'},'buffers':[{'uri':uri}]})
    root = tmp_path/'game'
    root.mkdir()
    with pytest.raises(ValueError):
        import_model(source/'model.gltf',root)
    assert not (root/'assets').exists()


def test_glb_external_dependency_is_copied(tmp_path):
    source = tmp_path/'source'
    source.mkdir()
    (source/'image.png').write_bytes(b'image')
    chunk = json.dumps({'asset':{'version':'2.0'},'images':[{'uri':'image.png'}]}).encode()
    chunk += b' ' * ((-len(chunk)) % 4)
    raw = struct.pack('<4sIII4s',b'glTF',2,len(chunk)+20,len(chunk),b'JSON') + chunk
    (source/'model.glb').write_bytes(raw)
    root = tmp_path/'game'
    root.mkdir()
    relative = import_model(source/'model.glb',root)
    assert (root/relative).read_bytes() == raw
    assert (root/'assets/model/image.png').read_bytes() == b'image'
