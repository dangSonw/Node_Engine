"""Author Unscaled in Qt, then exercise real keyboard input in the embedded SDL game."""
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
from PySide6.QtCore import QEvent,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QLineEdit
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify():
    directory=ROOT/'.cache'/('unscaled-timer-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/unscaled_timer_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='unscaled-timer-editor-'+uuid.uuid4().hex
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
    def world(state): return {key:state[key] for key in ('time','entities','timers')}
    def find(nid): return next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    def edit(text):
        window.inspect_node(find('game_timer'))
        field=next(f for f in window.inspector.findChildren(QLineEdit) if f.property('domain_property')=='value_Unscaled')
        field.setFocus(); field.selectAll(); QTest.keyClicks(field,text); QTest.keyClick(field,Qt.Key.Key_Return)
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        check('Old timer graphs default to scaled',find('game_timer').get_property('value_Unscaled') is False)
        edit('1'); check('Inspector rejects non-boolean clock mode',find('game_timer').get_property('value_Unscaled') is False)
        edit('true'); check('Inspector authors unscaled timer',find('game_timer').get_property('value_Unscaled') is True)
        window.actions['Undo'].trigger(); check('Undo restores scaled mode',find('game_timer').get_property('value_Unscaled') is False)
        window.actions['Redo'].trigger(); check('Redo restores unscaled mode',find('game_timer').get_property('value_Unscaled') is True)
        window.actions['Undo'].trigger()
        check('Timer graph validates and saves',window.validate_graph() and window.save_project())
        check('Timer graph reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        focus(); key(ord('0')); command('pause'); frozen=snapshot()
        check('Physical 0 freezes game clock',frozen['clock']['scale']==0 and frozen['clock']['dt']==0)
        command('play'); QTest.qWait(400); command('pause'); later=snapshot()
        check('Unscaled robot moves during game freeze',later['entities']['player']==frozen['entities']['player'] and later['entities']['menu']['rotation'][1]>frozen['entities']['menu']['rotation'][1] and later['time']==frozen['time'])
        QTest.qWait(300); check('Editor Pause freezes both clock domains',snapshot()==later)
        command('play'); key(ord('P')); command('pause'); paused=snapshot()
        command('play'); QTest.qWait(320); command('pause'); check('Manual Pause freezes the unscaled timer',world(snapshot())==world(paused))
        command('play'); key(ord('S')); command('pause'); saved=snapshot()
        check('Physical S saves both stopped timers',saved['persistence']['success'])
        command('play'); key(ord('U')); key(ord('1')); QTest.qWait(320); command('pause'); changed=snapshot()
        check('Physical U and 1 resume both clocks',changed['time']>saved['time'] and changed['entities']['menu']['rotation'][1]>saved['entities']['menu']['rotation'][1])
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Physical L restores frozen world and manually paused timer',loaded['persistence']['success'] and world(loaded)==world(saved) and loaded['clock']['scale']==0)
        command('play'); key(ord('R')); QTest.qWait(2200); command('pause'); resumed=snapshot()
        check('Unscaled countdown automatically resumes after two seconds',resumed['clock']['scale']==1 and resumed['time']>loaded['time'] and all(t['name']!='resume' for t in resumed['timers']))
        window.adapter.graph.clear_selection(); node=find('menu_timer'); node.set_selected(True); window.inspect_node(node)
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/unscaled-timer-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); stopped=snapshot()
        check('Stop clears both timer domains',not stopped['timers'] and stopped['frame']==0)
        command('play'); command('pause'); check('Restart creates both timer modes',len(snapshot()['timers'])==2)
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for letter in '01PURSL': user32.keybd_event(ord(letter),0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/unscaled-timer-editor-checks.json',report)
    return report


if __name__=='__main__': print('Unscaled timer editor:',len(verify()['checks']),'checks passed.')
