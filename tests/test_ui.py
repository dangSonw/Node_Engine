"""UI document boundaries and event values must survive authoring and lowering."""
from copy import deepcopy
import pytest
from editor.core import ui
from editor.core.document import default_scene
from editor.core.builder import GraphBuilder
from editor.core.codegen import CppEmitter, cpp_string
from editor.core.compiler import GraphError


def test_templates_are_scene_owned_without_aliasing():
    original=default_scene(); asset=ui.new_asset()
    changed=ui.put_asset(original,asset)
    asset['rml']='mutated'
    assert 'ui_assets' not in original
    assert ui.scene_assets(changed)[0]['rml']==ui.starter_template()
    assert ui.scene_assets(ui.put_asset(changed,dict(changed['ui_assets'][0],name='Menu')))[0]['name']=='Menu'


@pytest.mark.parametrize('field,value',[('version',True),('id','bad name'),('name','\n'),
    ('rml',''),('rml','a\0b'),('type','sound')])
def test_template_rejects_invalid_fields(field,value):
    asset=ui.new_asset(); asset[field]=value
    with pytest.raises(ValueError): ui.validate_assets([asset])


def test_template_limit_and_duplicate_ids():
    asset=ui.new_asset()
    with pytest.raises(ValueError): ui.validate_assets([dict(asset,rml='x'*(1024*1024+1))])
    with pytest.raises(ValueError): ui.validate_assets([asset,deepcopy(asset)])
    with pytest.raises(ValueError): ui.validate_assets([dict(asset,id=str(i),rml='x'*(1024*1024)) for i in range(9)])


def test_ui_event_value_scoped_to_handler_and_generated_with_native_binding():
    b=GraphBuilder(); b.add('submit','On UI Text Submitted',**{'Widget Filter':'hud','Element Filter':'name'})
    b.add('store','Set String Variable',Name='name')
    b.connect('submit','Out','store','In'); b.connect('submit','Value','store','Value')
    ir=b.compile(); assert ir['events']['ui'][0]['element']=='name'
    cpp=CppEmitter().generate(ir)
    assert 'rt::BindUiEvent(ctx, ' + ', '.join(cpp_string(s) for s in ('submit','submit','hud','name')) in cpp
    assert 'event.value' in cpp
    b.graph['links'].pop(0); b.add('start','On Game Start'); b.connect('start','Out','store','In')
    with pytest.raises(GraphError,match='inside that UI event handler'): b.compile()


def test_listener_filters_must_be_constants():
    b=GraphBuilder(); b.add('click','On Button Click'); b.add('name','String',Value='hud')
    b.connect('name','Value','click','Widget Filter')
    with pytest.raises(GraphError,match='must be a constant'): b.compile()
    b.graph['links']=[]; b.graph['nodes'][0]['values']['Element Filter']='bad/id'
    with pytest.raises(GraphError,match='UI identifier'): b.compile()
