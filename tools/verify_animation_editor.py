"""Author animation nodes, save/reopen, and operate the real embedded SDL preview."""
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo

def verify():
    directory=ROOT/'.cache'/('animation-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/animation_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage':node['values']['Game ID']='animation-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    user32=ctypes.windll.user32; user32.GetForegroundWindow.restype=wintypes.HWND
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]; user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory))
    def check(label,okay):
        if not okay:raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,seconds=40):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end:QTest.qWait(15)
        if not predicate():raise RuntimeError(window.console.toPlainText()+'\n'+window.build_output.toPlainText())
    def command(name,**data):
        begin=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]; check('Preview '+name+' succeeds',not any(m.get('event')=='node_error' for m in result)); return result
    def snapshot():return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    def key(code):
        user32.keybd_event(code,0,0,0); QTest.qWait(80); user32.keybd_event(code,0,2,0); QTest.qWait(50)
    def focus():
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert user32.GetWindowRect(hwnd,ctypes.byref(rect))
        # Foreground activation may be denied to a launched test process. Expose
        # its own viewport, then let an actual mouse click activate the window.
        assert user32.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        try:
            user32.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
            user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(80)
        finally:user32.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        info=GuiInfo(); info.cbSize=ctypes.sizeof(info)
        check('Mouse focuses the embedded viewport',bool(user32.GetGUIThreadInfo(0,ctypes.byref(info))) and info.focus==hwnd)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        start=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='walk')
        seek=window.adapter.add(13008); seek.set_property('value_Time',.25)
        start.outputs()['Out'].connect_to(seek.inputs()['In'])
        document=window.adapter.document(); window.actions['Undo'].trigger()
        check('Undo removes the animation wire',window.adapter.document()!=document)
        window.actions['Redo'].trigger(); check('Redo restores the animation wire',window.adapter.document()==document)
        check('Animation graph validates and saves',window.validate_graph() and window.save_project())
        reopened=load_project(directory/'project.json'); check('Animation node values and graph reopen exactly',reopened[1]==document)
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        QTest.qWait(150); command('pause'); first=snapshot()
        check('Authored seek runs in embedded preview',first['animation']['player']['time']>=.25 and first['animation']['player']['clip']=='Wave')
        QTest.qWait(120); check('Host Pause freezes both animation clocks',snapshot()==first)
        command('play'); focus(); key(ord('P')); key(ord('T')); command('pause'); paused=snapshot()
        check('Physical Pause and Seek hold the left robot at one second',paused['animation']['player']['paused'] and paused['animation']['player']['time']==1)
        command('play'); key(ord('S')); QTest.qWait(80); command('pause'); saved=snapshot()
        check('Physical Save succeeds with paused animation',saved['persistence']['success'] and saved['animation']['player']['paused'])
        command('play'); key(ord('3')); command('pause'); changed=snapshot()
        check('Physical 3 switches the selected robot to Walk',changed['animation']['player']['clip']=='Walk' and changed['animation']['player']['playing'])
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Physical Load restores the paused Wave pose',loaded['persistence']['success'] and loaded['animation']['player']==saved['animation']['player'])
        capture=ROOT/'artifacts/validation/animation-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        command('stop'); stopped=snapshot(); check('Stop restores bind poses and clears playback',stopped['frame']==0 and 'animation' not in stopped)
        command('play'); QTest.qWait(100); command('pause')
        check('Restart creates exactly two independent players',set(snapshot()['animation'])=={'player','walker'})
        check('Native sources remain unchanged',fingerprint()==report['native_fingerprint'])
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest(); report['passed']=True
    except Exception as error:report['error']=str(error); raise
    finally:
        for code in map(ord,'PTSL3'):user32.keybd_event(code,0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/animation-editor-checks.json',report)
    return report
if __name__=='__main__':print('Animation editor:',len(verify()['checks']),'checks passed.')
