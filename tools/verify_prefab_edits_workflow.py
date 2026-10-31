"""Visible Apply/Reset, live Flecs reload, and editor-built GPU game parity."""
from pathlib import Path
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
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QMessageBox
from editor.core.document import empty_graph, save_json
from editor.core.registry import ROOT
from editor.core.scene import entity
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow, SearchDialog

artifact = ROOT / 'artifacts/validation'
project = ROOT / '.cache' / ('prefab-edits-' + uuid.uuid4().hex[:8])
shutil.copytree(ROOT / 'examples/prefabs_demo', project, ignore=shutil.ignore_patterns('generated', 'build'))
save_json(project / 'graphs/gameplay.json', empty_graph())
assert current(ROOT / 'build/node_view.exe')
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
available = window.screen().availableGeometry()
window.resize(min(1500, available.width()-40), min(900, available.height()-60))
window.move(available.left()+20, available.top()+20); window.show()
messages, checks = [], []
window.runtime.message.connect(messages.append)


def wait(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText() + window.build_output.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label); print('PASS ' + label, flush=True)


def command(name, **data):
    begin = len(messages); serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    result = messages[begin:]
    assert not any(m.get('event') == 'node_error' for m in result), result
    return result


def snapshot():
    wait(lambda: window.reload_request is None)
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def edit(eid, prop, value):
    window.refresh_hierarchy(eid)
    cls = QSpinBox if prop == 'layer' else QLineEdit
    field = next(w for w in window.inspector.findChildren(cls) if w.accessibleName() == eid + ' ' + prop)
    if cls is QSpinBox:
        field.setValue(value)
    else:
        field.setFocus(); field.selectAll(); QTest.keyClicks(field, json.dumps(value)); QTest.keyClick(field, Qt.Key.Key_Return)
    if window.runtime.ready:
        wait(lambda: window.reload_request is None)


def apply(root):
    window.refresh_hierarchy(root); window.actions['Apply Prefab Overrides'].trigger()
    return snapshot()


def reset(root, button):
    window.refresh_hierarchy(root)
    def respond():
        dialog = app.activeModalWidget(); assert isinstance(dialog, QMessageBox)
        dialog.button(button).click()
    QTimer.singleShot(30, respond); window.actions['Reset Prefab Instance…'].trigger()
    return snapshot()


