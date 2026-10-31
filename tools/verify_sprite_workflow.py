"""Real editor edits, reload rollback, portable export and replay pixel parity."""
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
from PySide6.QtCore import QEvent, QPoint, QSettings, QTimer, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QSpinBox
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.scene import entity
from editor.core.registry import ROOT
from editor.ui.main_window import MainWindow
from tools.create_sprite_demo import create


def main():
    artifact = ROOT / 'artifacts/validation'
    workspace = ROOT / '.cache' / ('sprite-' + uuid.uuid4().hex[:8])
    project = create(workspace / 'project')
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
    window.resize(1600, 960); window.show(); window.splitter.setSizes([260, 1000])
    messages, checks = [], []
    window.runtime.message.connect(messages.append)
    def wait(predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline: QTest.qWait(10)
        assert predicate(), window.console.toPlainText() + '\n' + window.build_output.toPlainText()
    def check(label, condition):
        assert condition, label
        checks.append(label); print('PASS ' + label, flush=True)
    def command(name, error=False, **data):
        start = len(messages); serial = window.runtime.send(name, **data)
        wait(lambda: any(m.get('event') in ('ack', 'node_error') and m.get('id') == serial for m in messages[start:]))
        result = messages[start:]
        assert any(m.get('event') == 'node_error' for m in result) == error, result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')
    def capture(label):
        path = artifact / ('sprite-' + label + '.bmp'); start = len(messages)
        command('capture', path=str(path))
        wait(lambda: any(m.get('event') == 'capture_done' and m.get('path') == str(path) for m in messages[start:]))
        image = QImage(str(path)); assert not image.isNull(); image.save(str(path.with_suffix('.png')))
        return image
    def reload_done():
        wait(lambda: window.reload_request is None)
        command('play'); command('pause')
    try:
        window.actions['Play'].trigger()
        wait(lambda: window.runtime.ready and window.runtime.state == 'running' and window.container is not None)
        command('pause'); original = capture('editor-original'); pid = window.runtime.process.processId()
        check('Editor loads all sprite frames through native GPU', len([m for m in messages if m.get('event') == 'asset_loaded']) == 1)
        window.refresh_hierarchy('player')
        field = next(w for w in window.inspector.findChildren(QSpinBox) if w.accessibleName() == 'player sprite frame')
        field.setFocus(); QTest.keyClick(field, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier); QTest.keyClicks(field, '1'); QTest.keyClick(field, Qt.Key.Key_Return)
        wait(lambda: entity(window.scene, 'player')['sprite']['frame'] == 1); reload_done()
        changed = capture('editor-frame')
        check('Inspector frame edit changes native pixels in the same process', changed != original and window.runtime.process.processId() == pid)
        check('Frame edit affects only the selected entity', entity(snapshot()['scene'], 'player')['sprite']['frame'] == 1 and entity(snapshot()['scene'], 'third')['sprite']['frame'] == 2)
        window.actions['Undo'].trigger(); reload_done(); check('Undo restores exact sprite pixels', capture('editor-undo') == original)
        window.actions['Redo'].trigger(); reload_done(); check('Redo restores exact sprite pixels', capture('editor-redo') == changed)
        window.refresh_hierarchy('player')
        flag = next(w for w in window.inspector.findChildren(QCheckBox) if w.accessibleName() == 'player sprite flip_x')
        QTest.mouseClick(flag, Qt.MouseButton.LeftButton, pos=QPoint(8, flag.height() // 2))
        wait(lambda: entity(window.scene, 'player')['sprite']['flip_x']); reload_done()
        flipped = capture('editor-flip'); check('Inspector flip changes native pixels', flipped != changed)
        before = snapshot()
        invalid = deepcopy(compile_graph(window.adapter.document(), window.scene)); invalid['scene']['sprite_assets'][0]['columns'] = 3
        command('load_ir', error=True, ir=invalid)
        check('Invalid atlas dimensions preserve live state and framebuffer', snapshot() == before and capture('failed-reload') == flipped)
        command('load_ir', ir=compile_graph(window.adapter.document(), window.scene)); command('play'); command('pause')
        check('Valid reload recovers without replacing the process', capture('recovered') == flipped and window.runtime.process.processId() == pid)
        window.screen().grabWindow(int(window.winId())).save(str(artifact / 'sprite-desktop.png'))
        # Return to the original demo so replay checkpoints have deterministic starting values.
        window.actions['Undo'].trigger(); reload_done(); window.actions['Undo'].trigger(); reload_done()
        check('Authoring Undo returns to the original atlas', entity(window.scene, 'player')['sprite'] == dict(asset='atlas', frame=0, flip_x=False, flip_y=False))
        check('Sprite project saves', window.save_project()); signature = window.signature()
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.open_project(project / 'project.json'); check('Save/reopen preserves sprite assets', window.signature() == signature)
        results, ticks = [], []; window.builder.finished.connect(results.append)
        timer = QTimer(); timer.timeout.connect(lambda: ticks.append(time.monotonic())); timer.start(100)
        window.actions['Build Game'].trigger(); wait(lambda: not window.builder.busy and bool(results), 360); timer.stop()
        (artifact / 'sprite-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
        check('Build Game succeeds while the editor stays responsive', results == [True] and len(ticks) > 5)
        packaged = workspace / 'relocated game'; packaged.mkdir(); build = project / 'build'
        for name in ('node_view.exe', 'node_game_view.exe', 'SDL3.dll', 'SDL3_image.dll', 'SDL3_mixer.dll'): shutil.copy2(build / name, packaged / name)
        for name in ('assets', 'shaders'): shutil.copytree(build / name, packaged / name)
        shutil.copy2(project / 'generated/game.ir.json', packaged / 'game.ir.json')
        shutil.copy2(project / 'input-replay.json', packaged / 'input-replay.json')
        # Close the editor before moving its source project; only the exported files remain at their original path.
        window.saved_signature = window.signature(); window.document_changed(); window.close()
        project.rename(workspace / 'source-moved')
        system = Path(os.environ['SystemRoot']); clean = dict(os.environ); clean['PATH'] = str(system / 'System32') + os.pathsep + str(system)
        digests = {}
        for frame, label, expected in [(3, 'frame-one', (1, False, False)), (5, 'flip-x', (1, True, False)),
                                        (7, 'flip-both', (1, True, True)), (9, 'frame-two', (2, True, True))]:
            states, bitmaps = {}, {}
            for mode, exe in [('preview', 'node_view.exe'), ('compiled', 'node_game_view.exe')]:
                prefix = artifact / f'sprite-{label}-{mode}'
                args = [str(packaged / exe), '--frames', str(frame), '--input-replay', str(packaged / 'input-replay.json'),
                    '--capture', str(prefix.with_suffix('.bmp')), '--output', str(prefix.with_suffix('.json'))]
                if mode == 'preview': args += ['--ir', str(packaged / 'game.ir.json')]
                run = subprocess.run(args, cwd=packaged, env=clean, capture_output=True, text=True, encoding='utf-8', timeout=30)
                check(label + ' relocated ' + mode + ' runs with clean PATH and source moved', run.returncode == 0)
                states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8')); bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
            check(label + ' preview/export states and GPU bytes match', states['preview'] == states['compiled'] and bitmaps['preview'] == bitmaps['compiled'])
            binding = entity(states['compiled']['scene'], 'player')['sprite']
            check(label + ' replay changes the expected frame and flips', tuple(binding[k] for k in ('frame', 'flip_x', 'flip_y')) == expected)
            QImage(str(prefix.with_suffix('.bmp'))).save(str(prefix.with_suffix('.png')))
            digests[label] = hashlib.sha256(bitmaps['compiled']).hexdigest()
        check('All four interactions have distinct visible output', len(set(digests.values())) == 4)
        check('Only deliberate invalid atlas produces an error', len([m for m in messages if m.get('event') == 'node_error']) == 1)
        save_json(artifact / 'sprite-workflow-checks.json', dict(passed=True, checks=checks,
            package=str(packaged), heartbeat_ticks=len(ticks), bitmap_sha256=digests))
    finally:
        if window.builder.busy: window.builder.cancel(); wait(lambda: not window.builder.busy)
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()


if __name__ == '__main__': main()
