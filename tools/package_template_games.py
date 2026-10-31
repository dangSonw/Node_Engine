"""Package one verified template, then prove the relocated native game runs."""
import argparse
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
from editor.core.document import save_json
from editor.core.projects import project_child, compile_project, project_snapshot
from editor.core.runtime_build import current
from tools.verify_template_games import checked_contract, assert_state
from PySide6.QtGui import QImage


def package(project, build, verification, target):
    project = Path(project).resolve(); build = Path(build).resolve()
    verification = Path(verification).resolve(); target = Path(target).resolve()
    report = dict(passed=False, package=str(target), checks=[])
    save_json(verification / 'package-checks.json', report)
    def check(label, condition):
        assert condition, label
        report['checks'].append(label)
    evidence = json.loads((verification / 'checks.json').read_text('utf-8'))
    check('Four-host gameplay verification passed for this saved project', evidence['passed'] and evidence['project'] == str(project))
    program_digest = hashlib.sha256(json.dumps(compile_project(project_snapshot(project)), sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    check('Saved gameplay is unchanged since verification', evidence['program_sha256'] == program_digest)
    check('Gameplay contract is unchanged since verification', evidence['contract_sha256'] == hashlib.sha256((project.parent / 'acceptance.json').read_bytes()).hexdigest())
    for relative, digest in evidence['replay_sha256'].items():
        check(relative + ': replay is unchanged', hashlib.sha256(project_child(project.parent, relative).read_bytes()).hexdigest() == digest)
    check('Build is current', current(build / 'node_view.exe'))
    for mode, digest in evidence['binary_sha256'].items():
        check(mode + ': verified binary is unchanged', hashlib.sha256((build / (mode + '.exe')).read_bytes()).hexdigest() == digest)
    contract = checked_contract(project)
    case = next(s for s in contract['scenarios'] if 'scoring' in s.get('covers', []))
    if target.exists() and any(target.iterdir()):
        raise ValueError('Package output must be a new or empty directory: ' + str(target))
    target.mkdir(parents=True, exist_ok=True)
    try:
        for name in ('node_game_view.exe', 'SDL3.dll', 'SDL3_image.dll', 'SDL3_mixer.dll'):
            shutil.copy2(build / name, target / name)
        for folder in ('fonts', 'shaders', 'licenses'):
            shutil.copytree(build / folder, target / folder)
        for folder in ('assets', 'ui'):
            if (project.parent / folder).exists(): shutil.copytree(project.parent / folder, target / folder)
        shutil.copy2(project_child(project.parent, case['replay']), target / 'input-replay.json')
        (target / 'Play.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe %*\n', encoding='ascii')
        (target / 'Replay.cmd').write_text('@echo off\ncd /d "%~dp0"\nnode_game_view.exe --frames ' + str(case['frames']) + ' --input-replay input-replay.json %*\n', encoding='ascii')
        controls = contract.get('controls', 'See the editable project README for controls.')
        (target / 'README.md').write_text('# ' + project.stem + '\n\nRun Play.cmd to play.\n\n' + str(controls) + '\n\nReplay.cmd runs the supplied deterministic gameplay trace.\nThis native package requires neither Python nor Qt.\nThird-party licenses are in licenses/.\n', encoding='utf-8')
        system = Path(os.environ['SystemRoot'])
        env = dict(os.environ, PATH=str(system / 'System32') + os.pathsep + str(system))
        # A temporary copy proves independence from both the build and source locations.
        with tempfile.TemporaryDirectory(prefix='node-template-relocated-') as temporary:
            relocated = Path(temporary) / 'Trò chơi'
            shutil.copytree(target, relocated)
            for launcher in ('Play.cmd', 'Replay.cmd'):
                prefix = verification / ('relocated-package-' + Path(launcher).stem.lower())
                prefix.with_suffix('.json').unlink(missing_ok=True)
                prefix.with_suffix('.bmp').unlink(missing_ok=True)
                args = [os.environ['COMSPEC'], '/d', '/c', launcher]
                if launcher == 'Play.cmd': args += ['--frames', str(case['frames']), '--input-replay', 'input-replay.json']
                args += ['--project-root', str(relocated), '--save-root', str(Path(temporary) / ('saves-' + launcher)),
                         '--output', str(prefix.with_suffix('.json')), '--capture', str(prefix.with_suffix('.bmp'))]
                # Resolve the batch filename through cwd: cmd.exe's first-command quoting
                # rules otherwise split a quoted executable path containing spaces.
                run = subprocess.run(args, cwd=relocated, env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
                prefix.with_suffix('.log').write_text(run.stdout + run.stderr, encoding='utf-8')
                check('Relocated ' + launcher + ' runs with system-only PATH', run.returncode == 0)
                actual = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
                for assertion in case['assertions']: assert_state(actual, assertion)
                expected = json.loads((verification / (case['id'] + '-node_game_view.json')).read_text('utf-8'))
                check(launcher + ': relocated native gameplay matches the verified game', actual == expected)
                image = QImage(str(prefix.with_suffix('.bmp')))
                check(launcher + ': relocated framebuffer matches the verified game', not image.isNull() and image == QImage(str(verification / (case['id'] + '-node_game_view.bmp'))))
        report['sha256'] = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save_json(verification / 'package-checks.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--verification', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package(args.project, args.build, args.verification, args.output)
