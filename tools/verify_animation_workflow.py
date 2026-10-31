"""Relocated four-host animation playback, GPU pixels and exact saved continuation."""
import json
import hashlib
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
from tools.create_animation_demo import GAME,SLOT
from PySide6.QtGui import QImage

def verify():
    out=ROOT/'artifacts/validation/animation-playback'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('animation-game-'+uuid.uuid4().hex[:10]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    project=ROOT/'examples/animation_demo'; report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store):return store/GAME/('slot-'+SLOT.encode().hex()+'.json')
    states={}; images={}
    try:
        check('Root runtime matches sources',current(ROOT/'build/node_view.exe'))
        for file in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/file,package/file)
        for folder in ('fonts','licenses','shaders'):shutil.copytree(ROOT/'build'/folder,package/folder)
        shutil.copytree(project/'assets',package/'assets'); shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=v) for f,k,v in sorted(keys)]))
            args=[str(package/exe),'--frames',str(frames),'--output',str(prefix.with_suffix('.json')),
                '--input-replay','keys.json','--save-root',str(store)]
            if mode.endswith('preview'):args+=['--ir','game.ir.json']
            if mode.startswith('view'):args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,'utf-8')
            check(label+': '+mode+' succeeds',result.returncode==0)
            data=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(data)
            if mode.startswith('view'):
                image=QImage(str(prefix.with_suffix('.bmp'))); check(label+': '+mode+' captures pixels',not image.isNull())
                images.setdefault(label,[]).append(image)
            return data
        keys=[(9,'P',True),(10,'P',False),(10,'T',True),(11,'T',False),(12,'B',True),(13,'B',False),
              (14,'R',True),(15,'R',False),(30,'S',True),(31,'S',False)]
        for mode,exe in modes:
            wave=run('wave',mode,exe,60); p=wave['animation']
            check(mode+': independent Wave and Walk clocks',p['player']['clip']=='Wave' and p['walker']['clip']=='Walk' and
                  abs(p['player']['time']-1)<1e-12 and abs(p['walker']['time'])<1e-12)
            paused=run('paused',mode,exe,60,[(9,'P',True),(10,'P',False)])
            check(mode+': Pause freezes only the selected robot',abs(paused['animation']['player']['time']-.15)<1e-12 and
                paused['animation']['player']['paused'] and paused['animation']['walker']==p['walker'])
            stopped=run('stopped',mode,exe,60,[(0,'X',True),(1,'X',False)])
            check(mode+': Stop removes only the selected player',set(stopped['animation'])=={'walker'})
            saved=run('save',mode,exe,31,keys); store=workspace/'save'/mode
            raw=slot(store).read_bytes(); checkpoint=json.loads(raw)['checkpoint']
            check(mode+': checkpoint includes exact animation clocks and rate',checkpoint['animation']==saved['animation'] and
                saved['animation']['player']['speed']==-1 and saved['persistence']['success'])
            baseline=run('reference',mode,exe,75,keys)
            resumed=run('restored',mode,exe,45,[(0,'L',True),(1,'L',False)],store)
            check(mode+': fresh-process continuation matches all state',resumed==baseline and slot(store).read_bytes()==raw)
            for damage in ('time','clip','model','flags'):
                bad=json.loads(raw); a=bad['checkpoint']['animation']['player']
                if damage=='time':a['time']=99
                if damage=='clip':a['clip']='missing'
                if damage=='model':a['mesh']='assets/elsewhere.glb'
                if damage=='flags':a['paused']=True
                damaged=workspace/('bad-'+damage)/mode; file=slot(damaged); save_json(file,bad); before=file.read_bytes()
                rejected=run('bad-'+damage,mode,exe,60,[(0,'L',True),(1,'L',False)],damaged)
                check(mode+': invalid '+damage+' rolls back animation and preserves save',
                    not rejected['persistence']['success'] and rejected['animation']==p and
                    rejected['entities']==wave['entities'] and file.read_bytes()==before)
        for label,items in states.items():check(label+': four hosts agree',all(x==items[0] for x in items))
        for label,items in images.items():check(label+': interpreter and compiled GPU pixels match',items[0]==items[1])
        check('Checkpoint restores exact rendered poses',images['restored']==images['reference'])
        check('Wave, paused pose and rest pose visibly differ',images['wave'][0]!=images['paused'][0] and images['wave'][0]!=images['stopped'][0])
        # The right robot is unchanged; different clocks cannot overwrite its shared model.
        image=images['wave'][0]; right=(image.width()//2,image.height()//3,image.width()//2,image.height()*2//3)
        check('Changing the left robot preserves the right robot pixels',all(images[x][0].copy(*right)==image.copy(*right) for x in ('paused','stopped')))
        image.save(str(out/'robots.png'))
        check('Native sources remain unchanged',fingerprint()==report['native_fingerprint'])
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}
        report['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'runtime/src/animation_scene.cpp','runtime/include/animation_scene.hpp','runtime/src/assets.cpp','runtime/src/display.cpp',
            'runtime/src/app.cpp','runtime/src/headless.cpp','runtime/src/checkpoint.cpp','runtime/src/persistence.cpp','runtime/src/scene.cpp',
            'runtime/include/runtime.hpp','runtime/include/display.hpp','runtime/include/scene.hpp',
            'nodes/registry.yaml','CMakeLists.txt','tools/create_animated_robot.py','tools/create_animation_demo.py','tools/verify_animation_workflow.py')}
        report['passed']=True
    except Exception as error:report['error']=str(error); raise
    finally:save_json(ROOT/'artifacts/validation/animation-playback-checks.json',report)
    return report
if __name__=='__main__':print('Animation workflow:',len(verify()['checks']),'checks passed.')
