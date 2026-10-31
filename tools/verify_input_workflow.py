"""Actual Windows keyboard/mouse focus, Qt authoring and GPU replay parity."""
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
from PySide6.QtCore import QEvent, QPoint, QSettings, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from editor.core.document import save_json
from editor.core.compiler import compile_graph
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow
from editor.ui.input import InputDialog

artifact = ROOT / 'artifacts/validation'
project = ROOT / '.cache' / ('input-' + uuid.uuid4().hex[:8])
shutil.copytree(ROOT / 'examples/input_demo', project, ignore=shutil.ignore_patterns('build', 'generated'))
assert current(ROOT / 'build/node_view.exe')
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
window.resize(1600, 960)
window.show()
messages, checks, saves = [], [], []
window.runtime.message.connect(messages.append)
window.actions['Save'].triggered.connect(lambda: saves.append(time.monotonic()))
user32 = ctypes.windll.user32
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
held = set()
class GuiInfo(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('active', wintypes.HWND), ('focus', wintypes.HWND), ('capture', wintypes.HWND),
                ('menu', wintypes.HWND), ('move', wintypes.HWND), ('caret', wintypes.HWND), ('rect', wintypes.RECT)]


def wait(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText() + '\n' + window.build_output.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label)
    print('PASS ' + label, flush=True)


def command(name, expected_error=False, **data):
    begin = len(messages)
    serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    result = messages[begin:]
    assert any(m.get('event') == 'node_error' for m in result) == expected_error, result
    return result


def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def button(vk, down):
    assert user32.GetForegroundWindow() == int(window.winId()), 'Editor must own foreground before OS input'
    user32.keybd_event(vk, 0, 0 if down else 2, 0)
    if down:
        held.add(vk)
    else:
        held.discard(vk)
    QTest.qWait(45)


def key(vk):
    button(vk, True)
    button(vk, False)


def shortcut(vk):
    button(0x11, True)
    key(vk)
    button(0x11, False)


def focus_view():
    window.raise_()
    window.activateWindow()
    wait(lambda: user32.GetForegroundWindow() == int(window.winId()))
    hwnd = next(m['handle'] for m in reversed(messages) if m.get('event') == 'window_handle')
    rect = wintypes.RECT()
    assert user32.GetWindowRect(hwnd, ctypes.byref(rect))
    user32.SetCursorPos((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    user32.mouse_event(2, 0, 0, 0, 0)
    user32.mouse_event(4, 0, 0, 0, 0)
    QTest.qWait(100)
    info = GuiInfo(); info.cbSize = ctypes.sizeof(info)
    assert user32.GetGUIThreadInfo(0, ctypes.byref(info))
    assert info.focus == hwnd, 'Click must give the native viewport keyboard focus'


def edit_bindings():
    def edit():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, InputDialog)
        row = next(r for r in range(dialog.table.rowCount()) if dialog.table.item(r, 1).text() == 'reset')
        combo = dialog.table.cellWidget(row, 3)
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_T)
        assert combo.currentText() == 'T'
        QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
    QTimer.singleShot(30, edit)
    window.actions['Input Actions and Axes…'].trigger()


