"""Real slot files and public graph nodes, including late-load failure rollback."""
import copy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from editor.core.compiler import compile_graph
from editor.core.document import load_project,save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from tools.create_game_save_demo import GAME,SLOT


def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')


def run(project,store,frames=0,replay=False,ir=None):
    args=[str(ROOT/'build/node_preview.exe'),'--project-root',str(project),'--ir',str(ir or project/'game.ir.json'),
          '--frames',str(frames),'--save-root',str(store)]
    if replay: args+=['--input-replay',str(project/'input.json')]
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope='module')
def saved_game(tmp_path_factory):
    assert current(ROOT/'build/node_view.exe'),'Rebuild native runtime first'
    root=tmp_path_factory.mktemp('game-save'); project=root/'source'; project.mkdir()
    shutil.copytree(ROOT/'examples/game_save_demo/assets',project/'assets')
    _,graph,scene=load_project(ROOT/'examples/game_save_demo/project.json')
    save_json(project/'game.ir.json',compile_graph(graph,scene))
    save_json(project/'input.json',dict(version=1,events=[dict(frame=3,button='S',down=True)]))
    baseline=run(project,root/'empty')
    state=run(project,root/'writer',4,True)
    assert state['frame']==4 and state['persistence']['success']
    saved=slot(root/'writer').read_bytes()
    return project,saved,baseline


@pytest.mark.parametrize('damage',['truncated','duplicate','future','identity','clock','scene','input','audio','ui','meshes'])
def test_failed_load_keeps_live_state_and_file(tmp_path,saved_game,damage):
    project,raw,baseline=saved_game; data=json.loads(raw); checkpoint=data['checkpoint']
    if damage=='truncated': raw=b'{"format":'
    elif damage=='duplicate': raw=raw.replace(b'"version":2',b'"version":2,"version":2',1)
    else:
        if damage=='future': data['version']=99
        elif damage=='identity': checkpoint['program']['runtime']='incompatible'
        elif damage=='clock': checkpoint['clock']['time']=-1
        elif damage=='scene': checkpoint['scene']['entities'].append(checkpoint['scene']['entities'][0])
        elif damage=='input': checkpoint['input']['bindings']={'invalid':True}
        elif damage=='audio': checkpoint['audio']['voices']['music']['position_frames']+=9999
        elif damage=='ui': checkpoint['ui']['session']['documents'][0]['controls'][0]['at']['path']=[99999]
        elif damage=='meshes': checkpoint['identity']['meshes'].append('assets/not-loaded.gltf')
        raw=json.dumps(data).encode()
    path=slot(tmp_path); path.parent.mkdir(parents=True); path.write_bytes(raw)
    state=run(project,tmp_path)
    assert not state['persistence']['success'] and state['persistence']['error']
    expected=copy.deepcopy(baseline)
    # The graph itself records the accepted request before the failing boundary.
    for field in ('variables',):
        for name in ('accepted','pending'): expected[field][name]['value']=True
    for name in ('accepted','pending'): expected['scene']['variables'][name]['value']=True
    expected['persistence']=state['persistence']
    assert state==expected
    assert path.read_bytes()==raw


def test_program_and_resource_identity_reject_changes(tmp_path,saved_game):
    project,raw,_=saved_game; path=slot(tmp_path/'saves'); path.parent.mkdir(parents=True); path.write_bytes(raw)
    changed=tmp_path/'changed'; shutil.copytree(project,changed)
    # Same-length content edit: metadata/size-only identification would miss it.
    resource=changed/'assets/robot.gltf'; contents=resource.read_bytes()
    resource.write_bytes(contents.replace(b'"version"',b'"versioN"',1))
    assert resource.read_bytes()!=contents
    result=run(changed,tmp_path/'saves')
    assert not result['persistence']['success'] and 'identity' in result['persistence']['error']
    resource.write_bytes(contents)
    ir=json.loads((changed/'game.ir.json').read_text('utf-8')); ir['scene']['entities'][0]['name']='different program'
    save_json(changed/'game.ir.json',ir)
    result=run(changed,tmp_path/'saves')
    assert not result['persistence']['success'] and 'identity' in result['persistence']['error']
    assert path.read_bytes()==raw


