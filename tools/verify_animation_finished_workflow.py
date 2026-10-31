"""Four actual hosts: completion transitions, filters and fresh-process saves."""
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
from tools.create_animation_finished_demo import GAME,SLOT,FINISHED_SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/animation-finished'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('animation-finished-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store,name=SLOT): return store/GAME/('slot-'+name.encode().hex()+'.json')
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/animation_finished_demo'; shutil.copytree(project/'assets',package/'assets')
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
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(label+': '+mode+' runs',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return data
        for mode,exe in modes:
            before=run('before',mode,exe,60)
            check(mode+': Wave remains pending halfway through',before['variables']['completed']==0 and before['animation']['player']['clip']=='Wave')
            after=run('after',mode,exe,150)
            check(mode+': callback switches only completed robot to Idle',after['animation']['player']['clip']=='Idle' and
                after['animation']['walker']['clip']=='Walk' and after['variables']['completed']==after['variables']['late_completed']==1 and
                after['variables']['last_clip']['value']=='Wave' and after['variables']['last_entity']['value']=='player')
            completed_store=workspace/'after'/mode; completed_raw=slot(completed_store,FINISHED_SLOT).read_bytes()
            completed=json.loads(completed_raw)['checkpoint']; completed_frame=completed['clock']['frame']
            check(mode+': completion saves after Late Update in the same frame',after['persistence']['success'] and
                completed['animation']['player']['clip']=='Idle' and completed['animation']['player']['time']==0 and
                completed['scene']['variables']['completed']==completed['scene']['variables']['late_completed']==1)
            resumed=run('completion-load',mode,exe,150-completed_frame+1,[(0,'K',True),(completed_frame,'K',False)],completed_store)
            # Loading from another slot changes only the operation result's slot name.
            expected=dict(after); expected['persistence']=resumed['persistence']
            check(mode+': completed save resumes once without duplicate callback',resumed==expected and resumed['persistence']['success'] and
                resumed['variables']['completed']==1 and slot(completed_store,FINISHED_SLOT).read_bytes()==completed_raw)
            paused=run('paused',mode,exe,150,[(30,'P',True),(31,'P',False)])
            check(mode+': Pause suppresses completion',paused['animation']['player']['paused'] and paused['variables']['completed']==0)
            continued=run('resumed',mode,exe,200,[(30,'P',True),(31,'P',False),(60,'R',True),(61,'R',False)])
            check(mode+': Resume finishes exactly once',continued['variables']['completed']==1 and continued['animation']['player']['clip']=='Idle')
            reverse=run('reverse',mode,exe,150,[(0,'B',True),(1,'B',False)])
            check(mode+': reverse endpoint emits completion',reverse['variables']['completed']==1 and reverse['animation']['player']['clip']=='Idle')
            frozen=run('frozen',mode,exe,150,[(0,'0',True),(1,'0',False)])
            check(mode+': frozen clips do not complete',frozen['variables']['completed']==0 and frozen['animation']['player']['clip']=='Wave')
            stopped=run('stopped',mode,exe,150,[(0,'X',True),(1,'X',False)])
            check(mode+': Stop does not emit completion',stopped['variables']['completed']==0 and 'player' not in stopped['animation'])
            keys=[(40,'S',True),(41,'S',False)]
            saved=run('save',mode,exe,41,keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': save keeps in-progress clip and completion bindings',saved['persistence']['success'] and saved['variables']['completed']==0 and
                any(x['event']==13014 for x in json.loads(raw)['checkpoint']['events']['subscriptions']))
            reference=run('reference',mode,exe,150,keys)
            restored=run('restored',mode,exe,110,[(0,'L',True),(41,'S',False)],store)
            check(mode+': fresh-process mid-clip restoration matches entire state',reference==restored and slot(store).read_bytes()==raw)
            bad=json.loads(raw); bad['checkpoint']['events']['bindings']['events'][0]['listeners'][0]['filter']='Walk'
            bad_store=workspace/'bad-filter'/mode; file=slot(bad_store); save_json(file,bad); bad_bytes=file.read_bytes()
            rejected=run('bad-filter',mode,exe,60,[(0,'L',True),(1,'L',False)],bad_store)
            check(mode+': changed completion filter rolls back load',not rejected['persistence']['success'] and
                rejected['animation']==before['animation'] and rejected['variables']==before['variables'] and file.read_bytes()==bad_bytes)
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored animation transitions render the uninterrupted poses',images['restored']==images['reference'] and images['completion-load']==images['after'])
        check('Wave and completed Idle visibly differ',images['before'][0]!=images['after'][0])
        images['after'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/animation-finished-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Animation finished workflow:',len(verify()['checks']),'checks passed.')
