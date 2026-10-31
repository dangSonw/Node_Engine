import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.core.runtime_build import current, fingerprint


def test_runtime_stamp_rejects_old_source_or_changed_binary(tmp_path):
    exe=tmp_path/'node_view.exe'
    exe.write_bytes(b'fixture-native-binary')
    assert not current(exe,'abc')
    save_json(tmp_path/'runtime-build.json',{'fingerprint':'abc','binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest()})
    assert current(exe,'abc')
    assert not current(exe,'abc',node_code='new-hook')
    stamp=json.loads((tmp_path/'runtime-build.json').read_text('utf-8'))
    stamp['node_code']='built-hook'
    save_json(tmp_path/'runtime-build.json',stamp)
    assert current(exe,'abc',node_code='built-hook')
    assert not current(exe,'abc',node_code='edited-hook')
    assert not current(exe,'changed-source')
    exe.write_bytes(b'replaced')
    assert not current(exe,'abc')


def test_fingerprint_changes_for_native_sources_and_registry(tmp_path):
    for path in ['CMakeLists.txt','nodes/registry.yaml','runtime/include/runtime.hpp','runtime/generated/adapters.generated.cpp',
                 'deps/flecs-4.1.6/flecs.c','cmake/UiDependencies.cmake','deps/JoltPhysics-5.6.0/upstream.txt']:
        p=tmp_path/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('initial','utf-8')
    original=fingerprint(tmp_path)
    (tmp_path/'runtime/include/runtime.hpp').write_text('changed','utf-8')
    changed=fingerprint(tmp_path)
    assert original!=changed
    (tmp_path/'nodes/registry.yaml').write_text('changed','utf-8')
    assert changed!=fingerprint(tmp_path)
    before_dependency=fingerprint(tmp_path)
    (tmp_path/'deps/flecs-4.1.6/flecs.c').write_text('changed','utf-8')
    assert before_dependency!=fingerprint(tmp_path)
    before_cmake=fingerprint(tmp_path)
    (tmp_path/'cmake/UiDependencies.cmake').write_text('changed','utf-8')
    assert before_cmake!=fingerprint(tmp_path)
    before_provenance=fingerprint(tmp_path)
    (tmp_path/'deps/JoltPhysics-5.6.0/upstream.txt').write_text('changed','utf-8')
    assert before_provenance!=fingerprint(tmp_path)


def test_rmlui_checkpoint_patch_accepts_only_pinned_source(tmp_path):
    cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
    patched=(ROOT/'deps/RmlUi-6.3/Include/RmlUi/Core/Context.h').read_bytes()
    marker=b'\n\n\t// Node_Engine checkpoint adapter.'
    if marker in patched:
        start=patched.index(marker)
        end=patched.index(b'\n\n\t/// Adds an event listener',start)
        clean=patched[:start]+patched[end:]
    else:
        clean=patched
    assert hashlib.sha256(clean).hexdigest()=='3f3346173de4d7f611b3cf73156305c769e4bf54baab1cffbf60b9f45e5cbdb4'
    header=tmp_path/'Include/RmlUi/Core/Context.h'
    header.parent.mkdir(parents=True)
    header.write_bytes(clean)
    script=tmp_path/'patch.cmake'
    script.write_text(f'include("{ROOT.as_posix()}/cmake/PatchRmlUiCheckpoint.cmake")\n'
                      f'node_engine_patch_rmlui_checkpoint("{tmp_path.as_posix()}")\n',encoding='utf-8')
    def run():
        return subprocess.run([cmake,'-P',str(script)],capture_output=True,text=True,timeout=15)
    first=run()
    assert first.returncode==0,first.stderr
    assert hashlib.sha256(header.read_bytes()).hexdigest()=='e10f8b60a57f4db19e799cd04762ae28b3ac9eb28905f64f46c1e90618f812d0'
    modified=header.stat().st_mtime_ns
    assert run().returncode==0
    assert header.stat().st_mtime_ns==modified
    damaged=header.read_bytes()+b'\n// Upstream changed\n'
    header.write_bytes(damaged)
    rejected=run()
    assert rejected.returncode!=0 and 'Context.h changed' in rejected.stderr
    assert header.read_bytes()==damaged
    previous=patched.replace(b'\n\tbool ClearCheckpointFocus();',b'')
    assert hashlib.sha256(previous).hexdigest()=='2b39b6fb951c4c67d16b23fc957b6e55429bb1678bbace5e605fb5fffbd1a675'
    header.write_bytes(previous)
    assert run().returncode==0
    assert hashlib.sha256(header.read_bytes()).hexdigest()=='e10f8b60a57f4db19e799cd04762ae28b3ac9eb28905f64f46c1e90618f812d0'
