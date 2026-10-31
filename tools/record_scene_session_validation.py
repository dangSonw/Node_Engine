"""Freeze only passing acceptance results with source, evidence and package hashes."""
import hashlib,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.registry import Registry
from editor.core.runtime_build import current,fingerprint

def record():
    out=ROOT/'artifacts/validation'; target=out/'scene-session-summary.json'
    report=dict(passed=False,builtins=len(Registry().nodes),native_fingerprint=fingerprint(),tests=[],checks=[],skipped_cases=[])
    assert current(ROOT/'build/node_view.exe')
    cases=set()
    for name in ('scene-project-core.xml','scene-session-tests.xml','scene-session-assets.xml'):
        root=ET.parse(out/name).getroot(); suites=root.findall('testsuite')
        assert suites and all(all(int(s.get(k,0))==0 for k in ('errors','failures')) for s in suites),name
        skipped=sum(int(s.get('skipped',0)) for s in suites)
        report['tests'].append(dict(file=name,count=sum(int(s.get('tests',0)) for s in suites)-skipped,skipped=skipped,seconds=sum(float(s.get('time',0)) for s in suites)))
        for case in root.iter('testcase'):
            identity=(case.get('classname'),case.get('name'))
            skip=case.find('skipped')
            if skip is not None:
                assert identity==('tests.test_build_assets','test_model_staging_failure_preserves_existing_output[link]') and 'Symbolic links unavailable' in skip.get('message','')
                report['skipped_cases'].append(dict(test='/'.join(identity),reason=skip.get('message')))
            else: cases.add(identity)
    report['unique_pytest_cases']=len(cases)
    for name in ('scene-session-time-checks.json','scene-session-checkpoint-checks.json','scene-session-workflow-checks.json',
                 'scene-session-editor-checks.json','scene-session-build-checks.json','scene-session-package.json'):
        data=json.loads((out/name).read_text('utf-8')); assert data['passed'] and data['native_fingerprint']==report['native_fingerprint'],name
        report['checks'].append(dict(file=name,count=len(data['checks']) if 'checks' in data else data['check_count']))
    report['check_count']=sum(item['count'] for item in report['checks'])
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    sources={ROOT/name for name in ['spec.md','design.md','node_index.md','node_index_lib.md','README.md','CMakeLists.txt','nodes/registry.yaml',
        'docs/scenes.md','docs/roadmap.md','docs/acceptance-audit.md','docs/validation-report.md','docs/world-pause.md',
        'tests/test_projects.py','tests/test_scene_session.py','tests/test_world_pause.py','tests/test_core.py','tests/test_editor.py',
        'tests/test_runtime_build.py','tests/test_native.py','tests/test_physics_scene.py','tests/test_build_assets.py','tools/build.ps1',
        'tools/create_scene_session_demo.py','tools/create_time_demo.py','tools/verify_scene_session_workflow.py',
        'tools/verify_scene_session_editor.py','tools/verify_scene_session_build.py','tools/verify_scene_session_regressions.py',
        'tools/verify_game_checkpoint.py','tools/package_scene_session_demo.py','tools/record_scene_session_validation.py',
        'tools/time_probe/main.cpp','tools/game_checkpoint_probe/main.cpp','.cache/rerun_scene_session_tests.py']}
    sources.update((ROOT/'editor').rglob('*.py')); sources.update((ROOT/'cmake').glob('*.cmake'))
    sources.update(p for p in (ROOT/'runtime').rglob('*') if p.is_file() and p.suffix in ('.hpp','.cpp','.spv'))
    sources.update(p for p in (ROOT/'examples/scene_session_demo').rglob('*') if p.is_file() and 'build' not in p.parts)
    report['source_sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(sources)}
    evidence=set(out.glob('scene-session-*'))|set(out.glob('scene-project-*'))
    evidence={f for p in evidence for f in ([p] if p.is_file() else p.rglob('*')) if f.is_file() and f!=target}
    evidence.update(p for p in (out/'scene-session').rglob('*') if p.is_file())
    report['evidence_sha256']={p.relative_to(out).as_posix():sha(p) for p in sorted(evidence)}
    names=('node_view.exe','node_game_view.exe','node_preview.exe','node_game.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll','node_time_probe.exe','node_game_checkpoint_probe.exe')
    report['binary_sha256']={name:sha(ROOT/'build'/name) for name in names}
    package=ROOT/'artifacts/demos/scene-playground'; report['package_sha256']={p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob('*')) if p.is_file()}
    report['package']='artifacts/demos/scene-playground'; report['passed']=True
    save_json(target,report)
    print(report['unique_pytest_cases'],'pytest cases;',report['check_count'],'checks;',len(sources),'source files;',len(evidence),'evidence files')
    return report

if __name__=='__main__': record()
