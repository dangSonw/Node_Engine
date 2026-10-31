"""Real Windows cursor visibility, relative motion and editor lifecycle checks."""
import ctypes
from ctypes import wintypes
import hashlib,json,shutil,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QEvent,QPoint,QSettings,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget
from editor.core.builder import GraphBuilder
from editor.core.document import load_project,save_json
from editor.core.runtime_build import current,fingerprint
from editor.ui.main_window import MainWindow

class CursorInfo(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('flags',wintypes.DWORD),('hCursor',wintypes.HANDLE),('position',wintypes.POINT)]

def verify():
    directory=ROOT/'.cache'/('cursor-editor-'+uuid.uuid4().hex[:8])
    shutil.copytree(ROOT/'examples/cursor_demo',directory,ignore=shutil.ignore_patterns('build','generated'))
    b=GraphBuilder(); b.graph=json.loads((directory/'graphs/gameplay.json').read_text('utf-8'))
    for node in b.graph['nodes']:
        if node['id']=='storage': node['values']['Game ID']='cursor-editor-'+uuid.uuid4().hex
    b.add('error_key','On Key Pressed',Filter='F1'); b.add('deliberate_error','Assert',Condition=False,Message='Cursor recovery test')
    b.connect('error_key','Out','deliberate_error','In'); save_json(directory/'graphs/gameplay.json',b.graph)
    scene=json.loads((directory/'scenes/main.json').read_text('utf-8'))
    scene['ui_assets'][0]['rml']=scene['ui_assets'][0]['rml'].replace('</body>',
        '<div style="display:block;position:absolute;left:0px;top:0px;width:100%;height:100%;pointer-events:auto;"></div></body>')
    save_json(directory/'scenes/main.json',scene)
    app=QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
    window=MainWindow(directory/'project.json',QSettings(str(directory/'layout.ini'),QSettings.IniFormat)); window.resize(1600,960); window.show()
    messages=[]; window.runtime.message.connect(messages.append)
    report=dict(passed=False,native_fingerprint=fingerprint(),checks=[],project=str(directory)); popup=None
    u=ctypes.windll.user32
    u.SetForegroundWindow.argtypes=[wintypes.HWND]; u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    u.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,seconds=35):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end: QTest.qWait(15)
        if not predicate(): raise RuntimeError(window.console.toPlainText())
    def command(name):
        begin=len(messages); serial=window.runtime.send(name)
        wait(lambda:any(m.get('id')==serial and m.get('event') in ('ack','node_error') for m in messages[begin:]))
        result=messages[begin:]; check('Preview '+name,not any(m.get('event')=='node_error' for m in result)); return result
    def snapshot(): return next(m['state'] for m in command('snapshot') if m.get('event')=='snapshot')
    def status(): return next(m for m in command('cursor_status') if m.get('event')=='cursor_status')
    def visible():
        info=CursorInfo(); info.cbSize=ctypes.sizeof(info); assert u.GetCursorInfo(ctypes.byref(info)); return bool(info.flags&1)
    def clip():
        rect=wintypes.RECT(); assert u.GetClipCursor(ctypes.byref(rect)); return [rect.left,rect.top,rect.right,rect.bottom]
    baseline_clip=clip()
    def point(x,y):
        p=wintypes.POINT(x,y); assert u.ClientToScreen(hwnd,ctypes.byref(p)); return p
    def focus():
        command('release_input'); window.raise_(); window.activateWindow(); u.SetForegroundWindow(int(window.winId()))
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-1),0,0,0,0,3)
        p=point(width//2,height*3//4); u.SetCursorPos(p.x,p.y); QTest.qWait(30)
        u.mouse_event(2,0,0,0,0); QTest.qWait(40); u.mouse_event(4,0,0,0,0); QTest.qWait(120)
        s=status(); check('Native viewport focused and explicitly reclaimed',s['focused'] and not s['released'])
    def key(code):
        if isinstance(code,str): code=ord(code)
        u.keybd_event(code,0,0,0); QTest.qWait(100); u.keybd_event(code,0,2,0); QTest.qWait(130)
    def require_mode(label,locked,shown,requested_lock=None,requested_visible=None):
        s=status(); report.setdefault('modes',[]).append(dict(label=label,status=s,windows_visible=visible(),clip=clip()))
        check(label,s['relative']==locked and s['visible']==shown and visible()==shown and
              (requested_lock is None or s['requested_locked']==requested_lock) and (requested_visible is None or s['requested_visible']==requested_visible))
    try:
        check('Native sources match build',current(ROOT/'build/node_view.exe'))
        for type_id,name,port in [(10016,'Set Cursor Visible','Visible'),(10017,'Lock Cursor','Locked')]:
            window.library_search.setText(name); QTest.qWait(50); library=window.library_tree
            item=next(library.topLevelItem(i).child(j) for i in range(library.topLevelItemCount()) for j in range(library.topLevelItem(i).childCount())
                      if library.topLevelItem(i).child(j).data(0,Qt.ItemDataRole.UserRole)==type_id)
            library.scrollToItem(item); before=len(window.adapter.graph.all_nodes())
            QTest.mouseClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            QTest.mouseDClick(library.viewport(),Qt.MouseButton.LeftButton,pos=library.visualItemRect(item).center())
            check(name+' is created from Library',len(window.adapter.graph.all_nodes())==before+1)
            created=next(n for n in window.adapter.graph.selected_nodes() if n.get_property('type_id')==type_id)
            check(name+' exposes exec and boolean ports',set(created.inputs())=={'In',port} and set(created.outputs())=={'Out'})
            window.actions['Undo'].trigger(); check(name+' Undo',len(window.adapter.graph.all_nodes())==before)
            window.actions['Redo'].trigger(); check(name+' Redo',len(window.adapter.graph.all_nodes())==before+1); window.actions['Undo'].trigger()
        window.library_search.clear(); check('Cursor graph saves/reopens',window.save_project() and load_project(directory/'project.json')[1]==window.adapter.document())
        window.actions['Play'].trigger(); wait(lambda:window.runtime.ready and window.runtime.state=='running' and window.container is not None)
        hwnd=next(m['handle'] for m in reversed(messages) if m.get('event')=='window_handle')
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); width,height=rect.right,rect.bottom
        focus(); command('stop'); command('play'); require_mode('Fresh Play leaves cursor visible/unlocked',False,True,False,True)
        key('H'); require_mode('Hide affects the physical cursor',False,False,False,False)
        local=window.hierarchy.viewport().mapTo(window,QPoint(30,30)); ratio=window.devicePixelRatioF()
        p=wintypes.POINT(round(local.x()*ratio),round(local.y()*ratio)); u.ClientToScreen(int(window.winId()),ctypes.byref(p)); u.SetCursorPos(p.x,p.y); QTest.qWait(130)
        require_mode('Hidden gameplay cursor remains visible over Qt',False,True,False,False)
        p=point(width//2,height*3//4); u.SetCursorPos(p.x,p.y); QTest.qWait(130); require_mode('Returning to viewport restores hidden request',False,False,False,False)
        key('V'); require_mode('Show restores the physical cursor',False,True,False,True)
        key('K'); require_mode('Lock enables real relative mode and hides cursor',True,False,True,True)
        a=point(0,0); z=point(width,height); bounds=clip()
        report['confinement']={'initial':baseline_clip,'client':[a.x,a.y,z.x,z.y],'actual':bounds}
        check('Windows confines the cursor inside the viewport',bounds!=baseline_clip and bounds[0]>=a.x and bounds[1]>=a.y and bounds[2]<=z.x and bounds[3]<=z.y)
        before=snapshot()
        for _ in range(4): u.mouse_event(1,width,30,0,0); QTest.qWait(80)
        moved=snapshot(); dx=moved['variables']['total_delta']['value'][0]-before['variables']['total_delta']['value'][0]
        report['relative_motion']={'before':before['variables'],'after':moved['variables'],'width':width,'dx':dx}
        check('Relative motion continues past screen edges and bypasses pointer UI',dx>width*2 and moved['variables']['position']==before['variables']['position'] and moved['entities']['player']['rotation']!=before['entities']['player']['rotation'])
        key('V'); require_mode('Show request does not expose the locked cursor',True,False,True,True)
        key('U'); require_mode('Unlock restores requested visibility',False,True,False,True)
        key('H'); key('K'); key('U'); require_mode('Unlock preserves an explicit hidden request',False,False,False,False)
        key('V'); key('K'); command('pause'); require_mode('Pause releases the OS cursor but keeps intent',False,True,True,True)
        check('Pause removes Windows confinement',clip()==baseline_clip)
        command('play'); require_mode('Resume restores focused lock',True,False,True,True)
        key('S'); saved=snapshot(); check('Physical save succeeds while locked',saved['persistence']['success'])
        key('U'); key('H'); key('L'); loaded=snapshot(); require_mode('Load restores locked/visible requests',True,False,True,True)
        check('Load restores saved pose and logical mode variables',loaded['entities']==saved['entities'] and loaded['variables']['locked']==saved['variables']['locked'] and loaded['variables']['visible']==saved['variables']['visible'])
        key(27); require_mode('Editor Escape releases cursor without losing intent',False,True,True,True)
        check('Escape removes Windows confinement',clip()==baseline_clip and status()['released'])
        focus(); require_mode('Explicit viewport click reclaims requested lock',True,False,True,True)
        popup=QWidget(); popup.setWindowTitle('Cursor focus test'); popup.resize(300,120); popup.show(); popup.raise_(); popup.activateWindow(); u.SetForegroundWindow(int(popup.winId())); QTest.qWait(180)
        require_mode('Other-window focus releases cursor',False,True,True,True); check('Focus loss removes confinement',clip()==baseline_clip)
        popup.close(); popup=None; focus(); require_mode('Refocus restores lock',True,False,True,True)
        begin=len(messages); key(0x70); wait(lambda:any(m.get('event')=='node_error' and m.get('node')=='deliberate_error' for m in messages[begin:]))
        require_mode('Graph failure releases cursor while preserving requested state',False,True,True,True)
        check('Graph failure leaves no Windows confinement',clip()==baseline_clip)
        command('stop'); require_mode('Stop resets cursor intent',False,True,False,True)
        command('play'); focus(); key('K'); require_mode('Fresh session can lock again after error',True,False,True,True)
        command('pause'); window.adapter.clear_selection(); node=next(n for n in window.adapter.graph.all_nodes() if n.get_property('stable_id')=='cursor_K')
        node.set_selected(True); window.inspect_node(node); window.adapter.graph.reset_zoom(); window.adapter.graph.center_on([node]); QTest.qWait(80)
        capture=ROOT/'artifacts/validation/cursor-editor.png'; check('Editor screenshot saved',window.screen().grabWindow(int(window.winId())).save(str(capture)))
        report['screenshot_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        command('play'); focus(); require_mode('Cursor locked before shutdown',True,False,True,True)
        command('quit'); wait(lambda:not window.runtime.ready); QTest.qWait(100)
        check('Shutdown restores visible unconfined cursor',visible() and clip()==baseline_clip)
        check('Native sources unchanged',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error:
        report['error']=str(error); report['messages']=messages[-80:]; report['console']=window.console.toPlainText()
        window.screen().grabWindow(int(window.winId())).save(str(ROOT/'artifacts/validation/cursor-editor-failure.png')); raise
    finally:
        u.keybd_event(27,0,0,0); u.keybd_event(27,0,2,0)
        for code in [ord(c) for c in 'H V K U S L'.replace(' ','')]+[0x70]: u.keybd_event(code,0,2,0)
        u.mouse_event(4,0,0,0,0)
        if popup is not None: popup.close()
        if window.runtime.ready: window.runtime.send('quit'); QTest.qWait(150)
        u.SetWindowPos(int(window.winId()),wintypes.HWND(-2),0,0,0,0,3)
        window.saved_signature=window.signature(); window.document_changed(); window.close()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete); app.processEvents()
        save_json(ROOT/'artifacts/validation/cursor-editor-checks.json',report)
    return report

if __name__=='__main__': print('Cursor editor:',len(verify()['checks']),'checks passed.')
