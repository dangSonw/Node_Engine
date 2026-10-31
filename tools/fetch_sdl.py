"""Fetch the pinned SDL source; preserve existing dependency edits."""
import hashlib
from pathlib import Path
import shutil,tarfile,tempfile,urllib.request

ROOT=Path(__file__).resolve().parents[1]
URL='https://github.com/libsdl-org/SDL/releases/download/release-3.4.18/SDL3-3.4.18.tar.gz'
SHA256='9c75cf16330322c217dedd2e0609f1124f1b54b8633e763467b4684d0f4334a3'
PROVENANCE=(f'SDL 3.4.18 source archive, zlib license\nURL: {URL}\nSHA256: {SHA256}\n'
    'Windows focus adapter: cmake/PatchSdlEmbeddedFocus.cmake\n'
    'Original upstream sources are vendored; the validated adapter is applied by CMake.\n')

def fetch(target=ROOT/'deps/SDL3-source-3.4.18'):
    target=Path(target)
    if target.exists(): raise FileExistsError(f'Preserving existing dependency: {target}')
    archive=ROOT/'.cache/SDL3-3.4.18-source.tar.gz'; archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with urllib.request.urlopen(URL,timeout=60) as incoming, archive.open('wb') as output:
            shutil.copyfileobj(incoming,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256: raise ValueError(f'SDL archive hash mismatch: {archive}')
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sdl-',dir=target.parent) as temporary:
        base=Path(temporary); extracted=base/'dependency'; extracted.mkdir()
        with tarfile.open(archive) as source:
            root=extracted/'SDL3-3.4.18'
            for member in source.getmembers():
                if not (extracted/member.name).resolve().is_relative_to(root): raise ValueError('SDL archive path escapes its source directory')
            source.extractall(extracted,filter='data')
        (extracted/'upstream.txt').write_text(PROVENANCE,encoding='utf-8',newline='\n')
        extracted.rename(target)
    return target

if __name__=='__main__': print(fetch())
