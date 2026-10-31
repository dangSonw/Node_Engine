"""Add six joints and three clips to the existing Blockbench smoke-test robot."""
import base64
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.animation_fixture import add_accessor,identity,write


def create(directory=ROOT/'examples/animation_assets'):
    source=ROOT/'examples/character_demo/assets/robot.gltf'
    doc=json.loads(source.read_text('utf-8'))
    binary=bytearray(base64.b64decode(doc['buffers'][0]['uri'].split(',',1)[1]))
    def add(values,kind,**kw): return add_accessor(doc,binary,values,kind,**kw)
    # Geometry is in model space in the original nine-cube Blockbench export.
    pivots=[(0,0,0),(0,1.125,0),(-.3125,1.03125,0),(.3125,1.03125,0),(-.15625,.5,0),(.15625,.5,0)]
    names=['Root','Head','Left arm','Right arm','Left leg','Right leg']
    first=len(doc['nodes'])
    for i,(name,pivot) in enumerate(zip(names,pivots)):
        node=dict(name=name+' joint',translation=list(pivot))
        if not i: node['children']=list(range(first+1,first+len(pivots)))
        doc['nodes'].append(node)
    doc['scenes'][0]['nodes'].append(first)
    inverse=add([identity(*[-v for v in p]) for p in pivots],'MAT4')
    doc['skins']=[dict(name='Blockbench robot',joints=list(range(first,first+len(pivots))),skeleton=first,inverseBindMatrices=inverse)]
    mapping=[0,1,2,3,4,5,1,1,0]
    for i,node in enumerate(doc['nodes'][:first]):
        node['skin']=0
        for primitive in doc['meshes'][node['mesh']]['primitives']:
            count=doc['accessors'][primitive['attributes']['POSITION']]['count']
            primitive['attributes']['JOINTS_0']=add([[mapping[i],0,0,0]]*count,'VEC4',code='H',component=5123)
            primitive['attributes']['WEIGHTS_0']=add([[1,0,0,0]]*count,'VEC4')
    doc['animations']=[]
    def clip(name,channels):
        animation=dict(name=name,channels=[],samplers=[])
        for joint,path,times,values in channels:
            index=len(animation['samplers'])
            animation['samplers'].append(dict(input=add([[t] for t in times],'SCALAR'),
                output=add(values,'VEC4' if path=='rotation' else 'VEC3'),interpolation='LINEAR'))
            animation['channels'].append(dict(sampler=index,target={'node':first+joint,'path':path}))
        doc['animations'].append(animation)
    def rotations(axis,angles):
        rows=[]
        for angle in angles:
            half=math.radians(angle)/2; row=[0.,0.,0.,math.cos(half)]; row[axis]=math.sin(half); rows.append(row)
        return rows
    clip('Idle',[(0,'translation',[0,1,2],[[0,0,0],[0,.04,0],[0,0,0]])])
    clip('Wave',[(3,'rotation',[0,.5,1,1.5,2],rotations(2,[0,130,150,130,0]))])
    clip('Walk',[(joint,'rotation',[0,.25,.5,.75,1],rotations(0,[0,sign*30,0,-sign*30,0]))
                 for joint,sign in ((2,-1),(3,1),(4,1),(5,-1))])
    doc['asset']['generator']='Node_Engine: six-joint rig derived from the Blockbench robot'
    directory=Path(directory)
    write(directory,doc,binary,name='robot')
    write(directory,doc,binary,mode='glb',name='robot')
    return directory


if __name__=='__main__': print(create())
