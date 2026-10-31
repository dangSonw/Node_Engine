"""Verify fresh-process UI restoration, subsequent input, rollback and GPU pixels."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.core.runtime_build import fingerprint


def verify():
    build = ROOT / 'build'
    directory = ROOT / 'artifacts/validation/ui-checkpoint'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory.parent / 'ui-checkpoint-checks.json'
    source = ROOT / 'tools/ui_checkpoint_probe/main.cpp'
    report = dict(passed=False, native_fingerprint=fingerprint(),
                  probe_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), checks=[], runs=[], captures=[])
    try:
        cmake = shutil.which('cmake') or str(Path.home() / '.local/bin/cmake.exe')
        result = subprocess.run([cmake, '--build', str(build), '--target', 'node_ui_checkpoint_probe', '--parallel', '2'],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=600)
        output.with_suffix('.build.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Probe build failed; see ' + str(output.with_suffix('.build.log')))
        executable = build / ('node_ui_checkpoint_probe.exe' if os.name == 'nt' else 'node_ui_checkpoint_probe')
        report['binary_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
        for mode in ('headless', 'gpu'):
            folder = directory / mode
            folder.mkdir(exist_ok=True)
            for command in ('--self-test', '--write', '--read'):
                result = subprocess.run([str(executable), command, str(folder), *(['--gpu'] if mode == 'gpu' else [])],
                                        cwd=build, capture_output=True, text=True, encoding='utf-8', timeout=120)
                report['runs'].append(dict(mode=mode, command=command, exit_code=result.returncode,
                                          stdout=result.stdout, stderr=result.stderr))
                native = json.loads(result.stdout)
                report['checks'].extend(mode + ': ' + name for name in native['checks'])
                if result.returncode or not native['passed']:
                    raise RuntimeError(native.get('error', result.stderr))
                if command == '--write':
                    saved = (folder / 'checkpoint.json').read_bytes()
            if saved != (folder / 'checkpoint.json').read_bytes():
                raise RuntimeError('Restoration changed saved bytes')
            report['checks'].append(mode + ': saved file remains unchanged during restore')
            if mode == 'gpu':
                for name in ('0', '3', '6', '0-at-save', '3-at-save', '6-at-save'):
                    reference, restored = [(folder / f'{prefix}-{name}.bmp').read_bytes() for prefix in ('reference', 'restored')]
                    report['captures'].append(dict(cut=int(name.split('-')[0]), phase='restore' if name.endswith('at-save') else 'continued', reference_sha256=hashlib.sha256(reference).hexdigest(),
                                                  restored_sha256=hashlib.sha256(restored).hexdigest(), bytes=len(reference)))
                    if reference != restored:
                        raise RuntimeError('Restored UI GPU capture differs at cut ' + name)
                    report['checks'].append('GPU pixels match uninterrupted continuation at cut ' + name)
        headless, gpu = [json.loads((directory / mode / 'checkpoint.json').read_text('utf-8')) for mode in ('headless', 'gpu')]
        if headless != gpu:
            raise RuntimeError('Headless/GPU UI checkpoint state or continuation differs')
        report['checks'].append('Headless and GPU have identical checkpoint/continuation state')
        report['trace_frames_per_mode'] = sum(len(item['trace']) for item in headless)
        if fingerprint() != report['native_fingerprint'] or hashlib.sha256(source.read_bytes()).hexdigest() != report['probe_source_sha256']:
            raise RuntimeError('Sources changed during verification')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = verify()
    print(f"UI checkpoint: {len(result['checks'])} checks passed; {result['trace_frames_per_mode']} continuation frames per mode.")
