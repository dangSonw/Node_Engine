"""Inspector equal-value overrides, native propagation, Undo/Redo and export."""
from pathlib import Path
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
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox
from editor.core.builder import GraphBuilder
from editor.core.document import save_json
from editor.core.prefabs import PrefabLibrary
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.scene import entity
from editor.ui.main_window import MainWindow

artifact = ROOT / 'artifacts/validation'
project = ROOT / '.cache' / ('component-overrides-' + uuid.uuid4().hex[:8])
source = ROOT / 'examples/prefabs_demo'
shutil.copytree(source, project, ignore=shutil.ignore_patterns('generated', 'build'))
asset = next(a for a in json.loads((source / 'scenes/main.json').read_text('utf-8'))['prefab_assets'] if a['id'] == 'robot')
asset['component_definitions'] = [{'id': 1, 'name': 'Motion', 'properties': [
    {'id': 1, 'name': 'Speed', 'type': 'float', 'default': 90.0}]}]
asset['entities'][0]['components'] = {'1': {'enabled': True, 'properties': {'1': 90.0}}}
library = PrefabLibrary([asset])
scene = dict(version=1, entities=[], variables={}, prefab_assets=library.assets,
             component_definitions=library.component_definitions, prefab_instances=[])
for eid, position in [('left', [-2.2, 0, 0]), ('right', [2.2, 0, 0])]:
    record = library.instantiate_entities('robot', mapping={'root': eid}, position=position)
    scene['entities'].extend(record.pop('entities'))
    scene['prefab_instances'].append(record)
b = GraphBuilder('Independent component overrides', component_definitions=library.component_definitions)
b.add('update', 'On Update')
b.add('dt', 'Get Delta Time')
b.graph['nodes'][0]['position'] = [-300, 0]
b.graph['nodes'][1]['position'] = [-300, 260]
previous = 'update'
for row, eid in enumerate(('left', 'right')):
    for column, (nid, name, values) in enumerate([(eid + '_speed', 'Get Motion Speed', dict(Entity=eid)),
                              (eid + '_delta', 'Multiply', {}), (eid + '_vector', 'Make Vector3', {}),
                              (eid + '_rotate', 'Rotate', dict(Entity=eid))]):
        b.add(nid, name, **values)
        b.graph['nodes'][-1]['position'] = [column * 300, row * 260]
    b.connect(eid + '_speed', 'Value', eid + '_delta', 'A')
    b.connect('dt', 'Value', eid + '_delta', 'B')
    b.connect(eid + '_delta', 'Value', eid + '_vector', 'Y')
    b.connect(eid + '_vector', 'Value', eid + '_rotate', 'Degrees')
    b.connect(previous, 'Out', eid + '_rotate', 'In')
    previous = eid + '_rotate'
save_json(project / 'scenes/main.json', scene)
save_json(project / 'graphs/gameplay.json', b.graph)
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


def wait(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.console.toPlainText() + window.build_output.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label)
    print('PASS ' + label, flush=True)


def command(name):
    begin = len(messages)
    serial = window.runtime.send(name)
    wait(lambda: any(m.get('id') == serial and m.get('event') in ('ack', 'node_error') for m in messages[begin:]))
    result = messages[begin:]
    assert not any(m.get('event') == 'node_error' for m in result), result
    return result


def snapshot():
    wait(lambda: window.reload_request is None)
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def edit(eid, value):
    window.refresh_hierarchy(eid)
    field = next(w for w in window.inspector.findChildren(QLineEdit)
                 if w.accessibleName() == f'{eid} component 1 property 1')
    field.setFocus()
    field.selectAll()
    QTest.keyClicks(field, str(value))
    QTest.keyClick(field, Qt.Key.Key_Return)
    wait(lambda: window.reload_request is None)


def speed(state, eid):
    return entity(state['scene'], eid)['components']['1']['properties']['1']


def mask(state, eid):
    record = next(r for r in state['scene']['prefab_instances'] if r['root'] == eid)
    return record.get('component_overrides', {})


