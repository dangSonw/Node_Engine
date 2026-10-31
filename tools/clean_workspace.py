"""Preview or remove only known, reproducible workspace output (never game saves outside this workspace)."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_KEEP = ('.work/build-template-flappy', 'artifacts/validation/template-help')
OBSOLETE = ('game.generated.cpp', 'templates/games/flappy_bird/game.py',
            'templates/games/flappy_bird/contract.json', 'templates/games/flappy_bird/scenarios.json',
            'templates/games/flappy_bird/replays/restart.json',
            'templates/games/flappy_bird/project.json', 'templates/games/isometric_snake_3d/project.json',
            *('templates/games/isometric_snake_3d/replay-'+name+'.json' for name in
              ('eat','pause','restart','reverse_rejected','start','wall')))


def checked_target(root, path):
    root, path = Path(root).resolve(), Path(path)
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root) or path.is_symlink() or getattr(path,'is_junction',lambda:False)():
        raise ValueError('Refuse cleanup outside the workspace or through a link: ' + str(path))
    return resolved


def plan_cleanup(root=ROOT, keep=DEFAULT_KEEP):
    root = Path(root).resolve()
    protected = [checked_target(root, root/path) for path in keep]
    candidates = [root/'.cache', root/'.pytest_cache']
    for folder in (root/'.work', root/'artifacts/validation'):
        if folder.is_dir():
            candidates += list(folder.iterdir())
    candidates += [root/path for path in OBSOLETE]
    for source in ('editor','tools','tests','examples','templates'):
        for directory, dirs, _files in os.walk(root/source, followlinks=False):
            for name in dirs[:]:
                path = Path(directory)/name
                if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or name in ('build','dist','deps'):
                    dirs.remove(name)
                elif name == '__pycache__':
                    candidates.append(path); dirs.remove(name)
    result = []
    for candidate in sorted(set(candidates)):
        if not candidate.exists():
            continue
        path = checked_target(root,candidate)
        if any(path == saved or path.is_relative_to(saved) or saved.is_relative_to(path) for saved in protected):
            continue
        if any(path.is_relative_to(previous) for previous in result):
            continue
        result.append(path)
    return result


def clean(root=ROOT, *, apply=False, keep=DEFAULT_KEEP):
    root = Path(root).resolve()
    paths = plan_cleanup(root, keep)
    report = dict(applied=apply,files=0,bytes=0,targets=[p.relative_to(root).as_posix() for p in paths])
    for path in paths:
        files = [path] if path.is_file() else []
        if path.is_dir():
            for directory, dirs, names in os.walk(path,followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(directory)/name).is_symlink()
                           and not getattr(Path(directory)/name,'is_junction',lambda:False)()]
                files += [Path(directory)/name for name in names if not (Path(directory)/name).is_symlink()]
        report['files'] += len(files)
        report['bytes'] += sum(p.stat().st_size for p in files)
        if apply:
            checked_target(root,path)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='Delete the reviewed known outputs; default is preview only')
    parser.add_argument('--keep',action='append',default=[],help='Extra workspace-relative path to retain')
    parser.add_argument('--report',type=Path,help='Optional JSON audit file, usually under artifacts/validation/template-help/')
    args = parser.parse_args()
    report = clean(apply=args.apply,keep=(*DEFAULT_KEEP,*args.keep))
    if args.report:
        target = checked_target(ROOT,ROOT/args.report)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({**report,'targets_count':len(report['targets']),'targets':report['targets'][:15]},ensure_ascii=False))
