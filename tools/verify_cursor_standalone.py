"""Physical cursor checks in the exported game, without editor IPC."""
import ctypes
from ctypes import wintypes
import hashlib,json,os,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from editor.core.document import save_json
from editor.core.runtime_build import current,fingerprint
from tools.verify_cursor_editor import CursorInfo

def verify():
    out=ROOT/'artifacts/validation/cursor'; out.mkdir(parents=True,exist_ok=True)
    exe=ROOT/'build/node_game_view.exe'; project=ROOT/'examples/cursor_demo'
    report=dict(passed=False,native_fingerprint=fingerprint(),binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),checks=[])
    u=ctypes.windll.user32; process=None
    u.SetForegroundWindow.argtypes=[wintypes.HWND]; u.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
    u.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    def clip():
        rect=wintypes.RECT(); assert u.GetClipCursor(ctypes.byref(rect)); return [rect.left,rect.top,rect.right,rect.bottom]
    def visible():
        info=CursorInfo(); info.cbSize=ctypes.sizeof(info); assert u.GetCursorInfo(ctypes.byref(info)); return bool(info.flags&1)
    baseline=clip()
    def check(label,okay):
        if not okay: raise AssertionError(label)
        report['checks'].append(label); print('PASS '+label,flush=True)
    def wait(predicate,seconds=20):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end: time.sleep(.015)
        if not predicate(): raise RuntimeError('Standalone condition timed out')
    def key(code):
        code=ord(code) if isinstance(code,str) else code
        u.keybd_event(code,0,0,0); time.sleep(.07); u.keybd_event(code,0,2,0); time.sleep(.12)
    def launch(name,extra=()):
        nonlocal process
        messages=[]; lines=[]
        system=Path(os.environ['SystemRoot']); env=dict(os.environ,PATH=str(system/'System32')+os.pathsep+str(system))
        process=subprocess.Popen([str(exe),'--project-root',str(project),*extra],cwd=exe.parent,env=env,
                                 stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        def read():
            for line in process.stdout:
                lines.append(line)
                try: messages.append(json.loads(line))
                except ValueError: pass
        reader=threading.Thread(target=read,daemon=True); reader.start()
        wait(lambda:any(m.get('event')=='window_handle' for m in messages) or process.poll() is not None)
        handles=[m['handle'] for m in messages if m.get('event')=='window_handle']; assert handles,''.join(lines)
        hwnd=handles[-1]; u.SetWindowPos(hwnd,wintypes.HWND(-1),0,0,0,0,3); u.SetForegroundWindow(hwnd)
        rect=wintypes.RECT(); assert u.GetClientRect(hwnd,ctypes.byref(rect)); p=wintypes.POINT(rect.right//2,rect.bottom*3//4)
        assert u.ClientToScreen(hwnd,ctypes.byref(p)); u.SetCursorPos(p.x,p.y); time.sleep(.05)
        u.mouse_event(2,0,0,0,0); time.sleep(.04); u.mouse_event(4,0,0,0,0); time.sleep(.2)
        def finish(close=False):
            if close: u.PostMessageW(hwnd,0x10,0,0)
            process.wait(timeout=20); reader.join(timeout=2)
            (out/(name+'.log')).write_text(''.join(lines),encoding='utf-8')
            check(name+' exits without runtime errors',process.returncode==0 and not any(m.get('event')=='node_error' for m in messages))
        return finish
    try:
        check('Native source and preview build match',current(ROOT/'build/node_view.exe'))
        finish=launch('physical-standalone')
        check('Standalone starts visible and unconfined',visible() and clip()==baseline)
        key('K'); check('Physical K locks and hides exported cursor',not visible() and clip()!=baseline)
        key('V'); check('Visible request stays hidden while locked',not visible() and clip()!=baseline)
        key('U'); check('Unlock restores visible exported cursor',visible() and clip()==baseline)
        key('H'); check('Physical H hides exported cursor',not visible() and clip()==baseline)
        key('K'); key('U'); check('Unlock retains hidden request',not visible() and clip()==baseline)
        key('K'); key(27); check('Standalone Escape graph unlocks and shows cursor',visible() and clip()==baseline)
        key('K'); check('Standalone cursor is locked before close',not visible() and clip()!=baseline)
        finish(close=True); time.sleep(.1); check('Closing exported game restores OS cursor',visible() and clip()==baseline)
        replay=out/'locked-replay.json'; save_json(replay,dict(version=2,events=[dict(frame=0,button='K',down=True),dict(frame=0,button='H',down=True)]))
        state=out/'locked-replay-state.json'
        finish=launch('replay-standalone',['--frames','180','--input-replay',str(replay),'--output',str(state)])
        check('Focused replay does not grab or hide physical cursor',visible() and clip()==baseline)
        finish(); data=json.loads(state.read_text('utf-8'))
        check('Replay still executes locked and hidden logical requests',data['variables']['locked']['value'] and not data['variables']['visible']['value'])
        check('Replay exit leaves OS cursor unchanged',visible() and clip()==baseline)
        check('Sources unchanged during verification',fingerprint()==report['native_fingerprint']); report['passed']=True
    except Exception as error: report['error']=str(error); raise
    finally:
        for code in (27,ord('K'),ord('U'),ord('H'),ord('V')): u.keybd_event(code,0,2,0)
        u.mouse_event(4,0,0,0,0)
        if process is not None and process.poll() is None: process.terminate(); process.wait(timeout=10)
        save_json(ROOT/'artifacts/validation/cursor-standalone-checks.json',report)
    return report

if __name__=='__main__': print('Cursor standalone:',len(verify()['checks']),'checks passed.')
