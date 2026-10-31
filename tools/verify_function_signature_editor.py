"""Exercise signature dialogs, migration, Undo and embedded native preview in real Qt."""
from copy import deepcopy
import hashlib,json,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QLineEdit,QPushButton
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.functions import FunctionSignatureDialog,FunctionEditorDialog
from editor.ui.search import SearchDialog
from tools.create_functions_demo import create


def verify():
    directory=ROOT/'.cache'/('function-signatures-'+uuid.uuid4().hex[:8]); project=create(directory)
    out=ROOT/'artifacts/validation/function-signatures'; out.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    w=MainWindow(project,QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    screen=w.screen().availableGeometry(); w.resize(min(1560,screen.width()-24),min(950,screen.height()-60)); w.show()
    messages=[]; w.runtime.message.connect(messages.append)
    report=dict(passed=False,checks=[],native_fingerprint=fingerprint(),project=str(project),
                binary_sha256=hashlib.sha256((ROOT/'build/node_view.exe').read_bytes()).hexdigest())
    def check(label,condition):
        assert condition,label
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
    def find(nid,adapter=None): return next(n for n in (adapter or w.adapter).graph.all_nodes() if n.get_property('stable_id')==nid)
    def write(field,text):
        field.setFocus(); field.selectAll(); QTest.keyClicks(field,text)
    def cell(dialog,side,row,column,text):
        table=dialog.tables[side]; table.setCurrentCell(row,column); table.editItem(table.item(row,column))
        field=next(f for f in table.findChildren(QLineEdit) if f.isVisible())
        write(field,text); QTest.keyClick(field,Qt.Key.Key_Return)
    def click(button): QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    def signature(edit,select='left',search=None):
        for n in w.adapter.graph.all_nodes(): n.set_property('selected',False,push_undo=False)
        if select: find(select).set_property('selected',True,push_undo=False)
        errors=[]; seen=[]
        def fill():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,FunctionSignatureDialog),type(dialog)
                seen.append(True); edit(dialog)
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        def choose():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,SearchDialog)
                write(dialog.search,search); QTimer.singleShot(140,fill); QTest.keyClick(dialog.search,Qt.Key.Key_Return)
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        QTimer.singleShot(140,choose if search else fill)
        w.actions['Edit Function Signature…'].trigger()
        if errors: raise errors[0]
        assert seen
        wait(lambda:w.reload_request is None)
    def apply(dialog):
        click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)); assert not dialog.isVisible(),dialog.error.text()
    def cancel(dialog): click(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))
    def restart_check():
        check('Paused signature edit resets preview without running',w.runtime.state=='stopped' and snapshot()['frame']==0)
        command('play'); QTest.qWait(120); command('pause'); s=snapshot()
        save_json(out/'live-state.json',s)
        f=s['frame']; check('Renamed nested calls preserve live robot rotations',f>0 and abs(s['entities']['player']['rotation'][1]-60*s['time'])<1e-6
            and abs(s['entities']['partner']['rotation'][1]+90*s['time'])<1e-6
            and s['variables']['left_rotation']['value']==s['entities']['player']['rotation'])
    try:
        check('Shared native preview matches current sources',current(ROOT/'build/node_view.exe'))
        check('Original two-robot graph validates',w.validate_graph())
        # A preceding ordinary inspector edit must survive signature Undo/Redo.
        left=find('left'); w.adapter.selected.emit(left)
        field=next(f for f in w.findChildren(QLineEdit) if f.property('domain_property')=='value_Speed')
        write(field,'60'); QTest.keyClick(field,Qt.Key.Key_Return)
        check('Inspector edits original call before migration',left.get_property('value_Speed')==60)
        before=w.adapter.document(); count=w.adapter.graph.undo_stack().count()
        w.actions['Play'].trigger(); wait(lambda:w.runtime.ready and w.container is not None and w.runtime.state=='running'); command('pause')
        def action(dialog):
            check('Selected call opens its signature directly',dialog.original['id']==1000002 and not dialog.pure.isEnabled())
            write(dialog.name_field,'Turn Robot')
            for row,name in enumerate(('Actor','Rate','DeltaSeconds')): cell(dialog,'inputs',row,0,name)
            cell(dialog,'outputs',0,0,'Angle')
            table=dialog.tables['inputs']; table.setCurrentCell(2,0)
            up=next(b for b in dialog.findChildren(QPushButton) if b.text()=='Move up'); click(up); click(up)
            click(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add input'))
            cell(dialog,'inputs',3,0,'Note'); table.cellWidget(3,1).setCurrentText('string'); cell(dialog,'inputs',3,2,'"shared"')
            dialog.grab().save(str(out/'signature-dialog.png')); apply(dialog)
        signature(action)
        after=w.adapter.document()
        check('Root calls retain IDs, authored values, positions and renamed wires',find('left').get_property('value_Rate')==60
            and find('right').get_property('value_Rate')==-90 and find('left').pos()==left.pos()
            and find('left').outputs()['Angle'].connected_ports()[0].name()=='Value'
            and list(find('left').inputs())==['In','DeltaSeconds','Actor','Rate','Note'])
        check('Whole migration adds exactly one Undo step',w.adapter.graph.undo_stack().count()==count+1)
        restart_check()
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None)
        check('Undo restores signature and every original call wire',w.adapter.document()==before)
        w.actions['Undo'].trigger(); check('Earlier inspector history still targets original node',left.get_property('value_Speed')==45)
        w.actions['Redo'].trigger(); check('Earlier inspector Redo restores value',w.adapter.document()==before)
        w.actions['Redo'].trigger(); wait(lambda:w.reload_request is None)
        check('Migration Redo restores full edited document',w.adapter.document()==after); restart_check()
        def pure(dialog):
            check('Picker opens function without root call',dialog.original['id']==1000001)
            write(dialog.name_field,'Angular Step'); cell(dialog,'inputs',0,0,'Rate'); cell(dialog,'inputs',1,0,'Step')
            cell(dialog,'outputs',0,0,'Delta'); dialog.tables['inputs'].setCurrentCell(1,0)
            click(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Move up')); apply(dialog)
        signature(pure,select=None,search='Rotation Delta'); restart_check()
        action_def=next(f for f in w.adapter.functions if f['id']==1000002)
        check('Nested caller and Function Input/Output wires migrate together',
            {'from':['entry','Rate'],'to':['delta','Rate']} in action_def['graph']['links']
            and {'from':['delta','Delta'],'to':['rotate','Degrees']} in action_def['graph']['links'])
        stable=w.signature(); count=w.adapter.graph.undo_stack().count()
        def blocked(dialog):
            dialog.tables['inputs'].removeRow(0); click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
            check('Connected port removal stays in dialog with diagnostic',dialog.isVisible() and 'Cannot remove connected port' in dialog.error.text())
            dialog.grab().save(str(out/'rejected-removal.png')); cancel(dialog)
        signature(blocked); check('Rejected edit leaves graph and history unchanged',w.signature()==stable and w.adapter.graph.undo_stack().count()==count)
        def wrong_type(dialog):
            dialog.tables['inputs'].cellWidget(0,1).setCurrentText('int'); click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
            check('Incompatible body wiring blocks type changes',dialog.isVisible() and 'Type mismatch' in dialog.error.text()); cancel(dialog)
        signature(wrong_type,select=None,search='Angular Step'); check('Rejected type change preserves document',w.signature()==stable)
        def cancelled(dialog): write(dialog.name_field,'Discard me'); cancel(dialog)
        signature(cancelled); check('Cancel does not modify graph',w.signature()==stable)
        signature(apply); check('Unchanged Apply does not add history',w.signature()==stable and w.adapter.graph.undo_stack().count()==count)
        def defaults(dialog): cell(dialog,'inputs',2,2,'5'); apply(dialog)
        signature(defaults)
        check('Changing default preserves both existing call values',find('left').get_property('value_Rate')==60 and find('right').get_property('value_Rate')==-90)
        w.library_search.setText('Turn Robot'); tree=w.library_tree
        item=next(tree.topLevelItem(i).child(j) for i in range(tree.topLevelItemCount()) for j in range(tree.topLevelItem(i).childCount())
                  if tree.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==1000002)
        tree.scrollToItem(item); QTest.qWait(50); pos=tree.visualItemRect(item).center()
        QTest.mouseClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos)
        fresh=next(n for n in w.adapter.graph.all_nodes() if n.get_property('type_id')==1000002 and n.get_property('stable_id') not in ('left','right'))
        check('Library creates current ports and new defaults',fresh.get_property('value_Rate')==5 and fresh.get_property('value_Note')=='shared' and 'Angle' in fresh.outputs())
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None)
        # Open the body editor after migration; its scoped entry and nested call use new signatures.
        errors=[]
        def body():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,FunctionEditorDialog)
                check('Body editor exposes migrated Function Input and nested ports','DeltaSeconds' in find('entry',dialog.adapter).outputs()
                      and 'Step' in find('delta',dialog.adapter).inputs() and 'Delta' in find('delta',dialog.adapter).outputs())
                dialog.frame_all(); QTest.qWait(80); dialog.grab().save(str(out/'function-body.png')); dialog.reject()
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        QTimer.singleShot(140,body); w.edit_function(1000002)
        if errors: raise errors[0]
        command('play'); wait(lambda:w.runtime.state=='running')
        signature(lambda dialog:(cell(dialog,'inputs',2,2,'6'),apply(dialog)))
        wait(lambda:w.runtime.state=='running'); QTest.qWait(120); command('pause')
        s=snapshot()
        check('Applying while preview runs reloads and resumes with preserved call values',s['frame']>0
            and abs(s['entities']['player']['rotation'][1]-60*s['time'])<1e-6 and find('left').get_property('value_Rate')==60)
        command('frame_scene'); command('capture',path=str(out/'viewport.bmp'))
        wait(lambda:(out/'viewport.bmp').is_file()); im=QImage(str(out/'viewport.bmp')); background=im.pixelColor(0,0)
        check('Edited functions render actual GPU meshes',sum(im.pixelColor(x,y)!=background for y in range(0,im.height(),4) for x in range(0,im.width(),4))>100)
        check('Project save succeeds',w.save_project()); saved=w.adapter.document()
        w.runtime.shutdown(); wait(lambda:not w.runtime.active); w.open_project(project)
        check('Save and reopen retain signatures, values and wiring',w.adapter.document()==saved and not w.dirty and w.validate_graph())
        w.frame_all(); w.library_search.setText('Turn Robot'); QTest.qWait(100); w.grab().save(str(out/'editor.png'))
        report['passed']=True; report['messages']=messages; save_json(out/'editor-checks.json',report)
        return report
    finally:
        w.runtime.shutdown(); wait(lambda:not w.runtime.active)
        w.saved_signature=w.signature(); w.document_changed(); w.close(); app.processEvents()


if __name__=='__main__': verify()
