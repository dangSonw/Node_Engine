"""Controller replay, saved input/latent payloads and GPU parity in four native hosts."""
import copy,hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_gamepad_demo import GAME,SLOT,replay_trace
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/gamepad'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('gamepad-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    setup,future=replay_trace()
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        names=('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')
        for name in names: shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/gamepad_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview',names[0]),('compiled',names[1]),('view-preview',names[2]),('view-compiled',names[3])]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None,version=3):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=version,events=sorted(events,key=lambda e:e['frame'])))
            args=[str(package/exe),'--frames',str(frames),'--project-root',str(package),'--input-replay',str(package/'keys.json'),
                  '--save-root',str(store),'--output',str(prefix.with_suffix('.json'))]
            if mode.endswith('preview'): args+=['--ir',str(package/'game.ir.json')]
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8'); check(label+': '+mode+' runs',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': GPU capture exists',not image.isNull()); images.setdefault(label,[]).append(image)
            return data
        for mode,exe in modes:
            initial=run('initial',mode,exe,30); v=initial['variables']
            check(mode+': no devices starts neutral',v['controllers']['value']==[] and all((v[k]['value'] if isinstance(v[k],dict) else v[k])==0 for k in ('left_x','left_y','trigger','presses','releases','count')))
            for version in (1,2): check(mode+': legacy replay '+str(version),run('legacy'+str(version),mode,exe,30,version=version)==initial)
            saved=run('saved',mode,exe,3,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes(); data=json.loads(raw)['checkpoint']; v=saved['variables']
            check(mode+': save retains analog, held button and delayed callback',saved['persistence']['success'] and data['input']['version']==5 and
                  data['input']['gamepads']==[dict(controller=7,axes=[1,.15,0,0,.575,0],held=['East'])] and
                  v['presses']['value']==2 and v['releases']['value']==1 and v['delayed_controller']['value']==0)
            after_disconnect=[dict(frame=3,button='S',down=False),dict(frame=4,type='gamepad_connection',controller=7,connected=False),
                dict(frame=5,type='gamepad_connection',controller=12,connected=True)]
            delayed_reference=run('continuation-reference',mode,exe,30,setup+after_disconnect)
            delayed_restored=run('continuation-restored',mode,exe,28,[dict(frame=0,button='L',down=True)]+after_disconnect,store)
            check(mode+': saved callback retains disconnected controller ID',delayed_restored==delayed_reference and
                delayed_restored['variables']['controllers']['value']==[12] and delayed_restored['variables']['delayed_controller']['value']==7 and slot(store).read_bytes()==raw)
            reference=run('reference',mode,exe,30,setup+future)
            restored=run('restored',mode,exe,28,[dict(frame=0,button='L',down=True)]+future,store)
            check(mode+': fresh-process Load continues exactly',restored==reference and slot(store).read_bytes()==raw)
            v=reference['variables']; robot=reference['entities']['player']
            check(mode+': hotplug and synthetic releases keep original callback identity',v['controllers']['value']==[12] and v['count']['value']==1 and
                v['presses']['value']==v['releases']['value']==5 and v['last_controller']['value']==12 and v['delayed_controller']['value']==9)
            check(mode+': analog and South button move/rotate robot',abs(robot['position'][0]-.225)<1e-12 and abs(robot['position'][2]-.15)<1e-12 and robot['rotation']==[0,270,0])
            load=[dict(frame=0,button='L',down=True),dict(frame=1,button='L',down=False)]; missing=run('missing',mode,exe,30,load)
            for damage in ('controller','axis','held','duplicate'):
                bad=copy.deepcopy(json.loads(raw)); pads=bad['checkpoint']['input']['gamepads']
                if damage=='controller': pads[0]['controller']=0
                elif damage=='axis': pads[0]['axes'][4]=-.1
                elif damage=='held': pads[0]['held']=['Unknown']
                else: pads.append(copy.deepcopy(pads[0]))
                path=slot(workspace/('bad-'+damage)/mode); save_json(path,bad); before=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,30,load,path.parent.parent)
                check(mode+': corrupt '+damage+' rejects without replacing game',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==before and
                    all(rejected.get(k)==missing.get(k) for k in ('scene','entities','variables','animation','frame','time','events','continuations')))
        for label,items in states.items(): check(label+': all four hosts match',all(item==items[0] for item in items))
        for label,items in images.items(): check(label+': interpreted/generated pixels match',items[0]==items[1])
        check('Restored rendering equals uninterrupted gameplay',images['restored']==images['reference'])
        check('Saved disconnected-controller continuation renders identically',images['continuation-restored']==images['continuation-reference'])
        check('Gamepad replay visibly moves and rotates robot',images['initial'][0]!=images['reference'][0]); images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during validation',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={n:hashlib.sha256((package/n).read_bytes()).hexdigest() for n in names}; report['passed']=True
        save_json(project/'input-replay.json',dict(version=3,events=setup+future))
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/gamepad-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Gamepad workflow:',len(verify()['checks']),'checks passed.')
