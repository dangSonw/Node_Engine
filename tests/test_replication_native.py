"""Native local replication journal and authority parity."""
import json

from editor.core.builder import GraphBuilder
from editor.core.data_types import declaration
from editor.core.document import default_scene
from tests.test_native import native


def test_replication_authority_and_revision_match_in_both_native_hosts(native):
    scene = default_scene()
    scene['features'] = {'gameplay': {'replication': {'authority': 'server'}}}
    scene['variables'] = {
        'accepted': declaration('bool', False),
        'value': declaration('string', ''),
        'revision': declaration('int', 0),
    }
    b = GraphBuilder('Replication')
    b.add('start', 'On Game Start')
    b.add('publish', 'Publish Replicated Value', Key='score', Value='42')
    b.add('split', 'Sequence')
    b.add('accepted', 'Set Boolean Variable', Name='accepted')
    b.add('split2', 'Sequence')
    b.add('read', 'Get Replicated Value', Key='score')
    b.add('rev', 'Get Replication Revision')
    b.add('save_value', 'Set String Variable', Name='value')
    b.add('save_revision', 'Set Integer Variable', Name='revision')
    for a, o, d, i in [
        ('start', 'Out', 'publish', 'In'), ('publish', 'Out', 'split', 'In'),
        ('publish', 'Accepted', 'accepted', 'Value'), ('split', 'First', 'accepted', 'In'),
        ('accepted', 'Out', 'split2', 'In'), ('split2', 'First', 'save_value', 'In'),
        ('split2', 'Then', 'save_revision', 'In'), ('read', 'Value', 'save_value', 'Value'),
        ('rev', 'Value', 'save_revision', 'Value'),
    ]:
        b.connect(a, o, d, i)
    preview, game = native(b.graph, scene=scene, frames=1)
    assert preview.returncode == game.returncode == 0, preview.stderr + game.stderr
    left, right = json.loads(preview.stdout), json.loads(game.stdout)
    assert left == right
    assert left['variables']['accepted']['value'] is True
    assert left['variables']['value']['value'] == '42'
    assert left['variables']['revision']['value'] == 1
    assert left['replication']['values'] == {'score': '42'}

