"""Run the saved Qt collection proof project in all four actual native hosts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.projects import compile_project,project_snapshot
from editor.core.runtime_build import current,fingerprint
from PySide6.QtGui import QImage


def verify(project,output,build):
    project=project.resolve(); output=output.resolve(); build=build.resolve()
    output.mkdir(parents=True,exist_ok=True)
    program=compile_project(project_snapshot(project))
    ir=project.parent/'generated/game.ir.json'
    report=dict(passed=False,checks=[],native_fingerprint=fingerprint())
    states=[];images=[]
    def check(label,condition):
        assert condition,label
        report['checks'].append(label)
    try:
        check('Native build matches current sources',current(build/'node_view.exe'))
        check('IR matches the saved project',json.loads(ir.read_text('utf-8'))==program)
        modes=('node_preview','node_game','node_view','node_game_view')
        for mode in modes:
            prefix=output/mode
            args=[str(build/(mode+'.exe')),'--frames','3','--project-root',str(project.parent),
                  '--output',str(prefix.with_suffix('.json'))]
            if mode in ('node_preview','node_view'): args+=['--ir',str(ir)]
            if mode in ('node_view','node_game_view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            result=subprocess.run(args,cwd=project.parent,capture_output=True,text=True,encoding='utf-8',timeout=45)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,encoding='utf-8')
            check(mode+' exits successfully',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8'));states.append(state)
            for name,values in [('inventory',[1,2,9]),('sorted',[1,2,9]),('map_values',[3,4])]:
                check(mode+': '+name,state['variables'][name]==dict(type='array<struct:Vitals>',
                      value=[dict(health=n) for n in values]))
            check(mode+': edited C++ hook runs once',state['logs']==['Inventory stored'])
            if mode in ('node_view','node_game_view'):
                image=QImage(str(prefix.with_suffix('.bmp')))
                check(mode+': framebuffer captured',not image.isNull());images.append(image)
        check('Four complete native states match',all(s==states[0] for s in states))
        check('Interpreted and compiled GPU images match',images[0]==images[1])
        check('Sources stayed unchanged',report['native_fingerprint']==fingerprint())
        report['binary_sha256']={m:hashlib.sha256((build/(m+'.exe')).read_bytes()).hexdigest() for m in modes}
        report['passed']=True
    finally: save_json(output/'checks.json',report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--build',type=Path,default=ROOT/'build')
    args=parser.parse_args();verify(args.project,args.output,args.build)
