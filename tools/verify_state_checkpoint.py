"""Exercise native checkpoint restore across process exit, including PCM continuation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.core.runtime_build import fingerprint


def verify():
    build = ROOT / 'build'
    directory = ROOT / 'artifacts/validation/state-checkpoint'
    directory.mkdir(parents=True, exist_ok=True)
    output = directory.parent / 'state-checkpoint-checks.json'
    source = ROOT / 'tools/state_probe/main.cpp'
    report = dict(passed=False, native_fingerprint=fingerprint(),
                  probe_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), checks=[], runs=[])
    try:
        cmake = shutil.which('cmake') or str(Path.home() / '.local/bin/cmake.exe')
        result = subprocess.run([cmake, '--build', str(build), '--target', 'node_state_probe', '--parallel', '2'],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=600)
        output.with_suffix('.build.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Probe build failed; see ' + str(output.with_suffix('.build.log')))
        executable = build / ('node_state_probe.exe' if os.name == 'nt' else 'node_state_probe')
        report['binary_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
        assets = directory / 'assets'
        assets.mkdir(exist_ok=True)
        for name, rate, frames in [('tone', 48000, 5000), ('resample', 44100, 7000), ('short', 48000, 13),
                                  ('low', 22050, 3011), ('high', 96000, 10003)]:
            with wave.open(str(assets / (name + '.wav')), 'wb') as wav:
                wav.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
                wav.writeframes(b''.join(struct.pack('<hh', i * 97 % 24000 - 12000, i * 131 % 16000 - 8000)
                                         for i in range(frames)))
        shutil.copy2(ROOT / 'deps/SDL3_mixer-3.2.4/x86_64-w64-mingw32/libexec/installed-examples/SDL3_mixer/music.mp3', assets / 'music.mp3')

        def run(command):
            result = subprocess.run([str(executable), command, str(directory)], cwd=build,
                                    capture_output=True, text=True, encoding='utf-8', timeout=120)
            report['runs'].append(dict(command=command, exit_code=result.returncode,
                                       stdout=result.stdout, stderr=result.stderr))
            native = json.loads(result.stdout)
            report['checks'].extend(native['checks'])
            if result.returncode or not native['passed']:
                raise RuntimeError(result.stderr or result.stdout)

        run('--self-test')
        run('--write')
        saved = (directory / 'checkpoint.json').read_bytes()
        run('--read')
        if saved != (directory / 'checkpoint.json').read_bytes():
            raise RuntimeError('Restore changed saved file bytes')
        report['checks'].append('Restoration leaves saved file bytes unchanged')
        report['pcm'] = []
        for item in json.loads(saved):
            cut = item['cut']
            reference, restored = [(directory / f'{kind}-{cut}.wav').read_bytes() for kind in ['reference', 'restored']]
            report['pcm'].append(dict(cut=cut, reference_sha256=hashlib.sha256(reference).hexdigest(),
                                      restored_sha256=hashlib.sha256(restored).hexdigest(), bytes=len(reference)))
            if reference != restored:
                raise RuntimeError(f'Audio continuation differs from uninterrupted PCM at cut {cut}')
            report['checks'].append(f'Fresh-process PCM equals uninterrupted output byte-for-byte at cut {cut}')
        report['checkpoint_sha256'] = hashlib.sha256(saved).hexdigest()
        report['checkpoint_bytes'] = len(saved)
        report['trace_frames'] = sum(len(item['trace']) for item in json.loads(saved))
        if report['native_fingerprint'] != fingerprint() or report['probe_source_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise RuntimeError('Sources changed during verification')
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    report = verify()
    print(f"State checkpoint: {len(report['checks'])} checks passed; {report['trace_frames']} continuation frames.")
