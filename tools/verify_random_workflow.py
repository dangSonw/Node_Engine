"""Four-host seeded draws, fresh-process continuation, malformed-save rollback."""
import copy
import hashlib
import json
import math
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
from tools.create_random_demo import GAME,SLOT,ITEMS,DECK
from PySide6.QtGui import QImage


def verify():
    workspace=ROOT/'.cache'/('random-workflow-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'
    package.mkdir(parents=True); out=ROOT/'artifacts/validation/random'; out.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_mixer.dll','SDL3_image.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        project=ROOT/'examples/random_demo'
        shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=v) for f,k,v in keys]))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),
                '--input-replay',str(package/'keys.json'),'--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(label+': '+mode+' runs',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(state)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': capture exists',not image.isNull())
                images.setdefault(label,[]).append(image)
            return state
        draws=[(0,'Space',True),(1,'Space',False),(2,'Space',True),(3,'Space',False)]
        saved_keys=draws+[(5,'S',True),(6,'S',False)]
        for mode,exe in modes:
            first=run('first',mode,exe,2,draws[:2])
            variables=first['variables']
            for field in ('item','loot'):
                index=variables[field+'_index']['value']
                check(mode+': '+field+' value matches captured index',0<=index<len(ITEMS) and variables[field]['value']==ITEMS[index])
            check(mode+': shuffled deck preserves all cards',sorted(variables['deck']['value'])==sorted(DECK))
            direction=variables['direction']['value']; point=first['entities']['player']['position']
            marker=first['entities']['direction']['position']
            check(mode+': random vector respects all authored bounds',-2<=point[0]<1.4 and point[1]==0 and -1<=point[2]<1)
            check(mode+': random direction has unit length',math.isclose(sum(v*v for v in direction),1,rel_tol=0,abs_tol=1e-14))
            check(mode+': marker uses captured direction and origin',all(math.isclose(marker[i],point[i]+(0.8 if i==1 else 0)+1.8*direction[i],rel_tol=0,abs_tol=1e-14) for i in range(3)))
            repeat=run('reset',mode,exe,6,draws+[(4,'R',True),(5,'R',False),(5,'Space',True)])
            check(mode+': reset seed reproduces pose, roll and stream',
                repeat['entities']==first['entities'] and repeat['variables']==first['variables'] and repeat['random']==first['random'])
            saved=run('save',mode,exe,6,saved_keys); store=workspace/'save'/mode
            raw=slot(store).read_bytes(); checkpoint=json.loads(raw)['checkpoint']
            check(mode+': checkpoint persists RNG state',saved['persistence']['success'] and checkpoint['random']==saved['random'])
            reference=run('reference',mode,exe,16,saved_keys+[(8,'Space',True),(9,'Space',False),(12,'Space',True),(13,'Space',False)])
            # Replay is indexed by the restored simulation frame, not process age.
            restored=run('restored',mode,exe,11,[(0,'L',True),(6,'S',False),(8,'Space',True),(9,'Space',False),(12,'Space',True),(13,'Space',False)],store)
            check(mode+': fresh-process continuation matches every state field',restored==reference and slot(store).read_bytes()==raw)
            baseline=run('baseline',mode,exe,4,draws)
            for damage in ('algorithm','seed','state','missing','extra'):
                data=json.loads(raw); random=data['checkpoint']['random']
                if damage=='algorithm': random['algorithm']='unknown'
                elif damage=='seed': random['seed']=2**63
                elif damage=='state': random['state']='g'*16
                elif damage=='missing': data['checkpoint'].pop('random')
                else: random['extra']=1
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,data); before=path.read_bytes()
                failed=run('bad-'+damage,mode,exe,4,[(0,'L',True),*draws],bad_store)
                check(mode+': malformed '+damage+' preserves live state and slot',not failed['persistence']['success'] and
                    failed['random']==baseline['random'] and failed['entities']==baseline['entities'] and
                    failed['variables']==baseline['variables'] and path.read_bytes()==before)
        for label,items in states.items(): check(label+': four hosts match',all(s==items[0] for s in items))
        for label,items in images.items(): check(label+': native/compiled GPU pixels match',items[0]==items[1])
        check('Saved random continuation reproduces GPU pixels',images['reference']==images['restored'])
        check('Random draws move the robot visibly',images['first'][0]!=images['reference'][0])
        images['reference'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}
        report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/random-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Random workflow:',len(verify()['checks']),'checks passed.')
