"""Exercise design Flow B with Windows mouse/keyboard input in the real editor."""
import ctypes
from ctypes import wintypes
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QEvent, QSettings, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit
from editor.core.document import create_project, save_json, load_project
from editor.core.compiler import compile_graph
from editor.core.codegen import export
from editor.core.runtime_build import current, fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.search import SearchDialog


def verify():
    directory = ROOT/'.cache'/('port-search-'+uuid.uuid4().hex[:10])
    project = create_project(directory, 'Port Search')
    folder = ROOT/'artifacts/validation'
    report = dict(passed=False, checks=[], project=str(project), native_fingerprint=fingerprint(),
                  dependencies={name:version(name) for name in ('NodeGraphQt','PySide6-Essentials')})
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(project, QSettings(str(directory/'layout.ini'), QSettings.Format.IniFormat))
    window.resize(1500,900); window.show()
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.ClientToScreen.argtypes = [wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    adapter = window.adapter
    messages = []; window.runtime.message.connect(messages.append)

    def check(label, passed):
        if not passed: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label, flush=True)

    def wait(predicate, timeout=15):
        deadline = time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(15)
        if not predicate(): raise AssertionError('Timed out: '+window.console.toPlainText())

    def key(code, ctrl=False):
        if ctrl: user32.keybd_event(0x11,0,0,0)
        user32.keybd_event(code,0,0,0); user32.keybd_event(code,0,2,0)
        if ctrl: user32.keybd_event(0x11,0,2,0)
        QTest.qWait(40)

    def text(value):
        QApplication.clipboard().setText(value); key(ord('A'),True); key(ord('V'),True)

    def drop(port, offset=QPoint(220,110)):
        viewer = adapter.graph.viewer()
        start = viewer.mapFromScene(port.view.sceneBoundingRect().center())
        end = start+offset
        check('Drag endpoint is inside the visible graph',viewer.viewport().rect().contains(end))
        def screen_point(point):
            local = viewer.viewport().mapTo(window,point)
            scale = window.devicePixelRatioF()
            native = wintypes.POINT(round(local.x()*scale),round(local.y()*scale))
            if not user32.ClientToScreen(int(window.winId()),ctypes.byref(native)):
                raise ctypes.WinError()
            return QPoint(native.x,native.y)
        start_global = screen_point(start)
        end_global = screen_point(end)
        user32.SetCursorPos(start_global.x(),start_global.y()); QTest.qWait(30)
        user32.mouse_event(2,0,0,0,0)
        for i in range(1,9):
            p = start_global+(end_global-start_global)*i/8
            user32.SetCursorPos(p.x(),p.y()); QTest.qWait(15)
        user32.mouse_event(4,0,0,0,0)
        wait(lambda:isinstance(QApplication.activeModalWidget(),SearchDialog))
        return QApplication.activeModalWidget()

    def command(name):
        begin = len(messages); serial = window.runtime.send(name)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result = messages[begin:]
        check('Runtime '+name+' succeeds',not any(m.get('event')=='node_error' for m in result))
        return result

    try:
        check('Native runtime matches the sources',current(ROOT/'build/node_view.exe'))
        adapter.load(dict(version=1,name='Port Search',nodes=[],links=[]))
        source = adapter.add(3001,[-270,-80]); source.set_property('value_Value',2.5)
        window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        wait(lambda:user32.GetForegroundWindow()==int(window.winId()))
        adapter.graph.center_on([source]); QTest.qWait(100)
        before = adapter.document(); index = adapter.graph.undo_stack().index()
        dialog = drop(source.outputs()['Value'])
        check('Physical port drag opens a typed search',dialog.windowTitle()=='Connect float output')
        check('Every offered endpoint has the exact type',all(adapter.registry[int(tid)].inputs and
              next(p.type for p in adapter.registry[int(tid)].inputs if p.name==port)=='float'
              for _,(tid,port) in dialog.items))
        text('Add Math')
        check('Text search exposes both Add ports',dialog.list.count()==2)
        key(0x28)
        check('Arrow selects Add B',tuple(dialog.list.currentItem().data(Qt.ItemDataRole.UserRole))==(4001,'B'))
        check('Search screenshot saved',dialog.grab().save(str(folder/'port-search-dialog.png')))
        key(0x0D); wait(lambda:QApplication.activeModalWidget() is None)
        created = next(n for n in adapter.graph.all_nodes() if n.get_property('type_id')==4001)
        check('Chosen port is connected and the new node is inspected',created.inputs()['B'] in source.outputs()['Value'].connected_ports()
              and window.inspected_node is created)
        after = adapter.document()
        key(ord('Z'),True)
        check('Physical Ctrl Z removes node and connection together',adapter.document()==before and adapter.graph.undo_stack().index()==index)
        window.actions['Redo'].trigger()
        check('Redo restores identical IDs, position and link',adapter.document()==after)
        adapter.selected.emit(created); QTest.qWait(30)
        field = next(w for w in window.inspector.findChildren(QLineEdit) if w.accessibleName()=='Add A')
        field.setFocus(); text('invalid'); key(0x09)
        check('Inspector rejects invalid numeric input without mutating graph',adapter.document()==after and bool(field.styleSheet()))
        field.setFocus(); text('3.5'); key(0x09)
        check('Inspector accepts a corrected value',created.get_property('value_A')==3.5 and not field.styleSheet())
        adapter.graph.center_on([source]); QTest.qWait(40)
        before_cancel = adapter.document(); index = adapter.graph.undo_stack().index()
        dialog = drop(source.outputs()['Value'],QPoint(220,-110)); text('nothing_matches_123')
        check('Empty search is explicit',dialog.list.count()==0 and dialog.empty.isVisible())
        key(0x1B); wait(lambda:QApplication.activeModalWidget() is None)
        check('Physical Escape leaves graph and undo history unchanged',adapter.document()==before_cancel and adapter.graph.undo_stack().index()==index)
        created.set_pos(0,-60)
        start = adapter.add(1001,[-280,160]); setter = adapter.add(3005,[300,40])
        setter.set_property('value_Name','speed')
        start.outputs()['Out'].connect_to(setter.inputs()['In'])
        created.outputs()['Value'].connect_to(setter.inputs()['Value'])
        check('Authored graph validates and saves',window.validate_graph() and window.save_project())
        saved = adapter.document(); window.open_project(project)
        check('Reopening preserves stable IDs, typed links and Inspector values',window.adapter.document()==saved and load_project(project)[1]==saved)
        ir = compile_graph(saved,window.scene); export(ir,directory/'generated')
        run = subprocess.run([str(ROOT/'build/node_preview.exe'),'--ir',str(directory/'generated/game.ir.json'),
                              '--frames','2','--output',str(folder/'port-search-runtime.json')],
                             cwd=directory,capture_output=True,text=True,encoding='utf-8',timeout=30)
        (folder/'port-search-runtime.log').write_text(run.stdout+run.stderr,'utf-8')
        check('Saved graph runs in the native interpreter',run.returncode==0)
        state = json.loads((folder/'port-search-runtime.json').read_text('utf-8'))
        check('Native graph computes 2.5 plus 3.5',state['variables']['speed']==6.)
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None,40)
        command('pause')
        snapshot = next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
        check('Embedded SDL preview executes the same authored values',snapshot['variables']['speed']==6.)
        window.adapter.clear_selection(); window.adapter.graph.fit_to_selection()
        window.adapter.selected.emit(next(n for n in window.adapter.graph.all_nodes() if n.get_property('type_id')==4001))
        QTest.qWait(80)
        check('Final editor screenshot saved',window.grab().save(str(folder/'port-search-editor.png')))
        command('stop')
        report['source_sha256'] = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'editor/ui/graph.py','editor/ui/search.py','editor/ui/main_window.py','editor/core/registry.py',
            'editor/core/compiler.py','tools/verify_port_search.py','tests/test_port_search.py')}
        report['graph_sha256'] = hashlib.sha256((directory/'graphs/gameplay.json').read_bytes()).hexdigest()
        report['screenshot_sha256'] = {name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                      for name in ('port-search-dialog.png','port-search-editor.png')}
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        window.grab().save(str(folder/'port-search-failure.png'))
        raise
    finally:
        user32.mouse_event(4,0,0,0,0)
        for code in (0x11,0x1B,0x0D,ord('V'),ord('A'),ord('Z')): user32.keybd_event(code,0,2,0)
        if isinstance(QApplication.activeModalWidget(),SearchDialog): QApplication.activeModalWidget().reject()
        window.saved_signature = window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(folder/'port-search-editor-checks.json',report)
    return report


if __name__=='__main__':
    print(f"Port search: {len(verify()['checks'])} checks passed.")
