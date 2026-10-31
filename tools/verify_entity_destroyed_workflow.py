"""Four relocated native hosts: pre-deletion reads, callback loot and fresh-process Load."""
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
from editor.core.scene import is_active
from tools.create_entity_destroyed_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/entity-destroyed'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('entity-destroyed-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def keys(*events): return [(frame,key,True) for frame,key in events]+[(frame+1,key,False) for frame,key in events]
    def counts(data): return [data['variables'][k]['value'] for k in ('created','enabled','disabled','owned_disabled','destroyed','loot')]
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/entity_destroyed_demo'; shutil.copytree(project/'assets',package/'assets')
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
            check(mode+': no removal callback at scene construction',counts(initial)==[4,4,0,0,0,0])
            inactive=run('inactive-clone',mode,exe,60,keys((0,'T'),(2,'C'),(4,'X')))
            check(mode+': inactive clone removal reads original name and drops active loot',counts(inactive)==[6,5,3,1,1,1] and inactive['variables']['dead_name']['value']=='Clone' and not inactive['variables']['dead_active']['value'] and 'spawned_1' not in inactive['entities'] and is_active(inactive['scene'],'spawned_2'))
            reset=run('reset',mode,exe,60,keys((0,'N'),(2,'A'),(4,'R'),(6,'R')))
            check(mode+': prefab Reset preserves callback loot and repeated reset is idempotent',counts(reset)==[8,8,0,0,1,1] and reset['variables']['dead_name']['value']=='Temporary attachment' and 'spawned_3' not in reset['entities'] and 'spawned_4' in reset['entities'])
            cascade=run('cascade',mode,exe,60,keys((0,'N'),(2,'A'),(4,'X')))
            check(mode+': root, member and added child notify once despite self-destroy callbacks',counts(cascade)==[9,9,0,0,3,2] and all('spawned_'+str(i) not in cascade['entities'] for i in (1,2,3)) and all('spawned_'+str(i) in cascade['entities'] for i in (4,5)))
            applied=run('applied',mode,exe,60,keys((0,'N'),(2,'A'),(4,'P'),(6,'N'),(8,'X')))
            check(mode+': applied prefab additions participate in later destruction',counts(applied)==[12,12,0,0,3,2] and all('spawned_'+str(i) not in applied['entities'] for i in (4,5,6)))
            setup=keys((0,'N'),(2,'A'),(4,'R'),(6,'S'))
            saved=run('saved',mode,exe,7,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes()
            check(mode+': checkpoint is taken after committed removal and spawned loot',counts(saved)==[8,8,0,0,1,1] and saved['persistence']['success'])
            future=keys((8,'X'),(10,'N'),(12,'T'),(14,'A'),(16,'P'),(18,'R'))
            reference=run('reference',mode,exe,60,setup+future)
            restored=run('restored',mode,exe,54,[(0,'L',True),(7,'S',False)]+future,store)
            check(mode+': fresh-process Load does not emit removals and reproduces future IDs and loot',restored==reference and counts(restored)==[12,12,3,1,3,2] and slot(store).read_bytes()==raw)
            for damage in ('queued-destroyed','subscription','binding'):
                bad=copy.deepcopy(json.loads(raw)); event=bad['checkpoint']['events']
                if damage=='queued-destroyed': event['queue'].append(dict(event=1009,receiver='',sender='',args=['player',True],epoch=0,origin='forged'))
                elif damage=='subscription': next(s for s in event['subscriptions'] if s['event']==1009)['enabled']=False
                else: next(s for s in event['bindings']['events'] if s['event']==1009)['listeners']=['different-node']
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': damaged '+damage+' rejects before callbacks or world replacement',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','animation','frame','time','events')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': interpreted and compiled GPU pixels match',items[0]==items[1])
        check('Restored family and loot match uninterrupted rendering',images['restored']==images['reference'])
        check('Reset and destruction visibly leave callback-spawned loot',images['initial'][0]!=images['reset'][0] and images['initial'][0]!=images['cascade'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/entity-destroyed-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Entity Destroyed workflow:',len(verify()['checks']),'checks passed.')
