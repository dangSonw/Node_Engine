"""Exercise result handlers in all four hosts with real slots and GPU output."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_game_save_events_demo import GAME


def verify():
    artifacts=ROOT/'artifacts/validation/save-events'; artifacts.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('save-events-'+uuid.uuid4().hex[:10])
    package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/'slot-736c6f742d31.json'
    try:
        check('Native runtime is current',current(ROOT/'build/node_view.exe'))
        for file in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/file,package/file)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        shutil.copytree(ROOT/'examples/game_save_events_demo/assets',package/'assets')
        shutil.copy2(ROOT/'examples/game_save_events_demo/generated/game.ir.json',package/'game.ir.json')
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),
               ('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        states={}; images={}
        def launch(phase,mode,exe,store,frames,keys=(),click=False):
            prefix=artifacts/(phase+'-'+mode)
            replay=[dict(frame=frame,button=key,down=down) for frame,key,down in keys]
            # Clearing replay input disables stray desktop input in graphical runs.
            ui=[dict(frame=0,type='clear')]
            if click: ui += [dict(frame=2,type='move',x=75,y=140),dict(frame=2,type='button',button=0,down=True),
                            dict(frame=2,type='button',button=0,down=False)]
            save_json(package/'keys.json',dict(version=1,events=replay)); save_json(package/'ui.json',dict(version=1,events=ui))
            args=[str(package/exe),'--frames',str(frames),'--save-root',str(store),'--output',str(prefix.with_suffix('.json')),
                  '--input-replay','keys.json','--ui-replay','ui.json']
            if 'preview' in mode: args+=['--ir','game.ir.json']
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,'utf-8')
            check(phase+': '+mode+' exits successfully',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            states.setdefault(phase,[]).append(state)
            if mode.startswith('view'): images.setdefault(phase,[]).append(prefix.with_suffix('.bmp').read_bytes())
            return state
        for mode,exe in modes:
            store=workspace/'saves'/mode
            saved=launch('save',mode,exe,store,4,[(3,'S',True)])
            raw=slot(store).read_bytes(); checkpoint=json.loads(raw)['checkpoint']
            check(mode+': save completion follows the captured frame',saved['frame']==4 and saved['variables']['score']==4 and
                  saved['logs']==['Saved: slot-1'] and saved['persistence']['success'] and checkpoint['clock']['frame']==4 and
                  checkpoint['events']['queue']==[])
            loaded=launch('load',mode,exe,store,1)
            check(mode+': load fires in the restored world without OnStart replay',loaded['frame']==5 and
                  loaded['variables']['score']==5 and loaded['variables']['ticks']==4 and loaded['logs']==['Loaded: slot-1'] and
                  loaded['ui']['widgets']['hud']['elements']['status']['text']=='Loaded: slot-1' and slot(store).read_bytes()==raw)
            manual=launch('manual-load',mode,exe,store,3,[(6,'L',True)])
            check(mode+': restored listeners survive another load',manual['frame']==4 and manual['logs']==['Loaded: slot-1','Loaded: slot-1'] and
                  manual['variables']==saved['variables'] and slot(store).read_bytes()==raw)
            for phase,key,prefix in [('save-failed','F','Save failed: '),('load-failed','M','Load failed: ')]:
                result=launch(phase,mode,exe,workspace/phase/mode,1,[(0,key,True)])
                check(mode+': '+phase+' supplies the exact error and continues simulation',result['frame']==1 and result['variables']['score']==1 and
                      not result['persistence']['success'] and result['logs']==[prefix+result['persistence']['error']])
            retry_store=workspace/'retry'/mode
            retry=launch('retry',mode,exe,retry_store,2,[(0,'F',True),(1,'S',True)])
            check(mode+': a failure permits the next request',retry['persistence']['success'] and retry['logs'][0].startswith('Save failed: ') and
                  retry['logs'][1:]==['Saved: slot-1'] and json.loads(slot(retry_store).read_bytes())['checkpoint']['clock']['frame']==2)
            ui_saved=launch('ui-save',mode,exe,workspace/'ui-save'/mode,3,click=True)
            check(mode+': UI request emits a result after its callback returns',ui_saved['frame']==3 and ui_saved['logs']==['Saved: slot-1'] and
                  ui_saved['ui']['widgets']['hud']['elements']['status']['text']=='Saved: slot-1')
            bad=json.loads(raw)
            bad['checkpoint']['events']['subscriptions'][0]['enabled']=False
            damaged=json.dumps(bad).encode(); slot(store).write_bytes(damaged)
            failed=launch('tampered-bindings',mode,exe,store,1)
            check(mode+': malformed builtin subscription is rejected before commit',failed['frame']==1 and failed['variables']['score']==1 and
                  not failed['persistence']['success'] and failed['logs']==['Load failed: '+failed['persistence']['error']] and
                  'persistence subscription' in failed['persistence']['error'] and slot(store).read_bytes()==damaged)
        for phase,results in states.items():
            check(phase+': all four hosts have identical state',len({json.dumps(s,sort_keys=True) for s in results})==1)
            check(phase+': generated and interpreted GPU images are identical',len(set(images[phase]))==1)
        check('Sources remained unchanged',fingerprint()==report['native_fingerprint'])
        report['passed']=True
    finally: save_json(artifacts.parent/'save-events-checks.json',report)
    return report


if __name__=='__main__': print(f"Save events: {len(verify()['checks'])} checks passed.")
