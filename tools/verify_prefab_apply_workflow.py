"""Exercise live Apply through the visible editor, then both native GPU paths."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow

artifact = ROOT/'artifacts/validation'
source = ROOT/'examples/prefab_apply_demo'
project = ROOT/'.cache'/('prefab-apply-'+uuid.uuid4().hex[:8])
shutil.copytree(source, project, ignore=shutil.ignore_patterns('generated', 'build'))
assert current(ROOT/'build/node_view.exe')
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
window = MainWindow(project/'project.json', QSettings(str(project/'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
area = window.screen().availableGeometry()
window.resize(min(1500, area.width()-40), min(900, area.height()-60))
window.move(area.left()+20, area.top()+20); window.show()
messages, checks = [], []
window.runtime.message.connect(messages.append)


def wait(predicate, timeout=25):
    deadline = time.monotonic()+timeout
    while not predicate() and time.monotonic()<deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label); print('PASS '+label, flush=True)


def command(name, **data):
    begin = len(messages); serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    results = messages[begin:]
    assert not any(m.get('event') == 'node_error' and m.get('id') == serial for m in results), results
    return results


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def speed(state, root):
    return next(e for e in state['scene']['entities'] if e['id'] == root)['components']['1']['properties']['1']


def scale(state, root):
    return state['entities'][root+'_body']['scale']


def colored(image):
    return sum((c.blue()>c.red()*1.2 and c.red()>c.green()*1.2 and c.red()>40) or
               (c.green()>70 and c.blue()>70 and c.red()<60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    signature = window.signature()
    check('Editor loads Apply Prefab Overrides', any(n['type'] == 8040 for n in window.adapter.document()['nodes']))
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('stop'); command('play')
    pid = window.runtime.process.processId()
    observed = []
    deadline = time.monotonic()+12
    while time.monotonic()<deadline:
        state = snapshot(); observed.append(state)
        if state['frame']>=150:
            break
        QTest.qWait(15)
    command('pause'); final = snapshot()
    save_json(artifact/'prefab-apply-observed.json', observed)
    before = [s for s in observed if 21<=s['frame']<60]
    after = [s for s in observed if 61<=s['frame']<120]
    check('Gameplay edits initially affect only the left robot', bool(before) and all(
        scale(s, 'left') == [1.5]*3 and scale(s, 'middle') == [1]*3 for s in before))
    check('Apply propagates template values while preserving explicit overrides', bool(after) and all(
        scale(s, 'left') == scale(s, 'middle') == [1.5]*3 and scale(s, 'right') == [1]*3 and
        speed(s, 'left') == speed(s, 'middle') == 45 and speed(s, 'right') == 90 for s in after))
    check('Reset follows the newly applied template', final['frame']>=150 and all(
        scale(final, root) == [1.5]*3 and speed(final, root) == 45 for root in ('left', 'middle', 'right')))
    check('Live Apply and Reset preserve process and authored document',
        pid == window.runtime.process.processId() and signature == window.signature())
    check('Simulation time and owned timer continue', final['time']>=2.5-1e-9 and
        final['variables']['ticks']['value']>=10 and len(final['timers']) == 1)
    check('Queued event and On Start each run exactly once',
        final['logs'].count('Queued event survived Apply') == 1 and
        final['logs'].count('Timer started; apply at frame 60') == 1)
    check('Updated and reset bodies really inherit through Flecs IsA', all(
        final['prefab_state']['entities'][root+'_body']['base'] == {'asset': 'robot', 'local': 'e1'} and
        final['prefab_state']['entities'][root+'_body']['owned_components'] == [] for root in ('left', 'middle', 'right')))
    command('frame_scene'); window.frame_all(); window.raise_(); window.activateWindow(); QTest.qWait(250)
    compositor_pixels = colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Embedded viewport renders the updated Blockbench geometry', compositor_pixels>50)
    window.screen().grabWindow(int(window.winId())).save(str(artifact/'prefab-apply-desktop.png'))
    command('stop'); stopped = snapshot()
    check('Stop restores the authored prefab library and initial values', stopped['frame'] == 0 and not stopped['timers'] and
        all(scale(stopped, root) == [1]*3 and speed(stopped, root) == 90 for root in ('left', 'middle', 'right')))
    check('Successful workflow has no runtime node errors', not any(m.get('event') == 'node_error' for m in messages))

    # A runtime-only reference prevents Apply. Check the exact live scene after rejection.
    invalid = deepcopy(window.scene)
    target = dict(id=2, name='Target', type='entity', default='')
    invalid['component_definitions'][0]['properties'].append(target)
    invalid['prefab_assets'][0]['component_definitions'][0]['properties'].append(target)
    next(e for e in invalid['entities'] if e['id'] == 'left')['components']['1']['properties']['2'] = 'middle'
    b = GraphBuilder(component_definitions=invalid['component_definitions'])
    b.add('update', 'On Update'); b.add('bad_apply', 'Apply Prefab Overrides', Instance='left')
    b.connect('update', 'Out', 'bad_apply', 'In')
    command('load_ir', ir=compile_graph(b.graph, invalid))
    before_error = snapshot(); start_error = len(messages)
    command('play')
    wait(lambda: any(m.get('event') == 'node_error' for m in messages[start_error:]))
    failed = snapshot()
    errors = [m for m in messages[start_error:] if m.get('event') == 'node_error']
    check('Invalid Apply reports the originating graph node', len(errors) == 1 and
        errors[0]['node'] == 'bad_apply' and 'External' in errors[0]['message'])
    check('Rejected Apply preserves the exact live scene and Flecs inheritance',
        failed['scene'] == before_error['scene'] and failed['prefab_state'] == before_error['prefab_state'] and failed['frame'] == 0)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    check('Editor saves the original project after gameplay', window.save_project())
    window.open_project(project/'project.json')
    check('Reopen retains authored scene and Apply graph', window.signature() == signature)

    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(100)
    window.actions['Build Game'].trigger()
    check('Build Game starts an asynchronous worker', window.builder.busy)
    wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact/'prefab-apply-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor builds the Apply project while remaining responsive', results == [True] and len(ticks)>5)
    check('Build packages the Blockbench mesh and current runtime', current(project/'build/node_view.exe') and
        (project/'build/assets/robot.gltf').read_bytes() == (source/'assets/robot.gltf').read_bytes())

    parity = {}
    for frames in (30, 90, 150):
        states, bitmaps = {}, {}
        for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
            prefix = artifact/f'prefab-apply-{mode}-{frames}'
            args = [str(project/'build'/exe), '--frames', str(frames),
                    '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview':
                args += ['--ir', str(project/'generated/game.ir.json')]
            run = subprocess.run(args, cwd=project/'build', capture_output=True, text=True, encoding='utf-8', timeout=40)
            check(f'{mode} runs {frames} GPU frames', run.returncode == 0)
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
        state = states['compiled']
        check(f'{frames}-frame preview and export states match', states['preview'] == state)
        check(f'{frames}-frame GPU images match byte-for-byte', bitmaps['preview'] == bitmaps['compiled'])
        check(f'{frames}-frame timer continues across Apply and Reset', state['variables']['ticks']['value'] == frames//15)
        expected_scale = {'left': 1.5, 'middle': 1.5 if frames>60 else 1, 'right': 1.5 if frames>120 else 1}
        expected_speed = {'left': 45, 'middle': 45 if frames>60 else 90, 'right': 45 if frames>120 else 90}
        check(f'{frames}-frame exported game has correct propagated and pinned values', all(
            scale(state, root) == [expected_scale[root]]*3 and speed(state, root) == expected_speed[root] for root in expected_scale))
        image = QImage(str(artifact/f'prefab-apply-compiled-{frames}.bmp'))
        check(f'{frames}-frame exported image contains geometry', colored(image)>50)
        image.save(str(artifact/f'prefab-apply-compiled-{frames}.png'))
        parity[str(frames)] = dict(state_equal=True, bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest())
    save_json(artifact/'prefab-apply-workflow-checks.json', dict(passed=True, checks=checks,
        project=str(project/'project.json'), compositor_pixels=compositor_pixels, heartbeat_ticks=len(ticks), parity=parity, final=final))
finally:
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
