"""Small glTF fixtures with known poses; shared by animation import checks."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import struct


def add_accessor(doc, binary, values, kind, code='f', component=5126):
    binary.extend(b'\0'*(-len(binary)%4))
    data=struct.pack('<'+code*sum(len(row) for row in values),*(x for row in values for x in row))
    doc['bufferViews'].append(dict(buffer=0,byteOffset=len(binary),byteLength=len(data)))
    binary.extend(data)
    entry=dict(bufferView=len(doc['bufferViews'])-1,componentType=component,count=len(values),type=kind)
    if kind in ('SCALAR','VEC3'):
        entry.update(min=[min(row[i] for row in values) for i in range(len(values[0]))],
                     max=[max(row[i] for row in values) for i in range(len(values[0]))])
    doc['accessors'].append(entry)
    return len(doc['accessors'])-1


def identity(x=0,y=0,z=0):
    return [1,0,0,0, 0,1,0,0, 0,0,1,0, x,y,z,1]


def rig():
    doc=dict(asset={'version':'2.0'},scene=0,scenes=[{'nodes':[1,2,3]}],
             nodes=[{'name':'Tip','translation':[0,2,0]},
                    {'name':'Root','translation':[1,0,0],'children':[0]},
                    {'name':'Mesh','mesh':0,'skin':0,'translation':[9,0,0]},
                    {'name':'Matrix root','matrix':identity(0,0,3)}],
             accessors=[],bufferViews=[],buffers=[],meshes=[],skins=[],animations=[])
    binary=bytearray()
    def add(values,kind,**kw):return add_accessor(doc,binary,values,kind,**kw)
    position=add([[1,2,0],[1,3,0],[2,2,0]],'VEC3')
    joints=add([[0,1,0,0]]*3,'VEC4',code='H',component=5123)
    weights=add([[1,0,0,0]]*3,'VEC4')
    doc['meshes']=[{'primitives':[{'attributes':{'POSITION':position,'JOINTS_0':joints,'WEIGHTS_0':weights}}]}]
    bind=add([identity(-1,-2),identity(-1)],'MAT4')
    doc['skins']=[{'joints':[0,1],'skeleton':1,'inverseBindMatrices':bind}]
    def clip(name,channels):
        animation=dict(name=name,samplers=[],channels=[])
        for node,path,times,values,mode in channels:
            sampler=len(animation['samplers'])
            animation['samplers'].append(dict(input=add([[t] for t in times],'SCALAR'),
                output=add(values,'VEC4' if path=='rotation' else 'VEC3'),interpolation=mode))
            animation['channels'].append(dict(sampler=sampler,target={'node':node,'path':path}))
        doc['animations'].append(animation)
    clip('Linear',[(1,'translation',[0,2],[[1,0,0],[5,0,0]],'LINEAR'),
                   (0,'rotation',[0,2],[[0,0,0,1],[0,0,1,0]],'LINEAR')])
    clip('Step',[(1,'translation',[0,1,2],[[1,0,0],[3,0,0],[5,0,0]],'STEP')])
    clip('Cubic',[(1,'translation',[0,2],[[0,0,0],[1,0,0],[4,0,0],[0,0,0],[5,0,0],[0,0,0]],'CUBICSPLINE')])
    clip('Cubic rotation',[(0,'rotation',[0,2],[[0,0,0,0],[0,0,0,1],[0,0,0,0],
                                             [0,0,0,0],[0,0,1,0],[0,0,0,0]],'CUBICSPLINE')])
    clip('Scale',[(1,'scale',[0,2],[[1,1,1],[2,-1,.5]],'LINEAR')])
    clip('Delayed',[(1,'translation',[.5,1.5],[[2,0,0],[4,0,0]],'LINEAR')])
    clip('Step',[(1,'translation',[0],[[7,0,0]],'STEP')])
    return doc,binary


def write(directory,doc,binary,mode='external',name='rig'):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    doc=deepcopy(doc); doc['buffers']=[{'byteLength':len(binary)}]
    if mode=='glb':
        source=json.dumps(doc,separators=(',',':')).encode(); source+=b' '*(-len(source)%4)
        data=bytes(binary)+b'\0'*(-len(binary)%4)
        payload=struct.pack('<I4s',len(source),b'JSON')+source+struct.pack('<I4s',len(data),b'BIN\0')+data
        path=directory/(name+'.glb'); path.write_bytes(struct.pack('<4sII',b'glTF',2,12+len(payload))+payload)
    else:
        if mode=='embedded': doc['buffers'][0]['uri']='data:application/octet-stream;base64,'+base64.b64encode(binary).decode()
        else:
            doc['buffers'][0]['uri']='animation%20data.bin'; (directory/'animation data.bin').write_bytes(binary)
        path=directory/(name+'.gltf'); path.write_text(json.dumps(doc,indent=2)+'\n','utf-8')
    return path


def replace_values(doc,binary,accessor,values,code='f'):
    entry=doc['accessors'][accessor]; view=doc['bufferViews'][entry['bufferView']]
    offset=view.get('byteOffset',0)+entry.get('byteOffset',0)
    data=struct.pack('<'+code*len(values),*values)
    binary[offset:offset+len(data)]=data
