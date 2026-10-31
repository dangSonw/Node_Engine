"""General Health/Inventory data, typed function and Flecs component queries."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.components import edit_instance
from editor.core.functions import new_function
from editor.core.document import default_scene, save_json
from editor.core.codegen import export
from editor.core.registry import ROOT


def create():
    project = ROOT/'examples/components_demo'
    (project/'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'examples/blockbench_demo/assets/robot.gltf', project/'assets/robot.gltf')
    definitions = [
        {'id': 1, 'name': 'Health', 'properties': [{'id': 1, 'name': 'Points', 'type': 'int', 'default': 100}]},
        {'id': 2, 'name': 'Inventory', 'properties': [{'id': 1, 'name': 'Items', 'type': 'array<string>', 'default': []}]}]
    scene = default_scene()
    scene['component_definitions'] = definitions
    scene['entities'][0].update(name='Damageable robot', mesh='assets/robot.gltf', position=[-1, 0, 0])
    scene['entities'].append(dict(scene['entities'][0], id='collector', name='Collector', position=[1, 0, 0]))
    scene = edit_instance(scene, 'player', 1, 'add')
    scene = edit_instance(scene, 'collector', 2, 'add')
    damage = new_function('Damage', [{'name': 'Target', 'type': 'entity'}, {'name': 'Amount', 'type': 'int', 'default': 25}], [])
    damage['id'] = 1000001
    b = GraphBuilder(functions=[damage], function=damage['id'], component_definitions=definitions)
    nodes = [('entry', 'Function Input', {}), ('hp', 'Get Health Points', {}), ('subtract', 'Integer Subtract', {}),
             ('set', 'Set Health Points', {}), ('remaining', 'Get Health Points', {}), ('zero', 'Integer Less', {'B': 1}),
             ('branch', 'Branch', {}), ('disable', 'Set Health Enabled', {'Enabled': False}),
             ('hide', 'Set Entity Visibility', {'Visible': False}), ('items', 'Get Inventory Items', {'Entity': 'collector'}),
             ('append', 'Append String Item', {'Item': 'robot token'}),
             ('collect', 'Set Inventory Items', {'Entity': 'collector'}),
             ('log', 'Print Log', {'Message': 'Collected robot token; Health disabled and robot hidden.'}),
             ('return', 'Function Output', {})]
    for i, (nid, name, values) in enumerate(nodes):
        b.add(nid, name, **values); b.graph['nodes'][-1]['position'] = [(i%5)*250, (i//5)*240]
    for edge in [('entry','Out','set','In'), ('entry','Target','hp','Entity'), ('hp','Value','subtract','A'),
                 ('entry','Amount','subtract','B'), ('subtract','Value','set','Value'), ('entry','Target','set','Entity'),
                 ('set','Out','branch','In'), ('entry','Target','remaining','Entity'), ('remaining','Value','zero','A'),
                 ('zero','Value','branch','Condition'), ('branch','False','return','In'), ('branch','True','disable','In'),
                 ('entry','Target','disable','Entity'), ('disable','Out','hide','In'), ('entry','Target','hide','Entity'),
                 ('hide','Out','collect','In'), ('items','Value','append','Array'), ('append','Value','collect','Value'),
                 ('collect','Out','log','In'), ('log','Out','return','In')]:
        b.connect(*edge)
    damage['graph'] = b.graph
    b = GraphBuilder('Health and collectible components', functions=[damage], component_definitions=definitions)
    nodes = [('start','On Game Start',{}), ('timer','Start Timer',{'Name':'damage','Seconds':.25,'Repeat':True}),
             ('pulse','On Timer Finished',{'Filter':'damage'}), ('query','Find Entities With Health',{}),
             ('each','For Each Entity',{}), ('damage','Damage',{}),
             ('update','On Update',{}), ('rotate','Rotate',{'Entity':'collector','Degrees':[0,1,0]})]
    for i,(nid,name,values) in enumerate(nodes):
        b.add(nid,name,**values); b.graph['nodes'][-1]['position']=[(i%3)*300,(i//3)*230]
    for edge in [('start','Out','timer','In'),('pulse','Out','each','In'),('query','Value','each','Array'),
                 ('each','Body','damage','In'),('each','Item','damage','Target'),('update','Out','rotate','In')]:
        b.connect(*edge)
    ir = b.compile(scene)
    save_json(project/'scenes/main.json', scene)
    save_json(project/'graphs/gameplay.json', b.graph)
    save_json(project/'project.json', {'version': 1, 'name': 'Health and collectible components',
              'graph': 'graphs/gameplay.json', 'scene': 'scenes/main.json', 'assets': ['assets/robot.gltf']})
    export(ir, project/'generated')
    return project


if __name__ == '__main__':
    print(create())
