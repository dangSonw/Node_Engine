"""Four relocated production hosts: pause, input resume, save/load and final pixels."""
import hashlib,json,math,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_world_pause_demo import GAME,SLOT,trace

def verify():
    out=ROOT/'artifacts/validation/world-pause'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('world-pause-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def world(s): return {k:s[k] for k in ('entities','physics','animation','timers','time')}
    def simulation(s): return {k:s[k] for k in ('entities','physics','animation','time')}
    def close(a,b): return math.isclose(a,b,rel_tol=0,abs_tol=2e-12)
    def keys(*events): return [dict(frame=f,button=k,down=d) for f,k,d in events]
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        names=('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')
        for name in names: shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/world_pause_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview',names[0]),('compiled',names[1]),('view-preview',names[2]),('view-compiled',names[3])]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=events))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                '--save-root',str(store),'--output',str(prefix.with_suffix('.json')),'--audio-output',str(prefix.with_suffix('.wav'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            r=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(r.stdout+r.stderr,encoding='utf-8'); check(label+': '+mode+' runs',r.returncode==0)
            if mode.startswith('view'): check(label+': '+mode+' has no graph errors','"node_error"' not in r.stdout)
            s=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(s)
            if mode.startswith('view'):
                picture=QImage(str(prefix.with_suffix('.bmp'))); check(label+': '+mode+' renders',not picture.isNull()); images.setdefault(label,[]).append(picture)
            return s
        for mode,exe in modes:
            normal=run('normal',mode,exe,61)
            first=run('pause-first',mode,exe,1,keys((0,'P',True)))
            frozen=run('paused',mode,exe,61,keys((0,'P',True),(1,'P',False),(20,'P',True),(21,'P',False)))
            check(mode+': pause freezes physics, animation and game time',simulation(first)==simulation(frozen) and frozen['clock']['paused'] and frozen['clock']['scale']==1 and frozen['clock']['dt']==0)
            scaled=lambda s:[t for t in s['timers'] if t['name']=='turn']
            check(mode+': scaled timer freezes while unscaled timer continues',scaled(first)==scaled(frozen) and frozen['variables']['unscaled_ticks']==normal['variables']['unscaled_ticks']>0)
            check(mode+': repeated Pause produces only one callback and UI updates',frozen['variables']['pauses']==1 and frozen['variables']['resumes']==0 and frozen['variables']['world_paused']['value'])
            check(mode+': audio remains unscaled',frozen['audio']==normal['audio'] and (out/('paused-'+mode+'.wav')).read_bytes()==(out/('normal-'+mode+'.wav')).read_bytes())
            resumed=run('resumed',mode,exe,71,trace())
            check(mode+': input resumes exact remaining simulation time',not resumed['clock']['paused'] and close(resumed['time'],41/60) and resumed['physics']['ticks']==41 and resumed['variables']['pauses']==resumed['variables']['resumes']==1)
            scaled_run=run('scale',mode,exe,61,keys((0,'1',True),(1,'1',False),(10,'P',True),(11,'P',False),(20,'3',True),(21,'3',False),(30,'R',True),(31,'R',False)))
            check(mode+': scale changed during pause is retained on resume',scaled_run['clock']['scale']==2 and not scaled_run['clock']['paused'] and close(scaled_run['time'],63.5/60) and scaled_run['physics']['ticks']==63)
            save_keys=keys((10,'P',True),(11,'P',False),(25,'S',True),(26,'S',False)); resume_keys=keys((40,'R',True),(41,'R',False))
            saved=run('save',mode,exe,26,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': checkpoint stores paused state and frame boundary',saved['persistence']['success'] and json.loads(raw)['checkpoint']['clock']['paused'] and json.loads(raw)['checkpoint']['clock']['frame']==26)
            reference=run('reference',mode,exe,75,save_keys+resume_keys)
            restored=run('restored',mode,exe,50,keys((0,'L',True),(26,'S',False))+resume_keys,store)
            check(mode+': fresh-process restore has no synthetic Pause event',restored['logs']==['World resumed'] and restored['variables']['pauses']==restored['variables']['resumes']==1)
            check(mode+': full restored game state equals uninterrupted state',{k:v for k,v in reference.items() if k!='logs'}=={k:v for k,v in restored.items() if k!='logs'} and slot(store).read_bytes()==raw)
            for label,damage in [('bad-flag',lambda c:c.update(paused=1)),('extra-clock',lambda c:c.update(extra=True))]:
                corrupt=json.loads(raw); damage(corrupt['checkpoint']['clock']); bad_store=workspace/label/mode; save_json(slot(bad_store),corrupt); before=slot(bad_store).read_bytes()
                failed=run(label,mode,exe,61,keys((0,'L',True)),bad_store)
                check(mode+': '+label+' rejects without replacing live state or save',not failed['persistence']['success'] and world(failed)==world(normal) and failed['clock']==normal['clock'] and slot(bad_store).read_bytes()==before)
            quit_paused=run('quit-paused',mode,exe,120,keys((0,'P',True),(1,'P',False),(5,'Q',True)))
            check(mode+': paused game still quits through raw input',quit_paused['frame']==6 and quit_paused['clock']['paused'] and close(quit_paused['time'],1/60))
        for label,items in states.items(): check(label+': full four-host state parity',all(s==items[0] for s in items))
        for label,items in images.items(): check(label+': interpreted/generated GPU parity',items[0]==items[1])
        check('Restored and uninterrupted final GPU pixels match',images['restored']==images['reference'])
        check('Paused and resumed robots differ visually',images['paused']!=images['resumed'])
        for label in ('paused','resumed'): images[label][0].save(str(out/(label+'.png')))
        check('Native sources unchanged',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={n:hashlib.sha256((package/n).read_bytes()).hexdigest() for n in names}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/world-pause-workflow-checks.json',report)
    return report

if __name__=='__main__': print('World pause workflow:',len(verify()['checks']),'checks passed.')
