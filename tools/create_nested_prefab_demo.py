"""A separately placed robot becomes a linked member of a reusable group."""
import shutil
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import default_scene, save_json
from editor.core.events import new_event
from editor.core.prefabs import PrefabLibrary, capture_prefab
from editor.core.registry import ROOT


def create():
    project = ROOT/'examples/nested_prefab_demo'
    (project/'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'examples/prefabs_demo/assets/robot.gltf', project/'assets/robot.gltf')
    original = default_scene()
    original['component_definitions'] = [dict(id=1, name='Motion', properties=[
        dict(id=1, name='Speed', type='float', default=90.)])]
    original['entities'][0].update(name='Robot', components={'1': {'properties': {'1': 90.}}})
    original['entities'].append(dict(default_scene()['entities'][0], id='body', name='Body',
                                     parent='player', mesh='assets/robot.gltf'))
    robot = capture_prefab(original, 'player', 'Robot', asset_id='robot')
    group = dict(version=1, type='prefab', id='group', name='Robot Group', root='root',
                 entities=[dict(default_scene()['entities'][0], id='root', name='Group')])
    library = PrefabLibrary([group, robot])
    scene = dict(version=1, entities=[], prefab_instances=[], prefab_assets=library.assets,
                 component_definitions=library.component_definitions, variables={'ticks': {'type': 'int', 'value': 0}})
    for aid, mapping, parent, position in [
            ('group', {'root': 'left'}, '', [-3.6, 0, 0]),
            ('group', {'root': 'middle'}, '', [0, 0, 0]),
            ('robot', {'root': 'nested', 'e1': 'nested_body'}, 'left', [0, 0, 0]),
            ('robot', {'root': 'source', 'e1': 'source_body'}, '', [3.6, 0, 0])]:
        record = library.instantiate_entities(aid, mapping=mapping, parent=parent, position=position)
        scene['entities'].extend(record.pop('entities')); scene['prefab_instances'].append(record)
    notice = new_event('Nested Notice', [{'name': 'Message', 'type': 'string'}]); notice['id'] = 100001
    b = GraphBuilder('Apply independently placed nested robot', component_definitions=library.component_definitions,
                     event_definitions=[notice])
    def add(nid, name, **values):
        b.add(nid, name, **values)
        i = len(b.graph['nodes'])-1
        b.graph['nodes'][-1]['position'] = [(i % 6)*310, (i//6)*230]
    def chain(previous, steps):
        for nid, name, values in steps:
            add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    def frame(count, nid, name, **values):
        add(nid+'_update', 'On Update'); add(nid+'_frame', 'Get Frame Count')
        add(nid+'_eq', 'Nearly Equal', B=count, Epsilon=0); add(nid+'_if', 'Branch')
        add(nid, name, **values)
        b.connect(nid+'_update', 'Out', nid+'_if', 'In'); b.connect(nid+'_frame', 'Value', nid+'_eq', 'A')
        b.connect(nid+'_eq', 'Value', nid+'_if', 'Condition'); b.connect(nid+'_if', 'True', nid, 'In')
    add('start', 'On Game Start')
    chain('start', [('timer', 'Start Timer', dict(Name='heartbeat', Owner='nested_body', Seconds=.25, Repeat=True)),
                    ('pin', 'Set Motion Speed', dict(Entity='nested', Value=90))])
    add('tick', 'On Timer Finished', Receiver='nested_body', NameFilter='heartbeat')
    add('count', 'Get Integer Variable', Name='ticks'); add('inc', 'Integer Add', B=1)
    add('save', 'Set Integer Variable', Name='ticks')
    b.connect('tick', 'Out', 'save', 'In'); b.connect('count', 'Value', 'inc', 'A'); b.connect('inc', 'Value', 'save', 'Value')
    frame(20, 'enlarge', 'Set Scale', Entity='nested_body', Value=[1.5]*3)
    frame(60, 'queue', 'Send Nested Notice', Recipient='nested_body', Message='Nested event survived adoption')
    chain('queue', [('apply', 'Apply Prefab Overrides', dict(Instance='left'))])
    frame(100, 'speed', 'Set Motion Speed', Entity='source', Value=45)
    chain('speed', [('rename', 'Set Entity Name', dict(Entity='source_body', Name='Updated from source')),
                    ('apply_source', 'Apply Prefab Overrides', dict(Instance='source'))])
    frame(110, 'temporary', 'Set Scale', Entity='nested_body', Value=[.5]*3)
    frame(120, 'reset', 'Reset Prefab Instance', Instance='left')
    add('notice', 'On Nested Notice', Receiver='nested_body'); add('log', 'Print Log')
    b.connect('notice', 'Out', 'log', 'In'); b.connect('notice', 'Message', 'log', 'Message')
    save_json(project/'scenes/main.json', scene); save_json(project/'graphs/gameplay.json', b.graph)
    save_json(project/'project.json', dict(version=1, name='Linked nested prefab adoption',
        graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/robot.gltf']))
    export(compile_graph(b.graph, scene), project/'generated')
    return project


if __name__ == '__main__':
    print(create())
