"""Exercise time controls and frozen saved worlds in the actual editor."""
import ctypes
import hashlib
from ctypes import wintypes
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
    directory=ROOT/'.cache'/('time-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/time_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='time-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory))
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate):
        end=time.monotonic()+40
        while not predicate() and time.monotonic()<end: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText())
    def command(name):
        begin=len(messages); serial=window.runtime.send(name)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]; check('Preview '+name,not any(m.get('event')=='node_error' for m in result)); return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    user32=ctypes.windll.user32
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    def focus():
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert user32.GetWindowRect(hwnd,ctypes.byref(rect))
        assert user32.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        try:
            user32.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
            user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(80)
        finally: user32.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        info=GuiInfo(); info.cbSize=ctypes.sizeof(info)
        check('Embedded viewport has physical focus',bool(user32.GetGUIThreadInfo(0,ctypes.byref(info))) and info.focus==hwnd)
    def key(code):
        user32.keybd_event(code,0,0,0); QTest.qWait(90); user32.keybd_event(code,0,2,0); QTest.qWait(70)
    def world(state): return {key:state[key] for key in ('time','entities','physics','animation','timers')}
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        for nid in range(5030,5035):
            created=window.adapter.add(nid)
            check('Time node '+str(nid)+' is available',created is not None)
            window.actions['Undo'].trigger()
            check('Undo clears time node Inspector',window.inspected_node is None)
        check('Time graph validates and saves',window.validate_graph() and window.save_project())
        check('Time graph reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        command('pause'); initial=snapshot()
        command('play'); focus(); key(ord('0')); command('pause'); frozen=snapshot()
        check('Physical 0 requests freeze',frozen['clock']['scale']==0 and frozen['clock']['dt']==0)
        command('play'); QTest.qWait(220); command('pause'); later=snapshot()
        check('Frozen physics, animation and timers remain exact',world(later)==world(frozen))
        check('Real clock, input frames and audio continue',later['clock']['real_time']>frozen['clock']['real_time'] and later['frame']>frozen['frame'] and later['audio']['sample_frames']>frozen['audio']['sample_frames'])
        command('play'); key(ord('1')); command('pause'); slow=snapshot()
        check('Physical 1 resumes at quarter speed',slow['clock']['scale']==.25 and abs(slow['clock']['dt']-.25*slow['clock']['unscaled_dt'])<1e-14 and slow['time']>later['time'])
        command('play'); key(ord('3')); command('pause'); fast=snapshot()
        check('Physical 3 selects double speed',fast['clock']['scale']==2 and abs(fast['clock']['dt']-2*fast['clock']['unscaled_dt'])<1e-14)
        command('play'); key(ord('0')); key(ord('S')); command('pause'); saved=snapshot()
        check('Physical S saves the frozen world',saved['persistence']['success'] and saved['clock']['scale']==0)
        command('play'); key(ord('2')); QTest.qWait(220); command('pause'); changed=snapshot()
        check('Physical 2 resumes normal simulation',changed['clock']['scale']==1 and changed['time']>saved['time'])
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Physical L restores the frozen world',loaded['persistence']['success'] and world(loaded)==world(saved) and loaded['clock']['scale']==0)
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='scale_0')
        window.adapter.graph.clear_selection(); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/time-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot()
        check('Stop resets both clocks and scale',stopped['clock']['scale']==1 and stopped['clock']['real_time']==0 and stopped['time']==0)
        command('play'); command('pause'); check('Restart runs at default scale',snapshot()['clock']['scale']==1)
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for code in (ord('0'),ord('1'),ord('2'),ord('3'),ord('S'),ord('L')): user32.keybd_event(code,0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/time-editor-checks.json',report)
    return report

if __name__=='__main__': print('Time editor:',len(verify()['checks']),'checks passed.')
