"""Actual Qt extraction in Gameplay and nested function graphs, with native preview."""
import json,sys,time,uuid,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings,QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.projects import compile_project
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionExtractionDialog,FunctionEditorDialog
from tools.create_functions_demo import create


def verify():
    directory=ROOT/'.cache'/('function-extraction-'+uuid.uuid4().hex[:8]); project=create(directory)
    out=ROOT/'artifacts/validation/function-extraction'; out.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    w=MainWindow(project,QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=w.screen().availableGeometry(); w.resize(min(1560,screen.width()-24),min(950,screen.height()-60)); w.show()
    messages=[]; w.runtime.message.connect(messages.append)
    report=dict(passed=False,checks=[],project=str(project),native_fingerprint=fingerprint(),
                binary_sha256=hashlib.sha256((ROOT/'build/node_view.exe').read_bytes()).hexdigest())
    def check(label,okay):
        assert okay,label
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,seconds=30):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end: QTest.qWait(15)
        assert predicate(),w.console.toPlainText()
    def command(name,**data):
        begin=len(messages); serial=w.runtime.send(name,**data)
        wait(lambda:any(m.get('event') in ('ack','node_error') and m.get('id')==serial for m in messages[begin:]))
        result=messages[begin:]; assert not any(m.get('event')=='node_error' for m in result),result
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    def find(adapter,nid): return next(n for n in adapter.graph.all_nodes() if n.get_property('stable_id')==nid)
    def select(adapter,ids):
        adapter.clear_selection()
        for nid in ids: find(adapter,nid).set_property('selected',True,push_undo=False)
    def click(button): QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    def extracted(trigger,name,expected_pure,cancel=False):
        errors=[]; info=[]
        def fill():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,FunctionExtractionDialog)
                check('Extraction review shows inferred kind and typed ports',dialog.info['pure']==expected_pure and bool(dialog.info['inputs']))
                dialog.name_field.setFocus(); dialog.name_field.selectAll(); QTest.keyClicks(dialog.name_field,name)
                info.append(dialog.info); dialog.grab().save(str(out/('pure-review.png' if expected_pure else 'action-review.png')))
                click(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel if cancel else QDialogButtonBox.StandardButton.Ok))
                assert not dialog.isVisible(),dialog.error.text()
            except BaseException as error:
                errors.append(error)
                if dialog: dialog.reject()
        QTimer.singleShot(140,fill); trigger()
        if errors: raise errors[0]
        assert info; return info[0]
    def live():
        command('play'); QTest.qWait(120); command('pause'); s=snapshot()
        check('Extracted calls preserve both robot rotations and captured return',s['frame']>0
              and abs(s['entities']['player']['rotation'][1]-45*s['time'])<1e-6
              and abs(s['entities']['partner']['rotation'][1]+90*s['time'])<1e-6
              and s['variables']['left_rotation']['value']==s['entities']['player']['rotation'])
        return s
    try:
        check('Native preview is current',current(ROOT/'build/node_view.exe')); check('Initial graph validates',w.validate_graph())
        save_json(out/'original.ir.json',compile_project(w.snapshot_project()))
        original=w.signature(); select(w.adapter,['left','right','save'])
        extracted(w.actions['Extract Function…'].trigger,'Discarded',False,cancel=True)
        check('Cancel leaves root nodes and definitions untouched',w.signature()==original)
        select(w.adapter,['start']); w.actions['Extract Function…'].trigger()
        check('Unsafe event selection gives a diagnostic without mutation','Leave event entries' in w.console.toPlainText() and w.signature()==original)
        w.actions['Play'].trigger(); wait(lambda:w.runtime.ready and w.container is not None and w.runtime.state=='running'); command('pause')
        select(w.adapter,['left','right','save']); count=w.adapter.graph.undo_stack().count()
        action=extracted(w.actions['Extract Function…'].trigger,'Spin Pair',False)
        wait(lambda:w.reload_request is None)
        check('Three action nodes collapse to one call with copied dynamic time',action['removed']==['left','right','save'] and action['copied']==['dt']
              and w.adapter.graph.undo_stack().count()==count+1 and len(w.adapter.functions)==3)
        check('Paused preview resets without running after extraction',w.runtime.state=='stopped' and snapshot()['frame']==0)
        after_action=w.signature(); live()
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None); check('Gameplay Undo restores nodes, wires and definitions',w.signature()==original)
        w.actions['Redo'].trigger(); wait(lambda:w.reload_request is None); check('Gameplay Redo restores extracted graph',w.signature()==after_action)
        live()
        errors=[]; child=[]
        def body():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,FunctionEditorDialog) and dialog.current_id==1000001
                select(dialog.adapter,['multiply','degrees']); before=dialog.snapshot(); count=dialog.undo_stack.count()
                info=extracted(lambda:click(dialog.extract_button),'Angular Product',True); child.append(info)
                check('Nested extraction adds one shared history step',len(dialog.snapshot())==4 and dialog.undo_stack.count()==count+1)
                dialog.navigate(info['function_id']); check('Navigating new body keeps shared Undo history',dialog.undo_stack.count()==count+1)
                dialog.frame_all(); QTest.qWait(80); dialog.grab().save(str(out/'nested-body.png'))
                dialog.undo_stack.undo(); check('Undo while inside extracted function returns to valid definition',len(dialog.snapshot())==3 and dialog.snapshot()==before)
                dialog.undo_stack.redo(); check('Redo restores nested definition',len(dialog.snapshot())==4)
                click(dialog.buttons.button(QDialogButtonBox.StandardButton.Save)); assert not dialog.isVisible(),dialog.message.text()
            except BaseException as error:
                errors.append(error)
                if dialog: dialog.reject()
        # Save from the nested editor should reload a running preview and resume it.
        command('play'); wait(lambda:w.runtime.state=='running')
        QTimer.singleShot(140,body); w.edit_function(1000001)
        if errors: raise errors[0]
        wait(lambda:w.reload_request is None and w.runtime.state=='running'); command('pause')
        check('Saving nested extraction updates root definitions',len(w.adapter.functions)==4 and bool(child))
        after_nested=w.signature(); live()
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None); check('Outer Undo restores entire function-edit transaction',w.signature()==after_action)
        w.actions['Redo'].trigger(); wait(lambda:w.reload_request is None); check('Outer Redo restores nested extraction',w.signature()==after_nested)
        w.library_search.setText('Angular Product'); tree=w.library_tree
        item=next(tree.topLevelItem(i).child(j) for i in range(tree.topLevelItemCount()) for j in range(tree.topLevelItem(i).childCount())
                  if tree.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==child[0]['function_id'])
        tree.scrollToItem(item); QTest.qWait(40); pos=tree.visualItemRect(item).center()
        QTest.mouseClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos)
        check('New extracted function is reusable from Library',len([n for n in w.adapter.graph.all_nodes() if n.get_property('type_id')==child[0]['function_id']])==1)
        w.actions['Undo'].trigger(); check('Library insertion Undo leaves extracted program intact',w.signature()==after_nested)
        live(); command('frame_scene'); command('capture',path=str(out/'viewport.bmp')); wait(lambda:(out/'viewport.bmp').is_file())
        im=QImage(str(out/'viewport.bmp')); check('Native GPU renders extracted gameplay',not im.isNull() and sum(im.pixelColor(x,y)!=im.pixelColor(0,0)
            for y in range(0,im.height(),4) for x in range(0,im.width(),4))>100)
        check('Edited project saves',w.save_project()); saved=w.adapter.document()
        w.runtime.shutdown(); wait(lambda:not w.runtime.active); w.open_project(project)
        check('Reopen preserves extracted definitions, calls and wires',w.adapter.document()==saved and not w.dirty and w.validate_graph())
        w.frame_all(); w.library_search.setText('Spin Pair'); QTest.qWait(80); w.grab().save(str(out/'editor.png'))
        report.update(passed=True,messages=messages,action=action,pure=child[0]); save_json(out/'editor-checks.json',report); return report
    finally:
        w.runtime.shutdown(); wait(lambda:not w.runtime.active); w.saved_signature=w.signature(); w.document_changed(); w.close(); app.processEvents()


if __name__=='__main__': verify()
