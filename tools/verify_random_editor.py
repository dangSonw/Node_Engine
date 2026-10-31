"""Author seeded random values and exercise physical input in embedded Preview."""
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
    directory=ROOT/'.cache'/('random-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/random_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='random-editor-'+uuid.uuid4().hex
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
    try:
        check('Native build matches sources',current(ROOT/'build/node_view.exe'))
        extra=window.adapter.add(5021)
        check('Get Random Seed is available in editor',extra is not None)
        window.actions['Undo'].trigger()
        check('Undo removes the new node',not any(n.get_property('stable_id')==extra.get_property('stable_id') for n in window.adapter.graph.all_nodes()))
        window.actions['Redo'].trigger()
        check('Redo restores the node',any(n.get_property('stable_id')==extra.get_property('stable_id') for n in window.adapter.graph.all_nodes()))
        for node_type in (5025,5026):
            created=window.adapter.add(node_type)
            check('Spatial random node '+str(node_type)+' can be authored',created is not None)
            window.actions['Undo'].trigger()
        for base in (5100,5110,5120):
            for offset in range(6):
                created=window.adapter.add(base+offset)
                check('Collection random node '+str(base+offset)+' can be authored',created is not None)
                window.actions['Undo'].trigger()
                check('Undo clears removed node Inspector '+str(base+offset),window.inspected_node is None and window.inspector_form.rowCount()==0)
        check('Random graph validates and saves',window.validate_graph() and window.save_project())
        check('Random graph reopens exactly',load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        command('pause'); initial=snapshot(); check('Startup uses seed 42',initial['random']['seed']==42)
        command('play'); focus(); key(0x20); command('pause'); first=snapshot()
        check('Physical Space produces a draw and moves the robot',first['random']!=initial['random'] and first['entities']!=initial['entities'])
        check('Physical Space selects items and shuffles cards',all(name in first['variables'] for name in ('item','item_index','loot','loot_index','deck')))
        check('Physical Space places the direction marker',first['entities']['direction']['position']!=initial['entities']['direction']['position'] and abs(sum(x*x for x in first['variables']['direction']['value'])-1)<1e-14)
        command('play'); key(ord('R')); key(0x20); command('pause'); repeated=snapshot()
        check('Physical reset reproduces the first draw',repeated['random']==first['random'] and repeated['entities']==first['entities'] and repeated['variables']==first['variables'])
        command('play'); key(ord('S')); command('pause'); saved=snapshot()
        check('Physical Save succeeds',saved['persistence']['success'])
        command('play'); key(0x20); command('pause'); changed=snapshot()
        check('Another draw advances the stream',changed['random']!=saved['random'])
        command('play'); key(ord('L')); command('pause'); loaded=snapshot()
        check('Physical Load restores stream, robot and dice',loaded['persistence']['success'] and loaded['random']==saved['random'] and loaded['entities']==saved['entities'] and loaded['variables']==saved['variables'])
        nodes=[n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='direction']
        window.adapter.graph.clear_selection(); nodes[0].set_selected(True); window.inspect_node(nodes[0])
        window.adapter.graph.reset_zoom(); window.adapter.graph.center_on(nodes); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/random-editor.png'
        check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('stop'); check('Stop clears the random stream','random' not in snapshot())
        command('play'); command('pause'); check('Restart runs the authored seed again',snapshot()['random']==initial['random'])
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for code in (0x20,ord('R'),ord('S'),ord('L')): user32.keybd_event(code,0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/random-editor-checks.json',report)
    return report

if __name__=='__main__': print('Random editor:',len(verify()['checks']),'checks passed.')
