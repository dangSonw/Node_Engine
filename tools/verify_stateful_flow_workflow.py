"""Four real hosts: persistent gates, relocated GPU output and saved continuation."""
import copy
import hashlib
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
from tools.create_stateful_flow_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/stateful-flow'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('stateful-flow-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/stateful_flow_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in sorted(keys)]))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                '--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(label+': '+mode+' runs',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return data
        def keys(*events): return [(frame,key,True) for frame,key in events]+[(frame+1,key,False) for frame,key in events]
        def flow(data): return {s['node']:s for s in data['flow']['states']}
        def pose(data,position,scale=1,rotation=0):
            entity=data['entities']['player']
            return entity['position']==position and entity['scale']==[scale]*3 and abs(entity['rotation'][1]-rotation)<1e-8
        for mode,exe in modes:
            initial=run('initial',mode,exe,60)
            check(mode+': initially closed gate blocks Update',pose(initial,[0,0,0]) and not flow(initial)['gate']['flag'])
            limited_keys=keys((0,'O'),(2,'O'),(0,'N'),(2,'N'),(4,'N'),(6,'N'))
            limited=run('limited',mode,exe,60,limited_keys)
            check(mode+': Do Once and Do N stop at their exact limits',pose(limited,[1.5,.5,0]) and limited['variables']['used']['value']==3 and flow(limited)['once']['count']==1 and flow(limited)['quota']['count']==3)
            flipped=run('flipped',mode,exe,60,keys((0,'F'),(2,'F'),(4,'F')))
            check(mode+': Flip Flop alternates to A with captured Is A',pose(flipped,[0,0,0],1.25) and flipped['variables']['is_a']['value'] and not flow(flipped)['flip']['flag'])
            turned=run('turned',mode,exe,60,keys((0,'G'),(30,'G')))
            check(mode+': Gate admits exactly 30 rotation updates',pose(turned,[0,0,0],rotation=45) and not flow(turned)['gate']['flag'])
            reset_keys=limited_keys+keys((0,'F'),(0,'G'),(20,'R'),(30,'O'),(30,'N'),(30,'F'))
            reset=run('reset',mode,exe,60,reset_keys)
            check(mode+': Reset reopens counters and chooses A without opening Gate',pose(reset,[.5,.5,0],1.25) and flow(reset)['quota']['count']==1 and not flow(reset)['gate']['flag'])
            save_keys=keys((0,'O'),(0,'N'),(0,'F'),(0,'G'),(20,'S'))
            saved=run('save',mode,exe,21,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': Save contains all four owner states',saved['persistence']['success'] and len(flow(saved))==4 and json.loads(raw)['checkpoint']['flow']==saved['flow'])
            future=keys((30,'N'),(32,'F'),(40,'G'),(42,'O'),(44,'N'),(46,'F'),(48,'N'))
            reference=run('reference',mode,exe,75,save_keys+future)
            restored=run('restored',mode,exe,55,[(0,'L',True),(21,'S',False)]+future,store)
            check(mode+': fresh-process continuation matches entire state and saved bytes',reference==restored and slot(store).read_bytes()==raw and pose(restored,[1.5,.5,0],1.25,60))
            for damage in ('binding','owner','count'):
                bad=copy.deepcopy(json.loads(raw)); state=bad['checkpoint']['flow']
                if damage=='binding': state['bindings']['once']=2008
                elif damage=='owner': state['states'][0]['owner']='missing'
                else: state['states'][0]['count']=-1
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': invalid '+damage+' rejects without changing live world or file',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','flow','animation','frame','time')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored gates render the uninterrupted pose',images['restored']==images['reference'])
        check('Gate actions visibly affect the robot',images['initial'][0]!=images['limited'][0] and images['flipped'][0]!=images['initial'][0] and images['turned'][0]!=images['initial'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/stateful-flow-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Stateful flow workflow:',len(verify()['checks']),'checks passed.')
