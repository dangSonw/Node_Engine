"""Compare animated GPU pixels to independently baked glTF geometry."""
from copy import deepcopy
import json
import math
from pathlib import Path
import struct
import subprocess
import pytest
from PySide6.QtGui import QImage
from editor.core.builder import GraphBuilder
from editor.core.camera import default_camera
from editor.core.document import default_scene,save_json
from editor.core.registry import ROOT
from editor.core.runtime_build import current
from tools.create_animated_robot import create
from tools.animation_fixture import add_accessor,write
from tests.test_physics_scene import chain

@pytest.fixture(scope='module')
def gpu(tmp_path_factory):
    directory=create(tmp_path_factory.mktemp('animated-gpu'))
    doc=json.loads((directory/'robot.gltf').read_text('utf-8')); binary=(directory/'animation data.bin').read_bytes()
    exe=ROOT/'build/node_view.exe'; assert current(exe)
    def run(doc,binary,label,animated=True):
        path=write(directory/label,doc,binary,name='robot')
        scene=default_scene(); scene['entities'][0].update(mesh='robot.gltf',position=[.2,0,0],rotation=[0,15,0],scale=[1.1,.9,1])
        scene['entities'].append(dict(id='camera',name='Camera',position=[0,.9,4],rotation=[0,0,0],scale=[1,1,1],camera=default_camera()))
        scene['active_camera']='camera'; b=GraphBuilder(); b.add('start','On Game Start')
        if animated:chain(b,'start',('play','Play Animation',{'Clip':'Wave'}),('pause','Pause Animation',{}),('seek','Set Animation Time',{'Time':1}))
        ir=path.parent/'test.ir.json'; capture=path.parent/'pixels.bmp'; save_json(ir,b.compile(scene))
        result=subprocess.run([str(exe),'--ir',str(ir),'--project-root',str(path.parent),'--frames','2','--capture',str(capture)],
            capture_output=True,text=True,encoding='utf-8',timeout=30)
        return result,QImage(str(capture))
    return doc,binary,run

def rows(doc,binary,accessor):
    a=doc['accessors'][accessor]; v=doc['bufferViews'][a['bufferView']]
    return [struct.unpack_from('<fff',binary,v.get('byteOffset',0)+a.get('byteOffset',0)+i*v.get('byteStride',12)) for i in range(a['count'])]

@pytest.mark.parametrize('weighted',[False,True])
def test_skinned_pose_matches_independent_baked_geometry(gpu,weighted):
    doc,raw,run=gpu; animated=deepcopy(doc); binary=bytearray(raw)
    primitive=animated['meshes'][3]['primitives'][0]; count=animated['accessors'][primitive['attributes']['POSITION']]['count']
    if weighted:
        # A normalized u8 pair across two sets, including a non-unit quantized sum.
        primitive['attributes']['JOINTS_0']=add_accessor(animated,binary,[[0,0,0,0]]*count,'VEC4',code='B',component=5121)
        primitive['attributes']['WEIGHTS_0']=add_accessor(animated,binary,[[128,0,0,0]]*count,'VEC4',code='B',component=5121)
        primitive['attributes']['JOINTS_1']=add_accessor(animated,binary,[[3,0,0,0]]*count,'VEC4',code='B',component=5121)
        primitive['attributes']['WEIGHTS_1']=add_accessor(animated,binary,[[128,0,0,0]]*count,'VEC4',code='B',component=5121)
        for key in ('WEIGHTS_0','WEIGHTS_1'):animated['accessors'][primitive['attributes'][key]]['normalized']=True
    baked=deepcopy(animated); baked_binary=bytearray(binary)
    angle=math.radians(150); pivot=(.3125,1.03125); output=[]
    for x,y,z in rows(animated,binary,primitive['attributes']['POSITION']):
        dx,dy=x-pivot[0],y-pivot[1]
        rx=pivot[0]+math.cos(angle)*dx-math.sin(angle)*dy; ry=pivot[1]+math.sin(angle)*dx+math.cos(angle)*dy
        output.append([(rx+x)/2 if weighted else rx,(ry+y)/2 if weighted else ry,z])
    baked['meshes'][3]['primitives'][0]['attributes']['POSITION']=add_accessor(baked,baked_binary,output,'VEC3')
    for n in baked['nodes']:n.pop('skin',None)
    for mesh in baked['meshes']:
        for p in mesh['primitives']:p['attributes']={k:v for k,v in p['attributes'].items() if not k.startswith(('JOINTS_','WEIGHTS_'))}
    baked.pop('skins'); baked.pop('animations')
    a,image=run(animated,binary,'weighted' if weighted else 'animated')
    z,reference=run(baked,baked_binary,'baked-weighted' if weighted else 'baked',False)
    assert a.returncode==z.returncode==0,a.stderr+z.stderr
    assert not image.isNull() and image==reference

