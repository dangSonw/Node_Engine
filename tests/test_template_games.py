from pathlib import Path
import pytest

from editor.core.document import load_project
from editor.core.feature_pipeline import validate_feature_document
from tools.verify_template_games import assert_state, checked_contract, assert_gameplay

ROOT = Path(__file__).resolve().parents[1]


def test_templates_are_valid_projects_and_have_generated_ir():
    for name in ("flappy_bird", "isometric_snake_3d"):
        project = ROOT / "templates/games" / name / (name+'.nen')
        manifest, graph, scene = load_project(project)
        validate_feature_document(scene)
        assert manifest["version"] == 2 and manifest['format']=='NodeEngine.Project'
        assert (project.parent / "generated/game.ir.json").exists()
        assert graph['nodes'], 'The editable gameplay graph must exist'


@pytest.mark.parametrize('name', ['flappy_bird', 'isometric_snake_3d'])
def test_templates_declare_complete_native_gameplay_acceptance(name):
    checked_contract(ROOT / 'templates/games' / name / (name + '.nen'))


def test_gameplay_assertions_unwrap_typed_values_and_reject_wrong_results():
    state = {'variables': {'score': {'type': 'int', 'value': 2},
                           'snake': {'type': 'array<vec3>', 'value': [[0, 0, 0], [1, 0, 0]]},
                           'alive': {'type': 'bool', 'value': False}}}
    assert_state(state, dict(path='variables.score', op='ge', value=1))
    assert_state(state, dict(path=['variables', 'snake'], op='len_eq', value=2))
    assert_state(state, dict(path='variables.alive', op='eq', value=False))
    with pytest.raises(AssertionError, match='variables.score'):
        assert_state(state, dict(path='variables.score', op='ge', value=3))
    with pytest.raises(KeyError):
        assert_state(state, dict(path='variables.missing', op='eq', value=0))


def test_semantic_coverage_requires_real_scoring_growth_death_and_restart():
    def state(**variables):
        return {'variables': variables}
    initial = state(score=0, alive=True, steps=0, resets=1, snake=[0, 1, 2], status='RUNNING')
    grown = state(score=1, alive=True, steps=3, resets=1, snake=[0, 1, 2, 3], status='RUNNING')
    dead = state(score=1, alive=False, steps=9, resets=1, snake=[0, 1, 2, 3], status='SELF COLLISION  /  R TO RESTART')
    restarted = state(score=0, alive=True, steps=0, resets=2, snake=[0, 1, 2], status='RUNNING')
    assert_gameplay({}, {'covers': ['scoring', 'growth']}, grown, initial)
    assert_gameplay({}, {'covers': ['death', 'self_collision']}, dead)
    assert_gameplay({}, {'covers': ['restart']}, restarted, dead)
    for covers, after, before in [(['scoring'], initial, initial), (['growth'], initial, initial),
                                 (['wall_collision'], dead, None), (['restart'], initial, initial)]:
        with pytest.raises(AssertionError):
            assert_gameplay({}, {'covers': covers}, after, before)
