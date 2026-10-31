"""Scene-owned RmlUi templates shared by native Preview and generated games."""
from copy import deepcopy
import re
import uuid
from .scene import entity_text


def new_asset(name='HUD', rml=None):
    return dict(version=1, type='ui', id=uuid.uuid4().hex, name=name,
                rml=starter_template() if rml is None else rml)


def validate_assets(values):
    if not isinstance(values, list) or len(values)>128:
        raise ValueError('At most 128 UI templates are allowed')
    result, size = {}, 0
    for a in values:
        if not isinstance(a, dict) or set(a) != {'version','type','id','name','rml'}:
            raise ValueError('Invalid UI template fields')
        if type(a['version']) is not int or a['version']!=1 or a['type']!='ui':
            raise ValueError('Unsupported UI template version/type')
        uid = a['id']
        if not isinstance(uid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',uid) or uid in result:
            raise ValueError('Invalid or duplicate UI template ID')
        if not entity_text(a['name'],512): raise ValueError('Invalid UI template name')
        rml = a['rml']
        if not isinstance(rml,str) or not rml or '\0' in rml or len(rml.encode('utf-8'))>1024*1024:
            raise ValueError('UI RML requires 1 byte to 1 MiB of text without NUL')
        size += len(rml.encode('utf-8'))
        if size>8*1024*1024: raise ValueError('Scene UI templates exceed 8 MiB')
        result[uid] = a
    return result


def scene_assets(scene):
    return list(validate_assets(scene.get('ui_assets', [])).values())


def put_asset(scene, asset):
    from .scene import validate_scene
    validate_assets([asset]); result=deepcopy(scene)
    values={a['id']:a for a in scene_assets(result)}; values[asset['id']]=deepcopy(asset)
    result['ui_assets']=list(values.values())
    return validate_scene(result)


def starter_template():
    return '''<rml><head><title>HUD</title><style>
body { font-family: node-ui; font-size: 18px; color: #e9efff; }
#panel { display: block; position: absolute; left: 24px; top: 24px; width: 300px;
    padding: 20px; background-color: #172338e8; border-radius: 12px; }
p { display: block; margin: 0px 0px 12px; }
input { display: block; margin-bottom: 12px; }
input.button { width: 260px; height: 38px; background-color: #4080c0; text-align: center; }
input.button:hover { background-color: #559ce0; }
input.button:disabled { background-color: #4a4f58; }
input.text { width: 252px; height: 30px; padding: 4px; background-color: #0d1625; }
progress { display: block; width: 260px; height: 14px; background-color: #0d1625; margin-bottom: 12px; }
progress fill { background-color: #53cfa4; }
input.range { width: 260px; height: 20px; }
slidertrack { background-color: #263b55; height: 8px; margin-top: 6px; }
sliderbar { width: 14px; height: 20px; background-color: #8dbbff; }
input.checkbox { width: 20px; height: 20px; background-color: #4a586c; }
input.checkbox:checked { background-color: #53cfa4; }
</style></head><body><div id="panel">
<p id="title">Robot playground</p><p id="score">Score: 0</p>
<progress id="progress" value="0" />
<input id="add" type="button" class="button" value="Add point" />
<input id="name" type="text" class="text" value="Player" maxlength="128" />
<input id="volume" type="range" class="range" min="0" max="1" step="0.1" value="0.5" />
<input id="enabled" type="checkbox" class="checkbox" checked="checked" />
<p id="status">Click Add point to start</p>
</div></body></rml>'''