def test_unskinned_mesh_node_animation_matches_baked_translation(gpu):
    original,raw,run=gpu; doc=deepcopy(original); binary=bytearray(raw)
    doc.pop('skins'); doc.pop('animations')
    for node in doc['nodes']:node.pop('skin',None)
    for mesh in doc['meshes']:
        for p in mesh['primitives']:p['attributes']={k:v for k,v in p['attributes'].items() if not k.startswith(('JOINTS_','WEIGHTS_'))}
    times=add_accessor(doc,binary,[[0],[2]],'SCALAR')
    values=add_accessor(doc,binary,[[0,0,0],[.25,.5,0]],'VEC3')
    doc['animations']=[dict(name='Wave',channels=[dict(sampler=0,target=dict(node=3,path='translation'))],
        samplers=[dict(input=times,output=values,interpolation='LINEAR')])]
    baked=deepcopy(doc); baked.pop('animations'); baked_binary=bytearray(binary)
    p=baked['meshes'][3]['primitives'][0]
    output=[[x+.125,y+.25,z] for x,y,z in rows(doc,binary,p['attributes']['POSITION'])]
    p['attributes']['POSITION']=add_accessor(baked,baked_binary,output,'VEC3')
    a,image=run(doc,binary,'rigid'); z,reference=run(baked,baked_binary,'rigid-baked',False)
    assert a.returncode==z.returncode==0,a.stderr+z.stderr
    assert not image.isNull() and image==reference

@pytest.mark.parametrize('damage,fragment',[
    ('missing','Invalid glTF structure'),('joint','range'),('negative','weight'),('zero','zero'),
    ('count','count'),('truncated','accessor'),('morph','Morph')])
def test_invalid_skin_fails_explicitly(gpu,damage,fragment):
    original,raw,run=gpu; doc=deepcopy(original); binary=bytearray(raw); p=doc['meshes'][3]['primitives'][0]
    count=doc['accessors'][p['attributes']['POSITION']]['count']
    if damage=='missing':p['attributes'].pop('WEIGHTS_0')
    elif damage=='joint':p['attributes']['JOINTS_0']=add_accessor(doc,binary,[[99,0,0,0]]*count,'VEC4',code='H',component=5123)
    elif damage in ('negative','zero'):p['attributes']['WEIGHTS_0']=add_accessor(doc,binary,[[-1 if damage=='negative' else 0,0,0,0]]*count,'VEC4')
    elif damage=='count':doc['accessors'][p['attributes']['WEIGHTS_0']]['count']-=1
    elif damage=='truncated':doc['accessors'][p['attributes']['WEIGHTS_0']]['byteOffset']=999999
    elif damage=='morph':p['targets']=[{'POSITION':p['attributes']['POSITION']}]
    result,_=run(doc,binary,'bad-'+damage)
    assert result.returncode!=0 and fragment.lower() in result.stderr.lower(),result.stderr
