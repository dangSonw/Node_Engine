"""Four-host slow motion, frozen worlds, input resume and saved-clock rollback."""
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
from tools.create_time_demo import GAME,SLOT
from PySide6.QtGui import QImage

def verify():
    out=ROOT/'artifacts/validation/time'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('time-workflow-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/time_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in keys]))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                '--save-root',str(store),'--output',str(prefix.with_suffix('.json')),'--audio-output',str(prefix.with_suffix('.wav'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(label+': '+mode+' runs',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return data
        def world(data): return {name:data[name] for name in ('entities','animation','physics','timers','time')}
        def close(a,b): return math.isclose(a,b,rel_tol=0,abs_tol=2e-12)
        for mode,exe in modes:
            normal=run('normal',mode,exe,61)
            slow=run('slow',mode,exe,61,[(0,'1',True),(1,'1',False)])
            fast=run('fast',mode,exe,61,[(0,'3',True),(1,'3',False)])
            for label,data,scale,ticks in [('normal',normal,1,61),('slow',slow,.25,16),('fast',fast,2,121)]:
                expected=(1+60*scale)/60
                check(mode+': '+label+' clock and animation',close(data['time'],expected) and close(data['clock']['real_time'],61/60) and close(data['animation']['player']['time'],expected%2))
                check(mode+': '+label+' fixed physics and timer',data['physics']['ticks']==ticks and data['variables']['fixed_steps']==ticks and data['entities']['timer']['rotation'][1]==int(expected/.25)*15)
            check(mode+': audio remains unscaled',normal['audio']==slow['audio']==fast['audio'])
            # Scale 0 is requested during frame 0, so frame 0 finishes normally.
            frozen_first=run('freeze-first',mode,exe,1,[(0,'0',True)])
            frozen=run('freeze',mode,exe,61,[(0,'0',True),(1,'0',False)])
            check(mode+': zero scale freezes every simulation subsystem',world(frozen)==world(frozen_first) and frozen['variables']['dt']==0 and frozen['clock']['real_time']>frozen_first['clock']['real_time'])
            check(mode+': audio advances while frozen',frozen['audio']==normal['audio'])
            resumed=run('resume',mode,exe,92,[(0,'0',True),(1,'0',False),(30,'2',True),(31,'2',False)])
            check(mode+': input resumes a frozen game',resumed['clock']['scale']==1 and resumed['physics']['ticks']==62 and close(resumed['time'],62/60))
            keys=[(0,'1',True),(1,'1',False),(20,'0',True),(21,'0',False),(25,'S',True),(26,'S',False)]
            saved=run('save',mode,exe,26,keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': save retains frozen scale and both clocks',saved['persistence']['success'] and json.loads(raw)['checkpoint']['clock']['scale']==0)
            continuation=[(40,'2',True),(41,'2',False)]
            reference=run('reference',mode,exe,75,keys+continuation)
            restored=run('restored',mode,exe,50,[(0,'L',True),(26,'S',False),*continuation],store)
            check(mode+': fresh-process load resumes all state exactly',reference==restored and slot(store).read_bytes()==raw)
            for damage in ('scale','real_time','unscaled_dt','missing','extra'):
                bad=json.loads(raw); clock=bad['checkpoint']['clock']
                if damage in ('scale','real_time','unscaled_dt'): clock[damage]=-1
                elif damage=='missing': clock.pop('scale')
                else: clock['extra']=0
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); before=path.read_bytes()
                failed=run('bad-'+damage,mode,exe,61,[(0,'L',True)],bad_store)
                check(mode+': malformed '+damage+' preserves live clocks and world',not failed['persistence']['success'] and failed['clock']==normal['clock'] and world(failed)==world(normal) and path.read_bytes()==before)
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Frozen game renders the same pose',images['freeze-first']==images['freeze'])
        check('Restored game renders the uninterrupted pose',images['restored']==images['reference'])
        for mode,_ in modes:
            check(mode+': audio PCM ignores time scale',all((out/(label+'-'+mode+'.wav')).read_bytes()==(out/('normal-'+mode+'.wav')).read_bytes() for label in ('slow','fast','freeze')))
        images['reference'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/time-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Time workflow:',len(verify()['checks']),'checks passed.')
