"""Real Qt camera editing, native preview switching and packaged GPU parity."""
from pathlib import Path
from copy import deepcopy
import ctypes
from ctypes import wintypes
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton
from editor.core.document import save_json
from editor.core.compiler import compile_graph
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.scene import entity
from editor.ui.main_window import MainWindow, SearchDialog
from editor.ui.camera import CameraDialog

artifact = ROOT / 'artifacts/validation'
project = ROOT / '.cache' / ('camera-' + uuid.uuid4().hex[:8])
shutil.copytree(ROOT / 'examples/camera_demo', project, ignore=shutil.ignore_patterns('build', 'generated'))
assert current(ROOT / 'build/node_view.exe')
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
window.resize(1600, 960)
window.show()
messages, checks, held = [], [], set()
window.runtime.message.connect(messages.append)
user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]


def wait(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText() + '\n' + window.build_output.toPlainText()


def check(label, condition):
    assert condition, label
    checks.append(label)
    print('PASS ' + label, flush=True)


def command(name, expected_error=False, **data):
    begin = len(messages)
    serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    response = messages[begin:]
    assert any(m.get('event') == 'node_error' for m in response) == expected_error, response
    return response


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def capture(label):
    path = artifact / f'camera-{label}.bmp'
    begin = len(messages)
    command('capture', path=str(path))
    wait(lambda: any(m.get('event') == 'capture_done' and m.get('path') == str(path) for m in messages[begin:]))
    image = QImage(str(path))
    assert not image.isNull()
    image.save(str(path.with_suffix('.png')))
    return image


def colored(image):
    return sum((c.blue() > c.red() * 1.2 and c.red() > c.green() * 1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


def focus_view():
    window.raise_(); window.activateWindow()
    wait(lambda: user32.GetForegroundWindow() == int(window.winId()))
    hwnd = next(m['handle'] for m in reversed(messages) if m.get('event') == 'window_handle')
    rect = wintypes.RECT()
    assert user32.GetWindowRect(hwnd, ctypes.byref(rect))
    user32.SetCursorPos((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    user32.mouse_event(2, 0, 0, 0, 0); user32.mouse_event(4, 0, 0, 0, 0)
    QTest.qWait(80)


def button(vk, down):
    assert user32.GetForegroundWindow() == int(window.winId())
    user32.keybd_event(vk, 0, 0 if down else 2, 0)
    held.add(vk) if down else held.discard(vk)
    QTest.qWait(60)


def edit_lens():
    def edit():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, CameraDialog)
        dialog.projection.setCurrentText('orthographic')
        field = dialog.fields['size']
        field.setFocus(); QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(field, '7')
        QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok), Qt.MouseButton.LeftButton)
    QTimer.singleShot(30, edit)
    QTest.mouseClick(next(b for b in window.inspector.findChildren(QPushButton) if b.text() == 'Edit Camera…'), Qt.MouseButton.LeftButton)


try:
    check('Camera graph validates in editor', window.validate_graph())
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state == 'running' and window.container is not None)
    pid = window.runtime.process.processId()
    command('pause')
    original = capture('perspective')
    check('Selected game camera renders Blockbench robots', colored(original) > 50 and snapshot()['scene']['active_camera'] == 'camera')
    command('play'); focus_view()
    before = snapshot()
    button(ord('D'), True); QTest.qWait(280); button(ord('D'), False)
    moved = snapshot()
    check('Physical keyboard moves robot and following camera', moved['entities']['player']['position'][0] > before['entities']['player']['position'][0] + .3 and moved['entities']['camera']['position'][0] > before['entities']['camera']['position'][0] + .1)
    button(ord('C'), True); button(ord('C'), False)
    check('Physical C key switches game lens to orthographic', entity(snapshot()['scene'], 'camera')['camera']['projection'] == 'orthographic')
    command('pause')
    ortho = capture('orthographic')
    check('Orthographic view renders a different valid image', ortho != original and colored(ortho) > 50)
    before = snapshot()
    window.actions['Game Camera'].trigger()
    orbit = capture('editor-orbit')
    check('View menu switches to free editor camera without changing game state', orbit != ortho and snapshot() == before)
    window.actions['Game Camera'].trigger()
    check('Returning to game camera restores identical pixels', capture('restored') == ortho)
    # End preview mutations and exercise real authoring on a fresh camera.
    command('stop')
    window.actions['Create Camera'].trigger()
    wait(lambda: window.reload_request is None)
    created = window.selected_entity_id()
    check('Scene menu creates an undoable camera entity', entity(window.scene, created)['camera']['projection'] == 'perspective')
    edit_lens()
    wait(lambda: window.reload_request is None)
    check('Camera dialog edits projection and lens through widgets', entity(window.scene, created)['camera']['size'] == 7 and entity(window.scene, created)['camera']['projection'] == 'orthographic')
    QTest.mouseClick(next(b for b in window.inspector.findChildren(QPushButton) if b.text() == 'Use as Game Camera'), Qt.MouseButton.LeftButton)
    wait(lambda: window.reload_request is None)
    check('Choosing active camera reloads the same native process', snapshot()['scene']['active_camera'] == created and window.runtime.process.processId() == pid)
    window.actions['Undo'].trigger(); wait(lambda: window.reload_request is None)
    check('Undo restores previous active camera in native scene', snapshot()['scene']['active_camera'] == 'camera')
    window.actions['Redo'].trigger(); wait(lambda: window.reload_request is None)
    check('Redo restores chosen active camera', snapshot()['scene']['active_camera'] == created)
    window.actions['Delete Entity'].trigger(); wait(lambda: window.reload_request is None)
    check('Deleting active camera clears its scene reference', 'active_camera' not in snapshot()['scene'])
    window.actions['Undo'].trigger(); wait(lambda: window.reload_request is None)
    check('Undo deletion restores camera settings and selection', snapshot()['scene']['active_camera'] == created and entity(snapshot()['scene'], created)['camera']['size'] == 7)
    def choose():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, SearchDialog)
        dialog.search.setText('Following camera')
        QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    QTimer.singleShot(30, choose)
    window.actions['Choose Active Camera…'].trigger(); wait(lambda: window.reload_request is None)
    check('Camera chooser selects the authored follow camera', snapshot()['scene']['active_camera'] == 'camera')
    command('play'); QTest.qWait(80); command('pause')
    window.screen().grabWindow(int(window.winId())).save(str(artifact / 'camera-desktop.png'))
    before = snapshot()
    invalid = deepcopy(compile_graph(window.adapter.document(), window.scene))
    entity(invalid['scene'], 'camera')['camera']['near'] = 2000
    command('load_ir', expected_error=True, ir=invalid)
    check('Malformed camera reload preserves running world', snapshot() == before)
    inactive = deepcopy(compile_graph(window.adapter.document(), window.scene))
    entity(inactive['scene'], 'camera')['active'] = False
    command('load_ir', ir=inactive)
    check('Inactive selected camera renders an empty view', colored(capture('inactive')) == 0)
    command('load_ir', ir=compile_graph(window.adapter.document(), window.scene)); command('play'); command('pause')
    check('Camera project saves', window.save_project())
    signature = window.signature()
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.open_project(project / 'project.json')
    check('Reopen preserves camera settings, selected camera and graph', window.signature() == signature)
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(100)
    window.actions['Build Game'].trigger()
    wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact / 'camera-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor builds packaged camera game with responsive UI', results == [True] and len(ticks) > 5)
    build = project / 'build'
    digests = {}
    for projection in ('perspective', 'orthographic'):
        replay = json.loads((project / 'input-replay.json').read_text('utf-8'))
        if projection == 'orthographic':
            replay['events'] += [{'frame': 25, 'button': 'C', 'down': True}, {'frame': 26, 'button': 'C', 'down': False}]
        replay_path = project / f'{projection}-replay.json'
        save_json(replay_path, replay)
        states, bitmaps = {}, {}
        for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
            prefix = artifact / f'camera-{projection}-{mode}'
            args = [str(build / exe), '--frames', '30', '--input-replay', str(replay_path),
                    '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview': args += ['--ir', str(project / 'generated/game.ir.json')]
            run = subprocess.run(args, cwd=build, capture_output=True, text=True, encoding='utf-8', timeout=40)
            check(projection + ' ' + mode + ' runs packaged assets', run.returncode == 0)
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
        check(projection + ' preview/export states match', states['preview'] == states['compiled'])
        check(projection + ' preview/export GPU bitmaps match', bitmaps['preview'] == bitmaps['compiled'])
        check(projection + ' uses requested lens', entity(states['compiled']['scene'], 'camera')['camera']['projection'] == projection)
        check(projection + ' follows moving player', states['compiled']['entities']['camera']['position'][0] > .3 and all(abs(a-b) < 1e-9 for a, b in zip(states['compiled']['entities']['player']['position'], [.5, 0, -.5])))
        image = QImage(str(artifact / f'camera-{projection}-compiled.bmp'))
        check(projection + ' packaged game visibly renders robots', colored(image) > 50)
        image.save(str(artifact / f'camera-{projection}-compiled.png'))
        digests[projection] = hashlib.sha256(bitmaps['compiled']).hexdigest()
    check('Two projections have distinct GPU images', digests['perspective'] != digests['orthographic'])
    check('Only deliberate malformed reload reports an error', len([m for m in messages if m.get('event') == 'node_error']) == 1)
    save_json(artifact / 'camera-workflow-checks.json', dict(passed=True, checks=checks, project=str(project),
        heartbeat_ticks=len(ticks), bitmap_sha256=digests))
finally:
    for vk in held: user32.keybd_event(vk, 0, 2, 0)
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