def colored(image):
    return sum((c.blue() > c.red() * 1.2 and c.red() > c.green() * 1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    pid = window.runtime.process.processId()
    edit_bindings()
    wait(lambda: window.reload_request is None)
    check('Keyboard edits binding through the real dialog', window.scene['input']['actions']['reset'] == ['T'])
    check('Preview reload receives edited bindings in the same process', snapshot()['scene']['input'] == window.scene['input'] and window.runtime.process.processId() == pid)
    focus_view()
    initial = snapshot()
    button(ord('D'), True)
    QTest.qWait(240)
    moved = snapshot()
    check('Real focused keyboard moves the Blockbench robot', moved['variables']['horizontal'] == 1 and moved['entities']['player']['position'][0] > initial['entities']['player']['position'][0] + .3)
    button(ord('A'), True)
    check('Opposing physical keys cancel the axis', snapshot()['variables']['horizontal'] == 0)
    button(ord('D'), False)
    check('Releasing one opposing key restores the other direction', snapshot()['variables']['horizontal'] == -1)
    button(ord('A'), False)
    baseline = snapshot()['variables']
    button(0x20, True)
    QTest.qWait(650)
    state = snapshot()['variables']
    check('Holding Space and OS repeat produce only one action press', state['turn_count'] == baseline['turn_count'] + 1 and state['turn_held']['value'])
    user32.mouse_event(2, 0, 0, 0, 0)
    QTest.qWait(60)
    button(0x20, False)
    state = snapshot()['variables']
    check('Mouse button maintains the same action after Space release', state['turn_held']['value'] and state['release_count'] == baseline['release_count'])
    user32.mouse_event(4, 0, 0, 0, 0)
    QTest.qWait(70)
    state = snapshot()['variables']
    check('Last bound button release produces one action release', not state['turn_held']['value'] and state['release_count'] == baseline['release_count'] + 1)
    shortcut(ord('S'))
    check('Ctrl+S in native viewport does not trigger editor Save', not saves)
    button(ord('D'), True)
    key(0x1B)
    wait(lambda: any(m.get('event') == 'release_focus' for m in messages))
    check('Escape clears held gameplay input', snapshot()['variables']['horizontal'] == 0)
    at_escape = snapshot()['entities']['player']['position']
    QTest.qWait(180)
    check('Robot stays still after focus release with D physically held', snapshot()['entities']['player']['position'] == at_escape)
    button(ord('D'), False)
    shortcut(ord('S'))
    check('Ctrl+S works after Escape returns focus to Qt', len(saves) == 1 and not window.dirty)
    shortcut(ord('Z'))
    wait(lambda: window.reload_request is None)
    check('Qt Undo restores the binding and native scene', window.scene['input']['actions']['reset'] == ['R'] and snapshot()['scene']['input'] == window.scene['input'])
    window.actions['Redo'].trigger()
    wait(lambda: window.reload_request is None)
    check('Redo restores the authored binding', snapshot()['scene']['input']['actions']['reset'] == ['T'])
    focus_view()
    button(ord('D'), True)
    point = window.hierarchy.viewport().mapToGlobal(QPoint(30, 30))
    user32.SetCursorPos(point.x(), point.y())
    user32.mouse_event(2, 0, 0, 0, 0)
    user32.mouse_event(4, 0, 0, 0, 0)
    QTest.qWait(120)
    check('Clicking a Qt panel clears input on native focus loss', snapshot()['variables']['horizontal'] == 0)
    button(ord('D'), False)
    focus_view()
    button(ord('D'), True)
    command('pause')
    button(ord('D'), False)
    command('play')
    QTest.qWait(100)
    check('Pause/resume discards stale held input', snapshot()['variables']['horizontal'] == 0)
    key(ord('T'))
    check('Rebound reset action restores robot origin', snapshot()['entities']['player']['position'] == [0, 0, 0])
    command('pause')
    before = snapshot()
    invalid = deepcopy(compile_graph(window.adapter.document(), window.scene))
    invalid['scene']['input']['actions']['turn'] = ['Unknown button']
    command('load_ir', expected_error=True, ir=invalid)
    check('Malformed input reload fails without replacing live world', snapshot() == before)
    command('frame_scene')
    window.screen().grabWindow(int(window.winId())).save(str(artifact / 'input-desktop.png'))
    pixels = colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Embedded viewport visibly renders the controlled robot', pixels > 50)
    check('Bindings save', window.save_project())
    signature = window.signature()
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    window.open_project(project / 'project.json')
    check('Save/reopen preserves graph and input bindings', window.signature() == signature)
    check('Reopened input demo compiles before build', window.validate_graph())
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start(100)
    window.actions['Build Game'].trigger()
    wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact / 'input-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor builds game with responsive event loop', results == [True] and len(ticks) > 5)
    build = project / 'build'
    states, bitmaps = {}, {}
    for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
        prefix = artifact / ('input-' + mode)
        args = [str(build / exe), '--frames', '30', '--input-replay', str(project / 'input-replay.json'),
                '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
        if mode == 'preview':
            args += ['--ir', str(project / 'generated/game.ir.json')]
        run = subprocess.run(args, cwd=build, capture_output=True, text=True, encoding='utf-8', timeout=40)
        check(mode + ' executes replay using packaged assets', run.returncode == 0)
        states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
        bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
    position = states['compiled']['entities']['player']['position']
    check('Replay has expected movement and one turn per press', all(abs(a-b)<1e-9 for a,b in zip(position, [.5, 0, -.5])) and states['compiled']['variables']['turn_count'] == 2)
    check('Replay preview/export states match', states['preview'] == states['compiled'])
    check('Replay preview/export GPU bitmaps match', bitmaps['preview'] == bitmaps['compiled'])
    image = QImage(str(artifact / 'input-compiled.bmp'))
    check('Standalone replay visibly renders the robot', colored(image) > 50)
    image.save(str(artifact / 'input-compiled.png'))
    check('Only deliberate malformed reload reports an error', len([m for m in messages if m.get('event') == 'node_error']) == 1)
    save_json(artifact / 'input-workflow-checks.json', dict(passed=True, checks=checks, project=str(project),
        compositor_pixels=pixels, heartbeat_ticks=len(ticks), bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest()))
finally:
    for vk in held:
        user32.keybd_event(vk, 0, 2, 0)
    user32.mouse_event(4, 0, 0, 0, 0)
    if window.builder.busy:
        window.builder.cancel()
        wait(lambda: not window.builder.busy)
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature()
    window.document_changed()
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
