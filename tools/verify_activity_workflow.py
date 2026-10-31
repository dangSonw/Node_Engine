"""Actual Qt Inspector, SDL rendering, suspension and exported-game parity."""
from pathlib import Path
import hashlib
import ctypes
import json
import shutil
import subprocess
import sys
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QSpinBox
from editor.core.document import save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from editor.ui.main_window import MainWindow

artifact=ROOT/'artifacts/validation'
project=ROOT/'.cache'/('activity-'+uuid.uuid4().hex[:8])
shutil.copytree(ROOT/'examples/activity_demo',project,ignore=shutil.ignore_patterns('generated','build'))
assert current(ROOT/'build/node_view.exe')
app=QApplication([]); app.setQuitOnLastWindowClosed(False)
window=MainWindow(project/'project.json',QSettings(str(project/'layout.ini'),QSettings.IniFormat))
window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
window.resize(1600,960); window.show()
messages,checks=[],[]
window.runtime.message.connect(messages.append)

def wait(predicate,timeout=20):
    deadline=time.monotonic()+timeout
    while not predicate() and time.monotonic()<deadline: QTest.qWait(10)
    assert predicate(),window.console.toPlainText()

def check(label,result):
    assert result,label
    checks.append(label); print('PASS '+label,flush=True)

def command(name,**data):
    begin=len(messages); serial=window.runtime.send(name,**data)
    wait(lambda:any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[begin:]))
    result=messages[begin:]
    assert not any(m.get('event')=='node_error' for m in result),result
    return result

def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
def entities(state): return {e['id']:e for e in state['scene']['entities']}
def timer(state): return next(t for t in state['timers'] if t['owner']=='player')
def widget(kind,label): return next(w for w in window.inspector.findChildren(kind) if w.accessibleName()==label)
def colored(image):
    return sum((c.blue()>c.red()*1.2 and c.red()>c.green()*1.2 and c.red()>40) or
               (c.green()>70 and c.blue()>70 and c.red()<60)
               for y in range(0,image.height(),3) for x in range(0,image.width(),3)
               for c in [image.pixelColor(x,y)])

