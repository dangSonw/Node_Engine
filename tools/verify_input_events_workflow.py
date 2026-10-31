"""Four native hosts: ordered input callbacks and saved suspended event payloads."""
import copy,hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_input_events_demo import GAME,SLOT,COUNTERS
from PySide6.QtGui import QImage

def verify():
    out=ROOT/'artifacts/validation/input-events'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('input-events-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def counts(data): return [data['variables'][k]['value'] for k in COUNTERS]
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/input_events_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            # Stable frame sorting retains physical order for same-frame quick taps.
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in sorted(events,key=lambda e:e[0])]))
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
            initial=run('initial',mode,exe,60); check(mode+': no synthetic input at startup',counts(initial)==[0]*6)
            ordered=run('ordered',mode,exe,60,[(0,'Space',True),(0,'Space',True),(0,'MouseLeft',True),(0,'Space',False),
                (0,'MouseLeft',False),(0,'Space',True),(0,'Space',False),(2,'A',True),(3,'A',False)])
            check(mode+': quick taps, repeat suppression and action handoff preserve every edge',counts(ordered)==[3,3,2,2,2,1] and ordered['variables']['delayed_action']['value']=='turn')
            handoff=run('handoff',mode,exe,60,[(0,'Space',True),(1,'MouseLeft',True),(2,'Space',False),(3,'MouseLeft',False)])
            check(mode+': two held alternative buttons produce one action press/release',counts(handoff)==[1,1,2,1,1,1])
            setup=[(0,'Space',True),(1,'Space',False),(2,'S',True)]; release=[(3,'S',False)]
            saved=run('saved',mode,exe,3,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes()
            check(mode+': input callback save retains pending action capture',counts(saved)==[2,1,0,1,1,0] and saved['persistence']['success'] and len(saved['continuations']['tasks'])==1)
            future=[(6,'MouseLeft',True),(6,'MouseLeft',False),(10,'D',True),(20,'D',False),(30,'Space',True),(31,'Space',False)]
            reference=run('reference',mode,exe,60,setup+release+future)
            restored=run('restored',mode,exe,58,[(0,'L',True)]+release+future,store)
            check(mode+': fresh-process Load preserves input callbacks and delayed payload without replay',restored==reference and counts(restored)==[4,4,2,3,3,2] and slot(store).read_bytes()==raw)
            load=[(0,'L',True),(1,'L',False)]; missing=run('missing',mode,exe,60,load)
            for damage in ('filter','payload','subscription'):
                bad=copy.deepcopy(json.loads(raw)); event=bad['checkpoint']['events']
                if damage=='filter': next(e for e in event['bindings']['events'] if e['event']==10011)['listeners'][0]['filter']='missing'
                elif damage=='subscription': next(e for e in event['subscriptions'] if e['event']==10008)['enabled']=False
                else: event['queue'].append(dict(event=10008,receiver='',sender='',args=['MouseLeft',True],epoch=0,origin='forged'))
                path=slot(workspace/('bad-'+damage)/mode); save_json(path,bad); data=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,load,path.parent.parent)
                check(mode+': bad '+damage+' rejects before replacing live state',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==data and
                      all(rejected[k]==missing[k] for k in ('scene','entities','variables','animation','frame','time','events','continuations')))
        for label,items in states.items(): check(label+': all four hosts match',all(item==items[0] for item in items))
        for label,items in images.items(): check(label+': interpreted/generated pixels match',items[0]==items[1])
        check('Restored rendering equals uninterrupted gameplay',images['restored']==images['reference'])
        check('Input produces visible robot movement and rotation',images['initial'][0]!=images['reference'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during validation',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/input-events-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Input events workflow:',len(verify()['checks']),'checks passed')
