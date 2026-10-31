"""Actual asynchronous editor Build Game, all-scene snapshot and external asset staging."""
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow

def verify():
    project=ROOT/'.cache'/('scene-build-'+uuid.uuid4().hex[:8]); shutil.copytree(ROOT/'examples/scene_session_demo',project,ignore=shutil.ignore_patterns('build','generated'))
    (project/'models').mkdir(); shutil.copy2(project/'assets/robot.gltf',project/'models/robot.gltf')
    scene=json.loads((project/'scenes/level.json').read_text('utf-8')); scene['entities'][1]['mesh']='models/robot.gltf'; save_json(project/'scenes/level.json',scene)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    w=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat)); w.open_project(project/'project.json','level')
    out=ROOT/'artifacts/validation'; report=dict(passed=False,checks=[],native_fingerprint=fingerprint(),project=str(project)); completed=[]
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    try:
        w.scene['variables']['unsaved_build']=17; w.document_changed()
        w.builder.finished.connect(completed.append); w.actions['Build Game'].trigger()
        check('Build Game starts asynchronous worker',w.builder.busy)
        request=json.loads((project/'generated/build-request.json').read_text('utf-8'))
        check('Snapshot contains every scene and uses startup menu',request['entry_scene']=='menu' and set(request['scenes'])=={'menu','level'})
        w.scene['variables']['unsaved_build']=99
        broken=json.loads((project/'graphs/level.json').read_text('utf-8')); broken['nodes'][0]['type']=999999; save_json(project/'graphs/level.json',broken)
        end=time.monotonic()+1200; beats=0
        while w.builder.busy and time.monotonic()<end: QTest.qWait(50); beats+=1
        check('Build completes while editor pumps events',completed==[True] and beats>10)
        check('Built runtime matches native sources',current(project/'build/node_view.exe'))
        check('Dependency from non-entry scene staged outside assets',(project/'build/models/robot.gltf').read_bytes()==(project/'models/robot.gltf').read_bytes())
        keys=project/'keys.json'; save_json(keys,dict(version=1,events=[dict(frame=0,button='C',down=True)]))
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system)); states=[]
        for label,exe in [('compiled','node_game.exe'),('preview','node_preview.exe')]:
            args=[str(project/'build'/exe),'--frames','3','--input-replay',str(keys),'--save-root',str(project/'saves'/label)]
            if label=='preview': args+=['--ir',str(project/'generated/game.ir.json')]
            r=subprocess.run(args,cwd=project/'build',env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
            (out/('scene-session-build-'+label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
            check(label+' built game runs from build directory',r.returncode==0)
            state=json.loads(r.stdout); states.append(state)
            check(label+' uses captured unsaved edit despite subsequent source changes',state['scene_session']['active']=='level' and state['variables']['unsaved_build']==17)
        check('Built interpreted/generated state matches',states[0]==states[1])
        check('Authoring edits after Build remain in editor',w.scene['variables']['unsaved_build']==99 and w.dirty)
        report['binary_sha256']={n:hashlib.sha256((project/'build'/n).read_bytes()).hexdigest() for n in ['node_game.exe','node_preview.exe','node_game_view.exe','node_view.exe']}
        check('Sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        (out/'scene-session-editor-build.log').write_text(w.build_output.toPlainText(),encoding='utf-8'); save_json(out/'scene-session-build-checks.json',report)
        if w.builder.busy:
            w.builder.cancel(); end=time.monotonic()+10
            while w.builder.busy and time.monotonic()<end: QTest.qWait(50)
        w.dirty=False; w.close(); QTest.qWait(50)
    return report

if __name__=='__main__': print('Editor build:',len(verify()['checks']),'checks passed.')
