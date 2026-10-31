"""Run the Blockbench physics graph in four native hosts, including process restart."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.create_physics_demo import GAME


def verify(events=False, authoring=False, queries=False, overlaps=False):
    authoring=authoring or queries or overlaps
    events=events or authoring
    name='physics-queries' if queries else ('physics-authoring' if authoring else ('physics-events' if events else 'physics-scene'))
    project=ROOT/'examples'/('physics_queries_demo' if queries else ('physics_authoring_demo' if authoring else ('physics_events_demo' if events else 'physics_demo')))
    if overlaps: name='physics-overlaps'; project=ROOT/'examples/physics_overlaps_demo'
    game=GAME
    if events:
        from tools.create_physics_events_demo import GAME as game
    if authoring:
        from tools.create_physics_authoring_demo import GAME as game
    if queries:
        from tools.create_physics_queries_demo import GAME as game
    if overlaps:
        from tools.create_physics_overlaps_demo import GAME as game
    bodies={'floor','player','zone'} if events else {'floor','player'}
    artifacts=ROOT/'artifacts/validation'/name; artifacts.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('physics-'+uuid.uuid4().hex[:10]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/game/'slot-736c6f742d31.json'
    try:
        check('Native runtime matches sources',current(ROOT/'build/node_view.exe'))
        for file in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/file,package/file)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        states={}; images={}
        def launch(label,mode,exe,store,frames,keys=(),dt=None):
            prefix=artifacts/(label+'-'+mode)
            save_json(package/'keys.json',dict(version=1,events=[dict(frame=f,button=k,down=v) for f,k,v in sorted(keys)]))
            save_json(package/'ui.json',dict(version=1,events=[dict(frame=0,type='clear')]))
            args=[str(package/exe),'--frames',str(frames),'--save-root',str(store),'--output',str(prefix.with_suffix('.json')),
                  '--input-replay','keys.json','--ui-replay','ui.json']
            if 'preview' in mode: args+=['--ir','game.ir.json']
            if mode.startswith('view'): args+=['--capture',str(prefix.with_suffix('.bmp'))]
            if dt is not None: args+=['--dt',str(dt)]
            result=subprocess.run(args,cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
            prefix.with_suffix('.log').write_text(result.stdout+result.stderr,'utf-8')
            check(label+': '+mode+' exits successfully',result.returncode==0)
            state=json.loads(prefix.with_suffix('.json').read_text('utf-8')); states.setdefault(label,[]).append(state)
            if mode.startswith('view'): images.setdefault(label,[]).append(prefix.with_suffix('.bmp').read_bytes())
            return state
        keys=[(0,'D',True),(20,'D',False),(5,'Space',True),(6,'Space',False),(59,'S',True),(60,'S',False),(75,'Space',True),(76,'Space',False)]
        for mode,exe in modes:
            if overlaps:
                for label,frames,inputs,expected in [
                    ('inside-regions',2,(),{'box':['player','zone'],'capsule':[]}),
                    ('leave-regions',180,[(0,'D',True)],{'box':['zone'],'capsule':[]}),
                    ('return-regions',240,[(0,'D',True),(180,'D',False),(181,'R',True),(182,'R',False)],
                     {'box':['player','zone'],'capsule':['player']}),
                ]:
                    region=launch(label,mode,exe,workspace/label/mode,frames,inputs)
                    for key,entities in expected.items():
                        check(mode+': '+label+' '+key+' array and HUD match the region contents',
                              region['variables'][key+'_overlaps']['value']==entities and
                              region['ui']['widgets']['hud']['elements'][key+'_overlap']['text']==key.title()+f' overlap: {len(entities)} bodies')
            saved_store=workspace/'saved'/mode
            saved=launch('save',mode,exe,saved_store,60,keys)
            raw=slot(saved_store).read_bytes(); record=json.loads(raw)['checkpoint']['physics']
            check(mode+': graph creates and advances its rigid bodies',set(saved['physics']['bodies'])==bodies and saved['physics']['ticks']==60 and saved['variables']['fixed_steps']==60)
            check(mode+': physics changes scene transforms',saved['entities']['player']['position'][0]>.5 and saved['entities']['player']['position'][1]<3)
            if queries:
                for key,extent in [('ray',0),('sphere',.25),('box',.5),('capsule',.7)]:
                    v=saved['variables']; distance=v[key+'_origin']['value'][1]-extent
                    normal=v[key+'_normal']['value']; point=v[key+'_point']['value']
                    check(mode+': '+key+' reports six geometrically correct outputs and updates the HUD',
                          v[key+'_hit']['value'] and v[key+'_entity']['value']=='floor' and
                          abs(point[1])<1e-4 and all(abs(a-b)<1e-4 for a,b in zip(normal,[0,1,0])) and
                          abs(v[key+'_distance']-distance)<1e-4 and abs(v[key+'_fraction']-distance/10)<1e-4 and
                          key.title()+' hit: ' in saved['ui']['widgets']['hud']['elements'][key]['text'])
            check(mode+': save contains native state and all scene bindings',record['ticks']==60 and set(record['bindings'])==bodies and len(record['world']['bodies'])==len(bodies))
            if authoring:
                authored={e['id']:e['rigid_body'] for e in saved['scene']['entities'] if e.get('rigid_body')}
                check(mode+': scene snapshot retains all authored colliders and the robot prefab',
                      set(authored)==bodies and authored['zone']['sensor'] and
                      saved['scene']['prefab_instances'][0]['mapping']['root']=='player')
            reference=launch('reference',mode,exe,workspace/'reference'/mode,90,keys)
            restored=launch('restored',mode,exe,saved_store,30,keys)
            check(mode+': fresh-process continuation matches uninterrupted game exactly',restored==reference)
            check(mode+': load preserves saved bytes',slot(saved_store).read_bytes()==raw)
            if events:
                check(mode+': real collision and trigger handlers update the HUD',
                      reference['variables']['collision_enter']>=1 and saved['variables']['trigger_enter']>=1 and
                      reference['variables']['trigger_exit']>=1 and
                      'floor' in reference['ui']['widgets']['hud']['elements']['collision']['text'])
                contact=(saved_store/game/('slot-'+b'first-contact'.hex()+'.json')).read_bytes()
                checkpoint=json.loads(contact)['checkpoint']; cut=checkpoint['clock']['frame']
                check(mode+': contact callback saves only after completing the physics step',
                      0<cut<90 and checkpoint['physics']['ticks']==cut and checkpoint['events']['queue']==[] and
                      checkpoint['scene']['variables']['collision_enter']==1)
                contact_store=workspace/'contact-resume'/mode; slot(contact_store).parent.mkdir(parents=True)
                (slot(contact_store).parent/('slot-'+b'first-contact'.hex()+'.json')).write_bytes(contact)
                resumed=launch('contact-restored',mode,exe,contact_store,90-cut+1,keys+[(0,'C',True),(1,'C',False)])
                check(mode+': collision-triggered checkpoint resumes without replaying enter',resumed==reference)
                bad=json.loads(raw)
                next(s for s in bad['checkpoint']['events']['subscriptions'] if s['event']==1011)['enabled']=False
                slot(saved_store).write_bytes(json.dumps(bad).encode())
                rejected=launch('invalid-subscription',mode,exe,saved_store,1)
                check(mode+': corrupted physics listener is rejected before commit',
                      rejected['frame']==1 and not rejected['persistence']['success'] and
                      'physics subscription' in rejected['persistence']['error'])
            damaged=json.loads(raw); damaged['checkpoint']['physics']['bindings']['player']['radius']=-1
            corrupt=json.dumps(damaged).encode(); slot(saved_store).write_bytes(corrupt)
            failed=launch('failed-load',mode,exe,saved_store,1)
            check(mode+': invalid physics binding rolls back the running game',failed['frame']==1 and failed['physics']['ticks']==1 and failed['variables']['fixed_steps']==1 and not failed['persistence']['success'] and slot(saved_store).read_bytes()==corrupt)
            if mode.startswith('headless'):
                partial_keys=[(3,'S',True),(4,'S',False)]
                store=workspace/'partial'/mode
                partial=launch('partial-save',mode,exe,store,4,partial_keys,.005)
                record=json.loads(slot(store).read_bytes())['checkpoint']['physics']
                check(mode+': checkpoint captures a fractional physics step',record['ticks']==1 and 0<record['remainder']<1/60)
                reference=launch('partial-reference',mode,exe,workspace/'partial-reference'/mode,15,partial_keys,.005)
                restored=launch('partial-restored',mode,exe,store,11,partial_keys,.005)
                check(mode+': fractional-step restore preserves exact future motion',restored==reference)
        for label,group in states.items():
            check(label+': interpreted/generated state is identical',len({json.dumps(s,sort_keys=True) for s in group})==1)
            if label in images: check(label+': interpreted/generated GPU images are identical',len(set(images[label]))==1)
        check('Sources remain unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally: save_json(artifacts.parent/(name+'-checks.json'),report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--events',action='store_true')
    parser.add_argument('--authoring',action='store_true')
    parser.add_argument('--queries',action='store_true')
    parser.add_argument('--overlaps',action='store_true')
    args=parser.parse_args(); print(f"Physics scene: {len(verify(args.events,args.authoring,args.queries,args.overlaps)['checks'])} checks passed.")
