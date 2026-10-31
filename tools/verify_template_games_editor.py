"""Open an editable game through Project Browser and exercise the actual Qt/native UI."""
import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings,QTimer,Qt,QEvent
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QTabWidget
from editor.core.document import save_json
from editor.core.projects import compile_project,project_snapshot
from editor.ui.project_launcher import ProjectLauncher,recent_projects
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionEditorDialog
from editor.ui.node_code import NodeCodeDialog


def verify(source,output):
    source=Path(source).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    copy=output/'Editable Project'
    if copy.exists(): raise ValueError('Use a fresh output directory for editor verification')
    shutil.copytree(source.parent,copy,ignore=shutil.ignore_patterns('build','dist','generated','__pycache__'))
    project=copy/source.name
    app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
    settings=QSettings(str(output/'settings.ini'),QSettings.Format.IniFormat)
    report=dict(passed=False,project=str(source),checks=[]);window=None;messages=[];modal_errors=[]
    def check(label,okay):
        assert okay,label
        report['checks'].append(label);print('PASS '+label,flush=True)
    def wait(predicate,timeout=30):
        until=time.monotonic()+timeout
        while not predicate() and time.monotonic()<until: QTest.qWait(10)
        assert predicate(),window.console.toPlainText() if window else 'Qt action timed out'
    def capture(widget,name):
        app.processEvents();check(name+' screenshot',widget.grab().save(str(output/(name+'.png'))))
    def command(name,**args):
        begin=len(messages);serial=window.runtime.send(name,**args)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        received=messages[begin:]
        assert not any(m.get('event')=='node_error' for m in received),received
        return received
    def snapshot():return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    def value(state,key):
        result=state['variables'][key]
        return result['value'] if isinstance(result,dict) and set(result)=={'type','value'} else result
    def later(callback):
        def guarded():
            try:callback()
            except BaseException as error:
                modal_errors.append(repr(error))
                dialog=QApplication.activeModalWidget()
                if isinstance(dialog,QDialog):dialog.reject()
        QTimer.singleShot(100,guarded)
    try:
        browser=ProjectLauncher(settings,initial_project=project,project_roots=[copy])
        browser.show();QTest.qWait(150);capture(browser,'project-browser')
        browser.path.setText(str(project));QTest.mouseClick(browser.open_button,Qt.MouseButton.LeftButton)
        check('Project Browser accepts the game .nen',browser.result()==QDialog.DialogCode.Accepted and browser.project_path==project)
        window=MainWindow(browser.project_path,settings);window.resize(1600,960);window.show();QTest.qWait(150)
        check('Full editable game compiles',bool(compile_project(window.snapshot_project())))
        check('Project history retains the opened game',str(project) in recent_projects(settings))
        window.frame_all();capture(window,'gameplay-graph')
        node=next(n for n in window.adapter.graph.all_nodes() if window.adapter.registry[n.get_property('type_id')].kind=='action')
        def inspect_code():
            dialog=QApplication.activeModalWidget();assert isinstance(dialog,NodeCodeDialog)
            tabs=dialog.findChild(QTabWidget,'NodeCodeTabs');tabs.setCurrentIndex(1)
            check('Selected game node shows generated native code',bool(dialog.generated_call.toPlainText().strip()))
            capture(dialog,'game-node-code');dialog.reject()
        later(inspect_code);window.edit_node_code(node);assert not modal_errors,modal_errors
        if window.adapter.functions:
            def inspect_function():
                dialog=QApplication.activeModalWidget();assert isinstance(dialog,FunctionEditorDialog)
                check('Reusable game logic opens as a function graph',bool(dialog.adapter.graph.all_nodes()))
                dialog.frame_all();capture(dialog,'game-function-graph');dialog.reject()
            later(inspect_function);window.edit_function(window.adapter.functions[0]['id']);assert not modal_errors,modal_errors
        original=node.pos();node.set_pos(original[0]+45,original[1]+25)
        check('Graph edit marks the project dirty',window.dirty)
        window.actions['Undo'].trigger();check('Graph edit Undo restores the node',node.pos()==original)
        window.actions['Redo'].trigger();check('Graph edit Redo restores the move',node.pos()==[original[0]+45,original[1]+25])
        check('Game project saves',window.save_project());saved=window.signature()
        check('Saved project reopens',window.open_project(project) and window.signature()==saved)
        check('Graph layout edits preserve native gameplay',compile_project(project_snapshot(project))==compile_project(project_snapshot(source)))
        window.runtime.message.connect(messages.append)
        window.actions['Play'].trigger()
        wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None,45)
        check('Play embeds the actual native game window',window.runtime.active and window.foreign_window is not None)
        # The same OS keyboard path used by players must reach the foreign SDL child.
        user=ctypes.windll.user32;user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        window.raise_();window.activateWindow();QTest.qWait(150)
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT();assert user.GetWindowRect(hwnd,ctypes.byref(rect))
        user.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
        user.mouse_event(2,0,0,0,0);user.mouse_event(4,0,0,0,0);QTest.qWait(100)
        before=snapshot();user.keybd_event(ord('R'),0,0,0);QTest.qWait(60);user.keybd_event(ord('R'),0,2,0)
        wait(lambda:value(snapshot(),'restart_count')>value(before,'restart_count'))
        check('Physical R reaches gameplay and restarts',value(snapshot(),'restart_count')==value(before,'restart_count')+1)
        command('pause');wait(lambda:window.runtime.state=='paused')
        state=snapshot();save_json(output/'editor-native-state.json',state)
        capture_file=output/'editor-game.bmp';begin=len(messages);command('capture',path=str(capture_file))
        wait(lambda:any(m.get('event')=='capture_done' for m in messages[begin:]))
        image=QImage(str(capture_file));check('Native game framebuffer is readable',not image.isNull());image.save(str(output/'editor-game.png'))
        check('Pause preserves game state',snapshot()==state)
        command('play');wait(lambda:window.runtime.state=='running');QTest.qWait(80)
        check('Resume advances the native game clock',snapshot()['frame']>state['frame'])
        command('pause');window.screen().grabWindow(int(window.winId())).save(str(output/'editor-desktop.png'))
        window.runtime.shutdown();wait(lambda:not window.runtime.active)
        check('Native gameplay produced no node errors',not any(m.get('event')=='node_error' for m in messages))
        check('Runtime leaves authored graph and scene unchanged',window.signature()==saved and not window.dirty)
        report['passed']=True
    except BaseException as error:
        report['error']=repr(error);raise
    finally:
        if window:
            if window.builder.busy:window.builder.cancel();wait(lambda:not window.builder.busy)
            window.runtime.shutdown();wait(lambda:not window.runtime.active)
            window.dirty=False;window.close();window.deleteLater()
            # processEvents alone does not drain DeferredDelete without an
            # app.exec loop; destroy the foreign SDL container before Qt exits.
            app.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
        save_json(output/'checks.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(verify(args.project,args.output),ensure_ascii=False))
