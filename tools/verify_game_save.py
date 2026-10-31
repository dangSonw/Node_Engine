"""Public Save/Load nodes: separate processes, relocated packages, PCM and GPU parity."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_game_save_demo import GAME,SLOT


def verify():
    artifacts=ROOT/'artifacts/validation/game-save'; artifacts.mkdir(parents=True,exist_ok=True)
    output=artifacts.parent/'game-save-checks.json'
    workspace=ROOT/'.cache'/('game-save-'+uuid.uuid4().hex[:10]); package=workspace/'package'
    package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def pcm(path):
        data=path.read_bytes()
        check(path.stem+': stereo float32 PCM at 48 kHz',data[:4]==b'RIFF' and data[8:16]==b'WAVEfmt ' and
              struct.unpack_from('<HHI',data,20)==(3,2,48000) and data[36:40]==b'data' and
              struct.unpack_from('<I',data,40)[0]==len(data)-44)
        return data[44:]
    try:
        check('Native runtime build is current',current(ROOT/'build/node_view.exe'))
        for file in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/file,package/file)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        shutil.copytree(ROOT/'examples/game_save_demo/assets',package/'assets')
        shutil.copy2(ROOT/'examples/game_save_demo/generated/game.ir.json',package/'game.ir.json')
        check('Package carries the SHA-256 dependency license',(package/'licenses/PicoSHA2.txt').read_bytes()==(ROOT/'runtime/third_party/picosha2/LICENSE').read_bytes())
        save_json(package/'input.json',dict(version=1,events=[dict(frame=3,button='S',down=True),dict(frame=4,button='S',down=False)]))
        save_json(package/'resume.json',dict(version=1,events=[dict(frame=4,button='S',down=False)]))
        save_json(package/'empty-ui.json',dict(version=1,events=[dict(frame=0,type='clear')]))
        save_json(package/'load-ui.json',dict(version=1,events=[dict(frame=6,type='move',x=250,y=140),
            dict(frame=6,type='button',button=0,down=True),dict(frame=6,type='button',button=0,down=False)]))
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        saves={}; saved_states={}; references={}; states={}; images={}; audio={}
        def launch(phase,mode,exe,frames,store,replay='input.json',ui='empty-ui.json'):
            prefix=artifacts/(phase+'-'+mode)
            args=[str(package/exe),'--frames',str(frames),'--save-root',str(store),'--output',str(prefix.with_suffix('.json')),
                  '--ui-replay',ui,'--audio-output',str(prefix.with_suffix('.wav'))]
            if 'preview' in mode: args+=['--ir','game.ir.json']
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            if replay: args+=['--input-replay',replay]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,'utf-8')
            check(phase+': '+mode+' exits successfully',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            return state,prefix
        for mode,exe in modes:
            state,prefix=launch('reference',mode,exe,8,workspace/'reference'/mode)
            check('reference: '+mode+' completed save at frame four',state['frame']==8 and state['variables']['score']==8 and state['persistence']['success'])
            references[mode]=state; audio[mode]=pcm(prefix.with_suffix('.wav'))
            if mode.startswith('view'): images[mode]=prefix.with_suffix('.bmp').read_bytes()
            state,prefix=launch('save',mode,exe,4,workspace/'stores'/mode)
            saved_states[mode]=state
            check('save: '+mode+' captured after graph and timer work',state['frame']==4 and state['variables']['score']==4 and state['variables']['ticks']==3 and state['persistence']['success'])
            saves[mode]=slot(workspace/'stores'/mode).read_bytes()
            saved=json.loads(saves[mode])
            check('save: '+mode+' persisted deferred Accepted/Pending state',saved['version']==2 and saved['checkpoint']['clock']['frame']==4 and
                  saved['checkpoint']['scene']['variables']['accepted']['value'] and saved['checkpoint']['scene']['variables']['pending']['value'])
        # The actual Windows window uses the monitor DPI; headless defaults to 1.
        # Preserve that difference and exercise cross-density restoration below.
        checkpoints={mode:json.loads(data) for mode,data in saves.items()}
        report['ui_density']={mode:doc['checkpoint']['ui']['session'].pop('density') for mode,doc in checkpoints.items()}
        check('Four save documents match except their host UI density',len({json.dumps(doc,sort_keys=True) for doc in checkpoints.values()})==1)
        check('Preview and generated hosts write identical bytes at the same density',
              saves['headless-preview']==saves['headless-compiled'] and saves['view-preview']==saves['view-compiled'])
        check('Four reference hosts produce identical state',len({json.dumps(s,sort_keys=True) for s in references.values()})==1)
        check('Four reference hosts produce identical PCM',len(set(audio.values()))==1)
        check('Reference GPU image bytes match',images['view-preview']==images['view-compiled'])
        manifest=json.loads(next(iter(saves.values())))['checkpoint']['program']['assets']
        check('Every packaged resource SHA-256 matches Python hashlib',all(
            value==dict(bytes=(package/name).stat().st_size,sha256=hashlib.sha256((package/name).read_bytes()).hexdigest())
            for name,value in manifest.items()))
        moved=workspace/'Trò chơi đã di chuyển'; package.rename(moved); package=moved; report['package']=str(package)
        # Cross every writer with every reader, not only each host's own output.
        for index,(mode,exe) in enumerate(modes):
            store=workspace/'stores'/modes[(index+1)%4][0]; before=slot(store).read_bytes()
            state,prefix=launch('restore',mode,exe,4,store,'resume.json')
            check('restore: '+mode+' resumes saved clock without repeating OnStart',state==references[mode])
            check('restore: '+mode+' keeps the slot bytes intact',slot(store).read_bytes()==before)
            check('restore: '+mode+' has byte-identical continuation PCM',pcm(prefix.with_suffix('.wav'))==audio[mode][4*800*8:])
            if mode.startswith('view'):
                check('restore: '+mode+' has byte-identical final GPU pixels',prefix.with_suffix('.bmp').read_bytes()==images[mode])
            states[mode]=state
            loaded,prefix=launch('manual-load',mode,exe,3,store,'resume.json','load-ui.json')
            check('manual-load: '+mode+' restores at a UI callback boundary',loaded==saved_states[mode])
            check('manual-load: '+mode+' keeps the slot bytes intact',slot(store).read_bytes()==before)
        check('All relocated reader states match',len({json.dumps(s,sort_keys=True) for s in states.values()})==1)
        check('Sources remain unchanged during validation',fingerprint()==report['native_fingerprint'])
        report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally: save_json(output,report)
    return report


if __name__=='__main__': print(f"Game save: {len(verify()['checks'])} checks passed.")
