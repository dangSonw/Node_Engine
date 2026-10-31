"""Persistence is exercised through graph compilation and separate native processes."""
import json
import os
from pathlib import Path
import subprocess
import pytest
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.data_types import default_value


GAME='persistence-tests'
SLOT='../Tiến độ số 1'

def graph(*operations, game=GAME):
    b=GraphBuilder(); b.add('start','On Game Start')
    b.add('open','Open Save Storage',**{'Game ID':game}); b.connect('start','Out','open','In')
    previous='open'
    for index,(label,values) in enumerate(operations):
        node=f'op{index}'; b.add(node,label,**values); b.connect(previous,'Out',node,'In'); previous=node
    return b

def run(tmp_path,b,variables=None,root=None):
    assert current(ROOT/'build/node_view.exe'),'Rebuild the native runtime first'
    scene=default_scene(); scene['variables']=variables or {}
    path=tmp_path/'game.ir.json'; save_json(path,b.compile(scene))
    result=subprocess.run([str(ROOT/'build/node_preview.exe'),'--ir',str(path),'--frames','0',
        '--save-root',str(root or tmp_path/'saves')],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stderr
    return json.loads(result.stdout)

def file_at(tmp_path,slot=SLOT,game=GAME):
    return tmp_path/'saves'/game/('slot-'+slot.encode('utf-8').hex()+'.json')

def values():
    scalar={'float':12.25,'int':-(2**63),'bool':True,'string':'Đỗ Việt\0line\n😀',
            'vec3':[1.25,-2.,3.],'vec2':[4.5,-6.],'vec4':[1.,2.,3.,4.],
            'quat':[0.,0.,.5,.5],
            'mat4':[1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,2.,3.,4.,1.],
            'entity':'player'}
    result={}
    for kind,value in scalar.items():
        for shape,item in [('',value),('array',[value]),('map',{'điểm':value})]:
            type=f'{shape}<{kind}>' if shape else kind
            result[f'{kind}_{shape or "scalar"}']=dict(type=type,value=item)
    return result


def test_all_value_types_survive_restart_and_batch_load(tmp_path):
    original=values(); names=list(original)
    state=run(tmp_path,graph(('Save Variables',dict(Slot=SLOT,Names=names))),original)
    assert state['persistence']['success']
    stored=file_at(tmp_path).read_bytes()
    empty={name:dict(type=v['type'],value=default_value(v['type'])) for name,v in original.items()}
    loaded=run(tmp_path,graph(('Load Variables',dict(Slot=SLOT,Names=names))),empty)
    expected={k:(v['value'] if v['type']=='float' else v) for k,v in original.items()}
    assert loaded['persistence']['success'] and loaded['variables']==expected
    assert file_at(tmp_path).read_bytes()==stored
    assert list((tmp_path/'saves'/GAME).glob('*.json'))==[file_at(tmp_path)]


def test_failed_batch_has_no_partial_write_or_variable_load(tmp_path):
    original={'a':dict(type='int',value=12),'b':dict(type='string',value='saved')}
    save=graph(('Save Variables',dict(Slot=SLOT,Names=['a','b'])))
    run(tmp_path,save,original); before=file_at(tmp_path).read_bytes()
    bad_save=run(tmp_path,save,{'a':dict(type='int',value=99)})
    assert not bad_save['persistence']['success'] and file_at(tmp_path).read_bytes()==before
    changed={'a':dict(type='int',value=99),'b':dict(type='int',value=44)}
    state=run(tmp_path,graph(('Load Variables',dict(Slot=SLOT,Names=['a','b']))),changed)
    assert 'type mismatch: b' in state['persistence']['error'] and state['variables']==changed
    missing=run(tmp_path,graph(('Load Variable',dict(Slot=SLOT,Name='missing'))),original)
    assert not missing['persistence']['success'] and missing['variables']==original


@pytest.mark.parametrize('damage', ['truncated','future','duplicate','deep','oversize','identity','wrong-type','negative-version'])
def test_damaged_slot_is_rejected_and_never_overwritten(tmp_path,damage):
    b=graph(('Save Variable',dict(Slot=SLOT,Name='score')))
    run(tmp_path,b,{'score':1.})
    path=file_at(tmp_path); data=json.loads(path.read_text('utf-8'))
    if damage=='truncated': text='{"format":'
    elif damage=='duplicate': text=path.read_text('utf-8').replace('"version":1','"version":1,"version":1')
    elif damage=='deep': text='['*70+'0'+']'*70
    elif damage=='oversize': text=' '*(16*1024*1024+1)
    else:
        if damage=='future': data['version']=99
        elif damage=='identity': data['game_id']='different-game'
        elif damage=='wrong-type': data['variables']['score']['value']='wrong'
        else: data['version']=-1
        text=json.dumps(data)
    path.write_text(text,encoding='utf-8'); before=path.read_bytes()
    state=run(tmp_path,b,{'score':2.})
    assert not state['persistence']['success'] and state['persistence']['error']
    assert path.read_bytes()==before
    state=run(tmp_path,graph(('Validate Save Data',dict(Slot=SLOT))))
    assert not state['persistence']['success']
    if damage=='future':
        b=graph(('Get Save Version',dict(Slot=SLOT)))
        b.add('result','Set Integer Variable',Name='version'); b.connect('op0','Out','result','In'); b.connect('op0','Value','result','Value')
        assert run(tmp_path,b,{'version':dict(type='int',value=0)})['variables']['version']['value']==99
    assert run(tmp_path,graph(('Delete Save Slot',dict(Slot=SLOT))))['persistence']['success']
    assert not path.exists()


def test_slot_lifecycle_json_and_namespace_isolation(tmp_path):
    b=graph(('Create Save Slot',dict(Slot=SLOT)),('Save JSON',dict(Slot=SLOT,Key='settings',JSON='{"name":"Việt","n":9223372036854775807}')),
        ('Create Save Slot',dict(Slot=SLOT)),('Create Save Slot',dict(Slot='second')),('List Save Slots',{}))
    b.add('result','Set String Array Variable',Name='slots'); b.connect('op4','Out','result','In'); b.connect('op4','Value','result','Value')
    state=run(tmp_path,b,{'slots':dict(type='array<string>',value=[])})
    assert state['variables']['slots']['value']==[SLOT,'second']
    b=graph(('Load JSON',dict(Slot=SLOT,Key='settings')))
    b.add('result','Set String Variable',Name='json'); b.connect('op0','Out','result','In'); b.connect('op0','Value','result','Value')
    loaded=run(tmp_path,b,{'json':dict(type='string',value='')})
    assert json.loads(loaded['variables']['json']['value'])==dict(name='Việt',n=2**63-1)
    before=file_at(tmp_path).read_bytes()
    assert not run(tmp_path,graph(('Save JSON',dict(Slot=SLOT,JSON='{"bad":NaN}'))))['persistence']['success']
    assert file_at(tmp_path).read_bytes()==before
    other=run(tmp_path,graph(('Load JSON',dict(Slot=SLOT,Key='settings')),game='other-game'))
    assert 'does not exist' in other['persistence']['error']
    missing=run(tmp_path,graph(('Save Slot Exists',dict(Slot='absent'))))
    assert missing['persistence']['success'] and not missing['persistence']['error']
    deleted=run(tmp_path,graph(('Delete Save Slot',dict(Slot=SLOT))))
    assert deleted['persistence']['success'] and not file_at(tmp_path).exists()


@pytest.mark.parametrize('game',['../escape','a/b','C:drive','', 'A-game','x'*65])
def test_invalid_game_id_creates_nothing(tmp_path,game):
    state=run(tmp_path,graph(game=game))
    assert not state['persistence']['success'] and not (tmp_path/'saves').exists()


def test_blocked_replacement_keeps_previous_save_and_cleans_temporary(tmp_path):
    if os.name!='nt': pytest.skip('Windows readonly replacement failure')
    import ctypes
    b=graph(('Save Variable',dict(Slot=SLOT,Name='score')))
    run(tmp_path,b,{'score':1.}); path=file_at(tmp_path); before=path.read_bytes()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.SetFileAttributesW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32]
    assert kernel.SetFileAttributesW(str(path),1)
    try:
        state=run(tmp_path,b,{'score':2.})
        assert not state['persistence']['success'] and 'replace save' in state['persistence']['error']
        assert path.read_bytes()==before
        assert not list(path.parent.glob('.write-*.tmp'))
    finally: assert kernel.SetFileAttributesW(str(path),128)


