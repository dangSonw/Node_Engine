"""Visible nested Apply/Undo/save, live adoption and exported GPU equivalence."""
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
from PySide6.QtWidgets import QApplication, QLineEdit
from editor.core.builder import GraphBuilder
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.core.scene import set_entity_property
from editor.ui.main_window import MainWindow

artifact = ROOT/'artifacts/validation'
source = ROOT/'examples/nested_prefab_demo'
project = ROOT/'.cache'/('nested-prefab-'+uuid.uuid4().hex[:8])
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
    assert predicate(), window.console.toPlainText()+window.build_output.toPlainText()


def check(label, result):
    assert result, label
    checks.append(label); print('PASS '+label, flush=True)


def command(name, **data):
    begin = len(messages); serial = window.runtime.send(name, **data)
    wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[begin:]))
    result = messages[begin:]
    assert not any(m.get('event') == 'node_error' for m in result), result
    return result


def snapshot():
    wait(lambda: window.reload_request is None)
    return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')


def record(state, root):
    return next(r for r in state['scene']['prefab_instances'] if r['root'] == root)


def entities(state):
    return {e['id']: e for e in state['scene']['entities']}


def geometry(image):
    return sum((c.blue()>c.red()*1.2 and c.red()>c.green()*1.2 and c.red()>40) or
               (c.green()>70 and c.blue()>70 and c.red()<60)
               for y in range(0, image.height(), 3) for x in range(0, image.width(), 3)
               for c in [image.pixelColor(x, y)])


