"""Real editor prefab actions, native Flecs state and GPU export equivalence."""
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
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit
from editor.core.document import empty_graph, save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow, SearchDialog

artifact = ROOT / 'artifacts/validation'
project = ROOT / '.cache' / ('prefabs-' + uuid.uuid4().hex[:8])
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


def wait(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText()


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
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def colored(image):
    return sum((c.blue() > c.red()*1.2 and c.red() > c.green()*1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    check('Authored demo begins with no scene entities', window.scene['entities'] == [])
    roots = []
    def choose():
        dialog = app.activeModalWidget(); assert isinstance(dialog, SearchDialog)
        dialog.search.setText('Robot Pair'); QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for position in ([-2.8, 0, 0], [2.8, 0, 0]):
        QTimer.singleShot(30, choose); window.actions['Instantiate Prefab…'].trigger()
        root = window.selected_entity_id(); roots.append(root)
        field = next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName() == root + ' position')
        field.setFocus(); field.selectAll(); QTest.keyClicks(field, json.dumps(position)); QTest.keyClick(field, Qt.Key.Key_Return)
    records = json.loads(json.dumps(window.scene['prefab_instances']))
    check('Two dialog-created instances have independent stable mappings', len(records) == 2 and
          not set(records[0]['mapping'].values()) & set(records[1]['mapping'].values()))
    check('Inspector placement owns each root transform', all(r['owned_components']['group'] == ['transform'] for r in records))
    window.actions['Undo'].trigger(); window.actions['Undo'].trigger()
    check('Undo removes one entire instance', len(window.scene['entities']) == 3 and len(window.scene['prefab_instances']) == 1)
    window.actions['Redo'].trigger(); window.actions['Redo'].trigger()
    check('Redo restores identical mappings and overrides', window.scene['prefab_instances'] == records)
    window.refresh_hierarchy(roots[0])
    def capture():
        dialog = app.activeModalWidget(); assert isinstance(dialog, QInputDialog)
        dialog.setTextValue('Captured robot group'); dialog.accept()
    QTimer.singleShot(30, capture); window.actions['Create Prefab from Entity…'].trigger()
    check('Capture adds a reusable three-entity asset', len(window.scene['prefab_assets']) == 4 and
          len(window.scene['prefab_assets'][-1]['entities']) == 3)
    window.actions['Undo'].trigger(); check('Capture is undoable', len(window.scene['prefab_assets']) == 3)
    window.actions['Redo'].trigger()
    window.actions['Delete Entity'].trigger()
    check('Editor delete removes instance hierarchy and membership', len(window.scene['entities']) == 3 and len(window.scene['prefab_instances']) == 1)
    window.actions['Undo'].trigger()
    check('Authoring saves successfully', window.save_project())
    signature = window.signature(); window.open_project(project / 'project.json')
    check('Reopen preserves assets, mappings and overrides', window.signature() == signature)
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('pause'); state = snapshot()
    check('Authored instances become six native entities', len(state['entities']) == 6 and len(state['scene']['prefab_instances']) == 2)
    check('Native members have real IsA template targets', all(e['base']['asset'] == 'robot_pair' for e in state['prefab_state']['entities'].values()))
    check('Native ownership matches authored placements', all(state['prefab_state']['entities'][root]['owned_components'] == ['transform'] for root in roots))
    window.refresh_hierarchy(roots[0]); command('frame_scene'); window.frame_all()
    window.raise_(); window.activateWindow(); QTest.qWait(200)
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.argtypes = [wintypes.POINT]; user32.WindowFromPoint.restype = ctypes.c_void_p
    hwnd = int(window.winId()); rect = wintypes.RECT()
    assert user32.GetWindowRect(ctypes.c_void_p(int(window.container.winId())), ctypes.byref(rect))
    covering = user32.WindowFromPoint(wintypes.POINT((rect.left+rect.right)//2, (rect.top+rect.bottom)//2))
    check('Desktop viewport belongs to this editor', covering == hwnd or bool(user32.IsChild(ctypes.c_void_p(hwnd), ctypes.c_void_p(covering))))
    window.screen().grabWindow(hwnd).save(str(artifact / 'prefab-desktop.png'))
    compositor_pixels = colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Compositor shows native prefab robot geometry', compositor_pixels > 50)
    command('stop'); check('Stop restores authored instances', len(snapshot()['entities']) == 6)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    parity, gpu_pixels = {}, {}
    for frames in (30, 90):
        states, images = {}, {}
        for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
            prefix = artifact / f'prefab-{mode}-{frames}'
            args = [str(ROOT / 'build' / exe), '--project-root', str(ROOT / 'examples/prefabs_demo'),
                    '--frames', str(frames), '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview':
                args += ['--ir', str(ROOT / 'examples/prefabs_demo/generated/game.ir.json')]
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=40)
            check(f'{mode} executes {frames} GPU frames', result.returncode == 0)
            events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            check(f'{mode} preloads a template-only mesh at {frames} frames', any(
                e.get('event') == 'scene_loaded' and e['mesh_instances'] == 0 and e['unique_meshes'] == 1 for e in events))
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            images[mode] = prefix.with_suffix('.bmp').read_bytes()
        check(f'{frames}-frame native states match', states['preview'] == states['compiled'])
        check(f'{frames}-frame GPU images match byte-for-byte', images['preview'] == images['compiled'])
        state = states['compiled']; entities = {e['id']: e for e in state['scene']['entities']}
        check(f'{frames}-frame graph creates the nested pair with opposite rotations', len(entities) == 3 and
              entities['spawned_2']['rotation'][1] == frames and entities['spawned_3']['rotation'][1] == -frames and entities['spawned_3']['active'])
        check(f'{frames}-frame native nested template keeps variant IsA', state['prefab_state']['templates']['robot_pair']['right']['base'] ==
              {'asset': 'inactive_robot', 'local': 'root'})
        image = QImage(str(artifact / f'prefab-compiled-{frames}.bmp'))
        gpu_pixels[str(frames)] = colored(image)
        check(f'{frames}-frame GPU capture contains visible robot geometry', gpu_pixels[str(frames)] > 50)
        image.save(str(artifact / f'prefab-compiled-{frames}.png'))
        parity[str(frames)] = {'state_equal': True, 'bitmap_sha256': hashlib.sha256(images['compiled']).hexdigest()}
    check('No editor runtime node errors', not any(m.get('event') == 'node_error' for m in messages))
    save_json(artifact / 'prefab-workflow-checks.json', {'passed': True, 'checks': checks, 'messages': messages,
        'parity': parity, 'gpu_pixels': gpu_pixels, 'compositor_pixels': compositor_pixels, 'project': str(project / 'project.json')})
finally:
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
