"""Four real hosts: route cycles, shared random stream and checkpoint continuation."""
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
from tools.create_multi_gate_demo import GAME,SLOT,POSITIONS
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/multi-gate'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('multi-gate-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/multi_gate_demo'; shutil.copytree(project/'assets',package/'assets')
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
        def history(data): return list(map(int,data['variables']['history']['value'].split()))
        def route(data): return data['flow']['states'][0]['multi']
        def pose(data):
            selected=data['variables']['selected']['value']; entity=data['entities']['player']
            return entity['position']==POSITIONS[selected] and entity['rotation']==[0,selected*90,0]
        for mode,exe in modes:
            initial=run('initial',mode,exe,60)
            check(mode+': no route executes before entry',not initial['flow']['states'] and not history(initial) and initial['variables']['selected']['value']==-1)
            sequential_keys=keys(*[(i*2,'Space') for i in range(5)])
            sequential=run('sequential',mode,exe,60,sequential_keys)
            check(mode+': sequential tour visits each route once and then blocks',history(sequential)==[0,1,2,3] and pose(sequential) and route(sequential)==dict(branches=4,used=15,next=0) and sequential['random']==initial['random'])
            looped=run('looped',mode,exe,60,sequential_keys+keys((20,'T'),(22,'Space'),(24,'Space')))
            check(mode+': enabling Loop after exhaustion starts a new cycle',history(looped)==[0,1,2,3,0,1] and pose(looped) and route(looped)['used']==3)
            random_keys=keys((0,'M'),*[(2+i*2,'Space') for i in range(5)])
            random=run('random',mode,exe,60,random_keys)
            check(mode+': random tour uses each route exactly once',sorted(history(random))==[0,1,2,3] and pose(random) and route(random)['used']==15 and random['random']!=initial['random'])
            reset=run('reset',mode,exe,60,random_keys+keys((20,'R'),*[(30+i*2,'Space') for i in range(4)]))
            check(mode+': Reset plus seed repeats the complete random tour',history(reset)==history(random) and reset['flow']==random['flow'] and reset['random']==random['random'] and pose(reset))
            switched=run('switched',mode,exe,60,keys((0,'Space'),(2,'Space'),(4,'M'),(6,'Space'),(8,'Space')))
            check(mode+': switching Random preserves routes already used',history(switched)[:2]==[0,1] and sorted(history(switched))==[0,1,2,3] and pose(switched))
            save_keys=keys((0,'M'),(2,'Space'),(4,'Space'),(20,'S'))
            saved=run('save',mode,exe,21,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            checkpoint=json.loads(raw)['checkpoint']
            check(mode+': Save captures partial cycle and shared random stream',saved['persistence']['success'] and len(history(saved))==2 and checkpoint['flow']==saved['flow'] and checkpoint['random']==saved['random'])
            future=keys((30,'Space'),(32,'Space'),(34,'Space'),(40,'T'),(42,'Space'),(44,'Space'),(46,'Space'),(48,'Space'))
            reference=run('reference',mode,exe,75,save_keys+future)
            restored=run('restored',mode,exe,55,[(0,'L',True),(21,'S',False)]+future,store)
            check(mode+': fresh-process future cycles match all state and preserve saved bytes',reference==restored and slot(store).read_bytes()==raw and pose(restored) and len(history(restored))==8 and sorted(history(restored)[:4])==sorted(history(restored)[4:])==[0,1,2,3])
            for damage in ('binding','owner','bits','cursor','empty','flag','fields','duplicate'):
                bad=copy.deepcopy(json.loads(raw)); state=bad['checkpoint']['flow']; entry=state['states'][0]
                if damage=='binding': state['bindings']['route']=2007
                elif damage=='owner': entry['owner']='missing'
                elif damage=='bits': entry['multi']['used']=16
                elif damage=='cursor':
                    unused=next(i for i in range(4) if not entry['multi']['used']&(1<<i)); entry['multi']['next']=(unused+1)%4
                elif damage=='empty': entry['multi'].update(used=0,next=0)
                elif damage=='flag': entry['flag']=True
                elif damage=='fields': entry['multi']['extra']=0
                elif damage=='duplicate': state['states'].append(copy.deepcopy(entry))
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': invalid '+damage+' preserves live world and saved bytes',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','flow','animation','random','frame','time')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored route and HUD render the uninterrupted state',images['restored']==images['reference'])
        check('Routes visibly move the robot',images['initial'][0]!=images['sequential'][0] and images['looped'][0]!=images['sequential'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/multi-gate-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Multi Gate workflow:',len(verify()['checks']),'checks passed.')
