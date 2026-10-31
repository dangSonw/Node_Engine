"""Install the pinned, hash-checked Jolt source archive without replacing edits."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
URL='https://codeload.github.com/jrouwe/JoltPhysics/zip/refs/tags/v5.6.0'
SHA256='0af9beea51637ef805e624fe838ea2870f7b68cd48cbe1615c853bd9bcf4f1d7'
COMMIT='e77f175595e64cb44218cc9d9d56fc365ad0e36a'


def fetch():
    target=ROOT/'deps/JoltPhysics-5.6.0'
    if target.exists():
        raise FileExistsError(f'Preserving existing dependency: {target}')
    cache=ROOT/'.cache/downloads'; cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'JoltPhysics-5.6.0.zip'
    if not archive.exists():
        with urllib.request.urlopen(URL,timeout=60) as incoming, archive.open('wb') as output:
            shutil.copyfileobj(incoming,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise ValueError(f'Jolt archive hash mismatch: {archive}')
    with tempfile.TemporaryDirectory(prefix='jolt-',dir=ROOT/'deps') as temporary:
        base=Path(temporary); extracted=base/target.name
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if not (base/member.filename).resolve().is_relative_to(extracted):
                    raise ValueError('Archive path leaves its dependency directory')
                if (member.external_attr >> 16)&0o170000==0o120000:
                    raise ValueError('Archive contains a symbolic link')
            source.extractall(base)
        (extracted/'upstream.txt').write_text(f'Jolt Physics 5.6.0\nCommit: {COMMIT}\nArchive: {URL}\nSHA256: {SHA256}\nLicense: MIT (LICENSE)\n','utf-8')
        extracted.rename(target)
    return target


if __name__=='__main__': print(fetch())
