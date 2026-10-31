"""Cursor intent and anchored relative input in four relocated native hosts."""
import copy,hashlib,json,os,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_cursor_demo import GAME,SLOT
from PySide6.QtGui import QImage

def verify():
    out=ROOT/'artifacts/validation/cursor'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('cursor-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package)); states={}; images={}
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    def pointer(frame,kind,x,y,**kwargs): return dict(frame=frame,type=kind,x=x,y=y,**kwargs)
    def key(frame,name,down): return dict(frame=frame,button=name,down=down)
    setup=[pointer(0,'position',25.5,50.25),key(0,'K',True),key(1,'H',True),pointer(1,'motion',40.5,45.25,dx=15,dy=-5),
           pointer(1,'wheel',.25,1.5),key(2,'V',True),pointer(2,'motion',50.75,48,dx=10.25,dy=2.75),pointer(2,'wheel',-.5,-.25),key(2,'S',True)]
    future=[key(3,'S',False),pointer(4,'motion',80.75,58,dx=30,dy=10),key(5,'U',True),
            pointer(6,'motion',-10,20,dx=-90.75,dy=-38),key(7,'H',False),key(7,'H',True),pointer(7,'wheel',.125,-.5),dict(frame=9,release_all=True),pointer(10,'position',120,90)]
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/name,package/name)
        for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,package/name)
        project=ROOT/'examples/cursor_demo'; shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,events=(),store=None,version=2):
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
            initial=run('initial',mode,exe,30); check(mode+': replay starts visible/unlocked with neutral pointer',
                initial['variables']['locked']['value']==False and initial['variables']['visible']['value']==True and
                all(v['value']==[0,0,0] for k,v in initial['variables'].items() if k not in ('locked','visible')))
            legacy=run('legacy',mode,exe,30,version=1); check(mode+': version-1 button replay remains compatible',initial==legacy)
            saved=run('saved',mode,exe,3,setup); store=workspace/'saved'/mode; raw=slot(store).read_bytes()
            v=saved['variables']; data=json.loads(raw)['checkpoint']['input']
            check(mode+': save retains cursor intent, locked anchor and transient input',saved['persistence']['success'] and data['version']==5 and
                  data['cursor']==dict(visible=True,locked=True,node='cursor_V') and data['pointer']==dict(position=[25.5,50.25],delta=[10.25,2.75],wheel=[-.5,-.25]) and
                  v['total_delta']['value']==[25.25,-2.25,0] and v['total_wheel']['value']==[-.25,1.25,0])
            reference=run('reference',mode,exe,30,setup+future)
            restored=run('restored',mode,exe,28,[key(0,'L',True)]+future,store)
            check(mode+': fresh-process Load exactly continues pointer gameplay',restored==reference and slot(store).read_bytes()==raw)
            v=reference['variables']
            check(mode+': unlock resumes position while retaining explicit hidden request',not v['locked']['value'] and not v['visible']['value'] and v['position']['value']==[120,90,0] and v['delta']['value']==v['wheel']['value']==[0,0,0] and
                  v['total_delta']['value']==[-35.5,-30.25,0] and v['total_wheel']['value']==[-.125,.75,0])
            robot=reference['entities']['player']
            check(mode+': drag and wheel affect the robot without frame-time multiplication',robot['rotation']==[3.875,27.625,0] and abs(robot['position'][2]-.1125)<1e-12)
            load=[key(0,'L',True),key(1,'L',False)]; missing=run('missing',mode,exe,30,load)
            for damage in ('visible','locked','origin','missing'):
                bad=copy.deepcopy(json.loads(raw)); cursor_data=bad['checkpoint']['input']['cursor']
                if damage=='visible': cursor_data['visible']=1
                elif damage=='locked': cursor_data['locked']='true'
                elif damage=='origin': cursor_data['node']=[]
                else: cursor_data.pop('node')
                path=slot(workspace/('bad-'+damage)/mode); save_json(path,bad); before=path.read_bytes()
                rejected=run('bad-'+damage,mode,exe,30,load,path.parent.parent)
                check(mode+': malformed cursor '+damage+' leaves live game untouched',not rejected['persistence']['success'] and bool(rejected['persistence']['error']) and path.read_bytes()==before and
                      all(rejected.get(k)==missing.get(k) for k in ('scene','entities','variables','animation','frame','time','events','continuations')))
        for label,items in states.items(): check(label+': all four hosts match',all(item==items[0] for item in items))
        for label,items in images.items(): check(label+': interpreted/generated pixels match',items[0]==items[1])
        check('Restored rendering equals uninterrupted gameplay',images['restored']==images['reference'])
        check('Pointer gameplay visibly moves and rotates the robot',images['initial'][0]!=images['reference'][0])
        images['reference'][0].save(str(out/'robot.png'))
        check('Sources unchanged during validation',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for exe in [name for _,name in modes]+['SDL3.dll','SDL3_mixer.dll','SDL3_image.dll']}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/cursor-workflow-checks.json',report)
    return report

if __name__=='__main__': print('Cursor workflow:',len(verify()['checks']),'checks passed')
