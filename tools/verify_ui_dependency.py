"""Build and exercise pinned RmlUi with SDL GPU, before engine node integration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QImage, QColor
from editor.build_worker import find_tool
from editor.core.document import save_json
from editor.core.registry import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-build',action='store_true')
    args=parser.parse_args()
    artifacts=ROOT/'artifacts/validation'; build=ROOT/'.cache/ui-probe-build'
    artifacts.mkdir(parents=True,exist_ok=True)
    save_json(artifacts/'ui-dependency-checks.json',dict(passed=False,status='running'))
    if not args.skip_build:
        cmake,ninja,compiler=[find_tool(t) for t in ('cmake','ninja','clang++')]
        env=dict(os.environ,PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH',''))
        cache=build/'CMakeCache.txt'
        has_compilers=cache.exists() and 'CMAKE_C_COMPILER:' in cache.read_text('utf-8')
        compiler_options=[] if has_compilers else [f'-DCMAKE_CXX_COMPILER={compiler.as_posix()}',
            f'-DCMAKE_C_COMPILER={compiler.with_name("clang.exe").as_posix()}']
        configure=[cmake,'-S',ROOT/'tools/ui_probe','-B',build,'-G','Ninja',f'-DCMAKE_MAKE_PROGRAM={ninja}',
            *compiler_options,
            '-DCMAKE_BUILD_TYPE=Release']
        for command,name in [(configure,'ui-probe-configure.log'),
                             ([cmake,'--build',build,'--target','node_ui_probe','--parallel','2'],'ui-probe-build.log')]:
            with (artifacts/name).open('w',encoding='utf-8') as log:
                subprocess.run(list(map(str,command)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    package=ROOT/'.cache'/('ui-probe-'+uuid.uuid4().hex[:8])/'giao diện thử'; package.mkdir(parents=True)
    for name in ('node_ui_probe.exe','SDL3.dll','SDL3_image.dll'):
        shutil.copy2(build/name,package/name)
    (package/'shaders').mkdir()
    for name in ('UiComposite.vert.spv','UiComposite.frag.spv'):
        shutil.copy2(ROOT/'runtime/shaders'/name,package/'shaders'/name)
    fixture=QImage(8,8,QImage.Format.Format_RGBA8888); fixture.fill(QColor(64,128,192))
    assert fixture.save(str(package/'image.png'))
    fonts=ROOT/'deps/RmlUi-6.3/Samples/assets'
    shutil.copy2(fonts/'RobotoMono-Regular.ttf',package/'font.ttf')
    shutil.copy2(fonts/'LICENSE.txt',package/'FONT-LICENSE.txt')
    shutil.copy2(ROOT/'deps/RmlUi-6.3/LICENSE.txt',package/'RMLUI-LICENSE.txt')
    shutil.copy2(ROOT/'deps/freetype-2.15.0/docs/FTL.TXT',package/'FREETYPE-LICENSE.txt')
    system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
    results={}; checks=[]
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value))); print(('PASS ' if value else 'FAIL ')+name,flush=True)
    for mode,flags in [('headless',['--headless']),('sdr',[]),('linear',['--linear'])]:
        report=artifacts/f'ui-probe-{mode}.json'
        run=subprocess.run([str(package/'node_ui_probe.exe'),'--font','font.ttf','--output',str(report),
            '--capture',str(artifacts/f'ui-probe-{mode}'),*flags],cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
        (artifacts/f'ui-probe-{mode}.log').write_text(run.stdout+run.stderr,'utf-8')
        assert run.returncode==0,run.stdout+run.stderr
        results[mode]=json.loads(report.read_text('utf-8'))
        check(mode+' runs from an isolated package with clean PATH',results[mode]['passed'])
        check(mode+' fails operations on RmlUi warnings or errors',results[mode]['strict_diagnostics'])
        check(mode+' font includes Vietnamese glyphs',results[mode]['vietnamese_font_glyphs'])
        for name in results[mode]['checks']: check(mode+': '+name,True)
    check('Headless and both GPU modes have identical widget/input state',
          results['headless']['state']==results['sdr']['state']==results['linear']['state'])
    colors={}
    for mode in ('sdr','linear'):
        before=QImage(str(artifacts/f'ui-probe-{mode}-before.bmp'))
        after=QImage(str(artifacts/f'ui-probe-{mode}-after.bmp'))
        check(mode+' captures real 640x480 frames',before.width()==640 and before.height()==480 and after.size()==before.size())
        colors[mode]=after.pixelColor(560,70).getRgb()[:3]
        check(mode+' solid CSS color matches sRGB bytes',all(abs(a-b)<=1 for a,b in zip(colors[mode],(64,128,192))))
        def near(x,y,expected,tolerance=2):
            return all(abs(a-b)<=tolerance for a,b in zip(after.pixelColor(x,y).getRgb()[:3],expected))
        check(mode+' sampled image preserves sRGB color',near(550,250,(64,128,192),1))
        check(mode+' translucent UI layers blend in CSS color space',near(550,150,(43,84,126)))
        check(mode+' UI scissor clips overflowing child',near(540,320,(64,128,192),1) and near(580,320,(22,40,59),1))
        def srgb(v): return 12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055
        def linear(v): return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        alpha_expected=[round(srgb(linear(v/255)*128/255+linear(b/255)*127/255)*255) if mode=='linear' else round((v*128+b*127)/255)
                        for v,b in zip((64,128,192),(10,20,30))]
        check(mode+' translucent UI blends onto scene without dark fringes',near(550,472,alpha_expected))
        check(mode+' transparent UI preserves scene pixels',near(0,0,(10,20,30),0))
        resized=QImage(str(artifacts/f'ui-probe-{mode}-resized.bmp'))
        check(mode+' GPU layer reallocates and anchored widget follows resize',resized.size().width()==800 and resized.size().height()==600 and
              resized.pixelColor(700,560).getRgb()[:3]==(192,96,32))
        check(mode+' progress visibly fills after clicks',before.pixelColor(80,312)!=after.pixelColor(80,312))
        slider_pixels=[after.pixelColor(x,y).getRgb()[:3] for y in range(350,374) for x in range(32,232)]
        check(mode+' slider thumb and track are actually visible',slider_pixels.count((53,189,135))>100 and slider_pixels.count((52,82,104))>100)
        check(mode+' text has visible glyph pixels',len({after.pixelColor(x,y).rgba() for y in range(29,59) for x in range(32,330)})>12)
        after.save(str(artifacts/f'ui-probe-{mode}.png'))
    passed=all(c['passed'] for c in checks)
    sources=['cmake/UiDependencies.cmake','cmake/PatchRmlUiCheckpoint.cmake','runtime/include/ui_renderer.hpp','runtime/src/ui_renderer.cpp',
        'runtime/include/ui_session.hpp','runtime/src/ui_session.cpp','tools/ui_probe/main.cpp',
        'tools/ui_probe/CMakeLists.txt','tools/verify_ui_dependency.py',
        'runtime/shaders/UiComposite.vert.hlsl','runtime/shaders/UiComposite.frag.hlsl',
        'runtime/shaders/UiComposite.vert.spv','runtime/shaders/UiComposite.frag.spv',
        'deps/RmlUi-6.3/upstream.txt','deps/freetype-2.15.0/upstream.txt']
    save_json(artifacts/'ui-dependency-checks.json',dict(passed=passed,status='passed' if passed else 'failed',checks=checks,colors=colors,package=str(package),
        state=results['headless']['state'],rmlui=results['headless']['version'],
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}))
    assert passed,'See artifacts/validation/ui-dependency-checks.json'


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        path=ROOT/'artifacts/validation/ui-dependency-checks.json'
        report=json.loads(path.read_text('utf-8')) if path.exists() else {}
        report.update(passed=False,status='failed',error=str(error)); save_json(path,report)
        raise
