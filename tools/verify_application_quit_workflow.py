"""Actual four-host quit, exit checkpoint restoration and final GPU capture."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_application_quit_demo import GAME,SLOT,trace


def verify():
    out=ROOT/'artifacts/validation/application-quit'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('application-quit-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def value(s,k):
        v=s['variables'][k]; return v['value'] if isinstance(v,dict) else v
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        names=('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')
        for name in names: shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/application_quit_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview',names[0]),('compiled',names[1]),('view-preview',names[2]),('view-compiled',names[3])]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=3,events=events))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                '--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8'); check(label+': '+mode+' exits successfully',result.returncode==0)
            if mode.startswith('view'):
                messages=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                finished=[m for m in messages if m.get('event')=='application_quit']
                check(label+': '+mode+' reports exactly one completed shutdown',len(finished)==1 and finished[0]['success'] and finished[0]['started'])
                check(label+': '+mode+' has no node errors',not any(m.get('event')=='node_error' for m in messages))
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(state)
            if mode.startswith('view'):
                picture=QImage(str(prefix.with_suffix('.bmp'))); check(label+': '+mode+' final GPU capture exists',not picture.isNull()); images.setdefault(label,[]).append(picture)
            return state
        for mode,exe in modes:
            state=run('requested',mode,exe,120,trace()); store=workspace/'requested'/mode
            check(mode+': Quit node finishes frame 13 instead of 120',state['frame']==13 and value(state,'after_request'))
            check(mode+': callback runs once before final Save Completed',value(state,'quit_count')==1 and value(state,'quit_frame')==13 and
                value(state,'save_completed') and state['logs']==['On Application Quit','save_completed'])
            check(mode+': movement and action finish before shutdown',abs(state['entities']['player']['position'][0]-.4)<1e-12 and value(state,'turns')==1)
            raw=slot(store).read_bytes(); saved=json.loads(raw)['checkpoint']
            check(mode+': exit checkpoint records completed frame and quit callback',saved['clock']['frame']==13 and saved['scene']['variables']['quit_count']['value']==1)
            check(mode+': host shutdown intent is absent from saved state',not any('quit' in k for k in saved) and not any('quit' in k for k in saved['clock']))
            natural=run('limited',mode,exe,13,trace()[:-1])
            check(mode+': frame-limit exit also dispatches quit once',natural['frame']==13 and value(natural,'quit_count')==1 and not value(natural,'after_request'))
            menu=run('menu',mode,exe,120,[dict(frame=0,button='M',down=True),dict(frame=1,button='M',down=False),dict(frame=2,button='Q',down=True)])
            check(mode+': raw quit works while gameplay context is disabled',menu['frame']==3 and not value(menu,'game_enabled') and value(menu,'quit_count')==1)
            for label,events,expected_frame in [
                ('resumed',[dict(frame=0,button='L',down=True),dict(frame=13,button='Q',down=False),dict(frame=14,button='Space',down=True),
                    dict(frame=15,button='Space',down=False),dict(frame=16,button='Q',down=True)],17),
                ('load-and-quit',[dict(frame=0,button='L',down=True),dict(frame=0,button='Q',down=True)],13)]:
                target=workspace/label/mode; slot(target).parent.mkdir(parents=True); slot(target).write_bytes(raw)
                restored=run(label,mode,exe,120,events,target)
                check(mode+': '+label+' retains host intent and dispatches once',restored['frame']==expected_frame and value(restored,'quit_count')==2 and value(restored,'load_completed'))
                check(mode+': '+label+' writes the new exit checkpoint',json.loads(slot(target).read_bytes())['checkpoint']['clock']['frame']==expected_frame and slot(target).read_bytes()!=raw)
                if label=='resumed': check(mode+': restored game continues actions and latent work before later quit',value(restored,'turns')==2 and value(restored,'settled')==1)
            check(mode+': independent restore leaves original exit save untouched',slot(store).read_bytes()==raw)
            blocked=workspace/('invalid-storage-'+mode); blocked.write_text('not a directory',encoding='utf-8')
            failed=run('save-failed',mode,exe,120,[dict(frame=0,button='Q',down=True)],blocked)
            check(mode+': unavailable save storage reports failure without hanging shutdown',failed['frame']==1 and value(failed,'quit_count')==1 and not value(failed,'save_completed') and not failed['persistence']['success'])
        for label,items in states.items(): check(label+': four-host state parity',all(s==items[0] for s in items))
        for label,items in images.items(): check(label+': interpreted/generated final GPU parity',items[0]==items[1])
        check('Successful exit differs visibly from save failure',images['requested'][0]!=images['save-failed'][0])
        images['requested'][0].save(str(out/'robot.png')); images['menu'][0].save(str(out/'menu.png'))
        images['resumed'][0].save(str(out/'resumed.png')); images['save-failed'][0].save(str(out/'save-failed.png'))
        # The interpreted SDL host must also exit with useful diagnostics on a bad quit graph.
        # Compile the fault through the real compiler so expression/statement schemas stay authoritative.
        from editor.core.builder import GraphBuilder
        b=GraphBuilder(); b.add('quit','On Application Quit'); b.add('quit_failure','Assert',Condition=False,Message='quit failure'); b.connect('quit','Out','quit_failure','In')
        bad=b.compile(); save_json(package/'bad.ir.json',bad)
        result=subprocess.run([str(package/'node_view.exe'),'--ir',str(package/'bad.ir.json'),'--frames','1'],cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        (out/'quit-failure.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        messages=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        check('SDL quit callback failure exits with its originating node',result.returncode!=0 and any(m.get('event')=='node_error' and m.get('node')=='quit_failure' for m in messages))
        check('Failed callback is not retried',sum(m.get('event')=='application_quit' for m in messages)==1 and not next(m for m in messages if m.get('event')=='application_quit')['success'])
        check('Native sources unchanged',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={n:hashlib.sha256((package/n).read_bytes()).hexdigest() for n in names}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/application-quit-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Application quit workflow:',len(verify()['checks']),'checks passed.')
