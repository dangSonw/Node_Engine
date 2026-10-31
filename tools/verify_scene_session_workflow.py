"""Relocated interpreted/generated, headless/GPU scene and checkpoint acceptance."""
import hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_scene_session_demo import GAME,SLOT,trace

def verify():
    out=ROOT/'artifacts/validation/scene-session'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('scene-session-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def keys(*events): return [dict(frame=f,button=k,down=d) for f,k,d in events]
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    try:
        check('Production runtime matches sources',current(ROOT/'build/node_view.exe'))
        names=('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')
        for name in names: shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/scene_session_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
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
            prefix.with_suffix('.log').write_text(r.stdout+r.stderr,encoding='utf-8')
            check(label+': '+mode+' runs without graph errors',r.returncode==0 and '"node_error"' not in r.stdout)
            s=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(s)
            if mode.startswith('view'):
                pic=QImage(str(prefix.with_suffix('.bmp'))); check(label+': '+mode+' renders',not pic.isNull()); images.setdefault(label,[]).append(pic)
            return s
        enter=keys((2,'C',True),(3,'C',False)); save=enter+keys((10,'S',True),(11,'S',False))
        for mode,exe in modes:
            menu=run('menu',mode,exe,61)
            check(mode+': entry menu initializes once',menu['scene_session']['active']=='menu' and menu['logs']==['Loaded menu','Game started once'])
            level=run('level',mode,exe,61,enter)
            check(mode+': target world initializes animation, physics, timer, UI and audio',level['scene_session']['active']=='level' and len(level['entities'])==4 and level['physics']['ticks']>0 and level['animation'] and level['audio'] and len(level['timers'])==1)
            cycle=run('cycle',mode,exe,71,trace())
            check(mode+': three switches preserve host clock and start fires once',cycle['frame']==71 and abs(cycle['time']-71/60)<1e-12)
            check(mode+': old scenes discarded and loaded event fires once per commit',cycle['logs']==['Loaded menu','Game started once','Loaded level','Loaded menu','Loaded level'])
            returned=run('returned',mode,exe,61,enter+keys((20,'M',True),(21,'M',False)))
            check(mode+': return removes level entities, timers, voices and animation',returned['scene_session']['active']=='menu' and len(returned['entities'])==2 and not returned['timers'] and returned['entities']==menu['entities'])
            reloaded=run('reload',mode,exe,61,enter+keys((20,'R',True),(21,'R',False)))
            check(mode+': reload resets simulation but not host clock',reloaded['time']==level['time'] and reloaded['physics']['ticks']<level['physics']['ticks'] and reloaded['logs'].count('Loaded level')==2)
            paused=run('paused-switch',mode,exe,61,keys((0,'P',True),(1,'P',False),(2,'C',True),(3,'C',False)))
            check(mode+': world pause survives transition',paused['clock']['paused'] and paused['time']==1/60 and paused['physics']['ticks']==0)
            unknown=run('unknown',mode,exe,61,keys((0,'X',True),(1,'X',False)))
            check(mode+': unknown scene preserves current world',not unknown['scene_session']['success'] and unknown['entities']==menu['entities'] and unknown['scene_session']['error']=='Unknown scene ID')
            saved=run('save',mode,exe,11,save); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': checkpoint stores active scene',saved['persistence']['success'] and json.loads(raw)['checkpoint']['scene_session']['active']=='level')
            reference=run('reference',mode,exe,61,save)
            restored=run('restored',mode,exe,51,keys((0,'L',True),(11,'S',False)),store)
            check(mode+': cross-scene load resumes full world without Scene Loaded',restored['logs']==['Loaded menu','Game started once'] and {k:v for k,v in restored.items() if k!='logs'}=={k:v for k,v in reference.items() if k!='logs'} and slot(store).read_bytes()==raw)
            bad=json.loads(raw); bad['checkpoint']['scene_session']['active']='missing'; bad_store=workspace/'bad'/mode; save_json(slot(bad_store),bad); bad_bytes=slot(bad_store).read_bytes()
            rejected=run('bad-save',mode,exe,61,keys((0,'L',True)),bad_store)
            check(mode+': corrupt scene checkpoint leaves live world and file intact',not rejected['persistence']['success'] and rejected['entities']==menu['entities'] and rejected['scene_session']==menu['scene_session'] and slot(bad_store).read_bytes()==bad_bytes)
            quit_state=run('quit-pending',mode,exe,61,keys((0,'C',True),(0,'Q',True)))
            check(mode+': quit cancels pending scene change',quit_state['frame']==1 and quit_state['scene_session']['active']=='menu' and quit_state['logs']==menu['logs'])
        for label,items in states.items(): check(label+': four-host full state parity',all(s==items[0] for s in items))
        for label,items in images.items(): check(label+': interpreted/generated GPU parity',items[0]==items[1])
        check('Restored and uninterrupted GPU pixels match',images['reference']==images['restored'])
        check('Menu and level visually differ',images['menu']!=images['level'])
        for label in ('menu','level','cycle'): images[label][0].save(str(out/(label+'.png')))
        for label in states:
            check(label+': deterministic audio capture across four hosts',len({hashlib.sha256((out/(label+'-'+mode+'.wav')).read_bytes()).hexdigest() for mode,_ in modes})==1)
        check('Sources unchanged during verification',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={name:hashlib.sha256((package/name).read_bytes()).hexdigest() for name in names}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/scene-session-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Scene workflow:',len(verify()['checks']),'checks passed.')
