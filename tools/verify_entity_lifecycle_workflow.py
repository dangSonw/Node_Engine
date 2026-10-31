"""Four relocated native hosts: lifecycle counts, hierarchy and fresh-process Load."""
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
from tools.create_entity_lifecycle_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/entity-lifecycle'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('entity-lifecycle-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def keys(*events): return [(frame,key,True) for frame,key in events]+[(frame+1,key,False) for frame,key in events]
    def counts(data): return [data['variables'][k]['value'] for k in ('created','enabled','disabled','owned_disabled')]
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/entity_lifecycle_demo'; shutil.copytree(project/'assets',package/'assets')
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
            check(mode+': initial scene lifecycle occurs once',counts(initial)==[4,4,0,0] and initial['events']['pending']==0)
            inactive=run('inactive',mode,exe,60,keys((0,'T')))
            check(mode+': inherited disable still reaches the disabled robot receiver',counts(inactive)==[4,4,3,1] and not is_active(inactive['scene'],'player') and not is_active(inactive['scene'],'child'))
            spawned=run('spawned',mode,exe,60,keys((0,'T'),(2,'N'),(4,'C')))
            check(mode+': prefab descendants and inherited inactive clone report final state',counts(spawned)==[7,6,3,1] and not is_active(spawned['scene'],'spawned_3') and is_active(spawned['scene'],'spawned_1'))
            setup=keys((0,'T'),(2,'N'),(4,'C'),(6,'X'),(8,'T'),(10,'S'))
            saved=run('saved',mode,exe,11,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes()
            checkpoint=json.loads(raw)['checkpoint']['events']
            check(mode+': saves lifecycle binding state after clone deletion',counts(saved)==[7,9,3,1] and saved['persistence']['success'] and checkpoint['version']==3 and checkpoint['lifecycle_started'] and 'spawned_3' not in saved['entities'])
            future=keys((12,'T'),(14,'N'),(16,'R'),(18,'X'),(20,'T'))
            reference=run('reference',mode,exe,60,setup+future)
            restored=run('restored',mode,exe,50,[(0,'L',True),(11,'S',False)]+future,store)
            check(mode+': fresh-process Load preserves counts, entity IDs and future transitions',restored==reference and counts(restored)==[9,14,6,2] and slot(store).read_bytes()==raw)
            for damage in ('version','started','inactive','subscription','binding'):
                bad=copy.deepcopy(json.loads(raw)); event=bad['checkpoint']['events']
                if damage=='version': event['version']=2; del event['lifecycle_started']
                elif damage=='started': event['lifecycle_started']='true'
                elif damage=='inactive': next(s for s in event['subscriptions'] if s['receiver']=='player')['active']=False
                elif damage=='subscription': next(s for s in event['subscriptions'] if s['receiver']=='player')['enabled']=False
                elif damage=='binding': event['bindings']['types'][0]['types']=['entity','string']
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); bad_bytes=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,keys((0,'L')),bad_store)
                check(mode+': damaged '+damage+' rejects without replacing live scene',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==bad_bytes and
                      all(rejected[k]==initial[k] for k in ('scene','entities','variables','animation','frame','time','events')))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': interpreted and compiled GPU pixels match',items[0]==items[1])
        check('Restored robot family and HUD match uninterrupted rendering',images['restored']==images['reference'])
        check('Activity and spawning visibly change the scene',images['initial'][0]!=images['inactive'][0] and images['inactive'][0]!=images['spawned'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/entity-lifecycle-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Entity lifecycle workflow:',len(verify()['checks']),'checks passed.')
