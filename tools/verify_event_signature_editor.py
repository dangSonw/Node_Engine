"""Edit event signatures through actual Qt dialogs and exercise the native preview."""
import hashlib,json,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QLineEdit,QPushButton
from PySide6.QtGui import QImage
from editor.core.document import save_json
from editor.core.builder import GraphBuilder
from editor.core.functions import new_function
from editor.core.projects import project_snapshot,compile_project
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from editor.ui.events import EventSignatureDialog
from editor.ui.functions import FunctionEditorDialog
from editor.ui.search import SearchDialog
from tools.create_events_demo import create


def verify():
    directory=ROOT/'.cache'/('event-signatures-'+uuid.uuid4().hex[:8]); project=create(directory)
    document=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    publish=new_function('Publish Turn',[dict(name='Angle',type='float',default=15)]); publish['id']=1000002
    functions=[*document['functions'],publish]
    b=GraphBuilder(functions=functions,function=publish['id'],event_definitions=document['event_definitions'])
    b.add('entry','Function Input'); b.add('send','Broadcast Turn'); b.add('return','Function Output')
    b.connect('entry','Out','send','In').connect('entry','Angle','send','Angle').connect('send','Out','return','In')
    publish['graph']=b.graph; document['functions']=functions
    next(n for n in document['nodes'] if n['id']=='broadcast')['type']=publish['id']
    save_json(directory/'graphs/gameplay.json',document)
    out=ROOT/'artifacts/validation/event-signatures'; out.mkdir(parents=True,exist_ok=True)
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
    def write(field,text): field.setFocus(); field.selectAll(); QTest.keyClicks(field,text)
    def cell(dialog,row,column,text):
        table=dialog.tables['inputs']; table.setCurrentCell(row,column); table.editItem(table.item(row,column))
        field=next(f for f in table.findChildren(QLineEdit) if f.isVisible()); write(field,text); QTest.keyClick(field,Qt.Key.Key_Return)
    def click(button): QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    def signature(edit,select='boost',search=None):
        w.adapter.clear_selection()
        if select: find(select).set_property('selected',True,push_undo=False)
        errors=[]; seen=[]
        def fill():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,EventSignatureDialog); seen.append(True); edit(dialog)
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        def choose():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,SearchDialog); write(dialog.search,search)
                QTimer.singleShot(140,fill); QTest.keyClick(dialog.search,Qt.Key.Key_Return)
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        QTimer.singleShot(140,choose if search else fill); w.actions['Edit Event Signature…'].trigger()
        if errors: raise errors[0]
        assert seen; wait(lambda:w.reload_request is None)
    def apply(dialog):
        click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)); assert not dialog.isVisible(),dialog.error.text()
    def cancel(dialog): click(dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel))
    try:
        check('Native preview stamp matches current source',current(ROOT/'build/node_view.exe'))
        check('Original event graph with nested broadcaster validates',w.validate_graph())
        original=find('boost'); w.adapter.selected.emit(original)
        field=next(f for f in w.findChildren(QLineEdit) if f.property('domain_property')=='value_Angle')
        write(field,'90'); QTest.keyClick(field,Qt.Key.Key_Return)
        check('Inspector authors sender before migration',original.get_property('value_Angle')==90)
        before=w.adapter.document(); count=w.adapter.graph.undo_stack().count()
        check('Original reference saves',w.save_project()); save_json(out/'original.ir.json',compile_project(project_snapshot(project)))
        w.actions['Play'].trigger(); wait(lambda:w.runtime.ready and w.container is not None and w.runtime.state=='running'); command('pause')
        def edit(dialog):
            check('Selected sender opens its event signature',dialog.original['id']==100001 and dialog.pure.isHidden())
            write(dialog.name_field,'Rotate Notice'); cell(dialog,0,0,'Degrees')
            click(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add parameter'))
            cell(dialog,1,0,'Note'); dialog.tables['inputs'].cellWidget(1,1).setCurrentText('string'); cell(dialog,1,2,'"shared"')
            dialog.tables['inputs'].setCurrentCell(1,0); click(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Move up'))
            dialog.grab().save(str(out/'signature-dialog.png')); apply(dialog)
        signature(edit); after=w.adapter.document()
        check('Root sender and handler keep routing and renamed wires',find('boost').get_property('value_Degrees')==90
            and find('boost').get_property('value_Recipient')=='player' and find('boost').pos()==original.pos()
            and list(find('player_event').outputs())==['Out','Sender','Receiver','Note','Degrees']
            and find('player_event').outputs()['Degrees'].connected_ports()[0].name()=='Angle')
        check('Nested broadcaster wire migrates without changing function parameters',
            {'from':['entry','Angle'],'to':['send','Degrees']} in next(f for f in w.adapter.functions if f['id']==1000002)['graph']['links'])
        check('Whole event family migration is one Undo step',w.adapter.graph.undo_stack().count()==count+1)
        check('Paused edit reloads without starting simulation',w.runtime.state=='stopped' and snapshot()['frame']==0)
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None); check('Undo restores all original definitions and wires',w.adapter.document()==before)
        w.actions['Undo'].trigger(); check('Older Inspector edit still undoes original object',original.get_property('value_Angle')==60)
        w.actions['Redo'].trigger(); w.actions['Redo'].trigger(); wait(lambda:w.reload_request is None)
        check('Redo restores edited event and nested broadcaster',w.adapter.document()==after)
        stable=w.signature(); count=w.adapter.graph.undo_stack().count()
        def blocked(dialog):
            dialog.tables['inputs'].removeRow(1); click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
            check('Removing used parameter is rejected in dialog',dialog.isVisible() and 'Cannot remove' in dialog.error.text())
            dialog.grab().save(str(out/'rejected-removal.png')); cancel(dialog)
        signature(blocked,select=None,search='Rotate Notice')
        def wrong_type(dialog):
            dialog.tables['inputs'].cellWidget(1,1).setCurrentText('int'); click(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok))
            check('Incompatible type is rejected before graph mutation',dialog.isVisible() and 'Type mismatch' in dialog.error.text()); cancel(dialog)
        signature(wrong_type,select='player_event')
        signature(lambda d:(write(d.name_field,'Discard this'),cancel(d)))
        signature(apply,select='subscribe')
        check('Rejected edits Cancel and unchanged Apply keep history',w.signature()==stable and w.adapter.graph.undo_stack().count()==count)
        command('play'); signature(lambda d:(cell(d,1,2,'5'),apply(d)),select='detach')
        wait(lambda:w.runtime.state=='running'); QTest.qWait(1150); command('pause'); state=snapshot(); save_json(out/'live-state.json',state)
        check('Running edit reloads and resumes event delivery',state['time']>=1 and state['entities']['player']['rotation'][1]>=150
            and state['entities']['partner']['rotation'][1]==-45 and find('boost').get_property('value_Degrees')==90)
        check('Subscription state follows unchanged stable event identity',state['events']['subscriptions']==[
            dict(event=100001,receiver='partner',enabled=False),dict(event=100001,receiver='player',enabled=True)])
        w.library_search.setText('Send Rotate Notice'); tree=w.library_tree
        item=next(tree.topLevelItem(i).child(j) for i in range(tree.topLevelItemCount()) for j in range(tree.topLevelItem(i).childCount())
            if tree.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==200001)
        tree.scrollToItem(item); QTest.qWait(50); pos=tree.visualItemRect(item).center()
        QTest.mouseClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos); QTest.mouseDClick(tree.viewport(),Qt.MouseButton.LeftButton,pos=pos)
        fresh=next(n for n in w.adapter.graph.all_nodes() if n.get_property('type_id')==200001 and n.get_property('stable_id')!='boost')
        check('Library new sender uses new defaults and ports',fresh.get_property('value_Degrees')==5 and fresh.get_property('value_Note')=='shared')
        w.actions['Undo'].trigger(); wait(lambda:w.reload_request is None)
        errors=[]
        def body():
            dialog=app.activeModalWidget()
            try:
                assert isinstance(dialog,FunctionEditorDialog)
                check('Function editor sees migrated event registry','Degrees' in find('send',dialog.adapter).inputs()
                      and find('send',dialog.adapter).inputs()['Degrees'].connected_ports()[0].name()=='Angle')
                dialog.frame_all(); QTest.qWait(80); dialog.grab().save(str(out/'function-body.png')); dialog.reject()
            except BaseException as e:
                errors.append(e)
                if dialog: dialog.reject()
        QTimer.singleShot(140,body); w.edit_function(1000002)
        if errors: raise errors[0]
        command('frame_scene'); command('capture',path=str(out/'viewport.bmp')); wait(lambda:(out/'viewport.bmp').is_file())
        im=QImage(str(out/'viewport.bmp')); check('Native GPU renders event-driven robots',not im.isNull() and
            sum(im.pixelColor(x,y)!=im.pixelColor(0,0) for y in range(0,im.height(),4) for x in range(0,im.width(),4))>100)
        check('Edited project saves',w.save_project()); saved=w.adapter.document(); w.runtime.shutdown(); wait(lambda:not w.runtime.active); w.open_project(project)
        check('Reopen retains definitions defaults routing and body wires',w.adapter.document()==saved and not w.dirty and w.validate_graph())
        w.frame_all(); QTest.qWait(100); w.grab().save(str(out/'editor.png'))
        report['passed']=True; report['messages']=messages; save_json(out/'editor-checks.json',report); return report
    finally:
        w.runtime.shutdown(); wait(lambda:not w.runtime.active); w.saved_signature=w.signature(); w.document_changed(); w.close(); app.processEvents()


if __name__=='__main__': verify()
