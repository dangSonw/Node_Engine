"""Four real hosts: mixed clocks, countdown resume, saved paused timers and rollback."""
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
from tools.create_unscaled_timer_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/unscaled-timer'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('unscaled-timer-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/unscaled_timer_demo'; shutil.copytree(project/'assets',package/'assets')
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
        def timer(data,name): return next(t for t in data['timers'] if t['name']==name)
        def close(a,b): return math.isclose(a,b,rel_tol=0,abs_tol=2e-12)
        for mode,exe in modes:
            normal=run('normal',mode,exe,61)
            slow=run('slow',mode,exe,61,[(0,'2',True),(1,'2',False)])
            fast=run('fast',mode,exe,61,[(0,'3',True),(1,'3',False)])
            for label,data,scale in [('normal',normal,1),('slow',slow,.25),('fast',fast,2)]:
                expected=(1+60*scale)/60
                check(mode+': '+label+' independent rotations',data['entities']['player']['rotation'][1]==int(expected/.25)*15 and data['entities']['menu']['rotation'][1]==60)
                check(mode+': '+label+' remaining seconds',close(timer(data,'menu')['remaining'],.25-1/60) and timer(data,'menu')['unscaled'])
            first=run('freeze-first',mode,exe,1,[(0,'0',True)])
            frozen=run('freeze',mode,exe,61,[(0,'0',True),(1,'0',False)])
            check(mode+': freeze suspends only game timer',first['entities']['player']==frozen['entities']['player'] and timer(first,'game')==timer(frozen,'game') and frozen['entities']['menu']['rotation'][1]==60 and frozen['time']==first['time'])
            resumed=run('auto-resume',mode,exe,181,[(0,'R',True),(1,'R',False)])
            check(mode+': unscaled callback automatically resumes frozen game',resumed['clock']['scale']==1 and close(resumed['time'],62/60) and resumed['entities']['menu']['rotation'][1]==180 and all(t['name']!='resume' for t in resumed['timers']))
            paused=run('manual-pause',mode,exe,60,[(0,'P',True),(1,'P',False),(30,'U',True),(31,'U',False)])
            check(mode+': manual pause preserves unscaled timer phase',paused['entities']['menu']['rotation'][1]==30 and paused['entities']['player']['rotation'][1]==60 and close(timer(paused,'menu')['remaining'],.25))
            keys=[(0,'0',True),(1,'0',False),(20,'P',True),(21,'P',False),(25,'S',True),(26,'S',False)]
            saved=run('save',mode,exe,26,keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            checkpoint=json.loads(raw)['checkpoint']['events']
            check(mode+': save contains both clock domains and paused mode',saved['persistence']['success'] and checkpoint['version']==2 and checkpoint['clock']!=checkpoint['unscaled_clock'] and timer(saved,'menu')['paused'])
            continuation=[(40,'U',True),(41,'U',False),(50,'1',True),(51,'1',False)]
            reference=run('reference',mode,exe,75,keys+continuation)
            restored=run('restored',mode,exe,50,[(0,'L',True),(26,'S',False),*continuation],store)
            check(mode+': fresh-process dual-clock restoration is exact',reference==restored and slot(store).read_bytes()==raw)
            for damage in ('negative-clock','missing-clock','invalid-mode','missing-mode'):
                bad=json.loads(raw); events=bad['checkpoint']['events']
                if damage=='negative-clock': events['unscaled_clock']='-1'
                elif damage=='missing-clock': events.pop('unscaled_clock')
                elif damage=='invalid-mode': events['timers'][0]['unscaled']='true'
                else: events['timers'][0].pop('unscaled')
                bad_store=workspace/('bad-'+damage)/mode; path=slot(bad_store); save_json(path,bad); before=path.read_bytes()
                failed=run('bad-'+damage,mode,exe,61,[(0,'L',True)],bad_store)
                check(mode+': malformed '+damage+' preserves live state and bytes',not failed['persistence']['success'] and all(failed[k]==normal[k] for k in ('clock','time','entities','timers')) and path.read_bytes()==before)
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored game renders uninterrupted pose',images['restored']==images['reference'])
        images['freeze'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/unscaled-timer-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Unscaled timer workflow:',len(verify()['checks']),'checks passed.')
