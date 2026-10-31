"""Build the project authored by verify_prefabs_workflow through the real editor."""
from pathlib import Path
import json
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QSettings, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow

artifact = ROOT / 'artifacts/validation'
workflow = json.loads((artifact / 'prefab-workflow-checks.json').read_text('utf-8'))
assert workflow['passed']
project = Path(workflow['project'])
app = QApplication([]); app.setQuitOnLastWindowClosed(False)
window = MainWindow(project, QSettings(str(project.parent / 'build-layout.ini'), QSettings.IniFormat))
area = window.screen().availableGeometry()
window.resize(min(1450, area.width()-40), min(850, area.height()-60)); window.move(area.left()+20, area.top()+20)
window.show()
results, checks, ticks = [], [], []
window.builder.finished.connect(results.append)
heartbeat = QTimer(); heartbeat.timeout.connect(lambda: ticks.append(time.monotonic())); heartbeat.start(50)


def wait(predicate, timeout=420):
    deadline = time.monotonic()+timeout
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), window.build_output.toPlainText()[-6000:]


def check(label, result):
    assert result, label
    checks.append(label); print('PASS '+label, flush=True)


try:
    check('Reopened project contains two authored prefab instances', len(window.scene['prefab_instances']) == 2)
    window.actions['Build Game'].trigger()
    check('Build Game starts an asynchronous worker', window.builder.busy)
    wait(lambda: bool(results))
    (artifact / 'prefab-editor-build-output.log').write_text(window.build_output.toPlainText(), 'utf-8')
    check('Editor reports successful native build', results == [True])
    check('GUI event loop remains responsive during build', len(ticks) > 5)
    build = project.parent / 'build'
    check('Project native preview fingerprint matches current sources', current(build / 'node_view.exe'))
    check('Build copies Blockbench geometry into standalone asset tree',
          (build / 'assets/robot.gltf').read_bytes() == (project.parent / 'assets/robot.gltf').read_bytes())
    states = []
    for name, extra in [('node_preview.exe', ['--ir', str(project.parent / 'generated/game.ir.json')]), ('node_game.exe', [])]:
        result = subprocess.run([str(build / name), *extra, '--frames', '0'], cwd=build,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        check(name+' runs from the build directory', result.returncode == 0)
        states.append(json.loads(result.stdout))
    check('Authored preview and exported game states match', states[0] == states[1])
    check('Export keeps six entities and two real prefab instances', len(states[1]['entities']) == 6 and
          len(states[1]['scene']['prefab_instances']) == 2 and len(states[1]['prefab_state']['entities']) == 6)
    capture = artifact / 'prefab-authored-standalone.bmp'
    result = subprocess.run([str(build / 'node_game_view.exe'), '--frames', '1', '--capture', str(capture)],
                            cwd=build, capture_output=True, text=True, encoding='utf-8', timeout=40)
    check('Standalone GPU game loads assets using its own build directory', result.returncode == 0 and capture.is_file() and
          any(json.loads(line).get('event') == 'capture_done' for line in result.stdout.splitlines() if line.startswith('{')))
    from PySide6.QtGui import QImage
    image = QImage(str(capture)); pixels = sum(image.pixelColor(x, y).red() > 40
        for y in range(0, image.height(), 3) for x in range(0, image.width(), 3))
    check('Standalone GPU capture contains rendered geometry', pixels > 50)
    image.save(str(artifact / 'prefab-authored-standalone.png'))
    save_json(artifact / 'prefab-editor-build-checks.json', {'passed': True, 'checks': checks,
        'project': str(project), 'heartbeat_ticks': len(ticks), 'colored_pixels': pixels, 'state': states[1]})
finally:
    heartbeat.stop()
    if window.builder.busy:
        window.builder.cancel(); wait(lambda: not window.builder.busy, 20)
    window.runtime.shutdown(); window.saved_signature = window.signature()
    window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete); app.processEvents()
