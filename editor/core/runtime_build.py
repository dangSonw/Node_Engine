"""Reject preview binaries built against different native sources or node adapters."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from .registry import ROOT
from .document import save_json


def fingerprint(root=ROOT):
    root=Path(root)
    files=[root/'CMakeLists.txt',root/'nodes/registry.yaml']
    files += list((root/'cmake').glob('*.cmake'))
    files += list((root/'deps').glob('*/upstream.txt'))
    files += [p for p in (root/'runtime').rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp','.spv')]
    files += [p for p in (root/'deps/flecs-4.1.6').glob('*') if p.suffix in ('.c','.h')]
    digest=hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode()+b'\0')
        digest.update(path.read_bytes()+b'\0')
    return digest.hexdigest()


def record(directory, expected, node_code=None):
    directory=Path(directory)
    if fingerprint()!=expected:
        raise RuntimeError('Native sources changed during build; build again before preview')
    exe=directory/('node_view.exe' if os.name=='nt' else 'node_view')
    save_json(directory/'runtime-build.json',{'fingerprint':expected,
        'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(), 'node_code':node_code})


def current(executable, expected=None, node_code=None):
    executable=Path(executable)
    try:
        data=json.loads((executable.parent/'runtime-build.json').read_text('utf-8'))
        return (data['fingerprint']==(expected or fingerprint()) and
                (node_code is None or data.get('node_code')==node_code) and
                data['binary_sha256']==hashlib.sha256(executable.read_bytes()).hexdigest())
    except (OSError,ValueError,KeyError,TypeError):
        return False


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',type=Path)
    parser.add_argument('--expected')
    args=parser.parse_args()
    if args.record:
        if not args.expected:
            parser.error('--record needs --expected from before the build')
        record(args.record,args.expected)
    else:
        print(fingerprint())
