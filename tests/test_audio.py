"""Sound library authoring and actual shared native mixer node behavior."""
from copy import deepcopy
import json
import pytest
from PySide6.QtCore import QSettings,QTimer
from PySide6.QtWidgets import QApplication,QComboBox
from editor.core import audio
from editor.core.builder import GraphBuilder
from editor.core.document import default_scene,create_project,load_project
from editor.core.scene import validate_scene
from editor.ui.audio import SoundLibraryDialog
from editor.ui.main_window import MainWindow
from tools.create_audio_demo import tone,create
from tests.test_native import native


def sound_scene(root):
    (root/'assets').mkdir(parents=True,exist_ok=True); tone(root/'assets/tone.wav',duration=.1)
    scene=default_scene(); scene['audio_assets']=[dict(audio.new_asset('assets/tone.wav'),id='tone')]
    return scene


@pytest.mark.parametrize('change',[dict(version=True),dict(type='sprite'),dict(name=''),dict(id='x/y'),
    dict(file='../tone.wav'),dict(file='assets/../tone.wav'),dict(file='assets//tone.wav'),
    dict(file='assets/./tone.wav'),dict(file='assets/a:tone.wav'),dict(file='assets/tone.txt'),
    dict(file='tone.wav'),dict(extra=1)])
def test_asset_validation(change,tmp_path):
    scene=sound_scene(tmp_path); scene['audio_assets'][0].update(change)
    with pytest.raises(ValueError): validate_scene(scene)


def test_import_copy_and_duplicate_ids(tmp_path):
    source=tmp_path/'tone.wav'; tone(source); root=tmp_path/'project'; root.mkdir()
    original=default_scene(); scene,sid=audio.import_sound(original,root,source)
    assert original==default_scene() and audio.scene_assets(scene)[0]['id']==sid
    source.rename(tmp_path/'moved.wav')
    assert (root/scene['audio_assets'][0]['file']).read_bytes()==(tmp_path/'moved.wav').read_bytes()
    scene['audio_assets']*=2
    with pytest.raises(ValueError,match='duplicate'): validate_scene(scene)


def test_sound_dialog_undo_save_and_node_picker(app,tmp_path):
    source=tmp_path/'tone.wav'; tone(source); path=create_project(tmp_path/'project','Sound authoring')
    window=MainWindow(path,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat)); window.show()
    try:
        def import_dialog():
            dialog=QApplication.activeModalWidget(); assert isinstance(dialog,SoundLibraryDialog)
            dialog.import_sound(source); assert len(dialog.result_scene['audio_assets'])==1; dialog.accept()
        QTimer.singleShot(10,import_dialog); window.actions['Sounds…'].trigger()
        assets=deepcopy(window.scene['audio_assets']); sid=assets[0]['id']
        window.actions['Undo'].trigger(); assert not window.scene.get('audio_assets')
        window.actions['Redo'].trigger(); assert window.scene['audio_assets']==assets
        assert window.save_project() and load_project(path)[2]['audio_assets']==assets
        b=GraphBuilder(); b.add('play','Play Sound',Sound=sid); window.adapter.load(b.graph)
        window.inspect_node(window.adapter.graph.all_nodes()[0])
        picker=next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName()=='Play Sound Sound')
        assert picker.currentData()==sid
    finally:
        window.saved_signature=window.signature(); window.document_changed(); window.close()


def test_all_native_sound_nodes(native,tmp_path):
    scene=sound_scene(tmp_path); scene['variables']={}; b=GraphBuilder(); b.add('start','On Game Start'); last='start'
    def action(nid,label,**values):
        nonlocal last
        b.add(nid,label,**values); b.connect(last,'Out',nid,'In'); last=nid
    def query(nid,label,typ,**values):
        b.add(nid,label,**values); action('save_'+nid,'Set Variable' if typ=='Float' else 'Set '+typ+' Variable',Name=nid); b.connect(nid,'Value','save_'+nid,'Value')
    action('play','Play Sound',Sound='tone',Voice='first',Loop=True,Volume=.6)
    query('exists','Sound Exists','Boolean',Sound='tone'); query('playing','Is Sound Playing','Boolean',Voice='first')
    query('duration','Get Sound Duration','Float',Sound='tone'); query('position','Get Sound Position','Float',Voice='first')
    action('pause','Pause Sound',Voice='first'); query('paused','Is Sound Paused','Boolean',Voice='first')
    action('resume','Resume Sound',Voice='first'); action('gain','Set Sound Volume',Voice='first',Volume=.25)
    query('volume','Get Sound Volume','Float',Voice='first')
    action('master','Set Master Volume',Volume=.4); query('master_value','Get Master Volume','Float')
    action('second','Play Sound',Sound='tone',Voice='second'); action('stop','Stop Sound',Voice='second')
    action('all','Stop All Sounds')
    a,c=native(b.graph,scene=scene,frames=10,extra=['--project-root',str(tmp_path)])
    assert a.returncode==c.returncode==0,a.stderr+c.stderr
    state=json.loads(a.stdout); assert state==json.loads(c.stdout)
    assert state['variables']==dict(exists={'type':'bool','value':True},playing={'type':'bool','value':True},
        duration=.1,position=0.,paused={'type':'bool','value':True},volume=.25,master_value=.4)
    assert state['audio']['sample_frames']==8000 and state['audio']['master_volume']==.4
    assert not any(t['playing'] or t['paused'] for t in state['audio']['voices'].values())
    assert state['scene']['audio_assets']==scene['audio_assets']


def test_native_playback_replay_pause_loop_and_completion(native,tmp_path):
    root=create(tmp_path/'demo'); _,graph,scene=load_project(root/'project.json')
    for frames in (8,16,26,34,42):
        a,c=native(graph,scene=scene,frames=frames,extra=['--project-root',str(root),'--input-replay',str(root/'input-replay.json')])
        assert a.returncode==c.returncode==0,a.stderr+c.stderr
        state=json.loads(a.stdout); assert state==json.loads(c.stdout)
        music=state['audio']['voices']['music']
        assert state['audio']['sample_frames']==frames*800
        if frames==8: assert music['paused'] and music['position_frames']==4800
        if frames==16: assert music['playing'] and music['position_frames']==8000
        if frames==26: assert state['audio']['master_volume']==0 and music['volume']==.1
        if frames==34: assert state['audio']['master_volume']==1 and music['volume']==.4 and music['position_frames']==3200
        if frames==42: assert not music['playing']
        if frames>=16: assert not state['audio']['voices']['effect']['playing']


def test_invalid_nodes_report_source(native,tmp_path):
    scene=sound_scene(tmp_path)
    for label,values in [('Play Sound',dict(Sound='missing')),('Play Sound',dict(Sound='tone',Volume=-1)),
                         ('Stop Sound',dict(Voice='missing')),('Set Master Volume',dict(Volume=2))]:
        b=GraphBuilder(); b.add('start','On Game Start'); b.add('bad',label,**values); b.connect('start','Out','bad','In')
        a,c=native(b.graph,scene=scene,frames=0,extra=['--project-root',str(tmp_path)])
        assert a.returncode==c.returncode==1 and json.loads(a.stderr)==json.loads(c.stderr)
        assert json.loads(a.stderr)['node']=='bad'
