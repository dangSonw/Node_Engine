"""Capture the actual desktop compositor before/after a function editor modal."""
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPoint, QSettings, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.registry import ROOT
from editor.core.document import save_json
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog

app=QApplication([])
app.setQuitOnLastWindowClosed(False)
window=MainWindow(ROOT/'examples/functions_demo/project.json',QSettings(str(ROOT/'.cache/function-capture.ini'),QSettings.IniFormat))
events=[]
window.runtime.message.connect(events.append)
window.show()


def wait(predicate):
    end=time.monotonic()+12
    while not predicate() and time.monotonic()<end:
        QTest.qWait(10)
    assert predicate(),window.console.toPlainText()


def capture(name):
    window.raise_()
    window.activateWindow()
    QTest.qWait(220)
    p=window.mapToGlobal(QPoint(0,0))
    image=window.screen().grabWindow(0,p.x(),p.y(),window.width(),window.height())
    image.save(str(ROOT/'artifacts/validation'/f'functions-desktop-{name}.png'))
    p=window.container.mapToGlobal(QPoint(0,0))
    view=window.screen().grabWindow(0,p.x(),p.y(),window.container.width(),window.container.height()).toImage()
    count=0
    for y in range(0,view.height(),3):
        for x in range(0,view.width(),3):
            c=view.pixelColor(x,y)
            # Purple or cyan robot pixels, excluding the dark background/Qt theme.
            count += (c.blue()>c.red()*1.2 and c.red()>c.green()*1.2 and c.red()>40) or (c.green()>70 and c.blue()>70 and c.red()<60)
    return {'robot_pixels':count,'container_visible':window.container.isVisible(),
            'foreign_visible':window.foreign_window.isVisible()}


try:
    window.play()
    wait(lambda:window.runtime.state=='running' and window.container is not None)
    QTest.qWait(160)
    window.pause()
    wait(lambda:window.runtime.state=='paused')
    window.runtime.send('camera',yaw=10,pitch=15)
    window.runtime.send('frame_scene')
    window.frame_all()
    results={'before':capture('before')}
    def close_dialog():
        dialog=app.activeModalWidget()
        assert isinstance(dialog,FunctionEditorDialog)
        dialog.reject()
    QTimer.singleShot(180,close_dialog)
    window.edit_function(1000002)
    results['after']=capture('after')
    save_json(ROOT/'artifacts/validation/functions-embedding-checks.json',results)
    print(results,flush=True)
    assert all(v['robot_pixels']>100 for v in results.values()),'Native viewport must remain visible after modal editing'
finally:
    window.runtime.shutdown()
    wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature()
    window.document_changed()
    window.close()
    app.processEvents()
