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
from tools.create_switch_select_demo import GAME,SLOT,POSITIONS
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/switch-select'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('switch-select-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/switch_select_demo'; shutil.copytree(project/'assets',package/'assets')
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
            check(mode+': initial state has no pending route',initial['variables']['visits']['value']==0 and not initial['continuations']['tasks'])
            for label,choice,selected,position in [('left','1','Left',POSITIONS[0]),('center','2','Center',POSITIONS[1]),('right','3','Right',POSITIONS[2]),('fallback','9','Fallback',POSITIONS[3])]:
                result=run(label,mode,exe,60,keys((0,choice),(2,'Space')))
                check(mode+': '+label+' selects its integer and string branches',result['variables']['selected']['value']==selected and result['variables']['visits']['value']==1 and result['entities']['player']['position']==position and result['entities']['player']['rotation']==[0,{'Left':-30,'Center':0,'Right':30,'Fallback':0}[selected],0])
            changed=run('changed-input',mode,exe,60,keys((0,'3'),(2,'Space'),(5,'1')))
            check(mode+': changing selector while suspended preserves chosen route',changed['variables']['mode']['value']==0 and changed['variables']['selected']['value']=='Right' and changed['entities']['player']['position']==POSITIONS[2])
            mirrored=run('mirrored',mode,exe,60,keys((0,'3'),(2,'Space'),(5,'M')))
            check(mode+': Select reads condition on execution and chooses mirrored vector',mirrored['variables']['mirror']['value'] and mirrored['entities']['player']['position']==POSITIONS[0] and mirrored['variables']['selected']['value']=='Right')
            save_keys=keys((0,'3'),(2,'Space'),(8,'S'))
            saved=run('save',mode,exe,9,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            pending=json.loads(raw)['checkpoint']['continuations']; task=pending['tasks'][0]
            check(mode+': checkpoint captures chosen Switch branch inside a function',saved['persistence']['success'] and len(task['frames'])==2 and task['frames'][1]['stack'][1]['kind']=='switch' and task['frames'][1]['stack'][1]['pc']==2 and pending==saved['continuations'])
            future=keys((10,'1'),(11,'M'))
            reference=run('reference',mode,exe,60,save_keys+future)
            restored=run('restored',mode,exe,52,[(0,'L',True),(9,'S',False)]+future,store)
            check(mode+': fresh process reproduces suspended route and lazy Select result',restored==reference and slot(store).read_bytes()==raw and restored['entities']['player']['position']==POSITIONS[0] and restored['variables']['selected']['value']=='Right')
            for damage in ('route','child','kind','parameter','program','owner'):
                bad=copy.deepcopy(json.loads(raw)); state=bad['checkpoint']['continuations']; t=state['tasks'][0]
                if damage=='route': t['frames'][1]['stack'][1]['pc']=999
                elif damage=='child': t['frames'][1]['stack'][1]['pc']=0
                elif damage=='kind': t['frames'][1]['stack'][1]['kind']='flow'
                elif damage=='parameter': t['frames'][1]['parameters'][0]=dict(type='string',value='Right')
                elif damage=='program': state['program']='0'*64
                elif damage=='owner': t['owner']='missing'
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': damaged '+damage+' rejects before live-world replacement',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','continuations','animation','frame','time')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored robot and HUD match uninterrupted rendering',images['restored']==images['reference'])
        check('Switch routes visibly move the robot',images['initial'][0]!=images['left'][0] and images['left'][0]!=images['right'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/switch-select-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Switch/Select workflow:',len(verify()['checks']),'checks passed.')
