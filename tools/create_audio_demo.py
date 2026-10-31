"""A sprite board with independently controlled music and effect voices."""
from pathlib import Path
import math
import struct
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editor.core.audio import new_asset
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import load_project,save_json
from editor.core.registry import ROOT
from tools.create_sprite_demo import create as sprite_demo


def tone(path,frequency=220,duration=1.):
    with wave.open(str(path),'wb') as wav:
        wav.setparams((2,2,48000,0,'NONE','not compressed'))
        samples=bytearray()
        for i in range(round(duration*48000)):
            value=round(6000*math.sin(2*math.pi*frequency*i/48000))
            samples.extend(struct.pack('<hh',value,value))
        wav.writeframes(samples)


def create(directory=ROOT/'examples/audio_demo'):
    directory=sprite_demo(directory)
    _,_,scene=load_project(directory/'project.json')
    tone(directory/'assets/music.wav'); tone(directory/'assets/effect.wav',660,.1)
    scene['audio_assets']=[dict(new_asset('assets/'+key+'.wav',key.title()),id=key) for key in ('music','effect')]
    actions={'effect':'Space','pause':'P','resume':'R','stop':'S','quiet':'V','mute':'M','restart':'L'}
    scene['input']=dict(version=1,actions={k:[v] for k,v in actions.items()},axes={})
    b=GraphBuilder('Audio: Space effect, P pause, R resume, S stop, V volume, M master mute, L restart')
    b.add('start','On Game Start'); b.add('music','Play Sound',Sound='music',Voice='music',Loop=True,Volume=.4)
    b.connect('start','Out','music','In')
    commands={
        'effect':('Play Sound',dict(Sound='effect',Voice='effect',Volume=.3)),
        'pause':('Pause Sound',dict(Voice='music')),'resume':('Resume Sound',dict(Voice='music')),
        'stop':('Stop All Sounds',{}),'quiet':('Set Sound Volume',dict(Voice='music',Volume=.1)),
        'mute':('Set Master Volume',dict(Volume=0.)),
        'restart':('Play Sound',dict(Sound='music',Voice='music',Loop=True,Volume=.4))}
    for index,(action,(command,values)) in enumerate(commands.items()):
        b.add(action+'_update','On Update'); b.add(action+'_pressed','Is Action Pressed',Action=action)
        b.add(action+'_if','Branch'); b.add(action+'_run',command,**values)
        b.connect(action+'_update','Out',action+'_if','In'); b.connect(action+'_pressed','Value',action+'_if','Condition')
        b.connect(action+'_if','True',action+'_run','In')
        b.add(action+'_frame','Set Sprite Frame',Frame=index%4)
        b.connect(action+'_run','Out',action+'_frame','In')
        if action=='restart':
            b.add('unmute','Set Master Volume',Volume=1.); b.connect(action+'_frame','Out','unmute','In')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%5)*260,(i//5)*220]
    save_json(directory/'scenes/main.json',scene); save_json(directory/'graphs/gameplay.json',b.graph)
    save_json(directory/'project.json',dict(version=1,name='Audio playground',graph='graphs/gameplay.json',scene='scenes/main.json',
        assets=['assets/atlas.png','assets/music.wav','assets/effect.wav']))
    save_json(directory/'input-replay.json',dict(version=1,events=[dict(frame=frame+release,button=key,down=not release)
        for frame,key in [(2,'Space'),(6,'P'),(12,'R'),(18,'V'),(24,'M'),(30,'L'),(38,'S')]
        for release in (0,1)]))
    export(compile_graph(b.graph,scene),directory/'generated')
    return directory


if __name__=='__main__': print(create())
