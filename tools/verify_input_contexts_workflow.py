"""Context gating, suppressed held actions and saved continuation in four hosts."""
import copy,hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_input_contexts_demo import GAME,SLOT,replay_trace

def verify():
    out=ROOT/'artifacts/validation/input-contexts'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('input-contexts-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/input_contexts_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
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
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8'); check(label+': '+mode+' runs',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(state)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': GPU capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return state
        for mode,exe in modes:
            initial=run('initial',mode,exe,30)
            check(mode+': initial gameplay context is enabled and neutral',value(initial,'game_enabled') and not value(initial,'turn_held') and value(initial,'horizontal')==0)
            for cut,label in [(2,'disabled'),(4,'suppressed')]:
                setup,future=replay_trace(cut); saved=run(label+'-save',mode,exe,cut,setup); store=workspace/(label+'-save')/mode
                raw=slot(store).read_bytes(); data=json.loads(raw)['checkpoint']['input']
                check(mode+': '+label+' context state is saved',saved['persistence']['success'] and data['version']==5 and
                    data['enabled_contexts']==([] if cut==2 else ['gameplay']) and data['suppressed_actions']==([] if cut==2 else ['turn']) and not value(saved,'turn_held'))
                prefix='reference' if cut==2 else 'rearm-reference'
                reference=run(prefix,mode,exe,30,setup+future)
                restored=run(label+'-restored',mode,exe,31-cut,[dict(frame=0,button='L',down=True)]+future,store)
                check(mode+': '+label+' fresh Load continues exactly',restored==reference and slot(store).read_bytes()==raw)
                check(mode+': context transitions and rearming preserve exact action counts',value(reference,'turns')==value(reference,'action_releases')==3 and
                    value(reference,'game_enabled') and value(reference,'settled')==1 and value(reference,'delayed_action')=='turn')
                robot=reference['entities']['player']; check(mode+': only enabled frames move the robot',abs(robot['position'][0]-.6)<1e-12 and robot['rotation']==[0,270,0])
            load=[dict(frame=0,button='L',down=True),dict(frame=1,button='L',down=False)]; missing=run('missing',mode,exe,30,load)
            for damage in ('unknown','duplicate','suppression','press','definition'):
                bad=copy.deepcopy(json.loads(raw)); data=bad['checkpoint']['input']
                if damage=='unknown': data['enabled_contexts']=['missing']
                elif damage=='duplicate': data['enabled_contexts']=['gameplay','gameplay']
                elif damage=='suppression': data['suppressed_actions']=['missing']
                elif damage=='press': data['actions_pressed']=['turn']
                else: data['bindings']['contexts']['gameplay']['enabled']=False
                path=slot(workspace/('bad-'+damage)/mode); save_json(path,bad); before=path.read_bytes()
                state=run('bad-'+damage,mode,exe,30,load,path.parent.parent)
                check(mode+': invalid '+damage+' checkpoint leaves live game intact',not state['persistence']['success'] and state['persistence']['error'] and before==path.read_bytes() and
                    all(state[k]==missing[k] for k in ('scene','entities','variables','frame','time','events','continuations','animation')))
        for label,items in states.items(): check(label+': four-host state parity',all(s==items[0] for s in items))
        for label,items in images.items(): check(label+': interpreted/generated GPU parity',items[0]==items[1])
        check('Disabled save renders a visible menu state',images['disabled-save'][0]!=images['suppressed-save'][0])
        check('Both restored renders match uninterrupted state',images['disabled-restored']==images['reference'] and images['suppressed-restored']==images['rearm-reference'])
        images['reference'][0].save(str(out/'robot.png')); images['disabled-save'][0].save(str(out/'menu.png'))
        check('Native sources unchanged',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={n:hashlib.sha256((package/n).read_bytes()).hexdigest() for n in names}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/input-contexts-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Input contexts workflow:',len(verify()['checks']),'checks passed.')
