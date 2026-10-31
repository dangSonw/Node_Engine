"""Verify playable characters and exact game restoration in four relocated native hosts."""
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
from tools.create_character_demo import GAME


def verify(events=False):
    name='character-events' if events else 'character-scene'
    game=GAME
    if events:
        from tools.create_character_events_demo import GAME as game
    artifacts=ROOT/'artifacts/validation'/name; artifacts.mkdir(parents=True,exist_ok=True)
    workspace=ROOT/'.cache'/('character-'+uuid.uuid4().hex[:10]); package=workspace/'Trò chơi'; package.mkdir(parents=True)
    project=ROOT/'examples'/('character_events_demo' if events else 'character_demo')
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],package=str(package))
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def slot(store): return store/game/'slot-736c6f742d31.json'
    states={}; images={}
    try:
        check('Native runtime matches sources',current(ROOT/'build/node_view.exe'))
        for file in ('node_preview.exe','node_game.exe','node_view.exe','node_game_view.exe','SDL3.dll','SDL3_image.dll','SDL3_mixer.dll'):
            shutil.copy2(ROOT/'build'/file,package/file)
        for folder in ('fonts','licenses','shaders'): shutil.copytree(ROOT/'build'/folder,package/folder)
        shutil.copytree(project/'assets',package/'assets')
        shutil.copy2(project/'generated/game.ir.json',package/'game.ir.json')
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
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
        modes=[('headless-preview','node_preview.exe'),('headless-compiled','node_game.exe'),('view-preview','node_view.exe'),('view-compiled','node_game_view.exe')]
        crouch_keys=[(40,'C',True),(41,'C',False),(45,'W',True),(100,'W',False),(105,'V',True),(106,'V',False),(110,'S',True),(111,'S',False)]
        jump_keys=[(90,'Space',True),(91,'Space',False),(94,'S',True),(95,'S',False)]
        for mode,exe in modes:
            settled=launch('settled',mode,exe,workspace/'settled'/mode,90)
            body=settled['physics']['bodies']['player']
            check(mode+': authored capsule lands and ground HUD names the native state',
                body['character']['grounded'] and body['character']['ground_entity']=='floor' and .84<body['position'][1]<.9 and
                settled['ui']['widgets']['hud']['elements']['ground']['text']=='Ground: on_ground')
            if events:
                values=settled['variables']
                check(mode+': character delivers one solid and trigger Enter with persistent Stay',
                    values['collision_enter']==1 and values['trigger_enter']==1 and values['collision_stay']>30 and values['trigger_stay']>60 and
                    values['collision_exit']==0 and values['trigger_exit']==0 and values['collision_normal']['value'][1]<-.9 and
                    settled['ui']['widgets']['hud']['elements']['collision']['text']=='Collision stay: floor' and
                    settled['ui']['widgets']['hud']['elements']['trigger']['text']=='Trigger stay: zone')
                contact_path=workspace/'settled'/mode/game/('slot-'+b'first-contact'.hex()+'.json')
                raw=contact_path.read_bytes(); checkpoint=json.loads(raw)['checkpoint']; cut=checkpoint['clock']['frame']
                check(mode+': landing callback saves after its complete physics step',
                    0<cut<90 and checkpoint['physics']['ticks']==cut and checkpoint['events']['queue']==[] and
                    checkpoint['scene']['variables']['collision_enter']==1 and checkpoint['scene']['variables']['contact_saved']['value'])
                store=workspace/'contact-resume'/mode; saved=store/game/contact_path.name; saved.parent.mkdir(parents=True); saved.write_bytes(raw)
                resumed=launch('contact-restored',mode,exe,store,90-cut+1,[(0,'K',True),(1,'K',False)])
                check(mode+': collision-triggered save resumes without replaying Enter',resumed==settled and saved.read_bytes()==raw)
            wall=launch('wall',mode,exe,workspace/'wall'/mode,120,[(40,'D',True)])
            check(mode+': movement stops at the wall',2.3<wall['physics']['bodies']['player']['position'][0]<2.6)
            if events:
                check(mode+': wall collision and leaving the center trigger reach the HUD',
                    wall['variables']['collision_enter']==2 and wall['variables']['trigger_exit']==1 and
                    wall['ui']['widgets']['hud']['elements']['collision']['text']=='Collision stay: wall' and
                    wall['ui']['widgets']['hud']['elements']['trigger']['text']=='Trigger exit: zone')
            step=launch('step',mode,exe,workspace/'step'/mode,80,[(40,'A',True)])
            body=step['physics']['bodies']['player']
            check(mode+': character climbs the low step',body['position'][0]<-1.8 and body['position'][1]>1 and body['character']['grounded'])
            blocked=launch('standing-roof',mode,exe,workspace/'standing-roof'/mode,120,[(45,'W',True),(100,'W',False)])
            # The rounded capsule top can approach the roof edge more closely than a box.
            check(mode+': standing capsule cannot enter the low roof',-1.85<blocked['physics']['bodies']['player']['position'][2]<-1.4)
            for label,cut,total,keys in [('crouched',111,135,crouch_keys),('midair',95,125,jump_keys)]:
                store=workspace/label/mode
                saved=launch(label+'-save',mode,exe,store,cut,keys)
                raw=slot(store).read_bytes(); checkpoint=json.loads(raw)['checkpoint']
                world=checkpoint['physics']['world']; body=saved['physics']['bodies']['player']
                check(mode+': '+label+' checkpoint includes controller and scene binding',
                    world['version']==2 and set(world['characters'])=={'player'} and 'player' in checkpoint['physics']['bindings'])
                if label=='crouched':
                    check(mode+': crouch passes under roof and obstructed standing preserves body and mesh',
                        body['position'][2]<-2.6 and body['character']['half_height']==.2 and
                        saved['entities']['robot_mesh']['scale'][1]==1.1/1.7 and
                        saved['ui']['widgets']['hud']['elements']['posture']['text']=='Posture: crouching')
                else:
                    check(mode+': jump is airborne when saved',body['position'][1]>1.1 and not body['character']['grounded'])
                reference=launch(label+'-reference',mode,exe,workspace/(label+'-reference')/mode,total,keys)
                resumed=launch(label+'-restored',mode,exe,store,total-cut,keys)
                check(mode+': '+label+' fresh-process continuation matches complete game state',resumed==reference)
                check(mode+': '+label+' restoration preserves saved bytes',slot(store).read_bytes()==raw)
                damaged=json.loads(raw); damaged['checkpoint']['physics']['world']['characters']['player']['desired']=[0,1,0]
                corrupt=json.dumps(damaged).encode(); slot(store).write_bytes(corrupt)
                failed=launch(label+'-invalid',mode,exe,store,1)
                check(mode+': '+label+' malformed character load leaves initial game running',
                    failed['frame']==1 and failed['physics']['ticks']==1 and not failed['persistence']['success'] and
                    failed['physics']['bodies']['player']['character']['half_height']==.5 and slot(store).read_bytes()==corrupt)
                if label=='crouched':
                    damaged=json.loads(raw); damaged['checkpoint']['physics']['bindings']['player']['radius']=.7
                    corrupt=json.dumps(damaged).encode(); slot(store).write_bytes(corrupt)
                    failed=launch('inconsistent-binding',mode,exe,store,1)
                    check(mode+': valid but inconsistent character binding is rejected before commit',
                        failed['frame']==1 and not failed['persistence']['success'] and
                        'disagrees with scene dimensions' in failed['persistence']['error'] and
                        failed['physics']['bodies']['player']['character']['radius']==.35 and slot(store).read_bytes()==corrupt)
            if mode.startswith('headless'):
                keys=[(3,'S',True),(4,'S',False)]; store=workspace/'partial'/mode
                launch('partial-save',mode,exe,store,4,keys,.005)
                checkpoint=json.loads(slot(store).read_bytes())['checkpoint']['physics']
                check(mode+': fractional character physics step is saved',checkpoint['ticks']==1 and 0<checkpoint['remainder']<1/60)
                reference=launch('partial-reference',mode,exe,workspace/'partial-reference'/mode,15,keys,.005)
                resumed=launch('partial-restored',mode,exe,store,11,keys,.005)
                check(mode+': fractional character step resumes exactly',resumed==reference)
        for label,group in states.items():
            check(label+': interpreted/generated full state is identical',len({json.dumps(s,sort_keys=True) for s in group})==1)
            if label in images: check(label+': interpreted/generated GPU images are identical',len(set(images[label]))==1)
        check('Sources remain unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally: save_json(artifacts.parent/(name+'-checks.json'),report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--events',action='store_true')
    print(f"Character scene: {len(verify(parser.parse_args().events)['checks'])} checks passed.")
