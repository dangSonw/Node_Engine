"""Real file dialogs, live import/undo, save/reopen and portable GPU build parity."""
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
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QLineEdit
from editor.core.document import create_project, save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow, SearchDialog

artifact = ROOT / 'artifacts/validation'
workspace = ROOT / '.cache' / ('prefab-import-' + uuid.uuid4().hex[:8])
source = workspace / 'source'
shutil.copytree(ROOT / 'examples/prefabs_demo', source, ignore=shutil.ignore_patterns('build', 'generated'))
save_json(source / 'scenes/main.json', dict(entities=[], variables={}))
project = create_project(workspace / 'target', 'Imported prefab library')
assert current(ROOT / 'build/node_view.exe')
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
window = MainWindow(source / 'project.json', QSettings(str(workspace / 'layout.ini'), QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
area = window.screen().availableGeometry()
window.resize(min(1500, area.width() - 40), min(900, area.height() - 60))
window.move(area.left() + 20, area.top() + 20); window.show()
messages, checks = [], []
window.runtime.message.connect(messages.append)


def wait(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText() + window.build_output.toPlainText()[-5000:]


def check(label, value):
    assert value, label
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


def choose_files(action, files):
    multiple = len(files) > 1
    method = 'getOpenFileNames' if multiple else 'getOpenFileName'
    original = getattr(QFileDialog, method)
    # Keep a real modal Qt file chooser, deterministic without native shell automation.
    def open_dialog(*args, **kwargs):
        return original(*args, **kwargs, options=QFileDialog.Option.DontUseNativeDialog)
    def choose():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, QFileDialog)
        field = dialog.findChild(QLineEdit, 'fileNameEdit')
        field.setText(' '.join('"' + str(p).replace('\\', '/') + '"' for p in files))
        dialog.accept()
    setattr(QFileDialog, method, open_dialog)
    try:
        QTimer.singleShot(150, choose)
        window.actions[action].trigger()
    finally:
        setattr(QFileDialog, method, original)


def colored(image):
    return sum((c.blue() > c.red() * 1.2 and c.red() > c.green() * 1.2 and c.red() > 40) or
               (c.green() > 70 and c.blue() > 70 and c.red() < 60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    initial = window.signature()
    choose_files('Register Prefab Files…', sorted((source / 'assets/prefabs').glob('*.prefab.json')))
    registered = window.signature()
    check('Real multi-file dialog registers base, variant and nested assets', len(window.scene['prefab_assets']) == 3)
    window.actions['Undo'].trigger(); check('Registration undo restores the original scene', window.signature() == initial)
    window.actions['Redo'].trigger(); check('Registration redo restores the same library', window.signature() == registered)
    check('Registered library saves to its source project', window.save_project())
    window.open_project(project)
    before_import = window.signature()
    graph = window.adapter.document()
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('pause'); pid = window.runtime.process.processId()
    choose_files('Import Prefab Library…', [source / 'project.json'])
    imported = window.signature(); native = snapshot()
    check('Import preserves target graph and existing entities', window.adapter.document() == graph and len(window.scene['entities']) == 1)
    check('Live preview receives the entire imported template library', len(native['prefab_state']['templates']) == 3)
    window.actions['Undo'].trigger()
    check('Live import undo restores scene and removes templates', window.signature() == before_import and not snapshot().get('prefab_state', {}).get('templates'))
    window.actions['Redo'].trigger()
    check('Live import redo restores library without restarting runtime', window.signature() == imported and
          len(snapshot()['prefab_state']['templates']) == 3 and window.runtime.process.processId() == pid)
    copied = next(a for a in window.scene['prefab_assets'] if a['id'] == 'robot')['entities'][0]['mesh']
    check('Model was copied under the destination project', copied.startswith('assets/prefab-library-') and
          (project.parent / copied).read_bytes() == (source / 'assets/robot.gltf').read_bytes())
    choose_files('Import Prefab Library…', [source / 'project.json'])
    check('Duplicate library rejects without changing the document or native world', window.signature() == imported and
          snapshot()['prefab_state'] == native['prefab_state'] and 'Duplicate prefab ID' in window.console.toPlainText())
    roots = []
    def select_prefab():
        dialog = app.activeModalWidget(); assert isinstance(dialog, SearchDialog)
        dialog.search.setText('Robot Pair'); QTest.keyClick(dialog.search, Qt.Key.Key_Return)
    for position in ([-3, 0, 0], [3, 0, 0]):
        QTimer.singleShot(30, select_prefab); window.actions['Instantiate Prefab…'].trigger()
        root = window.selected_entity_id(); roots.append(root)
        field = next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName() == root + ' position')
        field.setText(json.dumps(position)); QTest.keyClick(field, Qt.Key.Key_Return)
        right = window.scene['prefab_instances'][-1]['mapping']['right']
        window.refresh_hierarchy(right)
        active = next(w for w in window.inspector.findChildren(QCheckBox) if w.accessibleName() == right + ' active')
        active.click()
    live = snapshot()
    records = window.scene['prefab_instances']
    check('Imported nested prefab places twice with separate IDs and native IsA', len(live['entities']) == 7 and
          not set(records[0]['mapping'].values()) & set(records[1]['mapping'].values()) and
          all(e['base']['asset'] == 'robot_pair' for e in live['prefab_state']['entities'].values()))
    command('frame_scene'); window.raise_(); window.activateWindow(); QTest.qWait(300)
    pixels = colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Visible embedded viewport renders imported Blockbench geometry', pixels > 50)
    window.screen().grabWindow(int(window.winId())).save(str(artifact / 'prefab-import-desktop.png'))
    check('Imported project saves', window.save_project())
    saved = window.signature()
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    moved = workspace / 'source-moved'
    assert source.resolve().is_relative_to(workspace.resolve()) and moved.resolve().is_relative_to(workspace.resolve())
    source.rename(moved)
    window.open_project(project)
    check('Reopen succeeds after original library project is moved away', window.signature() == saved)
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(100)
    window.actions['Build Game'].trigger(); wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact / 'prefab-import-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor Build Game succeeds with responsive event loop', results == [True] and len(ticks) > 5)
    build = project.parent / 'build'
    check('Build packages the imported mesh and current runtime', current(build / 'node_view.exe') and
          (build / copied).read_bytes() == (project.parent / copied).read_bytes())
    states, bitmaps = {}, {}
    for mode, name in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
        prefix = artifact / ('prefab-import-' + mode)
        args = [str(build / name), '--frames', '30', '--capture', str(prefix.with_suffix('.bmp')),
                '--output', str(prefix.with_suffix('.json'))]
        if mode == 'preview':
            args += ['--ir', str(project.parent / 'generated/game.ir.json')]
        run = subprocess.run(args, cwd=build, capture_output=True, text=True, encoding='utf-8', timeout=40)
        check(mode + ' runs using only packaged assets', run.returncode == 0)
        states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
        bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
    check('Packaged preview and compiled game states match', states['preview'] == states['compiled'])
    check('Packaged GPU captures match byte for byte', bitmaps['preview'] == bitmaps['compiled'])
    image = QImage(str(artifact / 'prefab-import-compiled.bmp'))
    check('Standalone image contains rendered imported geometry', colored(image) > 50)
    image.save(str(artifact / 'prefab-import-compiled.png'))
    check('No native node errors occurred', not any(m.get('event') == 'node_error' for m in messages))
    save_json(artifact / 'prefab-import-workflow-checks.json', dict(passed=True, checks=checks,
        project=str(project), compositor_pixels=pixels, heartbeat_ticks=len(ticks),
        bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest(), source_moved=True))
finally:
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
