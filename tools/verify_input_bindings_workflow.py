"""Mixed device mappings through all four native hosts and fresh-process saves."""
import copy,hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_input_bindings_demo import GAME,SLOT,bindings,replay_trace

def verify():
    out=ROOT/'artifacts/validation/input-bindings'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('input-bindings-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(name,okay):
        if not okay: raise AssertionError(name)
        report['checks'].append(name); print('PASS '+name,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def value(s,k):
        v=s['variables'][k]; return v['value'] if isinstance(v,dict) else v
    setup,future=replay_trace()
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        names=('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')
        for name in names: shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/input_bindings_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview',names[0]),('compiled',names[1]),('view-preview',names[2]),('view-compiled',names[3])]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None,version=3):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'input.json',dict(version=version,events=events))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'input.json'),
                '--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8'); check(label+': '+mode+' runs',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(state)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': image exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return state
        for mode,exe in modes:
            initial=run('initial',mode,exe,30)
            check(mode+': no devices reads neutral',all(value(initial,k)==0 for k in ('horizontal','vertical','trigger','turns','action_releases')))
            keys=[dict(frame=0,button='D',down=True),dict(frame=0,button='Space',down=True),dict(frame=5,release_all=True)]
            legacy=run('legacy',mode,exe,30,keys,version=1)
            check(mode+': old keyboard replay drives new mixed bindings',value(legacy,'turns')==value(legacy,'action_releases')==1 and abs(legacy['entities']['player']['position'][0]-.25)<1e-12)
            saved=run('saved',mode,exe,3,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes(); checkpoint=json.loads(raw)['checkpoint']
            check(mode+': whole-game save retains version-2 bindings and held action',saved['persistence']['success'] and checkpoint['input']['bindings']==bindings() and
                value(saved,'turn_held') and value(saved,'turns')==1 and value(saved,'action_releases')==0 and abs(value(saved,'horizontal')+.875)<1e-12)
            reference=run('reference',mode,exe,30,setup+future)
            restored=run('restored',mode,exe,28,[dict(frame=0,button='L',down=True)]+future,store)
            check(mode+': fresh-process restore continues exactly',restored==reference and slot(store).read_bytes()==raw)
            check(mode+': alternative handoffs and unplug deliver exact actions',value(reference,'turns')==value(reference,'action_releases')==4 and
                value(reference,'settled')==1 and value(reference,'delayed_action')=='turn' and not value(reference,'turn_held'))
            pose=reference['entities']['player']; check(mode+': mixed analog/digital movement and turns are correct',
                abs(pose['position'][0]-.35)<1e-12 and abs(pose['position'][2]-.25)<1e-12 and pose['rotation']==[0,360,0])
            load=[dict(frame=0,button='L',down=True),dict(frame=1,button='L',down=False)]; missing=run('missing',mode,exe,30,load)
            for damage in ('controller','dead-zone','duplicate','identity'):
                bad=copy.deepcopy(json.loads(raw)); b=bad['checkpoint']['input']['bindings']
                if damage=='controller': b['actions']['turn'][-1]['controller']=True
                elif damage=='dead-zone': b['axes']['horizontal']['gamepads'][0]['dead_zone']=1
                elif damage=='duplicate': b['axes']['horizontal']['gamepads']*=2
                else: b['axes']['horizontal']['gamepads'][0]['invert']=True
                path=slot(workspace/('bad-'+damage)/mode); save_json(path,bad); before=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,30,load,path.parent.parent)
                check(mode+': malformed/incompatible '+damage+' save rolls back',not rejected['persistence']['success'] and rejected['persistence']['error'] and path.read_bytes()==before and
                    all(rejected[k]==missing[k] for k in ('scene','entities','variables','frame','time','events','continuations','animation')))
        for name,items in states.items(): check(name+': all four host states match',all(item==items[0] for item in items))
        for name,items in images.items(): check(name+': interpreted/generated pixels match',items[0]==items[1])
        check('Fresh Load restores identical GPU output',images['reference']==images['restored'])
        check('Mapped controls visibly change the robot',images['initial'][0]!=images['reference'][0]); images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={n:hashlib.sha256((package/n).read_bytes()).hexdigest() for n in names}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/input-bindings-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Input bindings workflow:',len(verify()['checks']),'checks passed.')
