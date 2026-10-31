"""Actual Qt nominal collection authoring, node code editing and project refactor."""
import argparse
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings,QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QDialogButtonBox,QPushButton,QComboBox
from editor.core.builder import GraphBuilder
from editor.core.functions import new_function
from editor.core.document import create_project,save_json,load_project
from editor.core.projects import project_snapshot,compile_project
from editor.core.codegen import export
from editor.core.node_code import runtime_source_excerpt
from editor.ui.main_window import MainWindow
from editor.ui.user_types import TypeLibraryDialog,TypeSignatureDialog
from editor.ui.variables import VariablesDialog
from editor.ui.node_code import NodeCodeDialog


def authored_graph(window):
    schema=window.adapter.registry.type_schema
    structs=list(schema.structs.values()); enums=list(schema.enums.values())
    rank=new_function('Rank',[dict(name='Item',type='struct:Stats')],[dict(name='Rank',type='float')],True,schema=schema)
    body=GraphBuilder(functions=[rank],function=rank['id'],struct_definitions=structs,enum_definitions=enums)
    body.add('entry','Function Input'); body.add('fields','Break Stats'); body.add('float','Integer to Float'); body.add('return','Function Output')
    body.connect('entry','Item','fields','Value').connect('fields','hp','float','Value').connect('float','Value','return','Rank')
    rank['graph']=body.graph
    b=GraphBuilder(functions=[rank],struct_definitions=structs,enum_definitions=enums)
    for nid,label,values in [('start','On Game Start',{}),('source','Get Stats Array Variable',dict(Name='inventory')),
        ('append','Append Stats Item',dict(Item=dict(hp=9))),('save','Set Stats Array Variable',dict(Name='inventory')),
        ('sort','Sort Stats Array',dict(Callback=rank['id'])),('sorted','Set Stats Array Variable',dict(Name='sorted')),
        ('map','Stats Map Values',dict(Map={'b':dict(hp=4),'a':dict(hp=3)})),
        ('values','Set Stats Array Variable',dict(Name='map_values'))]: b.add(nid,label,**values)
    for a,c in [('start','save'),('save','sorted'),('sorted','values')]: b.connect(a,'Out',c,'In')
    b.connect('source','Value','append','Array').connect('append','Value','save','Value')
    b.connect('source','Value','sort','Array').connect('sort','Value','sorted','Value').connect('map','Value','values','Value')
    for i,node in enumerate(b.graph['nodes']): node['position']=[(i%3)*350,(i//3)*230]
    return b.graph


def verify(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    path=create_project(output/'Project','Nominal collections')
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(path,QSettings(str(output/'settings.ini'),QSettings.Format.IniFormat)); window.show()
    checks={}; errors=[]
    def capture(widget,name):
        app.processEvents(); assert widget.grab().save(str(output/(name+'.png')))
    def run(callback):
        try: callback()
        except BaseException:
            errors.append(traceback.format_exc())
            for widget in app.topLevelWidgets():
                if isinstance(widget,QDialog): widget.reject()
            window.dirty=False;window.close();app.exit(1)
    def later(callback): QTimer.singleShot(120,lambda:run(callback))
    def click_ok(dialog):
        QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
    def start():
        later(library); window.actions['Structs and Enums…'].trigger()
    def library():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,TypeLibraryDialog)
        later(define)
        QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='New Struct'),Qt.MouseButton.LeftButton)
    def define():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,TypeSignatureDialog)
        dialog.name_field.setText('Stats'); dialog.table.item(0,0).setText('hp')
        dialog.table.cellWidget(0,1).setCurrentText('int'); dialog.table.item(0,2).setText('7')
        later(defined);click_ok(dialog)
    def defined():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,TypeLibraryDialog)
        checks['struct_authored_in_project_dialog']=True
        later(variables);click_ok(dialog)
    def variables():
        later(edit_variables);window.actions['Scene Variables…'].trigger()
    def edit_variables():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,VariablesDialog)
        assert {'array<struct:Stats>','map<struct:Stats>','set<struct:Stats>'}.issubset(dialog.type_delegate.types)
        row=dialog.add_row('inventory','float',0)
        index=dialog.table.model().index(row,1)
        editor=dialog.type_delegate.createEditor(dialog.table,None,index)
        editor.setCurrentText('array<struct:Stats>');dialog.type_delegate.setModelData(editor,dialog.table.model(),index);editor.deleteLater()
        dialog.table.item(row,2).setText('[{"hp":1},{"hp":2}]'); capture(dialog,'collection-variable')
        checks['typed_collection_delegate_and_values']=True
        later(graph);click_ok(dialog)
    def graph():
        assert window.scene['variables']['inventory']['type']=='array<struct:Stats>'
        window.adapter.load(authored_graph(window),struct_definitions=window.scene['struct_definitions'])
        node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='save')
        spec=window.adapter.registry[node.get_property('type_id')]
        assert 'Value DispatchUserCollection' in runtime_source_excerpt(spec)
        checks['runtime_view_matches_collection_dispatcher']=True
        later(code); assert window.edit_node_code(node)
        checks['ctrl_s_saves_embedded_collection_code']=node.get_property('embedded_code')==HOOK
        before=node.get_property('embedded_code');window.actions['Undo'].trigger();assert not node.get_property('embedded_code')
        window.actions['Redo'].trigger();assert node.get_property('embedded_code')==before
        checks['embedded_code_undo_redo']=True
        later(rename_library);window.actions['Structs and Enums…'].trigger()
    def code():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,NodeCodeDialog)
        dialog.editor.setPlainText(HOOK);capture(dialog,'collection-node-code')
        QTest.keyClick(dialog.editor,Qt.Key.Key_S,Qt.KeyboardModifier.ControlModifier)
    def rename_library():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,TypeLibraryDialog)
        dialog.list.setCurrentRow(0);later(rename)
        QTest.mouseClick(next(b for b in dialog.findChildren(QPushButton) if b.text()=='Edit selected'),Qt.MouseButton.LeftButton)
    def rename():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,TypeSignatureDialog)
        dialog.name_field.setText('Vitals');dialog.table.item(0,0).setText('health')
        later(renamed);click_ok(dialog)
    def renamed():
        dialog=QApplication.activeModalWidget();assert isinstance(dialog,TypeLibraryDialog)
        assert dialog.result_scene['variables']['inventory']==dict(type='array<struct:Vitals>',value=[dict(health=1),dict(health=2)])
        checks['collection_refactor_updates_literals_and_callbacks']=True
        later(save);click_ok(dialog)
    def save():
        assert window.save_project() and window.open_project(path)
        manifest,graph,scene=load_project(path)
        assert next(n for n in graph['nodes'] if n['id']=='save')['code']==HOOK
        assert scene['variables']['inventory']['value']==[dict(health=1),dict(health=2)]
        assert graph['functions'][0]['inputs'][0]['type']=='struct:Vitals'
        checks['project_saved_and_reopened']=True
        window.library_search.setText('Vitals');capture(window,'collection-project-reopened')
        program=compile_project(project_snapshot(path));export(program,path.parent/'generated')
        checks['saved_project_exported']=True
        window.close();app.quit()
    HOOK='{{call}}\nrt::Print(ctx, "Inventory stored");'
    watchdog=QTimer();watchdog.setSingleShot(True)
    watchdog.timeout.connect(lambda:run(lambda:(_ for _ in ()).throw(TimeoutError('Collection proof exceeded 90 seconds'))))
    watchdog.start(90000);later(start);app.exec();watchdog.stop()
    result=dict(checks=checks,errors=errors,project=str(path));save_json(output/'checks.json',result)
    assert len(checks)==8 and all(checks.values()) and not errors,result
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    verify(parser.parse_args().output)