def test_hashes_binary_boundaries_and_unicode_resource_paths(tmp_path,saved_game):
    project,_,_=saved_game; changed=tmp_path/'project'; shutil.copytree(project,changed)
    for size in (0,1,55,56,63,64,65,65535,65536,65537):
        (changed/'assets'/f'Tiếng Việt-{size}.bin').write_bytes(bytes(range(256))*(size//256)+bytes(range(size%256)))
    result=run(changed,tmp_path/'saves',4,True)
    assert result['persistence']['success'],result['persistence']['error']
    manifest=json.loads(slot(tmp_path/'saves').read_bytes())['checkpoint']['program']['assets']
    assert len(manifest)==12
    for name,value in manifest.items():
        data=(changed/name).read_bytes()
        assert value==dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize('legacy_animation',[False,True])
def test_older_slot_retains_progress_data_access(tmp_path,saved_game,legacy_animation):
    from editor.core.builder import GraphBuilder
    from editor.core.document import default_scene
    project,raw,_=saved_game; data=json.loads(raw)
    data['checkpoint'].pop('flow')
    data['checkpoint'].pop('random')
    for field in ('scale','real_time','unscaled_dt'): data['checkpoint']['clock'].pop(field)
    if not legacy_animation: data['checkpoint'].pop('animation')
    data['variables']['score']={'type':'float','value':42.5}
    path=slot(tmp_path); save_json(path,data); before=path.read_bytes()
    b=GraphBuilder(); b.add('start','On Game Start')
    b.add('open','Open Save Storage',**{'Game ID':GAME}); b.connect('start','Out','open','In')
    b.add('load','Load Variable',Slot=SLOT,Name='score'); b.connect('open','Out','load','In')
    scene=default_scene(); scene['variables']={'score':0.}
    ir=tmp_path/'progress.ir.json'; save_json(ir,b.compile(scene))
    result=run(project,tmp_path,ir=ir)
    assert result['persistence']['success'] and result['variables']['score']==42.5
    assert path.read_bytes()==before


def test_outside_assets_model_and_buffer_save_load_relocation(tmp_path,saved_game):
    from editor.build_worker import stage_assets
    project=tmp_path/'Trò chơi'; shutil.copytree(saved_game[0],project)
    model=project/'models/nhân vật/robot.gltf'; model.parent.mkdir(parents=True)
    document=json.loads((project/'assets/robot.gltf').read_bytes())
    data=base64.b64decode(document['buffers'][0]['uri'].split(',',1)[1])
    buffer=model.parent/'robot data.bin'; buffer.write_bytes(data)
    document['buffers'][0]['uri']='robot%20data.bin'; save_json(model,document)
    image=model.parent/'texture.png'
    shutil.copy2(ROOT/'examples/texture_demo/assets/images/quadrants.png',image)
    document['images']=[{'uri':'texture.png'}]; save_json(model,document)
    (project/'assets/robot.gltf').unlink()
    ir=json.loads((project/'game.ir.json').read_bytes())
    ir['scene']['entities'][0]['mesh']=model.relative_to(project).as_posix()
    save_json(project/'game.ir.json',ir)
    saved=run(project,tmp_path/'saves',4,True)
    assert saved['persistence']['success'],saved['persistence']['error']
    path=slot(tmp_path/'saves'); before=path.read_bytes()
    build=project/'build'; build.mkdir(); stage_assets(project,build,ir['scene'])
    shutil.copy2(project/'game.ir.json',build/'game.ir.json')
    loaded=run(build,tmp_path/'saves')
    assert loaded['persistence']['success'],loaded['persistence']['error']
    assert loaded['scene']==saved['scene']
    for relative in (model.relative_to(project),buffer.relative_to(project),image.relative_to(project)):
        file=build/relative; raw=file.read_bytes()
        changed=raw.replace(b'generator',b'generatoR',1) if file.suffix=='.gltf' else bytes([raw[0]^1])+raw[1:]
        assert changed!=raw; file.write_bytes(changed)
        rejected=run(build,tmp_path/'saves')
        assert not rejected['persistence']['success'] and 'identity' in rejected['persistence']['error']
        assert path.read_bytes()==before
        file.write_bytes(raw)
    assert run(build,tmp_path/'saves')['persistence']['success']
