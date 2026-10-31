"""Install the pinned ozz archive without overwriting local dependency edits."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://codeload.github.com/guillaumeblanc/ozz-animation/zip/refs/tags/0.17.0'
SHA256 = '5ce66c94226cb11f360d2cdcef2618dd8238759959a46204af9973e73c5a7d77'
COMMIT = '744eb9d99f606eda849acb0b1204f7a3dc20bca1'


def fetch():
    target = ROOT/'deps/ozz-animation-0.17.0'
    if target.exists():
        raise FileExistsError(f'Preserving existing dependency: {target}')
    cache = ROOT/'.cache/downloads'; cache.mkdir(parents=True,exist_ok=True)
    archive = cache/'ozz-animation-0.17.0.zip'
    if not archive.exists():
        with urllib.request.urlopen(URL,timeout=60) as incoming, archive.open('wb') as output:
            shutil.copyfileobj(incoming,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError(f'ozz archive hash mismatch: {archive}')
    with tempfile.TemporaryDirectory(prefix='ozz-',dir=ROOT/'deps') as temporary:
        base = Path(temporary); extracted = base/target.name
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if not (base/member.filename).resolve().is_relative_to(extracted):
                    raise ValueError('Archive path leaves its dependency directory')
                if (member.external_attr >> 16)&0o170000 == 0o120000:
                    raise ValueError('Archive contains a symbolic link')
            source.extractall(base)
        (extracted/'upstream.txt').write_text(
            f'ozz-animation 0.17.0\nCommit: {COMMIT}\nArchive: {URL}\nSHA256: {SHA256}\nLicense: MIT (LICENSE.md)\n','utf-8')
        extracted.rename(target)
    return target


if __name__ == '__main__': print(fetch())
