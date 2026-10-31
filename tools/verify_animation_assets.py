"""Native glTF TRS/skin checks against analytic references, including bad assets."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.animation_fixture import rig,write,replace_values,identity,add_accessor
from tools.create_animated_robot import create as create_robot
from editor.core.runtime_build import fingerprint
from editor.core.document import save_json


def verify(build=ROOT/'build'):
    output=ROOT/'artifacts/validation/animation-assets-checks.json'
    directory=ROOT/'.cache'/('animation-'+uuid.uuid4().hex[:10]); directory.mkdir(parents=True)
    exe=Path(build)/('node_animation_probe.exe' if os.name=='nt' else 'node_animation_probe')
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],rejections={},workspace=str(directory))
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def run(path,samples=(),success=True):
        request=dict(file=str(path),samples=samples); file=directory/'request.json'; save_json(file,request)
        result=subprocess.run([str(exe),str(file)],capture_output=True,text=True,encoding='utf-8',timeout=20)
        data=json.loads(result.stdout)
        if data['ok']!=success or result.returncode!=(0 if success else 1): raise AssertionError(result.stdout+result.stderr)
        return data
    def near(a,b): return all(abs(x-y)<=3.e-5 for x,y in zip(a,b))
    def position(sample,node):return sample['nodes'][node][12:15]
    def query(time,clip=0,**extra):return dict(clip=clip,time=time,**extra)
    def reject(name,mutate,fragment):
        doc,binary=rig(); mutate(doc,binary)
        result=run(write(directory/name,doc,binary),success=False)
        expected=(fragment,) if isinstance(fragment,str) else fragment
        report['rejections'][name]=result['error']
        check(name+': rejects invalid asset',result['error']=='Invalid animation glTF structure' or
              any(f.casefold() in result['error'].casefold() for f in expected))
    try:
        cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
        built=subprocess.run([cmake,'--build',str(build),'--target','node_animation_probe','--parallel','2'],
                             cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=600)
        output.with_suffix('.build.log').write_text(built.stdout+built.stderr,'utf-8')
        if built.returncode: raise RuntimeError('Animation probe build failed; see '+str(output.with_suffix('.build.log')))
        report['binary_sha256']=hashlib.sha256(exe.read_bytes()).hexdigest()
        doc,binary=rig(); path=write(directory/'valid',doc,binary)
        samples=[query(t,clip) for clip in range(7) for t in (0,.5,1,2)]
        result=run(path,samples)
        check('Child-before-parent indices retain document identity',result['parents']==[1,-1,-1,-1] and result['nodes']==['Tip','Root','Mesh','Matrix root'])
        check('Ozz evaluates rest hierarchy and matrix roots',near(position(result['rest'],0),[1,2,0]) and near(position(result['rest'],3),[0,0,3]))
        check('Inverse binds yield identity rest skin matrices',all(near(m,identity()) for m in result['rest']['skins'][0]))
        check('Clip names, channels and zero duration are preserved',len(result['clips'])==7 and result['clips'][0]['channels']==2 and result['clips'][-1]==dict(name='Step (2)',duration=0.,channels=1))
        half=result['samples'][1]
        check('LINEAR translation retains unanimated local offset',near(position(half,1),[2,0,0]) and near(position(half,0),[2,2,0]))
        check('LINEAR rotation follows shortest-arc spherical interpolation',near(half['nodes'][0][:2],[math.sqrt(.5),math.sqrt(.5)]))
        boundary=run(path,[query(t,1) for t in (.999999,1,1.000001,2)])['samples']
        check('STEP changes exactly at the authored key',all(near(position(s,1),[x,0,0]) for s,x in zip(boundary,[1,3,3,5])))
        check('CUBICSPLINE scales tangents by interval duration',near(position(result['samples'][9],1),[2.75,0,0]) and near(position(result['samples'][10],1),[4,0,0]))
        qz,qw=.15625,.84375; length=math.hypot(qz,qw); qz/=length; qw/=length
        check('Cubic quaternion polynomial is normalized after interpolation',near(result['samples'][13]['nodes'][0][:2],[1-2*qz*qz,2*qz*qw]))
        scale=result['samples'][19]['nodes'][1]
        check('Negative and nonuniform scale survive ozz model evaluation',near([scale[0],scale[5],scale[10]],[2,-1,.5]))
        check('Tracks clamp before their first and after their last key',near(position(result['samples'][20],1),[2,0,0]) and near(position(result['samples'][23],1),[4,0,0]))
        check('Single-key zero-duration animation holds its value',all(near(position(s,1),[7,0,0]) for s in result['samples'][24:28]))
        wrapped=run(path,[query(t,loop=True) for t in (2,2.5,-1.5,-2)]+[query(-1),query(10)])['samples']
        check('Loop endpoints, negative time and clamped playback are defined',all(near(position(s,1),[x,0,0]) for s,x in zip(wrapped,[1,2,2,1,1,5])))
        vertices=[
            dict(position=[1,3,0],weights=[[0,1]]),dict(position=[1,3,0],weights=[[0,.25],[1,.25]])]
        skin=run(path,[query(.5,vertices=vertices)])['samples'][0]['positions']
        check('Skinning applies joint and inverse-bind transforms exactly once',near(skin[0],[2-math.sqrt(.5),2+math.sqrt(.5),0]))
        check('Multiple influences normalize quantized weight sums',near(skin[1],[2-math.sqrt(.5)/2,2.5+math.sqrt(.5)/2,0]))
        repeated=run(path,[query(.5),query(1.25),query(.5)])['samples']
        check('Sampling is independent of previous time or instance',repeated[0]==repeated[2] and repeated[0]!=repeated[1])
        check('Independent process reproduces complete sampled matrices',run(path,samples)==result)
        for mode in ('embedded','glb'):
            check(mode+' agrees with external URI document',run(write(directory/mode,doc,binary,mode),samples)==result)
        sparse=deepcopy(doc); data=bytearray(binary)
        accessor=sparse['animations'][0]['samplers'][0]['output']; old=sparse['accessors'][accessor].pop('bufferView')
        idx=add_accessor(sparse,data,[[0],[1]],'SCALAR','B',5121)
        sparse['accessors'][accessor]['sparse']=dict(count=2,indices={'bufferView':sparse['accessors'][idx]['bufferView'],'componentType':5121},values={'bufferView':old})
        sparse_data=bytes(data)
        check('Sparse translation keys retain exact animation poses',run(write(directory/'sparse',sparse,data),samples)==result)
        stride=deepcopy(doc); data=bytearray(binary); a=stride['accessors'][accessor]; view=stride['bufferViews'][a['bufferView']]
        padded=add_accessor(stride,data,[[1,0,0,99],[5,0,0,99]],'VEC4')
        a['bufferView']=stride['accessors'][padded]['bufferView']; stride['bufferViews'][a['bufferView']]['byteStride']=16
        check('Interleaved accessor stride is honored',run(write(directory/'stride',stride,data),samples)==result)
        check('Unicode asset directory resolves correctly',run(write(directory/'Nhân vật mẫu',doc,binary),samples)==result)
        missing_bind=deepcopy(doc); missing_bind['skins'][0].pop('inverseBindMatrices')
        no_bind=run(write(directory/'no-bind',missing_bind,binary))
        check('Missing inverse binds use identity matrices',no_bind['rest']['skins'][0][0]==no_bind['rest']['nodes'][0])
        extra_bind=deepcopy(doc); extra_binary=bytearray(binary)
        extra_bind['skins'][0]['inverseBindMatrices']=add_accessor(extra_bind,extra_binary,
            [identity(-1,-2),identity(-1),identity(99)],'MAT4')
        check('Inverse bind accessor may include unused trailing matrices',run(write(directory/'extra-bind',extra_bind,extra_binary),samples)==result)
        invalid_sparse=deepcopy(sparse); sparse_binary=bytearray(sparse_data)
        sparse_view=invalid_sparse['accessors'][accessor]['sparse']['indices']['bufferView']
        sparse_binary[invalid_sparse['bufferViews'][sparse_view]['byteOffset']+1]=99
        check('Sparse index overflow is rejected before sampling','Sparse animation indices' in
              run(write(directory/'bad-sparse',invalid_sparse,sparse_binary),success=False)['error'])
        # Required failures exercise parsing and sampling, not only Python validation.
        reject('cycle',lambda d,b:d['nodes'][0].update(children=[1]),'cycle')
        reject('multiple-parents',lambda d,b:d['nodes'][3].update(children=[0]),'parents')
        reject('bad-skin-joint',lambda d,b:d['skins'][0].update(joints=[0,0]),'skin')
        reject('bad-skeleton-root',lambda d,b:d['skins'][0].update(skeleton=3),'ancestor')
        reject('disconnected-joints',lambda d,b:(d['skins'][0].pop('skeleton'),d['skins'][0].update(joints=[0,3])),'ancestor')
        reject('missing-scene-root',lambda d,b:d['scenes'][0].update(nodes=[2,3]),'same scene')
        reject('cubic-single-key',lambda d,b:d['animations'][-1]['samplers'][0].update(interpolation='CUBICSPLINE'),'two keys')
        reject('bind-count',lambda d,b:d['accessors'][d['skins'][0]['inverseBindMatrices']].update(count=1),'bind')
        reject('matrix-target',lambda d,b:(d['nodes'][1].pop('translation'),d['nodes'][1].update(matrix=identity(1))),'matrix node')
        reject('sheared-matrix',lambda d,b:d['nodes'][3]['matrix'].__setitem__(4,.5),'shear')
        reject('duplicate-channel',lambda d,b:d['animations'][0]['channels'].append(deepcopy(d['animations'][0]['channels'][0])),('duplicate','structure'))
        reject('morph-channel',lambda d,b:d['animations'][0]['channels'][0]['target'].update(path='weights'),'morph')
        reject('cubic-count',lambda d,b:d['animations'][2]['samplers'][0].update(output=d['animations'][0]['samplers'][0]['output']),'count')
        for label,values in [('repeated-time',[0,0]),('negative-time',[-1,2]),('infinite-time',[0,math.inf])]:
            reject(label,lambda d,b,v=values:replace_values(d,b,d['animations'][0]['samplers'][0]['input'],v),'times')
        reject('nonfinite-key',lambda d,b:replace_values(d,b,d['animations'][0]['samplers'][0]['output'],[math.inf,0,0,5,0,0]),'finite')
        reject('nonunit-quaternion',lambda d,b:replace_values(d,b,d['animations'][0]['samplers'][1]['output'],[0,0,0,2,0,0,1,0]),'quaternion')
        reject('truncated-accessor',lambda d,b:d['accessors'][d['animations'][0]['samplers'][0]['input']].update(byteOffset=1024),'accessor')
        for label,query_value,fragment in [
            ('nonfinite-sampling-time',query(0,nonfinite=True),'finite'),
            ('unknown-clip',query(0,99),'range'),
            ('unknown-joint',query(0,vertices=[dict(position=[0,0,0],weights=[[20,1]])]),'range'),
            ('negative-weight',query(0,vertices=[dict(position=[0,0,0],weights=[[0,-1]])]),'weight'),
            ('zero-weights',query(0,vertices=[dict(position=[0,0,0],weights=[[0,0]])]),'zero')]:
            response=run(path,[query_value],False); check(label,fragment in response['error'].lower())
        zero_quaternion=deepcopy(doc); zero_binary=bytearray(binary)
        a=zero_quaternion['animations'][3]['samplers'][0]['output']
        replace_values(zero_quaternion,zero_binary,a,[0,0,0,0, 0,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,-1, 0,0,0,0])
        check('Degenerate cubic quaternion fails instead of producing NaN','zero length' in
              run(write(directory/'zero-quaternion',zero_quaternion,zero_binary),[query(1,3)],False)['error'])
        escape=directory/'escape'; escape_path=write(escape,doc,binary)
        content=json.loads(escape_path.read_text('utf-8')); content['buffers'][0]['uri']='../valid/animation%20data.bin'; save_json(escape_path,content)
        check('External buffer cannot escape its model directory','escapes' in run(escape_path,success=False)['error'])
        robot=create_robot(directory/'robot')
        samples=[query(0,1),query(1,1),query(.25,2)]
        animated=run(robot/'robot.gltf',samples)
        check('Blockbench robot imports six joints and Idle/Wave/Walk clips',len(animated['rest']['skins'][0])==6 and
              [c['name'] for c in animated['clips']]==['Idle','Wave','Walk'])
        check('Robot inverse binds preserve the original model at rest',all(near(m,identity()) for m in animated['rest']['skins'][0]))
        check('Robot Wave changes the right arm without changing left arm or root',
              animated['samples'][0]['skins'][0][3]!=animated['samples'][1]['skins'][0][3] and
              all(animated['samples'][0]['skins'][0][i]==animated['samples'][1]['skins'][0][i] for i in (0,1,2,4,5)))
        check('Robot Walk moves arms and legs independently',all(animated['samples'][2]['skins'][0][i]!=animated['rest']['skins'][0][i] for i in (2,3,4,5)))
        check('Rigged robot GLB and glTF produce identical sampled poses',run(robot/'robot.glb',samples)==animated)
        report['robot']=str(robot/'robot.glb')
        report['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'runtime/src/animation_asset.cpp','runtime/include/animation_asset.hpp','tools/animation_probe/main.cpp',
            'tools/animation_fixture.py','tools/create_animated_robot.py','tools/verify_animation_assets.py',
            'cmake/AnimationDependencies.cmake','tools/fetch_ozz.py')}
        if fingerprint()!=report['native_fingerprint']: raise RuntimeError('Native sources changed during verification')
        report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally:save_json(output,report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',type=Path,default=ROOT/'build');args=parser.parse_args()
    print(f"Animation assets: {len(verify(args.build)['checks'])} checks passed.")
