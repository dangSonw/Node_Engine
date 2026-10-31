"""Real editor import, failed-reload recovery and relocated native GPU export."""
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
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit
from editor.core.compiler import compile_graph
from editor.core.document import save_json, load_project
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow
from tools.create_texture_demo import create
from tests.test_textures import rgb


def main():
    artifact = ROOT / 'artifacts/validation'
    workspace = ROOT / '.cache' / ('texture-' + uuid.uuid4().hex[:8])
    source = create(workspace / 'source')
    project = workspace / 'project'; project.mkdir()
    manifest, graph, scene = load_project(source / 'project.json')
    scene['entities'][0].pop('mesh'); manifest['assets'] = []
    save_json(project / 'project.json', manifest)
    save_json(project / manifest['graph'], graph); save_json(project / manifest['scene'], scene)
    assert current(ROOT / 'build/node_view.exe')
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    window = MainWindow(project / 'project.json', QSettings(str(project / 'layout.ini'), QSettings.IniFormat))
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    window.resize(1600, 960); window.show()
    messages, checks = [], []
    window.runtime.message.connect(messages.append)
    def wait(predicate, timeout=20):
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
    def snapshot():
        return next(m['state'] for m in command('snapshot') if m['event'] == 'snapshot')
    def capture(label):
        path = artifact / ('texture-' + label + '.bmp'); start = len(messages)
        command('capture', path=str(path))
        wait(lambda: any(m.get('event') == 'capture_done' and m.get('path') == str(path) for m in messages[start:]))
        image = QImage(str(path)); assert not image.isNull()
        image.save(str(path.with_suffix('.png')))
        return image
    try:
        window.refresh_hierarchy('board')
        def choose():
            dialog = app.activeModalWidget()
            assert isinstance(dialog, QFileDialog)
            field = dialog.findChild(QLineEdit, 'fileNameEdit')
            field.setText(str(source / 'assets/board.glb'))
            QTest.keyClick(field, Qt.Key.Key_Return)
        QTimer.singleShot(100, choose)
        window.actions['Import Model…'].trigger()
        mesh = window.scene['entities'][0]['mesh']
        check('File dialog imports GLB into selected entity', mesh == 'assets/board/board.glb')
        check('Import copies PNG and percent-encoded JPEG dependencies',
            (project / 'assets/board/images/quadrants.png').is_file() and
            (project / 'assets/board/images/solid color.jpg').is_file())
        window.actions['Undo'].trigger()
        check('Undo removes the assigned mesh', not window.scene['entities'][0].get('mesh'))
        window.actions['Redo'].trigger()
        check('Redo restores the mesh', window.scene['entities'][0]['mesh'] == mesh)
        source.rename(workspace / 'source-unavailable')
        window.actions['Play'].trigger()
        wait(lambda: window.runtime.ready and window.runtime.state == 'running' and window.container is not None)
        command('pause')
        original = capture('editor')
        check('Embedded native viewport renders copied PNG after source directory is moved', rgb(original, -.6, -.9) == (255, 0, 0))
        check('Embedded native viewport renders copied JPEG', all(abs(a-b)<=2 for a,b in zip(rgb(original, 2, 1.5), (32,160,225))))
        before = snapshot(); pid = window.runtime.process.processId()
        image_path = project / 'assets/board/images/quadrants.png'
        original_bytes = image_path.read_bytes()
        try:
            image_path.write_bytes(b'broken PNG')
            command('load_ir', error=True, ir=compile_graph(window.adapter.document(), window.scene))
            check('Failed texture reload keeps scene state and process', snapshot() == before and window.runtime.process.processId() == pid)
            check('Failed texture reload keeps previous GPU resources and pixels', capture('failed-reload') == original)
        finally:
            image_path.write_bytes(original_bytes)
        command('load_ir', ir=compile_graph(window.adapter.document(), window.scene)); command('play'); command('pause')
        check('Fixed texture reload succeeds in same process', capture('recovered') == original and window.runtime.process.processId() == pid)
        # Widen the scene panel for a useful complete-board desktop artifact.
        window.splitter.setSizes([260, 1000]); window.output_tabs.setCurrentWidget(window.console)
        QTest.qWait(150)
        window.screen().grabWindow(int(window.winId())).save(str(artifact / 'texture-desktop.png'))
        check('Texture project saves', window.save_project())
        signature = window.signature()
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.open_project(project / 'project.json')
        check('Reopen preserves imported asset assignment', window.signature() == signature)
        results, ticks = [], []
        window.builder.finished.connect(results.append)
        timer = QTimer(); timer.timeout.connect(lambda: ticks.append(time.monotonic())); timer.start(100)
        window.actions['Build Game'].trigger()
        wait(lambda: not window.builder.busy and bool(results), 300)
        timer.stop()
        (artifact / 'texture-editor-build.log').write_text(window.build_output.toPlainText(), 'utf-8')
        check('Editor builds with responsive event loop', results == [True] and len(ticks)>5)
        # Only runtime files go into a separate directory, with a working directory
        # that contains no source model, Python packages or development dependencies.
        packaged = workspace / 'relocated game'; packaged.mkdir()
        build = project / 'build'
        for name in ('node_view.exe', 'node_game_view.exe', 'SDL3.dll', 'SDL3_image.dll', 'SDL3_mixer.dll'):
            shutil.copy2(build / name, packaged / name)
        for name in ('shaders', 'assets'): shutil.copytree(build / name, packaged / name)
        shutil.copy2(project / 'generated/game.ir.json', packaged / 'game.ir.json')
        check('Package contains image decoder and all nested texture files',
            (packaged / 'SDL3_image.dll').is_file() and (packaged / 'SDL3_mixer.dll').is_file() and (packaged / 'assets/board/images/mip.png').is_file())
        states, bitmaps = {}, {}
        clean_env = dict(os.environ)
        system = Path(os.environ['SystemRoot'])
        clean_env['PATH'] = str(system / 'System32') + os.pathsep + str(system)
        for mode, exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
            prefix = artifact / ('texture-relocated-' + mode)
            args = [str(packaged / exe), '--frames', '3', '--capture', str(prefix.with_suffix('.bmp')),
                    '--output', str(prefix.with_suffix('.json'))]
            if mode == 'preview': args += ['--ir', str(packaged / 'game.ir.json')]
            run = subprocess.run(args, cwd=packaged, env=clean_env, capture_output=True, text=True, encoding='utf-8', timeout=30)
            check('Relocated ' + mode + ' runs', run.returncode == 0)
            states[mode] = json.loads(prefix.with_suffix('.json').read_text('utf-8'))
            bitmaps[mode] = prefix.with_suffix('.bmp').read_bytes()
        check('Preview and exported game states are identical', states['preview'] == states['compiled'])
        check('Preview and exported GPU bitmaps are identical', bitmaps['preview'] == bitmaps['compiled'])
        exported = QImage(str(artifact / 'texture-relocated-compiled.bmp'))
        check('Exported texture has correct measured red pixel', rgb(exported, -4.4, 1.9) == (255,0,0))
        check('Exported alpha blending has correct measured pixel', all(abs(a-b)<=2 for a,b in zip(rgb(exported,-.4,1.1),(187,187,255))))
        check('Only deliberately broken texture reports a runtime error', len([m for m in messages if m.get('event')=='node_error']) == 1)
        exported.save(str(artifact / 'texture-relocated-compiled.png'))
        save_json(artifact / 'texture-workflow-checks.json', dict(passed=True, checks=checks,
            project=str(project), package=str(packaged), heartbeat_ticks=len(ticks),
            bitmap_sha256=hashlib.sha256(bitmaps['compiled']).hexdigest()))
    finally:
        if window.builder.busy:
            window.builder.cancel(); wait(lambda: not window.builder.busy)
        window.runtime.shutdown(); wait(lambda: not window.runtime.active)
        window.saved_signature = window.signature(); window.document_changed(); window.close(); window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()


if __name__ == '__main__': main()
