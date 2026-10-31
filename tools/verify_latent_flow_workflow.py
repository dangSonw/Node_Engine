"""Four native hosts: suspended loop/function restoration and damaged-save rollback."""
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
from tools.create_latent_flow_demo import GAME,SLOT,POSITIONS
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/latent-flow'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('latent-flow-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def keys(*events): return [(frame,key,True) for frame,key in events]+[(frame+1,key,False) for frame,key in events]
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/latent_flow_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,input=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in sorted(input)]))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                  '--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(label+': '+mode+' runs',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return data
        for mode,exe in modes:
            initial=run('initial',mode,exe,60)
            check(mode+': Wait Until leaves other frame systems running',initial['variables']['progress']['value']==0 and len(initial['continuations']['tasks'])==1 and initial['animation'])
            partial=run('partial',mode,exe,45,keys((0,'Space')))
            check(mode+': Delay resumes a function and advances For Each',partial['variables']['progress']['value']==1 and partial['entities']['player']['position']==POSITIONS[0])
            save_keys=keys((0,'Space'),(10,'R'),(15,'R'),(20,'S'))
            saved=run('save',mode,exe,21,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            pending=json.loads(raw)['checkpoint']['continuations']; task=next(t for t in pending['tasks'] if len(t['frames'])==2)
            check(mode+': Save captures loop snapshot, function parameter and retriggered delay',saved['persistence']['success'] and len(pending['tasks'])==2 and
                  task['frames'][1]['parameters']==[dict(type='vec3',value=POSITIONS[0])] and task['frames'][0]['stack'][1]['items']['value']==POSITIONS and pending==saved['continuations'])
            reference=run('reference',mode,exe,140,save_keys)
            restored=run('restored',mode,exe,120,[(0,'L',True),(21,'S',False)],store)
            check(mode+': fresh-process restoration matches every state and preserves save bytes',restored==reference and slot(store).read_bytes()==raw)
            check(mode+': restored tour completes all four stations and both waits',restored['variables']['progress']['value']==4 and restored['entities']['player']['position']==POSITIONS[3] and not restored['continuations']['tasks'])
            for damage in ('program','owner','position','parameter','local','loop','wait','negative','duplicate','serial','field','caller'):
                bad=copy.deepcopy(json.loads(raw)); state=bad['checkpoint']['continuations']; t=next(t for t in state['tasks'] if len(t['frames'])==2)
                if damage=='program': state['program']='0'*64
                elif damage=='owner': t['owner']='missing'
                elif damage=='position': t['frames'][1]['stack'][0]['pc']=999
                elif damage=='parameter': t['frames'][1]['parameters'][0]=dict(type='int',value=1)
                elif damage=='local': t['frames'][0]['locals'].clear()
                elif damage=='loop': t['frames'][0]['stack'][1]['pc']=99
                elif damage=='wait': t['wait']=0
                elif damage=='negative': t['remaining']=-1
                elif damage=='duplicate': state['tasks'].append(copy.deepcopy(t))
                elif damage=='serial': state['next']=1
                elif damage=='field': t['unexpected']=True
                elif damage=='caller': t['frames'][0]['stack'][-1]['pc']=0
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': damaged '+damage+' rejects before live-world replacement',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','continuations','animation','frame','time')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored robot and HUD match uninterrupted rendering',images['restored']==images['reference'])
        check('Delayed tour visibly moves the robot',images['initial'][0]!=images['partial'][0] and images['partial'][0]!=images['reference'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/latent-flow-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Latent flow workflow:',len(verify()['checks']),'checks passed.')
