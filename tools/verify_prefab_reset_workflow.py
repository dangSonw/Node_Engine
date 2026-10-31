"""Verify gameplay Reset in the visible editor and in both native GPU paths."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow

artifact = ROOT / 'artifacts/validation'
source = ROOT / 'examples/prefab_reset_demo'
project = ROOT / '.cache' / ('prefab-reset-' + uuid.uuid4().hex[:8])
shutil.copytree(source, project, ignore=shutil.ignore_patterns('generated', 'build'))
assert current(ROOT / 'build/node_view.exe')
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
area = window.screen().availableGeometry()
window.resize(min(1500, area.width() - 40), min(900, area.height() - 60))
window.move(area.left() + 20, area.top() + 20)
window.show()
messages, checks = [], []
window.runtime.message.connect(messages.append)


def wait(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label)
    print('PASS ' + label, flush=True)


def command(name, **data):
    begin = len(messages)
    serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    result = messages[begin:]
    assert not any(m.get('event') == 'node_error' for m in result), result
    return result


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def colored(image):
    return sum((c.blue() > c.red() * 1.2 and c.red() > c.green() * 1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    signature = window.signature()
    check('Editor loads the gameplay Reset node', any(n['type'] == 8039 for n in window.adapter.document()['nodes']))
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    # Finish native-window embedding before observing the short damage interval.
    command('stop')
    command('play')
    pid = window.runtime.process.processId()
    observed = []
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        state = snapshot()
        observed.append(state)
        if state['frame'] >= 90:
            break
        QTest.qWait(15)
    damaged = [s for s in observed if 21 <= s['frame'] < 60]
    save_json(artifact / 'prefab-reset-observed.json', observed)
    check('Running game deletes one member and enlarges the survivor', bool(damaged) and
          all('left' not in s['entities'] and s['entities']['right']['scale'] == [1.8] * 3 for s in damaged))
    command('pause')
    restored = snapshot()
    check('Gameplay Reset restores original member IDs and transforms', restored['frame'] >= 90 and
          set(restored['entities']) == {'pair', 'left', 'right'} and
          all(restored['entities'][eid]['scale'] == [1, 1, 1] for eid in ('left', 'right')))
    check('Reset preserves the runtime process and authored document',
          window.runtime.process.processId() == pid and window.signature() == signature)
    check('Timer and game time continue through Reset', restored['time'] >= 1.5 - 1e-9 and
          restored['variables']['ticks']['value'] >= 6 and len(restored['timers']) == 1)
    check('Start and queued custom event each execute exactly once',
          restored['logs'].count('Timer started; reset at frame 60') == 1 and
          restored['logs'].count('Queued event survived Reset') == 1)
    check('Restored child regains real Flecs inheritance',
          restored['prefab_state']['entities']['left']['base'] == {'asset': 'robot_pair', 'local': 'left'} and
          restored['prefab_state']['entities']['left']['owned_components'] == [])
    command('frame_scene')
    window.frame_all()
    window.raise_()
    window.activateWindow()
    QTest.qWait(250)
    compositor_pixels = colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Embedded native viewport displays restored Blockbench geometry', compositor_pixels > 50)
    window.screen().grabWindow(int(window.winId())).save(str(artifact / 'prefab-reset-desktop.png'))
    command('stop')
    stopped = snapshot()
    check('Stop resets game time, timers and variables', stopped['frame'] == 0 and not stopped['timers'] and
          stopped['variables']['ticks']['value'] == 0 and len(stopped['entities']) == 3)
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    check('Gameplay Reset project saves', window.save_project())
    window.open_project(project / 'project.json')
    check('Reopen retains Reset graph and original scene', window.signature() == signature)

    parity = {}
    for frames in (30, 90):
        states, bitmaps = {}, {}
        for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
            prefix = artifact / f'prefab-reset-{mode}-{frames}'
            args = [str(ROOT / 'build' / exe), '--project-root', str(source), '--frames', str(frames),
                    '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview':
                args += ['--ir', str(source / 'generated/game.ir.json')]
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=40)
            check(f'{mode} executes {frames} GPU frames', result.returncode == 0)
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
        check(f'{frames}-frame preview and export states match', states['preview'] == states['compiled'])
        check(f'{frames}-frame GPU images match byte-for-byte', bitmaps['preview'] == bitmaps['compiled'])
        state = states['compiled']
        check(f'{frames}-frame timer count is continuous', state['variables']['ticks']['value'] == frames // 15)
        if frames == 30:
            check('Export displays damaged instance before Reset', 'left' not in state['entities'] and
                  state['entities']['right']['scale'] == [1.8] * 3)
        else:
            check('Export restores both robots and delivers the queued event', len(state['entities']) == 3 and
                  state['entities']['right']['scale'] == [1, 1, 1] and
                  state['logs'].count('Queued event survived Reset') == 1)
        image = QImage(str(artifact / f'prefab-reset-compiled-{frames}.bmp'))
        check(f'{frames}-frame exported GPU image contains geometry', colored(image) > 50)
        image.save(str(artifact / f'prefab-reset-compiled-{frames}.png'))
        parity[str(frames)] = {'state_equal': True, 'bitmap_sha256': hashlib.sha256(bitmaps['compiled']).hexdigest()}
    check('No runtime node errors occurred', not any(m.get('event') == 'node_error' for m in messages))
    save_json(artifact / 'prefab-reset-workflow-checks.json', dict(passed=True, checks=checks, parity=parity,
        project=str(project / 'project.json'), compositor_pixels=compositor_pixels, restored=restored))
finally:
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature()
    window.document_changed()
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