try:
    initial = window.signature()
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('stop'); command('play'); pid = window.runtime.process.processId()
    wait(lambda: snapshot()['frame']>=150)
    command('pause'); live = snapshot()
    check('Live Apply adopts nested IDs and creates the second robot',
          record(live, 'left')['mapping']['nested_1'] == 'nested' and
          record(live, 'left')['mapping']['nested_1/e1'] == 'nested_body' and len(live['entities']) == 8)
    check('Nested source remains a dependency', next(a for a in live['scene']['prefab_assets'] if a['id'] == 'group')['nested'] ==
          [dict(id='nested_1', prefab='robot', parent='root')])
    check('Child timer and queued event survive adoption and Reset', live['variables']['ticks']['value']>=10 and
          live['logs'] == ['Nested event survived adoption'] and len(live['timers']) == 1)
    check('Future source changes propagate while captured overrides remain',
          entities(live)['nested_body']['name'] == 'Updated from source' and
          entities(live)['nested_body']['scale'] == [1.5]*3 and
          entities(live)['nested']['components']['1']['properties']['1'] == 90 and
          entities(live)['source']['components']['1']['properties']['1'] == 45)
    check('Gameplay preserves runtime process and authored document',
          pid == window.runtime.process.processId() and window.signature() == initial)
    command('frame_scene'); window.raise_(); window.activateWindow(); QTest.qWait(300)
    pixels = geometry(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Visible native viewport contains the Blockbench robots', pixels>50)
    window.screen().grabWindow(int(window.winId())).save(str(artifact/'nested-prefab-desktop.png'))
    command('stop'); check('Stop restores four independent authored instances', len(snapshot()['scene']['prefab_instances']) == 4)

    # Invoke the actual editor action, including shared Undo/Redo and live reload.
    window.refresh_hierarchy('nested_body')
    field = next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName() == 'nested_body scale')
    field.setText('[1.5, 1.5, 1.5]'); QTest.keyClick(field, Qt.Key.Key_Return)
    before = window.signature(); snapshot()
    window.refresh_hierarchy('left'); window.actions['Apply Prefab Overrides'].trigger()
    applied = snapshot(); signature = window.signature()
    check('Editor Apply keeps nested IDs and changes only the containing asset', len(applied['scene']['prefab_instances']) == 3 and
          'nested_body' in record(applied, 'left')['mapping'].values() and
          next(a for a in applied['scene']['prefab_assets'] if a['id'] == 'robot') ==
          next(a for a in json.loads((source/'scenes/main.json').read_text('utf-8'))['prefab_assets'] if a['id'] == 'robot'))
    window.actions['Undo'].trigger()
    check('Undo restores independent child membership and its overrides', window.signature() == before and
          len(snapshot()['scene']['prefab_instances']) == 4)
    window.actions['Redo'].trigger(); redo = snapshot()
    check('Redo restores identical native scene and IsA ownership', window.signature() == signature and
          redo['scene'] == applied['scene'] and redo['prefab_state'] == applied['prefab_state'])
    check('Edited project saves', window.save_project())
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.open_project(project/'project.json')
    check('Reopen preserves authored bindings and adopted IDs', window.signature() == signature)

    # A partially detached child must fail without any live-world mutation.
    invalid = json.loads((source/'scenes/main.json').read_text('utf-8'))
    invalid = set_entity_property(invalid, 'nested_body', 'parent', '')
    b = GraphBuilder(component_definitions=invalid['component_definitions'])
    b.add('update', 'On Update'); b.add('bad_nested', 'Apply Prefab Overrides', Instance='left')
    b.connect('update', 'Out', 'bad_nested', 'In')
    window.actions['Play'].trigger(); wait(lambda: window.runtime.ready and window.runtime.state == 'running')
    command('pause'); command('load_ir', ir=compile_graph(b.graph, invalid)); command('pause')
    before_invalid = snapshot(); start = len(messages)
    window.runtime.send('play')
    wait(lambda: any(m.get('event') == 'node_error' and m.get('node') == 'bad_nested' for m in messages[start:]))
    after_invalid = snapshot()
    check('Rejected nested Apply preserves exact scene and Flecs metadata',
          before_invalid['scene'] == after_invalid['scene'] and before_invalid['prefab_state'] == after_invalid['prefab_state'])

    # Build the original authored demo so adoption executes in the standalone game.
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    shutil.copy2(source/'scenes/main.json', project/'scenes/main.json')
    window.open_project(project/'project.json')
    results, ticks = [], []
    window.builder.finished.connect(results.append)
    heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(100)
    window.actions['Build Game'].trigger(); wait(lambda: not window.builder.busy and bool(results), 300)
    heartbeat.stop()
    (artifact/'nested-prefab-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor builds the nested project with responsive UI', results == [True] and len(ticks)>5)
    check('Build packages the current runtime and Blockbench mesh', current(project/'build/node_view.exe') and
          (project/'build/assets/robot.gltf').read_bytes() == (source/'assets/robot.gltf').read_bytes())
    parity = {}
    for frames in (30, 90, 150):
        states, bitmaps = {}, {}
        for mode, name in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
            prefix = artifact/f'nested-prefab-{mode}-{frames}'
            args = [str(project/'build'/name), '--frames', str(frames), '--capture', str(prefix.with_suffix('.bmp')),
                    '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview':
                args += ['--ir', str(project/'generated/game.ir.json')]
            run = subprocess.run(args, cwd=project/'build', capture_output=True, text=True, encoding='utf-8', timeout=40)
            check(f'{mode} renders {frames} frames', run.returncode == 0)
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
        state = states['compiled']
        check(f'{frames}-frame native states and GPU bytes match', states['preview'] == state and bitmaps['preview'] == bitmaps['compiled'])
        check(f'{frames}-frame membership and timer are correct', len(state['entities']) == (6 if frames<60 else 8) and
              len(state['scene']['prefab_instances']) == (4 if frames<60 else 3) and state['variables']['ticks']['value'] == frames//15)
        check(f'{frames}-frame nested overrides and Reset are correct', entities(state)['nested_body']['scale'] == [1.5]*3 and
              entities(state)['nested']['components']['1']['properties']['1'] == 90 and
              entities(state)['source']['components']['1']['properties']['1'] == (45 if frames>100 else 90))
        image = QImage(str(artifact/f'nested-prefab-compiled-{frames}.bmp'))
        check(f'{frames}-frame export contains geometry', geometry(image)>50)
        image.save(str(artifact/f'nested-prefab-compiled-{frames}.png'))
        parity[str(frames)] = dict(state_equal=True, bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest())
    save_json(artifact/'nested-prefab-workflow-checks.json', dict(passed=True, checks=checks,
        project=str(project/'project.json'), compositor_pixels=pixels, heartbeat_ticks=len(ticks), parity=parity))
finally:
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy)
    window.runtime.shutdown(); wait(lambda: not window.runtime.active)
    window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
