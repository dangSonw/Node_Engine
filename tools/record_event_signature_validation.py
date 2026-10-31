"""Record passing event-signature evidence, with hashes for source and delivered files."""
import hashlib,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.registry import Registry
from editor.core.runtime_build import current,fingerprint


def record():
    out=ROOT/'artifacts/validation'; evidence=out/'event-signatures'
    report=dict(passed=False,builtins=len(Registry().nodes),native_fingerprint=fingerprint(),tests=[],checks=[])
    assert current(ROOT/'build/node_view.exe')
    cases={}
    for name in ('core','edits','native'):
        file=f'event-signatures-{name}.xml'; root=ET.parse(out/file).getroot(); suites=root.findall('testsuite')
        assert suites and all(all(int(s.get(k,0))==0 for k in ('errors','failures','skipped')) for s in suites),file
        report['tests'].append(dict(file=file,count=sum(int(s.get('tests',0)) for s in suites),seconds=sum(float(s.get('time',0)) for s in suites)))
        module_cases={}
        for c in root.iter('testcase'): module_cases.setdefault(c.get('classname'),set()).add(c.get('name'))
        # Each report reruns its entire module; keep its latest complete result.
        cases.update(module_cases)
    report['unique_pytest_cases']=sum(map(len,cases.values()))
    for name in ('editor-checks.json','export-checks.json'):
        data=json.loads((evidence/name).read_text('utf-8')); assert data['passed'] and data['native_fingerprint']==report['native_fingerprint']
        report['checks'].append(dict(file='event-signatures/'+name,count=len(data['checks'])))
    report['check_count']=sum(c['count'] for c in report['checks'])
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    sources=set((ROOT/'editor').rglob('*.py'))
    sources.update(ROOT/name for name in ['spec.md','design.md','node_index.md','node_index_lib.md','README.md','CMakeLists.txt','nodes/registry.yaml',
        'docs/events.md','docs/roadmap.md','docs/acceptance-audit.md','docs/validation-report.md','tools/build.ps1',
        'tools/create_events_demo.py','tools/verify_event_signature_editor.py','tools/verify_event_signature_export.py',
        'tools/record_event_signature_validation.py','tests/test_function_edits.py','tests/test_event_edit_native.py',
        'tests/test_functions.py','tests/test_event_edits.py','tests/test_events.py','tests/test_latent_flow.py','tests/test_native.py','tests/test_core.py','tests/test_editor.py',
        'tests/test_projects.py','tests/test_switch_editor.py','tests/test_function_extraction.py','tests/test_function_extraction_editor.py','tests/test_physics_scene.py','tests/test_scene_session.py','tests/conftest.py','.cache/rerun_event_signature_tests.py'])
    sources.update(p for p in (ROOT/'runtime').rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp','.spv'))
    sources.update((ROOT/'cmake').glob('*.cmake'))
    sources.update(p for p in (ROOT/'examples/event_signature_demo').rglob('*') if p.is_file())
    report['source_sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(sources)}
    files=set(out.glob('event-signatures-*.xml'))|set(out.glob('event-signatures-*.log'))|{p for p in evidence.iterdir() if p.is_file()}
    report['evidence_sha256']={p.relative_to(out).as_posix():sha(p) for p in sorted(files)}
    report['binary_sha256']={name:sha(ROOT/'build'/name) for name in ('node_view.exe','node_game_view.exe','node_preview.exe','node_game.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll')}
    package=ROOT/'artifacts/demos/event-signatures'; saved=json.loads((evidence/'export-checks.json').read_text('utf-8'))
    package_hashes={p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob('*')) if p.is_file()}
    assert package_hashes==saved['package_sha256']
    report.update(package='artifacts/demos/event-signatures',package_sha256=package_hashes,passed=True)
    save_json(out/'event-signatures-summary.json',report)
    print(report['unique_pytest_cases'],'distinct pytest cases;',report['check_count'],'integration checks;',len(sources),'source files')
    return report


if __name__=='__main__': record()
