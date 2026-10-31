"""Runs outside the GUI process; build output streams through QProcess."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from .core.registry import ROOT
from .core.compiler import compile_graph
from .core.projects import compile_project
from .core.codegen import export, generate_adapters
from .core.document import write_text_if_changed
from .core.runtime_build import fingerprint, record
from .core.assets import model_dependencies
from .core.scene import asset_path


def find_tool(name):
    path = shutil.which(name)
    if path:
        return Path(path)
    local = Path.home() / ".local/bin" / (name + (".exe" if os.name == "nt" else ""))
    if local.exists():
        return local
    if name == "clang++" and os.name == "nt":
        candidates = sorted((Path.home() / "AppData/Local/Programs").glob("llvm-mingw-*/bin/clang++.exe"))
        if candidates:
            return candidates[-1]
    raise RuntimeError(f"Required build tool is missing: {name}")


def stage_assets(project_root,destination,scene=None):
    """Replace the generated asset copy, including files removed from the source."""
    project_root=Path(project_root).resolve(); destination=Path(destination)
    if destination.resolve()!=project_root/'build' or destination.is_symlink():
        raise RuntimeError('Asset staging requires the project build directory')
    target=destination/'assets'
    if target.is_symlink() or target.resolve()!=destination.resolve()/'assets':
        raise RuntimeError('Build assets directory cannot be a link')
    destination=destination.resolve()
    def regular(root,relative):
        asset_path(relative)
        path=root/relative
        for part in (path,*path.parents):
            if part==root: break
            if part.is_symlink() or part.resolve()!=part:
                raise RuntimeError(f'Staged resource cannot be a link: {relative}')
        if path.exists() and not path.is_file():
            raise RuntimeError(f'Staged resource must be a file: {relative}')
        return path
    extra={}
    scene=scene or {}
    documents=scene if isinstance(scene,list) else [scene]
    for descriptor in [part for doc in documents for part in (doc,*doc.get('prefab_templates',[]))]:
        for entity in descriptor.get('entities',[]):
            mesh=entity.get('mesh','')
            if not mesh: continue
            source=regular(project_root,mesh)
            for dependency in model_dependencies(source):
                name=dependency.relative_to(project_root).as_posix()
                regular(project_root,name)
                if not name.startswith('assets/'): extra[name]=dependency
    # Only files recorded by an earlier staging run may be replaced or removed.
    manifest=regular(destination,'.model-assets.json')
    previous=json.loads(manifest.read_text('utf-8')) if manifest.exists() else {}
    if not isinstance(previous,dict): raise RuntimeError('Invalid staged model manifest')
    for name,digest in previous.items():
        path=regular(destination,name)
        if name.startswith('assets/') or not isinstance(digest,str):
            raise RuntimeError('Invalid staged model manifest')
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise RuntimeError(f'Staged model was modified; preserve or move it before rebuilding: {name}')
    for name in extra:
        path=regular(destination,name)
        if name=='.model-assets.json' or (path.exists() and name not in previous):
            raise RuntimeError(f'Model resource conflicts with an existing build file: {name}')
    with tempfile.TemporaryDirectory(prefix='.assets-',dir=destination) as temporary:
        prepared=Path(temporary)/'assets'; source=project_root/'assets'
        if source.is_symlink() or source.resolve()!=source:
            raise RuntimeError('Source assets directory cannot be a link')
        if source.is_dir():
            for entry in source.rglob('*'):
                if entry.is_symlink() or entry.resolve()!=entry:
                    raise RuntimeError('Source assets cannot contain links')
            shutil.copytree(source,prepared)
        staged=Path(temporary)/'models'; hashes={}
        for name,source in extra.items():
            copied=staged/name; copied.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,copied)
            hashes[name]=hashlib.sha256(copied.read_bytes()).hexdigest()
        manifest_copy=Path(temporary)/'manifest.json'
        manifest_copy.write_text(json.dumps(hashes,sort_keys=True),encoding='utf-8')
        if target.exists(): shutil.rmtree(target)
        if prepared.exists(): prepared.replace(target)
        for name in previous.keys()-extra.keys():
            regular(destination,name).unlink(missing_ok=True)
        for name in extra:
            path=regular(destination,name); path.parent.mkdir(parents=True,exist_ok=True)
            (staged/name).replace(path)
        manifest_copy.replace(manifest)


def build(project, request):
    project = Path(project).resolve()
    data = json.loads(Path(request).read_text("utf-8"))
    ir = compile_project(data)
    generated = project.parent / "generated"
    source = export(ir, generated)
    hook_source = generated / 'node-code.generated.cpp'
    hook_hash = hashlib.sha256(hook_source.read_bytes()).hexdigest()
    write_text_if_changed(ROOT / "runtime/generated/adapters.generated.cpp", generate_adapters())
    native_fingerprint = fingerprint()
    destination = project.parent / "build"
    cmake, ninja, compiler = [find_tool(n) for n in ("cmake", "ninja", "clang++")]
    env = os.environ.copy()
    env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
    # Existing SDL/fastgltf builds already selected a C compiler. Overriding it
    # causes CMake to discard the cache (including the supplied Ninja path).
    cache=destination/'CMakeCache.txt'
    has_c_compiler=cache.exists() and any(line.startswith('CMAKE_C_COMPILER:FILEPATH=')
                                        for line in cache.read_text('utf-8').splitlines())
    c_options=[] if has_c_compiler else [f"-DCMAKE_C_COMPILER={compiler.with_name('clang' + compiler.suffix)}"]
    commands = [
        [cmake, "-S", ROOT, "-B", destination, "-G", "Ninja", f"-DCMAKE_MAKE_PROGRAM={ninja}",
         f"-DCMAKE_CXX_COMPILER={compiler}", *c_options,
         f"-DNODE_ENGINE_GENERATED={source}", "-DCMAKE_BUILD_TYPE=Release",
         "-DNODE_ENGINE_SDL=ON"],
        [cmake, "--build", destination, "--parallel", "2"],
    ]
    for command in commands:
        print(" ".join(map(str, command)), flush=True)
        subprocess.run(list(map(str, command)), env=env, check=True)
    if hashlib.sha256(hook_source.read_bytes()).hexdigest() != hook_hash:
        raise RuntimeError('Embedded node code changed during build; build again before preview')
    record(destination, native_fingerprint, node_code=hook_hash)
    # Preserve the relative project layout for asset lookup in standalone games.
    stage_assets(project.parent,destination,[p['scene'] for p in ir['scenes'].values()] if 'scenes' in ir else ir['scene'])
    print(f"Build complete: {destination}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    build(args.project, args.request)
