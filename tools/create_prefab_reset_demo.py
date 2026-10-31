"""A live prefab reset with a continuing timer and a queued custom event."""
from copy import deepcopy
from pathlib import Path
import json
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editor.core.builder import GraphBuilder
from editor.core.codegen import export
from editor.core.compiler import compile_graph
from editor.core.document import save_json
from editor.core.events import new_event
from editor.core.prefabs import PrefabLibrary
from editor.core.registry import ROOT


def create():
    project = ROOT / 'examples/prefab_reset_demo'
    source = ROOT / 'examples/prefabs_demo'
    (project / 'assets').mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'assets/robot.gltf', project / 'assets/robot.gltf')
    assets = json.loads((source / 'scenes/main.json').read_text('utf-8'))['prefab_assets']
    assets = deepcopy(assets)
    pair = next(a for a in assets if a['id'] == 'robot_pair')
    pair['nested'][1]['overrides']['root']['active'] = True
    library = PrefabLibrary(assets)
    record = library.instantiate_entities('robot_pair', mapping={'group': 'pair', 'left': 'left', 'right': 'right'})
    scene = dict(version=1, entities=record.pop('entities'), prefab_instances=[record],
                 prefab_assets=library.assets, component_definitions=library.component_definitions,
                 variables={'ticks': {'type': 'int', 'value': 0}})
    notice = new_event('Reset Notice', [{'name': 'Message', 'type': 'string'}]); notice['id'] = 100001
    b = GraphBuilder('Reset robots while playing', event_definitions=[notice])
    def add(nid, name, **values):
        b.add(nid, name, **values)
        index = len(b.graph['nodes']) - 1
        b.graph['nodes'][-1]['position'] = [(index % 5) * 310, (index // 5) * 240]
    def chain(previous, steps):
        for nid, name, values in steps:
            add(nid, name, **values); b.connect(previous, 'Out', nid, 'In'); previous = nid
    def frame(frame, nid, name, **values):
        add(nid + '_event', 'On Update'); add(nid + '_count', 'Get Frame Count')
        add(nid + '_eq', 'Nearly Equal', B=frame, Epsilon=0); add(nid + '_if', 'Branch')
        add(nid, name, **values)
        b.connect(nid + '_event', 'Out', nid + '_if', 'In')
        b.connect(nid + '_count', 'Value', nid + '_eq', 'A')
        b.connect(nid + '_eq', 'Value', nid + '_if', 'Condition')
        b.connect(nid + '_if', 'True', nid, 'In')
    add('start', 'On Game Start')
    chain('start', [('timer', 'Start Timer', dict(Name='heartbeat', Owner='pair', Seconds=.25, Repeat=True)),
                    ('log_start', 'Print Log', dict(Message='Timer started; reset at frame 60'))])
    add('tick', 'On Timer Finished', Receiver='pair', NameFilter='heartbeat')
    add('read_ticks', 'Get Integer Variable', Name='ticks'); add('increment', 'Integer Add', B=1)
    add('save_ticks', 'Set Integer Variable', Name='ticks')
    b.connect('tick', 'Out', 'save_ticks', 'In'); b.connect('read_ticks', 'Value', 'increment', 'A')
    b.connect('increment', 'Value', 'save_ticks', 'Value')
    frame(20, 'delete', 'Destroy Entity', Entity='left')
    chain('delete', [('enlarge', 'Set Scale', dict(Entity='right', Value=[1.8, 1.8, 1.8])),
                     ('log_damage', 'Print Log', dict(Message='Left deleted; right enlarged'))])
    frame(60, 'queue', 'Send Reset Notice', Recipient='pair', Message='Queued event survived Reset')
    chain('queue', [('reset', 'Reset Prefab Instance', dict(Instance='pair')),
                    ('log_reset', 'Print Log', dict(Message='Prefab restored; timer continues'))])
    add('notice', 'On Reset Notice', Receiver='pair'); add('log_notice', 'Print Log')
    b.connect('notice', 'Out', 'log_notice', 'In'); b.connect('notice', 'Message', 'log_notice', 'Message')
    save_json(project / 'scenes/main.json', scene)
    save_json(project / 'graphs/gameplay.json', b.graph)
    save_json(project / 'project.json', dict(version=1, name='Live prefab reset',
        graph='graphs/gameplay.json', scene='scenes/main.json', assets=['assets/robot.gltf']))
    export(compile_graph(b.graph, scene), project / 'generated')
    return project


if __name__ == '__main__':
    print(create())
