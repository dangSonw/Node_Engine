"""Real Qt authoring, native reload recovery and relocated material-demo export."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QDialogButtonBox, QPushButton
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.scene import entity
from editor.core.registry import ROOT
from editor.ui.main_window import MainWindow
from editor.ui.materials import MaterialLibraryDialog, MaterialParametersDialog
from tools.create_material_demo import create


def main():
    artifact = ROOT / 'artifacts/validation'
    workspace = ROOT / '.cache' / ('material-' + uuid.uuid4().hex[:8])
    project = create(workspace / 'project')
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    window.resize(1600, 960); window.show(); window.splitter.setSizes([260, 1000])
    messages, checks = [], []
    window.runtime.message.connect(messages.append)
    def wait(predicate, timeout=20):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline: QTest.qWait(10)
        assert predicate(), window.console.toPlainText() + '\n' + window.build_output.toPlainText()
    def check(label, condition):
        assert condition, label
        checks.append(label); print('PASS ' + label, flush=True)
    def click(widget): QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    def accept(dialog): click(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok))
    def text(field, value):
        field.setFocus(); QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier); QTest.keyClicks(field, value)
    def command(name, error=False, **data):
        start = len(messages); serial = window.runtime.send(name, **data)
        wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[start:]))
        result = messages[start:]
        assert any(m.get('event') == 'node_error' for m in result) == error, result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')
    def capture(label):
        path = artifact / ('material-' + label + '.bmp'); start = len(messages)
        command('capture', path=str(path))
        wait(lambda: any(m.get('event') == 'capture_done' and m.get('path') == str(path) for m in messages[start:]))
        image = QImage(str(path)); assert not image.isNull(); image.save(str(path.with_suffix('.png')))
        return image
    def reload_done():
        wait(lambda: window.reload_request is None)
        command('play'); command('pause')
    def edit_library(new=False):
        def parameters():
            dialog = app.activeModalWidget(); assert isinstance(dialog, MaterialParametersDialog)
            if new: text(dialog.name, 'Accent')
            for field, value in zip(dialog.color, ['.4', '.8', '.12']): text(field, value)
            accept(dialog)
        def library():
            dialog = app.activeModalWidget(); assert isinstance(dialog, MaterialLibraryDialog)
            if not new:
                item = next(dialog.list.item(i) for i in range(dialog.list.count()) if dialog.list.item(i).data(Qt.ItemDataRole.UserRole) == 'robot_blue')
                dialog.list.setCurrentItem(item)
            QTimer.singleShot(50, parameters)
            click(next(b for b in dialog.findChildren(QPushButton) if b.text() == ('New…' if new else 'Edit…')))
            accept(dialog)
        QTimer.singleShot(50, library); window.actions['Materials…'].trigger()
    def assign(mid):
        window.refresh_hierarchy('player')
        combo = next(w for w in window.inspector.findChildren(QComboBox) if w.accessibleName() == 'player material')
        combo.setFocus(); combo.showPopup(); QTest.keyClick(combo.view(), Qt.Key.Key_Home)
        for _ in range(combo.findData(mid)): QTest.keyClick(combo.view(), Qt.Key.Key_Down)
        QTest.keyClick(combo.view(), Qt.Key.Key_Return)
        wait(lambda: (entity(window.scene, 'player').get('material') or {}).get('asset') == mid)
    try:
        edit_library(new=True)
        accent = next(a['id'] for a in window.scene['material_assets'] if a['name'] == 'Accent')
        check('Material library dialog creates a stable asset', bool(accent) and len(window.scene['material_assets']) == 2)
        window.actions['Undo'].trigger(); check('Undo removes new material', len(window.scene['material_assets']) == 1)
        window.actions['Redo'].trigger(); check('Redo restores the same material ID', accent in [a['id'] for a in window.scene['material_assets']])
        assign(accent); check('Inspector selects reusable material', entity(window.scene, 'player')['material']['asset'] == accent)
        window.actions['Undo'].trigger(); check('Assignment Undo restores previous binding', entity(window.scene, 'player')['material']['asset'] == 'robot_blue')
        window.actions['Redo'].trigger(); check('Assignment Redo restores selected binding', entity(window.scene, 'player')['material']['asset'] == accent)
        assign('robot_blue')
        window.actions['Play'].trigger()
        wait(lambda: window.runtime.ready and window.runtime.state == 'running' and window.container is not None)
        command('pause'); original = capture('shared-blue'); pid = window.runtime.process.processId()
        edit_library(); reload_done()
        shared = capture('shared-green')
        check('Shared material edit reloads in the existing native process', window.runtime.process.processId() == pid)
        check('Shared material edit changes visible pixels', shared != original)
        check('Native snapshot contains edited shared color', next(a for a in snapshot()['scene']['material_assets'] if a['id'] == 'robot_blue')['color'] == [.4, .8, .12])
        window.actions['Undo'].trigger(); reload_done(); check('Material asset Undo restores exact GPU pixels', capture('undo-shared') == original)
        window.actions['Redo'].trigger(); reload_done(); check('Material asset Redo restores exact GPU pixels', capture('redo-shared') == shared)
        window.refresh_hierarchy('player')
        def instance():
            dialog = app.activeModalWidget(); assert isinstance(dialog, MaterialParametersDialog)
            for field, value in zip(dialog.color, ['1', '.18', '.04']): text(field, value)
            accept(dialog)
        QTimer.singleShot(50, instance)
        click(next(w for w in window.inspector.findChildren(QPushButton) if w.text() == 'Edit Material Instance…'))
        reload_done(); tinted = capture('instance')
        state = snapshot()
        check('Instance edit changes only the selected entity binding', entity(state['scene'], 'player')['material']['overrides']['color'] == [1, .18, .04]
              and all(entity(state['scene'], e)['material']['overrides'] == {} for e in ('left', 'right')))
        # Three robots occupy disjoint screen thirds; the side instances must retain their pixels.
        third = shared.width() // 3
        check('Side instances retain exact GPU pixels', tinted.copy(0, 0, third, shared.height()) == shared.copy(0, 0, third, shared.height())
              and tinted.copy(2*third, 0, third, shared.height()) == shared.copy(2*third, 0, third, shared.height()) and tinted != shared)
        before = snapshot(); invalid = deepcopy(compile_graph(window.adapter.document(), window.scene))
        entity(invalid['scene'], 'player')['material']['asset'] = 'missing'
        command('load_ir', error=True, ir=invalid)
        check('Unknown material reload preserves scene and framebuffer', snapshot() == before and capture('failed-reload') == tinted)
        command('load_ir', ir=compile_graph(window.adapter.document(), window.scene)); command('play'); command('pause')
        check('Valid material reload recovers in the same process', window.runtime.process.processId() == pid and capture('recovered') == tinted)
        window.output_tabs.setCurrentWidget(window.console)
        window.screen().grabWindow(int(window.winId())).save(str(artifact / 'material-desktop.png'))
        check('Material project saves', window.save_project()); signature = window.signature()
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.open_project(project / 'project.json')
        check('Save/reopen preserves shared assets and instance overrides', signature == window.signature())
        results, ticks = [], []; window.builder.finished.connect(results.append)
        timer = QTimer(); timer.timeout.connect(lambda: ticks.append(time.monotonic())); timer.start(100)
        window.actions['Build Game'].trigger(); wait(lambda: not window.builder.busy and bool(results), 300); timer.stop()
        (artifact / 'material-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
        check('Editor builds material nodes while its event loop stays responsive', results == [True] and len(ticks) > 5)
        packaged = workspace / 'relocated game'; packaged.mkdir(); build = project / 'build'
        for name in ('node_view.exe', 'node_game_view.exe', 'SDL3.dll', 'SDL3_image.dll', 'SDL3_mixer.dll'): shutil.copy2(build / name, packaged / name)
        for name in ('assets', 'shaders'): shutil.copytree(build / name, packaged / name)
        shutil.copy2(project / 'generated/game.ir.json', packaged / 'game.ir.json')
        shutil.copy2(project / 'input-replay.json', packaged / 'input-replay.json')
        system = Path(os.environ['SystemRoot']); clean = dict(os.environ); clean['PATH'] = str(system / 'System32') + os.pathsep + str(system)
        digests = {}
        for frame, name in [(3, 'tint'), (5, 'fade'), (7, 'original'), (9, 'reset')]:
            states, bitmaps = {}, {}
            for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
                prefix = artifact / f'material-{name}-{mode}'
                args = [str(packaged / exe), '--frames', str(frame), '--input-replay', str(packaged / 'input-replay.json'),
                    '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
                if mode == 'preview': args += ['--ir', str(packaged / 'game.ir.json')]
                run = subprocess.run(args, cwd=packaged, env=clean, capture_output=True, text=True, encoding='utf-8', timeout=30)
                check(name + ' relocated ' + mode + ' runs with clean PATH', run.returncode == 0)
                states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8')); bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
            check(name + ' preview/export state and GPU pixels match', states['preview'] == states['compiled'] and bitmaps['preview'] == bitmaps['compiled'])
            binding = entity(states['compiled']['scene'], 'player').get('material')
            expected = {'tint': {'asset': 'robot_blue', 'overrides': {'color': [1, .18, .04]}},
                'fade': {'asset': 'robot_blue', 'overrides': {'alpha_mode': 'blend', 'opacity': .3}},
                'original': None, 'reset': {'asset': 'robot_blue', 'overrides': {}}}[name]
            check(name + ' input changes selected material only', binding == expected and all(entity(states['compiled']['scene'], e)['material']['overrides'] == {} for e in ('left', 'right')))
            image = QImage(str(artifact / f'material-{name}-compiled.bmp')); image.save(str(artifact / f'material-{name}-compiled.png'))
            digests[name] = hashlib.sha256(bitmaps['compiled']).hexdigest()
        check('All four material interactions have distinct visible output', len(set(digests.values())) == 4)
        check('Only deliberate invalid material produces a runtime error', len([m for m in messages if m.get('event') == 'node_error']) == 1)
        save_json(artifact / 'material-workflow-checks.json', dict(passed=True, checks=checks, project=str(project),
            package=str(packaged), heartbeat_ticks=len(ticks), bitmap_sha256=digests))
    finally:
        if window.builder.busy: window.builder.cancel(); wait(lambda: not window.builder.busy)
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()


if __name__ == '__main__': main()
