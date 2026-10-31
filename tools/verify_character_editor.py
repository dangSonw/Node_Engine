"""Exercise Character Inspector, graph authoring and physical input in the actual editor."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
import argparse
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QSettings,Qt,QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialogButtonBox,QPushButton
from editor.ui.physics import RigidBodyDialog
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow
from tools.verify_physics_editor import GuiInfo


def verify(events=False):
    name='character-events-editor' if events else 'character-editor'
    directory=ROOT/'.cache'/('character-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples'/('character_events_demo' if events else 'character_demo'),directory,ignore=shutil.ignore_patterns('build','generated'))
    graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='character-editor-'+uuid.uuid4().hex
    save_json(directory/'graphs/gameplay.json',graph)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[])
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat))
    window.resize(1600,960); window.show(); messages=[]; window.runtime.message.connect(messages.append)
    user32=ctypes.windll.user32; user32.GetForegroundWindow.restype=wintypes.HWND
    user32.SetForegroundWindow.argtypes=[wintypes.HWND]; user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    def check(label,ok):
        if not ok: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,timeout=40):
        deadline=time.monotonic()+timeout
        while not predicate() and time.monotonic()<deadline: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText()+'\n'+window.build_output.toPlainText())
    def command(name,**data):
        begin=len(messages); serial=window.runtime.send(name,**data)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]
        check('Preview command '+name+' succeeds',not any(m.get('event')=='node_error' for m in result))
        return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m['event']=='snapshot')
    def key(code,duration=80):
        user32.keybd_event(code,0,0,0); QTest.qWait(duration); user32.keybd_event(code,0,2,0)
    try:
        check('Native runtime is current',current(ROOT/'build/node_view.exe'))
        before=json.loads(json.dumps(window.scene)); errors=[]
        def edit():
            try:
                dialog=QApplication.activeModalWidget()
                check('Inspector exposes authored character configuration',isinstance(dialog,RigidBodyDialog) and dialog.character.isChecked())
                buttons=dialog.findChild(QDialogButtonBox); dialog.character_fields['max_slope'].setText('90')
                QTest.mouseClick(buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
                check('Invalid character slope keeps dialog open and scene unchanged',dialog.isVisible() and bool(dialog.error.text()) and window.scene==before)
                dialog.character_fields['max_slope'].setText('40'); dialog.character_fields['step_height'].setText('.4')
                check('Character Inspector screenshot is saved',dialog.grab().save(str(ROOT/'artifacts/validation'/(name+'-dialog.png'))))
                QTest.mouseClick(buttons.button(QDialogButtonBox.Ok),Qt.LeftButton)
            except Exception as error:
                errors.append(error)
                if QApplication.activeModalWidget(): QApplication.activeModalWidget().reject()
        window.refresh_hierarchy('player'); QTimer.singleShot(80,edit)
        button=next(w for w in window.findChildren(QPushButton) if w.accessibleName()=='player rigid body settings')
        QTest.mouseClick(button,Qt.LeftButton)
        if errors: raise errors[0]
        edited=json.loads(json.dumps(window.scene))
        check('Character edit is one inherited collider override',
            next(e for e in edited['entities'] if e['id']=='player')['rigid_body']['character']['step_height']==.4 and
            'rigid_body' in edited['prefab_instances'][0]['owned_components']['root'])
        window.actions['Undo'].trigger(); check('Undo restores character settings and prefab ownership',window.scene==before)
        window.actions['Redo'].trigger(); check('Redo restores exact character settings',window.scene==edited)
        window.actions['Undo'].trigger()
        event=window.adapter.add(1002); query=window.adapter.add(12008)
        event.outputs()['Out'].connect_to(query.inputs()['In']); last=query
        for port,label in [('Grounded','Boolean'),('State','String'),('Entity','Entity'),('Point','Vector3'),('Normal','Vector3'),('Velocity','Vector3')]:
            setter=window.adapter.add(window.adapter.registry.by_name('Set '+label+' Variable').id)
            setter.set_property('value_Name','gui_ground_'+port.lower())
            last.outputs()['Out'].connect_to(setter.inputs()['In']); query.outputs()[port].connect_to(setter.inputs()['Value']); last=setter
        connected=window.adapter.document(); window.actions['Undo'].trigger()
        check('Undo removes a typed ground output connection',window.adapter.document()!=connected)
        window.actions['Redo'].trigger(); check('Redo restores typed ground output connection',window.adapter.document()==connected)
        event=window.adapter.add(1001); config=window.adapter.add(12007)
        config.set_property('value_Max Slope',35.); event.outputs()['Out'].connect_to(config.inputs()['In'])
        check('Character graph validates and saves',window.validate_graph() and window.save_project())
        reopened=load_project(directory/'project.json')
        check('Saved graph and character scene reopen exactly',reopened[1]==window.adapter.document() and reopened[2]==window.scene)
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        QTest.qWait(1100); command('pause'); first=snapshot()
        check('Embedded character lands and Configure Character runs',first['physics']['bodies']['player']['character']['grounded'] and
            first['physics']['bodies']['player']['character']['max_slope']==35.)
        if events:
            check('Character landing and trigger callbacks update the embedded HUD',
                first['variables']['collision_enter']==1 and first['variables']['trigger_enter']==1 and
                first['variables']['collision_stay']>0 and first['variables']['trigger_stay']>0 and
                first['ui']['widgets']['hud']['elements']['collision']['text']=='Collision stay: floor' and
                first['ui']['widgets']['hud']['elements']['trigger']['text']=='Trigger stay: zone')
        check('Editor-authored ground outputs execute with correct types',first['variables']['gui_ground_grounded']['value'] and
            first['variables']['gui_ground_entity']['value']=='floor' and first['variables']['gui_ground_normal']['value']==[0,1,0])
        QTest.qWait(150); check('Pause freezes character, input and accumulator',snapshot()==first)
        command('play'); window.raise_(); window.activateWindow(); user32.SetForegroundWindow(int(window.winId()))
        wait(lambda:user32.GetForegroundWindow()==int(window.winId()))
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert user32.GetWindowRect(hwnd,ctypes.byref(rect))
        user32.SetCursorPos((rect.left+rect.right)//2,(rect.top+rect.bottom)//2)
        user32.mouse_event(2,0,0,0,0); user32.mouse_event(4,0,0,0,0); QTest.qWait(80)
        focus=GuiInfo(); focus.cbSize=ctypes.sizeof(focus)
        check('Click focuses embedded SDL viewport',bool(user32.GetGUIThreadInfo(0,ctypes.byref(focus))) and focus.focus==hwnd)
        before=snapshot(); key(ord('D'),300); command('pause'); moved=snapshot()
        check('Physical D key moves the visible character',moved['entities']['player']['position'][0]>before['entities']['player']['position'][0]+.5)
        report['keyboard_motion']={'before':before['entities']['player']['position'],'after':moved['entities']['player']['position'],
            'ticks':moved['physics']['ticks']-before['physics']['ticks']}
        command('play'); key(ord('C')); command('pause'); crouched=snapshot()
        check('Physical C crouches capsule and visible mesh together',crouched['physics']['bodies']['player']['character']['half_height']==.2 and
            crouched['entities']['robot_mesh']['scale'][1]==1.1/1.7)
        command('play'); key(ord('V')); key(0x20); QTest.qWait(80); command('pause'); jumped=snapshot()
        check('Physical V stands and Space jumps',jumped['physics']['bodies']['player']['character']['half_height']==.5 and
            jumped['entities']['player']['position'][1]>1.2 and not jumped['physics']['bodies']['player']['character']['grounded'])
        if events:
            check('Physical jump delivers floor Exit while the center trigger remains active',
                jumped['variables']['collision_exit']==1 and jumped['variables']['trigger_exit']==0 and
                jumped['ui']['widgets']['hud']['elements']['collision']['text']=='Collision exit: floor')
        check('Actual editor screenshot is saved',window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation'/(name+'.png'))))
        command('stop'); stopped=snapshot()
        check('Stop restores authored character dimensions and pose',stopped['physics']['ticks']==0 and stopped['entities']['player']['position']==[0,2,0] and
            stopped['physics']['bodies']['player']['character']['half_height']==.5 and stopped['physics']['bodies']['player']['character']['max_slope']==45)
        command('play'); QTest.qWait(80); command('pause')
        check('Restart recreates exactly one character',sum('character' in b for b in snapshot()['physics']['bodies'].values())==1)
        check('Sources remain unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); raise
    finally:
        for code in (ord('D'),ord('C'),ord('V'),0x20): user32.keybd_event(code,0,2,0)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation'/(name+'-checks.json'),report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--events',action='store_true')
    print(f"Character editor: {len(verify(parser.parse_args().events)['checks'])} checks passed.")