def test_another_process_lock_prevents_lost_updates(tmp_path):
    if os.name!='nt': pytest.skip('Windows exclusive handle fixture')
    import ctypes
    b=graph(('Save Variable',dict(Slot=SLOT,Name='score')))
    run(tmp_path,b,{'score':1.}); path=file_at(tmp_path); before=path.read_bytes()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    kernel.CreateFileW.restype=ctypes.c_void_p
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.CreateFileW(str(path.parent/'.storage.lock'),0xC0000000,0,None,3,128,None)
    assert handle not in (None,ctypes.c_void_p(-1).value)
    try:
        state=run(tmp_path,graph())
        assert not state['persistence']['success'] and 'lock' in state['persistence']['error']
        assert path.read_bytes()==before
    finally: kernel.CloseHandle(handle)


def test_directory_at_slot_path_cannot_be_read_or_deleted(tmp_path):
    run(tmp_path,graph()); path=file_at(tmp_path); path.mkdir(); (path/'keep').write_text('user file')
    for operation in ('Save Variable','Load Variable','Delete Save Slot'):
        args=dict(Slot=SLOT)
        if operation!='Delete Save Slot': args['Name']='score'
        state=run(tmp_path,graph((operation,args)),{'score':1.})
        assert not state['persistence']['success'] and (path/'keep').read_text()=='user file'