try:
    window.refresh_hierarchy('group')
    active=widget(QCheckBox,'group active'); active.setFocus(); QTest.keyClick(active,Qt.Key.Key_Space)
    check('Keyboard disables parent and marks descendants inactive',not entities({'scene':window.scene})['group']['active'] and
          '[inactive]' in window.hierarchy.topLevelItem(0).child(0).child(0).text(0))
    window.refresh_hierarchy('player')
    check('Child retains its own Active flag',widget(QCheckBox,'player active').isChecked())
    layer=widget(QSpinBox,'player layer'); layer.setFocus(); layer.selectAll(); QTest.keyClicks(layer,'12'); QTest.keyClick(layer,Qt.Key.Key_Return)
    check('Keyboard changes entity layer',entities({'scene':window.scene})['player']['layer']==12)
    window.actions['Undo'].trigger()
    check('Undo restores entity layer',widget(QSpinBox,'player layer').value()==3)
    window.actions['Undo'].trigger()
    check('Undo restores active ancestry',entities({'scene':window.scene})['group'].get('active',True))
    window.actions['Redo'].trigger()
    check('Redo restores inactive ancestry',not entities({'scene':window.scene})['group']['active'])
    check('Authored activity saves',window.save_project())
    signature=window.signature(); window.open_project(project/'project.json')
    check('Reopen preserves activity and layer',window.signature()==signature)
    original=json.loads((ROOT/'examples/activity_demo/scenes/main.json').read_text('utf-8'))
    window.push_scene('Restore activity demo',original,'group'); window.save_project()
    window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running')
    command('pause'); command('frame_scene'); command('camera',yaw=15,pitch=15)
    # Scene-owned toggle continues even after the group is disabled.
    command('play')
    observed=[]
    deadline=time.monotonic()+4
    while time.monotonic()<deadline and not (any(not entities(s)['group']['active'] for s in observed) and
                                            len(observed)>1 and entities(observed[-1])['group']['active']):
        QTest.qWait(80); observed.append(snapshot())
    inactive=[s for s in observed if not entities(s)['group']['active']]
    check('Scene timer disables and reactivates the group',bool(inactive) and entities(observed[-1])['group']['active'])
    check('Inactive group excludes both children from active layer query',all(s['variables']['active_actors']['value']==[] for s in inactive))
    check('Owned timer is suspended independently of manual Pause',all(timer(s).get('suspended') and not timer(s)['paused'] for s in inactive))
    check('Suspended timer keeps remaining time and rotation',len({timer(s)['remaining'] for s in inactive})==1 and
          len({tuple(entities(s)['player']['rotation']) for s in inactive})==1)
    check('Independent beacon keeps updating',entities(inactive[-1])['beacon']['rotation'][1]>entities(inactive[0])['beacon']['rotation'][1])
    check('Active layer query recovers both children',observed[-1]['variables']['active_actors']['value']==['child','player'])
    command('pause'); window.refresh_hierarchy('group'); window.frame_all(); window.raise_(); window.activateWindow(); QTest.qWait(150)
    user32=ctypes.windll.user32
    from ctypes import wintypes
    user32.WindowFromPoint.argtypes=[wintypes.POINT]
    user32.WindowFromPoint.restype=ctypes.c_void_p
    hwnd=int(window.winId())
    rect=wintypes.RECT()
    assert user32.GetWindowRect(ctypes.c_void_p(int(window.container.winId())),ctypes.byref(rect))
    covering=user32.WindowFromPoint(wintypes.POINT((rect.left+rect.right)//2,(rect.top+rect.bottom)//2))
    check('Desktop viewport belongs to the editor',covering==hwnd or bool(user32.IsChild(ctypes.c_void_p(hwnd),ctypes.c_void_p(covering))))
    window.screen().grabWindow(hwnd).save(str(artifact/'activity-desktop.png'))
    pixels=colored(window.screen().grabWindow(int(window.container.winId())).toImage())
    check('Desktop compositor shows embedded native robots',pixels>50)
    command('stop'); stopped=snapshot()
    check('Stop resets active state and clears runtime timers',entities(stopped)['group']['active'] and not stopped['timers'])
    window.runtime.shutdown(); wait(lambda:not window.runtime.active)
    parity={}; visible_pixels={}
    for frames in (15,45,75):
        states,images={},{}
        for mode,exe in [('preview','node_view.exe'),('compiled','node_game_view.exe')]:
            prefix=artifact/f'activity-{mode}-{frames}'
            args=[str(ROOT/'build'/exe),'--project-root',str(ROOT/'examples/activity_demo'),'--frames',str(frames),
                  '--capture',str(prefix.with_suffix('.bmp')),'--output',str(prefix.with_suffix('.json'))]
            if mode=='preview': args+=['--ir',str(ROOT/'examples/activity_demo/generated/game.ir.json')]
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=40)
            check(f'{mode} executes {frames} frames',result.returncode==0)
            states[mode]=json.loads(prefix.with_suffix('.json').read_text('utf-8')); images[mode]=prefix.with_suffix('.bmp').read_bytes()
        check(f'{frames}-frame native states match',states['preview']==states['compiled'])
        check(f'{frames}-frame GPU bitmaps match',images['preview']==images['compiled'])
        state=states['compiled']; active=frames!=45
        check(f'{frames}-frame activity and layer query match expected state',entities(state)['group']['active']==active and
              state['variables']['active_actors']['value']==(['child','player'] if active else []))
        check(f'{frames}-frame owner timer suspension matches activity',timer(state).get('suspended',False)==(not active))
        visible_pixels[frames]=colored(QImage(str(artifact/f'activity-compiled-{frames}.bmp')))
        parity[str(frames)]={'state_equal':True,'bitmap_sha256':hashlib.sha256(images['compiled']).hexdigest()}
    check('GPU shows fewer robots while group is inactive',visible_pixels[45]>50 and visible_pixels[15]>visible_pixels[45]*1.5 and visible_pixels[75]>visible_pixels[45]*1.5)
    check('No runtime node errors occurred',not any(m.get('event')=='node_error' for m in messages))
    save_json(artifact/'activity-workflow-checks.json',{'passed':True,'checks':checks,'messages':messages,'parity':parity,
        'project':str(project/'project.json'),'compositor_pixels':pixels,'gpu_pixels':visible_pixels})
finally:
    window.runtime.shutdown(); wait(lambda:not window.runtime.active)
    window.saved_signature=window.signature(); window.document_changed(); window.close(); window.deleteLater()
    app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
