import json
from editor.core.builder import GraphBuilder
from editor.core.document import create_project, save_json
from editor.core.project_format import load_manifest
from editor.core.projects import add_scene, project_snapshot, compile_project
from tests.test_native import native


def test_nen_multiscene_startup_uses_shared_native_hosts(native,tmp_path):
    path=create_project(tmp_path/'Native game','Native launch')
    project=add_scene(path,'level')
    project['entry_scene']='level'; save_json(path,project)
    for scene_id,value in [('main',99),('level',42)]:
        builder=GraphBuilder()
        builder.add('start','On Game Start')
        builder.add('score','Set Integer Variable',Name='score',Value=value)
        builder.connect('start','Out','score','In')
        entry=next(entry for entry in project['scenes'] if entry['id']==scene_id)
        save_json(path.parent/entry['graph'],builder.graph)
    program=compile_project(project_snapshot(path))
    a,b=native(program=program,frames=3)
    assert a.returncode==b.returncode==0,a.stderr+b.stderr
    state=json.loads(a.stdout)
    assert state==json.loads(b.stdout)
    assert state['variables']['score']=={'type':'int','value':42}
    assert state['scene_session']['active']=='level'
    assert load_manifest(path)['entry_scene']=='level'
