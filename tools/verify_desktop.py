"""Real Windows/Qt/SDL GPU integration checks, independent of desktop automation.

Runs our own application through Qt actions and records actual GPU captures.
Use --build to include the asynchronous per-project native build.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.registry import ROOT
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.ui.main_window import MainWindow

parser = argparse.ArgumentParser()
parser.add_argument('--build',action='store_true')
args = parser.parse_args()
app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
artifact = ROOT/'artifacts/validation'
artifact.mkdir(parents=True,exist_ok=True)
window = MainWindow(ROOT/'examples/blockbench_demo/project.json', QSettings(str(ROOT/'.cache/desktop-check.ini'),QSettings.IniFormat))
messages, checks, build_results = [], [], []
window.runtime.message.connect(messages.append)
window.builder.finished.connect(build_results.append)
window.show()
def wait(predicate, timeout=10):
    until = time.monotonic()+timeout
    while not predicate() and time.monotonic() < until:
        QTest.qWait(10)
    if not predicate():
        raise AssertionError('Timeout. Console: '+window.console.toPlainText())
def command(name, **data):
    before = len(messages)
    request = window.runtime.send(name,**data)
    wait(lambda:any(m.get('event')=='ack' and m.get('id')==request for m in messages[before:]))
    return messages[before:]
def snapshot():
    return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
def capture_image(path):
    before=len(messages)
    command('capture',path=str(path))
    wait(lambda:any(m.get('event')=='capture_done' and Path(m['path'])==path for m in messages[before:]))
    return QImage(str(path))
def check(name, predicate):
    assert predicate,name
    checks.append(name)
    print('PASS '+name,flush=True)
timer = QTimer()
heartbeats = [0]
timer.timeout.connect(lambda:heartbeats.__setitem__(0,heartbeats[0]+1))
timer.start(20)
try:
    QTest.qWait(150)
    window.frame_all()
    original = window.signature()
    if args.build:
        start = heartbeats[0]
        window.actions['Build Game'].trigger()
        wait(lambda:bool(build_results),timeout=240)
        check('Native build from GUI completes',build_results[-1])
        check('GUI event loop stays responsive during build',heartbeats[0]-start>10)
        (artifact/'editor-build.log').write_text(window.build_output.toPlainText(),encoding='utf-8')
    window.actions['Play'].trigger()
    wait(lambda:window.runtime.state=='running' and window.container is not None)
    wait(lambda:any(m.get('event')=='metrics' and m['frame']>=30 for m in messages))
    check('SDL GPU runtime embedded in Qt',window.container is not None and window.foreign_window is not None)
    check('Robot loaded by fastgltf',any(m.get('event')=='asset_loaded' and m['triangles']==108 for m in messages))
    window.actions['Pause'].trigger()
    wait(lambda:window.runtime.state=='paused')
    first = snapshot()
    QTest.qWait(120)
    check('Pause freezes graph execution',snapshot()['frame']==first['frame'])
    command('set_property',entity='player',property='rotation',value=[0,0,0])
    image = capture_image(artifact/'editor-viewport.bmp')
    check('Native GPU capture contains visible model',image.pixelColor(image.width()//2,image.height()//2)!=image.pixelColor(0,0))
    window.output_tabs.setCurrentWidget(window.console)
    window.hierarchy.setCurrentItem(window.hierarchy.topLevelItem(0).child(0))
    window.splitter.setSizes([650,550])
    QTest.qWait(200)
    window.screen().grabWindow(window.winId()).save(str(artifact/'editor-running.png'))
    command('set_property',entity='player',property='position',value=[.25,0,0])
    check('Live entity property reaches native runtime',snapshot()['entities']['player']['position']==[.25,0,0])
    window.actions['Stop'].trigger()
    wait(lambda:window.runtime.state=='stopped')
    stopped = snapshot()
    check('Stop resets frame and scene',stopped['frame']==0 and stopped['entities']['player']['position']==[0,0,0])
    ir = compile_graph(window.adapter.document(),window.scene)
    broken = deepcopy(ir)
    broken['scene']['entities'][0]['mesh']='assets/missing.gltf'
    before = len(messages)
    window.reload_preview(broken,True)
    wait(lambda:any(m.get('event')=='node_error' for m in messages[before:]))
    check('Bad asset leaves previous scene intact',snapshot()==stopped)
    check('Failed reload does not resume an old scene',window.runtime.state=='stopped' and window.reload_request is None)
    empty = deepcopy(ir)
    empty['scene']['entities'][0].pop('mesh')
    command('load_ir',ir=empty)
    capture = artifact/'reset-empty.bmp'
    image = capture_image(capture)
    check('Loading meshless scene clears previous geometry',image.pixelColor(image.width()//2,image.height()//2)==image.pixelColor(0,0))
    command('load_ir',ir=ir)
    window.runtime.process.kill()
    wait(lambda:not window.runtime.active and window.container is None)
    check('Runtime crash preserves graph and scene',window.signature()==original)
    window.actions['Play'].trigger()
    wait(lambda:window.runtime.state=='running' and window.container is not None)
    check('Preview restarts after runtime crash',window.runtime.ready)
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active and window.container is None)
    save_json(artifact/'desktop-checks.json',{'passed':True,'checks':checks,'events':messages})
finally:
    if window.runtime.active:
        window.runtime.process.kill()
        wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
