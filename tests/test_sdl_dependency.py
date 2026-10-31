"""The pinned SDL child-window focus adapter must reproduce and reject drift."""
import hashlib,shutil,subprocess
from pathlib import Path
from editor.core.registry import ROOT

def test_sdl_embedded_focus_adapter_is_exact_idempotent_and_rejects_unknown_source(tmp_path):
    cmake=shutil.which('cmake') or str(Path.home()/'.local/bin/cmake.exe')
    relative=Path('src/video/windows/SDL_windowsevents.c'); path=tmp_path/relative; path.parent.mkdir(parents=True)
    data=(ROOT/'deps/SDL3-source-3.4.18/SDL3-3.4.18'/relative).read_bytes()
    if hashlib.sha256(data).hexdigest()=='e68e1280186fe436be89ffcf69ac01b8d9cb8ca738caae48d320f9c3cfd69ae4':
        adapter=b'''    // Node_Engine: Qt embeds this native window under a foreign top-level HWND.
    HWND foreground = GetForegroundWindow();
    bool has_focus = (foreground == hwnd) ||
        ((GetWindowLongPtr(hwnd, GWL_STYLE) & WS_CHILD) && GetFocus() == hwnd &&
         GetAncestor(hwnd, GA_ROOT) == foreground);'''
        data=data.replace(adapter,b'    bool has_focus = (GetForegroundWindow() == hwnd);')
    assert hashlib.sha256(data).hexdigest()=='e18c859aec38e658f0c44a986c4ff19a5eb0ca82b6c274013ee18d5f5d602b7e'
    path.write_bytes(data)
    script=tmp_path/'check.cmake'; script.write_text(f'include("{(ROOT/"cmake/PatchSdlEmbeddedFocus.cmake").as_posix()}")\nnode_engine_patch_sdl_embedded_focus("{tmp_path.as_posix()}")\n',encoding='utf-8')
    def run(): return subprocess.run([cmake,'-P',str(script)],capture_output=True,text=True,encoding='utf-8',timeout=20)
    result=run(); assert result.returncode==0,result.stdout+result.stderr
    patched=path.read_bytes(); assert hashlib.sha256(patched).hexdigest()=='e68e1280186fe436be89ffcf69ac01b8d9cb8ca738caae48d320f9c3cfd69ae4'
    assert run().returncode==0 and path.read_bytes()==patched
    path.write_bytes(patched+b'\n// unexpected source change\n'); before=path.read_bytes(); result=run()
    assert result.returncode!=0 and 'source changed' in result.stderr and path.read_bytes()==before