try:
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('stop')
    initial = snapshot()
    check('Native templates initially supply both component speeds', speed(initial, 'left') == speed(initial, 'right') == 90)
    edit('left', 90)
    pinned = snapshot()
    check('Same-value Inspector edit records an explicit native property override', mask(pinned, 'left') ==
          {'root': {'1': {'properties': [1]}}} and speed(pinned, 'left') == 90)
    window.actions['Undo'].trigger()
    check('Undo removes the explicit write without changing its numeric value', not mask(snapshot(), 'left'))
    window.actions['Redo'].trigger()
    check('Redo restores the explicit write', mask(snapshot(), 'left') == mask(pinned, 'left'))
    edit('right', 45)
    window.actions['Apply Prefab Overrides'].trigger()
    applied = snapshot()
    check('Apply updates template speed while preserving the equal-value override',
          speed(applied, 'left') == 90 and speed(applied, 'right') == 45 and not mask(applied, 'right'))
    signature = window.signature()
    window.refresh_hierarchy('left')
    def confirm():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        dialog.button(QMessageBox.StandardButton.Yes).click()
    QTimer.singleShot(30, confirm)
    window.actions['Reset Prefab Instance…'].trigger()
    reset = snapshot()
    check('Reset releases property ownership and follows the latest template', speed(reset, 'left') == 45 and not mask(reset, 'left'))
    window.actions['Undo'].trigger()
    check('Undo Reset recovers the explicit property and value', mask(snapshot(), 'left') == mask(pinned, 'left') and window.signature() == signature)
    check('Project saves after explicit override edits', window.save_project())
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    window.open_project(project / 'project.json')
    check('Reopen preserves property masks, values and prefab sources', window.signature() == signature)
    window.actions['Play'].trigger()
    wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('pause')
    check('Reopened preview reloads the explicit override', mask(snapshot(), 'left') == mask(pinned, 'left'))
    command('frame_scene')
    window.refresh_hierarchy('left')
    window.frame_all()
    window.raise_()
    window.activateWindow()
    QTest.qWait(250)
    window.screen().grabWindow(int(window.winId())).save(str(artifact / 'component-overrides-desktop.png'))
    window.runtime.shutdown()
    wait(lambda: not window.runtime.active)
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    heartbeat.start(100)
    window.actions['Build Game'].trigger()
    check('Build Game starts asynchronously', window.builder.busy)
    wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact / 'component-overrides-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor builds the edited project while remaining responsive', results == [True] and len(ticks) > 5)
    states, bitmaps = {}, {}
    for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
        prefix = artifact / ('component-overrides-' + mode)
        args = [str(project / 'build' / exe), '--frames', '30', '--capture', str(prefix.with_suffix('.bmp')),
                '--output', str(prefix.with_suffix('.json'))]
        if mode == 'preview':
            args += ['--ir', str(project / 'generated/game.ir.json')]
        result = subprocess.run(args, cwd=project / 'build', capture_output=True, text=True, encoding='utf-8', timeout=40)
        check(mode + ' runs using packaged assets', result.returncode == 0)
        states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
        bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
    check('Exported component values drive different rotation speeds',
          states['compiled']['entities']['left']['rotation'][1] == 45 and
          states['compiled']['entities']['right']['rotation'][1] == 22.5)
    check('Preview and exported native states match', states['preview'] == states['compiled'])
    check('Preview and exported GPU bytes match', bitmaps['preview'] == bitmaps['compiled'])
    image = QImage(str(artifact / 'component-overrides-compiled.bmp'))
    pixels = sum(image.pixelColor(x, y).red() > 40 for y in range(0, image.height(), 3) for x in range(0, image.width(), 3))
    check('Exported GPU image contains rendered robot geometry', pixels > 50)
    image.save(str(artifact / 'component-overrides-compiled.png'))
    check('No native node errors occurred during component editing', not any(m.get('event') == 'node_error' for m in messages))
    save_json(artifact / 'component-overrides-workflow-checks.json', dict(passed=True, checks=checks,
        project=str(project / 'project.json'), heartbeat_ticks=len(ticks), gpu_pixels=pixels,
        bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest()))
finally:
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
