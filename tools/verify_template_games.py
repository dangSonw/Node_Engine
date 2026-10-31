"""Verify saved game templates against explicit native gameplay scenarios."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from editor.core.document import save_json
from editor.core.projects import compile_project, project_snapshot, project_child
from editor.core.runtime_build import current, fingerprint
from PySide6.QtGui import QImage

REQUIRED = {
    'flappy_bird': {'scoring', 'death', 'restart'},
    'isometric_snake_3d': {'scoring', 'growth', 'wall_collision', 'self_collision', 'restart'},
}
MODES = ('node_preview', 'node_game', 'node_view', 'node_game_view')


def checked_contract(project):
    contract = json.loads((project.parent / 'acceptance.json').read_text('utf-8'))
    if contract.get('version') != 1 or not isinstance(contract.get('scenarios'), list):
        raise ValueError('acceptance.json requires version 1 and scenarios array')
    covered = set(); ids = set()
    for case in contract['scenarios']:
        name = case.get('id')
        if not isinstance(name, str) or not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name) or name in ids:
            raise ValueError('Scenario IDs must be unique lowercase file-safe names')
        ids.add(name)
        if type(case.get('frames')) is not int or not 1 <= case['frames'] <= 10000:
            raise ValueError(name + ': frames must be 1..10000 (graphical frames=0 means unlimited play)')
        replay = project_child(project.parent, case['replay'])
        trace = json.loads(replay.read_text('utf-8'))
        if trace.get('version') != 1 or not isinstance(trace.get('events'), list):
            raise ValueError(name + ': invalid input replay')
        assertions = case.get('assertions')
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(name + ': explicit state assertions are required')
        for assertion in assertions:
            if not isinstance(assertion.get('path'), (str, list)) or assertion.get('op') not in ('eq', 'ne', 'gt', 'ge', 'lt', 'le', 'len_eq', 'len_ge', 'contains') or 'value' not in assertion:
                raise ValueError(name + ': invalid state assertion')
        tags = case.get('covers', [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(name + ': covers requires an array of strings')
        covered.update(tags)
        if set(tags) & {'scoring', 'growth', 'restart'}:
            if type(case.get('before_frames')) is not int or not 1 <= case['before_frames'] < case['frames']:
                raise ValueError(name + ': scoring/growth/restart requires before_frames earlier than frames')
    missing = REQUIRED[project.stem] - covered
    if missing:
        raise ValueError('Missing gameplay scenarios: ' + ', '.join(sorted(missing)))
    return contract


def state_value(state, path):
    keys = path.split('.') if isinstance(path, str) else path
    actual = state
    for key in keys:
        actual = actual[int(key)] if isinstance(actual, list) else actual[key]
    if isinstance(actual, dict) and set(actual) == {'type', 'value'}:
        actual = actual['value']
    return actual


def assert_state(state, assertion):
    path = assertion['path']
    actual = state_value(state, path)
    expected = assertion['value']; op = assertion['op']
    if op == 'eq': okay = actual == expected
    elif op == 'ne': okay = actual != expected
    elif op == 'gt': okay = actual > expected
    elif op == 'ge': okay = actual >= expected
    elif op == 'lt': okay = actual < expected
    elif op == 'le': okay = actual <= expected
    elif op == 'len_eq': okay = len(actual) == expected
    elif op == 'len_ge': okay = len(actual) >= expected
    elif op == 'contains': okay = expected in actual
    else: raise ValueError('Unknown assertion operator: ' + op)
    assert okay, f'{path}: got {actual!r}, expected {op} {expected!r}'


def assert_gameplay(contract, case, after, before=None):
    """Coverage labels need measured transitions, rather than self-reported tags."""
    paths = dict(score='variables.score', alive='variables.alive', ticks='variables.steps',
                 resets='variables.resets', body='variables.snake', reason='variables.status')
    paths.update(contract.get('state_paths', {}))
    def read(state, name): return state_value(state, paths[name])
    for tag in case.get('covers', []):
        if tag in ('scoring', 'growth'):
            assert before is not None and read(after, 'score') > read(before, 'score'), tag + ': score must increase'
            assert read(after, 'ticks') > read(before, 'ticks'), tag + ': simulation must advance'
            if tag == 'growth':
                assert len(read(after, 'body')) > len(read(before, 'body')), 'growth: actual body must grow'
        elif tag in ('death', 'wall_collision', 'self_collision'):
            assert read(after, 'alive') is False, tag + ': player must be dead'
            assert read(after, 'ticks') > 0, tag + ': simulation must have advanced'
            reason = read(after, 'reason')
            assert isinstance(reason, str) and reason, tag + ': a death reason must be recorded'
            if tag != 'death':
                default = 'WALL HIT  /  R TO RESTART' if tag == 'wall_collision' else 'SELF COLLISION  /  R TO RESTART'
                expected = contract.get('death_reasons', {}).get(tag, default)
                assert reason == expected, tag + ': incorrect collision reason'
        elif tag == 'restart':
            assert before is not None and read(before, 'alive') is False, 'restart: observe a dead round before reset'
            assert read(after, 'alive') is True and read(after, 'score') == 0, 'restart: restore alive state and zero score'
            assert read(after, 'resets') > read(before, 'resets'), 'restart: reset counter must increase'
            assert read(after, 'ticks') < read(before, 'ticks'), 'restart: round tick count must reset'


def verify(project, build, output):
    project = Path(project).resolve(); build = Path(build).resolve(); output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = dict(passed=False, project=str(project), build=str(build), checks=[], native_fingerprint=fingerprint(), run_id=uuid.uuid4().hex)
    # Replace a previous success before any process runs, so interruption cannot leave a green report.
    save_json(output / 'checks.json', report)
    def check(label, condition):
        assert condition, label
        report['checks'].append(label)
        print('PASS ' + label, flush=True)
    try:
        contract = checked_contract(project)
        program = compile_project(project_snapshot(project))
        report['program_sha256'] = hashlib.sha256(json.dumps(program, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        ir = project.parent / 'generated/game.ir.json'
        check('Generated IR equals the saved .nen project', json.loads(ir.read_text('utf-8')) == program)
        check('Native build matches current source files', current(build / 'node_view.exe'))
        report['contract_sha256'] = hashlib.sha256((project.parent / 'acceptance.json').read_bytes()).hexdigest()
        report['replay_sha256'] = {}
        for case in contract['scenarios']:
            states = []; images = []; before_states = []
            replay = project_child(project.parent, case['replay'])
            report['replay_sha256'][case['replay']] = hashlib.sha256(replay.read_bytes()).hexdigest()
            for mode in MODES:
                prefix = output / (case['id'] + '-' + mode)
                args = [str(build / (mode + '.exe')), '--frames', str(case['frames']),
                        '--project-root', str(project.parent), '--input-replay', str(replay),
                        '--save-root', str(output / 'saves' / report['run_id'] / case['id'] / mode),
                        '--output', str(prefix.with_suffix('.json'))]
                if mode in ('node_preview', 'node_view'): args += ['--ir', str(ir)]
                graphical = mode in ('node_view', 'node_game_view')
                if graphical: args += ['--capture', str(prefix.with_suffix('.bmp'))]
                # A successful process that fails to write output must not reuse old evidence.
                prefix.with_suffix('.json').unlink(missing_ok=True)
                prefix.with_suffix('.bmp').unlink(missing_ok=True)
                run = subprocess.run(args, cwd=project.parent, text=True, encoding='utf-8', capture_output=True, timeout=120)
                prefix.with_suffix('.log').write_text(run.stdout + run.stderr, encoding='utf-8')
                check(case['id'] + ': ' + mode + ' exits successfully', run.returncode == 0)
                state = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
                for assertion in case['assertions']: assert_state(state, assertion)
                before = None
                if 'before_frames' in case:
                    before_prefix = output / (case['id'] + '-before-' + mode)
                    before_args = args.copy()
                    before_args[before_args.index('--frames') + 1] = str(case['before_frames'])
                    before_args[before_args.index('--output') + 1] = str(before_prefix.with_suffix('.json'))
                    before_args[before_args.index('--save-root') + 1] += '-before'
                    if graphical: before_args[before_args.index('--capture') + 1] = str(before_prefix.with_suffix('.bmp'))
                    before_prefix.with_suffix('.json').unlink(missing_ok=True)
                    before_prefix.with_suffix('.bmp').unlink(missing_ok=True)
                    observed = subprocess.run(before_args, cwd=project.parent, text=True, encoding='utf-8', capture_output=True, timeout=120)
                    before_prefix.with_suffix('.log').write_text(observed.stdout + observed.stderr, encoding='utf-8')
                    check(case['id'] + ': ' + mode + ' observes the earlier round', observed.returncode == 0)
                    before = json.loads(before_prefix.with_suffix('.json').read_text('utf-8'))
                    for assertion in case.get('before_assertions', []): assert_state(before, assertion)
                    before_states.append(before)
                assert_gameplay(contract, case, state, before)
                check(case['id'] + ': ' + mode + ' satisfies gameplay assertions', True)
                states.append(state)
                if graphical:
                    image = QImage(str(prefix.with_suffix('.bmp')))
                    check(case['id'] + ': ' + mode + ' captures framebuffer', not image.isNull())
                    images.append(image)
            check(case['id'] + ': complete states match across four native hosts', all(s == states[0] for s in states))
            if before_states: check(case['id'] + ': before states match across four native hosts', all(s == before_states[0] for s in before_states))
            check(case['id'] + ': interpreted and compiled GPU pixels match', images[0] == images[1])
        check('Native sources stayed unchanged during verification', report['native_fingerprint'] == fingerprint())
        report['binary_sha256'] = {mode: hashlib.sha256((build / (mode + '.exe')).read_bytes()).hexdigest() for mode in MODES}
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        save_json(output / 'checks.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verify(args.project, args.build, args.output)
