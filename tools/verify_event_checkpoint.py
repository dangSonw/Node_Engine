"""Build and exercise native event checkpoints, including separate-process restore."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.core.runtime_build import fingerprint


def verify(build=ROOT / 'build', output=ROOT / 'artifacts/validation/event-checkpoint-checks.json'):
    build, output = Path(build), Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'passed': False, 'native_fingerprint': fingerprint(), 'checks': [], 'runs': []}
    probe_source = ROOT / 'tools/event_probe/main.cpp'
    report['probe_source_sha256'] = hashlib.sha256(probe_source.read_bytes()).hexdigest()
    try:
        cmake = shutil.which('cmake') or str(Path.home() / '.local/bin/cmake.exe')
        build_result = subprocess.run([cmake, '--build', str(build), '--target', 'node_event_probe', '--parallel', '2'],
                                      cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=300)
        output.with_suffix('.build.log').write_text(build_result.stdout + build_result.stderr, encoding='utf-8')
        if build_result.returncode:
            raise RuntimeError('Probe build failed; see ' + str(output.with_suffix('.build.log')))
        executable = build / ('node_event_probe.exe' if os.name == 'nt' else 'node_event_probe')
        report['binary_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()

        def run(*args):
            result = subprocess.run([str(executable), *map(str, args)], cwd=build,
                                    capture_output=True, text=True, encoding='utf-8', timeout=60)
            report['runs'].append({'arguments': list(map(str, args)), 'exit_code': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr})
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            native = json.loads(result.stdout)
            if not native['passed']:
                raise RuntimeError('Native checkpoint assertions failed')
            report['checks'].extend(native['checks'])

        run('--self-test')
        with tempfile.TemporaryDirectory(prefix='event-checkpoint-') as directory:
            saved = Path(directory) / 'checkpoint.json'
            run('--write', saved)
            before = saved.read_bytes()
            run('--read', saved)
            if before != saved.read_bytes():
                raise RuntimeError('Restoration changed the saved checkpoint')
            report['checks'].append('restoration leaves the saved checkpoint bytes unchanged')
            payload = json.loads(before)
            report['trace_frames'] = len(payload['trace'])
            report['checkpoint_bytes'] = len(before)
            report['checkpoint_sha256'] = hashlib.sha256(before).hexdigest()
        if fingerprint() != report['native_fingerprint'] or hashlib.sha256(probe_source.read_bytes()).hexdigest() != report['probe_source_sha256']:
            raise RuntimeError('Sources changed during validation')
        report['passed'] = True
        return report
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    result = verify()
    print(f"Event checkpoint: {len(result['checks'])} checks passed; {result['trace_frames']} replay frames.")
