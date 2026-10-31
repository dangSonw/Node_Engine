"""Real four-host target scanning, GPU output and saved continuation."""
import hashlib
import json
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
from tools.create_loop_control_demo import GAME,SLOT
from PySide6.QtGui import QImage


def verify():
    out=ROOT/'artifacts/validation/loop-control'; out.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('loop-control-'+uuid.uuid4().hex[:8]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
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
        project=ROOT/'examples/loop_control_demo'; shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        modes=[('preview','node_preview.exe'),('compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        def run(label,mode,exe,frames,keys=(),store=None):
            store=store or workspace/label/mode; prefix=out/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=d) for f,k,d in sorted(keys)]))
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
        def selection(data,entity,visited,scans):
            v=data['variables']
            return (v['selected']['value']==entity and v['visited']['value']==visited and v['scans']==scans and
                    all(data['entities'][eid]['scale']==([1.25]*3 if eid==entity else [1]*3) for eid in ('player','robot_b','robot_c')))
        def keys(*events): return [(frame,key,True) for frame,key in events]+[(frame+1,key,False) for frame,key in events]
        for mode,exe in modes:
            initial=run('initial',mode,exe,60)
            check(mode+': Continue skips camera and inactive player; Break avoids last robot',selection(initial,'robot_b',3,1))
            first=run('first',mode,exe,60,keys((0,'1'),(2,'Space')))
            check(mode+': enabling first robot shortens scan',selection(first,'player',2,2))
            last=run('last',mode,exe,60,keys((0,'2'),(2,'Space')))
            check(mode+': disabled middle robot is skipped',selection(last,'robot_c',4,2))
            empty_keys=keys((0,'2'),(0,'3'),(2,'Space'))
            empty=run('empty',mode,exe,60,empty_keys)
            check(mode+': no match exits normally without stale selection',selection(empty,'',4,2))
            recovered=run('recovered',mode,exe,60,empty_keys+keys((5,'1'),(7,'Space')))
            check(mode+': later function call has fresh loop control and local state',selection(recovered,'player',2,3))
            save_keys=keys((0,'2'),(2,'Space'),(20,'S'))
            saved=run('save',mode,exe,21,save_keys); store=workspace/'save'/mode; raw=slot(store).read_bytes()
            check(mode+': Save includes function results and visual selection',saved['persistence']['success'] and selection(saved,'robot_c',4,2))
            future=keys((40,'1'),(42,'Space'))
            reference=run('reference',mode,exe,75,save_keys+future)
            restored=run('restored',mode,exe,55,[(0,'L',True),(21,'S',False)]+future,store)
            check(mode+': fresh-process Save/Load and later scan match entire state',reference==restored and slot(store).read_bytes()==raw and selection(restored,'player',2,3))
        for label,items in states.items(): check(label+': four hosts match',all(data==items[0] for data in items))
        for label,items in images.items(): check(label+': compiled and interpreted GPU pixels match',items[0]==items[1])
        check('Restored scene renders uninterrupted selection',images['restored']==images['reference'])
        check('Selected and empty scenes visibly differ',images['first'][0]!=images['last'][0] and images['last'][0]!=images['empty'][0])
        images['first'][0].save(str(out/'robots.png'))
        check('Sources unchanged during verification',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={exe:hashlib.sha256((package/exe).read_bytes()).hexdigest() for _,exe in modes}; report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally: save_json(ROOT/'artifacts/validation/loop-control-workflow-checks.json',report)
    return report


if __name__=='__main__': print('Loop control workflow:',len(verify()['checks']),'checks passed.')
