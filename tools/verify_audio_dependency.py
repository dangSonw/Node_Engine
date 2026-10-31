"""Build and run the pinned SDL_mixer probe with only staged DLLs on Windows."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'artifacts/validation'
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / '.cache/audio-dependency-probe'
    work.mkdir(parents=True, exist_ok=True)
    compilers = sorted((Path(os.environ['LOCALAPPDATA']) / 'Programs').glob('llvm-mingw-*/bin/clang++.exe'))
    if not compilers: raise RuntimeError('LLVM-MinGW compiler is required')
    sdl = ROOT / 'deps/SDL3-3.4.18/x86_64-w64-mingw32'
    mix = ROOT / 'deps/SDL3_mixer-3.2.4/x86_64-w64-mingw32'
    exe = work / 'audio-probe.exe'
    args = [str(compilers[-1]), '-std=c++20', '-O2', '-Wall', '-Wextra', '-static',
        str(ROOT / 'tools/audio_dependency_probe.cpp'), '-I'+str(ROOT / 'deps/include'),
        '-I'+str(sdl / 'include'), '-I'+str(mix / 'include'),
        str(mix / 'lib/libSDL3_mixer.dll.a'), str(sdl / 'lib/libSDL3.dll.a'), '-o', str(exe)]
    build = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=120)
    (output / 'audio-dependency-build.log').write_text(build.stdout+build.stderr, 'utf-8')
    if build.returncode: raise RuntimeError(build.stdout+build.stderr)
    shutil.copy2(sdl / 'bin/SDL3.dll', work / 'SDL3.dll')
    shutil.copy2(mix / 'bin/SDL3_mixer.dll', work / 'SDL3_mixer.dll')
    with wave.open(str(work / 'fixture.wav'), 'wb') as wav:
        wav.setparams((2, 2, 48000, 1024, 'NONE', 'not compressed'))
        wav.writeframes(struct.pack('<hh',8192,4096)*1024)
    system = Path(os.environ['SystemRoot'])
    clean = dict(os.environ, PATH=str(system/'System32')+os.pathsep+str(system))
    report = output / 'audio-dependency-checks.json'
    run = subprocess.run([str(exe), str(work/'fixture.wav'), str(report)], cwd=work, env=clean,
        capture_output=True, text=True, encoding='utf-8', timeout=30)
    (output / 'audio-dependency-run.log').write_text(run.stdout+run.stderr, 'utf-8')
    if run.returncode: raise RuntimeError(run.stdout+run.stderr)
    data = json.loads(report.read_text('utf-8'))
    assert data['passed'] and len(data['checks'])==9
    print(json.dumps(data, indent=2))


if __name__ == '__main__': main()
