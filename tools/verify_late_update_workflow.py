"""Four real hosts: same-frame camera/animation observations and late-phase saves."""
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
from tools.create_late_update_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/late-update'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('late-update-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/late_update_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in keys]))
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
        def close(a,b): return math.isclose(a,b,rel_tol=0,abs_tol=2e-6)
        def follows(data):
            player=data['entities']['player']['position']; camera=data['entities']['camera']['position']
            return all(close(a,b+offset) for a,b,offset in zip(camera,player,(0,1,7)))
        def observed(data):
            return (data['variables']['after']['value']==data['entities']['player']['position']
                    and close(data['variables']['animation'],data['animation']['player']['time'])
                    and data['variables']['late_frame']==data['frame']-1)
        def world(data): return {key:data[key] for key in ('entities','physics','animation','time')}
        for mode,exe in modes:
            normal=run('normal',mode,exe,61)
            fast=run('fast',mode,exe,61,[(0,'2',True),(1,'2',False)])
            for label,data,scale in [('normal',normal,1),('fast',fast,2)]:
                check(mode+': '+label+' analytic physics displacement',close(data['entities']['player']['position'][0],(1+60*scale)/60))
                check(mode+': '+label+' camera follows final physical pose',follows(data))
                check(mode+': '+label+' late phase reads advanced animation and original frame',observed(data))
                check(mode+': '+label+' update observes earlier pose',close(data['variables']['after']['value'][0]-data['variables']['before']['value'][0],scale/60))
            first=run('freeze-first',mode,exe,1,[(0,'0',True)])
            frozen=run('freeze',mode,exe,61,[(0,'0',True),(1,'0',False)])
            check(mode+': frozen simulation still runs late handlers',world(first)==world(frozen) and frozen['variables']['late_frame']==60 and frozen['variables']['delta']==0 and follows(frozen) and observed(frozen))
            left=run('left',mode,exe,61,[(0,'A',True),(1,'A',False)])
            stopped=run('stopped',mode,exe,61,[(0,'Space',True),(1,'Space',False)])
            check(mode+': input changes movement before late camera tracking',close(left['entities']['player']['position'][0],-122/60) and follows(left) and follows(stopped) and stopped['entities']['player']['position'][0]==0)
            keys=[(20,'S',True),(21,'S',False)]
            saved=run('save',mode,exe,21,keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': late callback saves completed frame',saved['persistence']['success'] and saved['frame']==21 and observed(saved) and follows(saved))
            continuation=[(40,'D',True),(41,'D',False)]
            reference=run('reference',mode,exe,75,keys+continuation)
            restored=run('restored',mode,exe,55,[(0,'L',True),(21,'S',False),*continuation],store)
            check(mode+': fresh-process late save restoration is exact',reference==restored and slot(store).read_bytes()==raw and observed(restored) and follows(restored))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored game renders uninterrupted pose',images['restored']==images['reference'])
        images['reference'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/late-update-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Late Update workflow:',len(verify()['checks']),'checks passed.')