def geometry(image):
    return sum((c.blue() > c.red()*1.2 and c.red() > c.green()*1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    roots = []
    def choose():
        dialog = app.activeModalWidget(); assert isinstance(dialog, SearchDialog)
        dialog.search.setText('Robot Pair'); QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for position in ([-3.5, 0, 0], [3.5, 0, 0]):
        QTimer.singleShot(30, choose); window.actions['Instantiate Prefab…'].trigger()
        roots.append(window.selected_entity_id()); edit(roots[-1], 'position', position)
    first, second = window.scene['prefab_instances']
    a, b = dict(first['mapping']), dict(second['mapping'])
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('pause')
    check('Two nested instances load as six native entities', len(snapshot()['entities']) == 6)
    edit(b['left'], 'layer', 7); edit(a['left'], 'layer', 11)
    applied = apply(roots[0])
    check('Apply reaches native templates while preserving another instance override',
          entity(applied['scene'], a['left'])['layer'] == 11 and entity(applied['scene'], b['left'])['layer'] == 7)
    check('Applied source releases Activity ownership',
          applied['prefab_state']['entities'][a['left']]['owned_components'] == [] and
          applied['prefab_state']['entities'][b['left']]['owned_components'] == ['activity'])
    window.refresh_hierarchy(a['left']); window.actions['Duplicate Entity'].trigger()
    added = window.selected_entity_id(); edit(added, 'position', [0, 2.5, 0]); edit(added, 'scale', [.5, .5, .5])
    applied = apply(roots[0])
    first, second = window.scene['prefab_instances']
    local = next(k for k, sid in first['mapping'].items() if sid == added)
    check('Apply adopts added child and creates an independent second copy',
          len(applied['entities']) == 8 and second['mapping'][local] != added and
          applied['prefab_state']['entities'][added]['base'] == {'asset': 'robot_pair', 'local': local})
    window.refresh_hierarchy(a['right']); window.actions['Delete Entity'].trigger()
    removed = apply(roots[0])
    check('Apply removes template members in both native instances and reserves their IDs',
          len(removed['entities']) == 6 and all(r['retired'].get('right') in (a['right'], b['right'])
                                             for r in removed['scene']['prefab_instances']))
    window.refresh_hierarchy(b['left']); window.actions['Delete Entity'].trigger()
    check('Deleting one member produces a native tombstone', len(snapshot()['entities']) == 5)
    signature = window.signature()
    reset(roots[1], QMessageBox.StandardButton.Cancel)
    check('Cancel Reset preserves the complete authored document', window.signature() == signature)
    restored = reset(roots[1], QMessageBox.StandardButton.Yes)
    check('Reset restores the same child ID and latest template values', len(restored['entities']) == 6 and
          entity(restored['scene'], b['left'])['layer'] == 11 and
          restored['prefab_state']['entities'][b['left']]['owned_components'] == [])
    check('Apply and Reset preserve each root placement',
          entity(window.scene, roots[0])['position'] == [-3.5, 0, 0] and
          entity(window.scene, roots[1])['position'] == [3.5, 0, 0])
    window.actions['Undo'].trigger(); check('Undo Reset restores native deletion', len(snapshot()['entities']) == 5)
    window.actions['Redo'].trigger(); redo = snapshot()
    check('Redo Reset restores identical native scene and IsA metadata',
          redo['scene'] == restored['scene'] and redo['prefab_state'] == restored['prefab_state'])
    command('frame_scene'); window.frame_all(); window.raise_(); window.activateWindow(); QTest.qWait(300)
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [wintypes.POINT]; user32.WindowFromPoint.restype = ctypes.c_void_p
    hwnd = int(window.winId()); rect = wintypes.RECT()
    assert user32.GetWindowRect(ctypes.c_void_p(int(window.container.winId())), ctypes.byref(rect))
    covering = user32.WindowFromPoint(wintypes.POINT((rect.left+rect.right)//2, (rect.top+rect.bottom)//2))
    check('Edited native viewport belongs to this editor', covering == hwnd or bool(user32.IsChild(ctypes.c_void_p(hwnd), ctypes.c_void_p(covering))))
    pixels = geometry(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Compositor displays edited Blockbench geometry', pixels > 50)
    window.screen().grabWindow(hwnd).save(str(artifact / 'prefab-edits-desktop.png'))
    check('Edited prefab project saves', window.save_project())
    signature = window.signature()
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.open_project(project / 'project.json')
    check('Reopen keeps applied sources, mappings, retired IDs and resets', window.signature() == signature)
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(100)
    window.actions['Build Game'].trigger()
    check('Build Game starts from the reconciled project', window.builder.busy)
    wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact / 'prefab-edits-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Edited game builds with responsive UI', results == [True] and len(ticks) > 5)
    states, bitmaps = {}, {}
    for mode, name in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
        prefix = artifact / ('prefab-edits-' + mode)
        args = [str(project / 'build' / name), '--frames', '30', '--capture', str(prefix.with_suffix('.bmp')),
                '--output', str(prefix.with_suffix('.json'))]
        if mode == 'preview':
            args += ['--ir', str(project / 'generated/game.ir.json')]
        result = subprocess.run(args, cwd=project / 'build', capture_output=True, text=True, encoding='utf-8', timeout=40)
        check(mode + ' runs using packaged assets after Apply/Reset', result.returncode == 0)
        states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
        bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
    check('Edited preview and compiled native states match', states['preview'] == states['compiled'])
    check('Edited GPU output matches byte-for-byte', bitmaps['preview'] == bitmaps['compiled'])
    image = QImage(str(artifact / 'prefab-edits-compiled.bmp'))
    check('Export renders the reconciled geometry', geometry(image) > 50)
    image.save(str(artifact / 'prefab-edits-compiled.png'))
    check('Export preserves all six native mappings and retired IDs', len(states['compiled']['entities']) == 6 and
          all(r.get('retired') for r in states['compiled']['scene']['prefab_instances']))
    check('No runtime node errors during editing', not any(m.get('event') == 'node_error' for m in messages))
    save_json(artifact / 'prefab-edits-workflow-checks.json', {'passed': True, 'checks': checks,
        'project': str(project / 'project.json'), 'compositor_pixels': pixels, 'gpu_pixels': geometry(image),
        'heartbeat_ticks': len(ticks), 'bitmap_sha256': hashlib.sha256(bitmaps['compiled']).hexdigest()})
finally:
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
