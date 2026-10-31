"""Apply a robot's gameplay edits while preserving another instance's overrides."""
import shutil
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import default_scene, save_json
from editor.core.events import new_event
from editor.core.prefabs import PrefabLibrary, capture_prefab
from editor.core.registry import ROOT


def create():
    project = ROOT / 'examples/prefab_apply_demo'
    (project / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'examples/prefabs_demo/assets/robot.gltf', project / 'assets/robot.gltf')
    scene = default_scene()
    scene['component_definitions'] = [dict(id=1, name='Motion', properties=[
        dict(id=1, name='Speed', type='float', default=90.)])]
    scene['entities'][0].update(name='Robot group', components={'1': {'properties': {'1': 90.}}})
    scene['entities'].append(dict(default_scene()['entities'][0], id='body', name='Robot body',
                                  parent='player', mesh='assets/robot.gltf'))
    asset = capture_prefab(scene, 'player', 'Robot', asset_id='robot')
    library = PrefabLibrary([asset])
    entities, records = [], []
    for root, x in [('left', -3.6), ('middle', 0), ('right', 3.6)]:
        record = library.instantiate_entities('robot', mapping={'root': root, 'e1': root+'_body'}, position=[x, 0, 0])
        entities.extend(record.pop('entities')); records.append(record)
    scene = dict(version=1, entities=entities, prefab_instances=records,
                 prefab_assets=library.assets, component_definitions=library.component_definitions,
                 variables={'ticks': {'type': 'int', 'value': 0}})
    notice = new_event('Apply Notice', [{'name': 'Message', 'type': 'string'}]); notice['id'] = 100001
    b = GraphBuilder('Apply robots during gameplay', component_definitions=library.component_definitions,
                     event_definitions=[notice])
    def add(nid, name, **values):
        b.add(nid, name, **values)
        i = len(b.graph['nodes']) - 1
        b.graph['nodes'][-1]['position'] = [(i % 6) * 310, (i // 6) * 230]
    def chain(previous, steps):
        for nid, name, values in steps:
            add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    def frame(count, nid, name, **values):
        add(nid+'_update', 'On Update'); add(nid+'_frame', 'Get Frame Count')
        add(nid+'_eq', 'Nearly Equal', B=count, Epsilon=0); add(nid+'_if', 'Branch')
        add(nid, name, **values)
        b.connect(nid+'_update', 'Out', nid+'_if', 'In')
        b.connect(nid+'_frame', 'Value', nid+'_eq', 'A')
        b.connect(nid+'_eq', 'Value', nid+'_if', 'Condition'); b.connect(nid+'_if', 'True', nid, 'In')
    add('start', 'On Game Start')
    chain('start', [('timer', 'Start Timer', dict(Name='heartbeat', Owner='middle_body', Seconds=.25, Repeat=True)),
                    ('pin_scale', 'Set Scale', dict(Entity='right_body', Value=[1, 1, 1])),
                    ('pin_speed', 'Set Motion Speed', dict(Entity='right', Value=90)),
                    ('start_log', 'Print Log', dict(Message='Timer started; apply at frame 60'))])
    add('tick', 'On Timer Finished', Receiver='middle_body', NameFilter='heartbeat')
    add('ticks', 'Get Integer Variable', Name='ticks'); add('increment', 'Integer Add', B=1)
    add('save_ticks', 'Set Integer Variable', Name='ticks')
    b.connect('tick', 'Out', 'save_ticks', 'In'); b.connect('ticks', 'Value', 'increment', 'A')
    b.connect('increment', 'Value', 'save_ticks', 'Value')
    frame(20, 'enlarge', 'Set Scale', Entity='left_body', Value=[1.5]*3)
    chain('enlarge', [('slow', 'Set Motion Speed', dict(Entity='left', Value=45))])
    frame(60, 'queue', 'Send Apply Notice', Recipient='middle_body', Message='Queued event survived Apply')
    chain('queue', [('apply', 'Apply Prefab Overrides', dict(Instance='left_body')),
                    ('applied', 'Print Log', dict(Message='Applied; middle follows, right stays pinned'))])
    frame(120, 'reset', 'Reset Prefab Instance', Instance='right')
    chain('reset', [('reset_log', 'Print Log', dict(Message='Reset right to the updated template'))])
    add('notice', 'On Apply Notice', Receiver='middle_body'); add('notice_log', 'Print Log')
    b.connect('notice', 'Out', 'notice_log', 'In'); b.connect('notice', 'Message', 'notice_log', 'Message')
    save_json(project/'scenes/main.json', scene); save_json(project/'graphs/gameplay.json', b.graph)
    save_json(project/'project.json', dict(version=1, name='Live prefab Apply and Reset',
        graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/robot.gltf']))
    export(compile_graph(b.graph, scene), project/'generated')
    return project


if __name__ == '__main__':
    print(create())
