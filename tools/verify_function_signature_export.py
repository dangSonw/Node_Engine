"""Run the editor-authored migration through four relocated native hosts and a launcher."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.projects import project_snapshot,compile_project
from editor.core.runtime_build import current,fingerprint


def verify():
    source=ROOT/'examples/function_signature_demo'; out=ROOT/'artifacts/validation/function-signatures'
    relocated=out/'relocated'; relocated.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,checks=[],native_fingerprint=fingerprint())
    def check(label,condition):
        assert condition,label
        report['checks'].append(label); print('PASS '+label,flush=True)
    check('Native build stamp matches sources',current(ROOT/'build/node_view.exe'))
    ir=json.loads((source/'generated/game.ir.json').read_text('utf-8'))
    check('Export IR equals saved editor project',ir==compile_project(project_snapshot(source/'project.json')))
    cache=(ROOT/'build/CMakeCache.txt').read_text('utf-8')
    check('CMake compiled this project source',f'NODE_ENGINE_GENERATED:FILEPATH={source.as_posix()}/generated/game.generated.cpp' in cache)
    for name in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
        shutil.copy2(ROOT/'build'/name,relocated/name)
    for name in ('fonts','shaders','licenses'): shutil.copytree(ROOT/'build'/name,relocated/name,dirs_exist_ok=True)
    shutil.copytree(source/'assets',relocated/'assets',dirs_exist_ok=True)
    shutil.copy2(source/'generated/game.ir.json',relocated/'game.ir.json')
    system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
    states={}
    for mode,exe in [('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]:
        args=[str(relocated/exe),'--project-root',str(relocated),'--frames','120']
        if 'preview' in mode: args+=['--ir',str(relocated/'game.ir.json')]
        if mode.startswith('view'): args+=['--capture',str(out/(mode+'.bmp')),'--output',str(out/(mode+'.json'))]
        result=subprocess.run(args,cwd=relocated,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
        (out/(mode+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8'); check(mode+' executes with system-only PATH',result.returncode==0)
        states[mode]=json.loads((out/(mode+'.json')).read_text('utf-8')) if mode.startswith('view') else json.loads(result.stdout)
        if not mode.startswith('view'): save_json(out/(mode+'.json'),states[mode])
    reference=states['headless-preview']
    check('All four hosts produce identical complete state',all(state==reference for state in states.values()))
    check('Independent expected results after renamed/reordered nested calls',reference['entities']['player']['rotation']==[0,120,0]
          and reference['entities']['partner']['rotation']==[0,-180,0] and reference['variables']['left_rotation']['value']==[0,120,0])
    a,b=QImage(str(out/'view-preview.bmp')),QImage(str(out/'view-compiled.bmp'))
    check('Interpreted and compiled GPU pixels match',not a.isNull() and a==b)
    check('GPU image contains both meshes',sum(a.pixelColor(x,y)!=a.pixelColor(0,0) for y in range(0,a.height(),4) for x in range(0,a.width(),4))>100)
    package=ROOT/'artifacts/demos/function-signatures'; package.mkdir(parents=True,exist_ok=True)
    for name in ('node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'): shutil.copy2(relocated/name,package/name)
    for name in ('fonts','shaders','licenses','assets'): shutil.copytree(relocated/name,package/name,dirs_exist_ok=True)
    (package/'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n',encoding='ascii')
    (package/'README.md').write_text('''# Editable function signatures

Run Play.cmd. Two Blockbench robots rotate through the same Turn Robot action,
which calls Angular Step. Their renamed/reordered inputs, outputs and nested
wires were edited in the actual Python editor. Left: 60 degrees/second; right:
-90. Existing call values survive changing the Rate default to 6 for new calls.

Editable project: examples/function_signature_demo/project.json.
Use Graph > Edit Function Signature to edit a selected call or choose a function.
The compiled demo requires no Python or Qt. Windows/Vulkan was verified on this
desktop; other platforms were not tested. Dependencies are listed in licenses/.
''',encoding='utf-8')
    result=subprocess.run([os.environ['COMSPEC'],'/d','/c',str(package/'Play.cmd'),'--frames','120',
        '--capture',str(out/'package.bmp'),'--output',str(out/'package.json')],cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    (out/'package.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    check('Standalone launcher executes without Python or Qt on PATH',result.returncode==0)
    check('Standalone launcher matches reference state and GPU pixels',json.loads((out/'package.json').read_text('utf-8'))==reference and QImage(str(out/'package.bmp'))==a)
    report['package']=str(package); report['package_sha256']={p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*')) if p.is_file()}
    check('Native source fingerprint unchanged',fingerprint()==report['native_fingerprint'])
    report['passed']=True; save_json(out/'export-checks.json',report); return report


if __name__=='__main__': verify()
