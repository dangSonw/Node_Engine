"""Pinned dependency extraction must be reproducible and preserve existing files."""
import hashlib
import shutil
import zipfile
import pytest
from tools import fetch_jolt


def install_root(tmp_path,monkeypatch):
    (tmp_path/'deps').mkdir()
    cache=tmp_path/'.cache/downloads'; cache.mkdir(parents=True)
    monkeypatch.setattr(fetch_jolt,'ROOT',tmp_path)
    return cache/'JoltPhysics-5.6.0.zip'


def test_verified_archive_installs_and_existing_dependency_is_preserved(tmp_path,monkeypatch):
    original=fetch_jolt.ROOT
    archive=install_root(tmp_path,monkeypatch)
    shutil.copyfile(original/'.cache/downloads/JoltPhysics-5.6.0.zip',archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==fetch_jolt.SHA256
    installed=fetch_jolt.fetch()
    assert (installed/'Jolt/Jolt.h').read_bytes()==(original/'deps/JoltPhysics-5.6.0/Jolt/Jolt.h').read_bytes()
    assert (installed/'upstream.txt').read_text('utf-8')==(original/'deps/JoltPhysics-5.6.0/upstream.txt').read_text('utf-8')
    edited=installed/'local.txt'; edited.write_text('preserve this')
    with pytest.raises(FileExistsError,match='Preserving existing dependency'): fetch_jolt.fetch()
    assert edited.read_text()=='preserve this'


def test_bad_archive_digest_is_rejected_before_extraction(tmp_path,monkeypatch):
    archive=install_root(tmp_path,monkeypatch); archive.write_bytes(b'wrong archive')
    with pytest.raises(ValueError,match='hash mismatch'): fetch_jolt.fetch()
    assert list((tmp_path/'deps').iterdir())==[]


@pytest.mark.parametrize('symlink',[False,True])
def test_paths_and_symlinks_cannot_escape_dependency_directory(tmp_path,monkeypatch,symlink):
    archive=install_root(tmp_path,monkeypatch)
    with zipfile.ZipFile(archive,'w') as output:
        item=zipfile.ZipInfo('JoltPhysics-5.6.0/link' if symlink else 'JoltPhysics-5.6.0/../../escaped.txt')
        if symlink:
            item.create_system=3; item.external_attr=0o120777<<16
        output.writestr(item,'../../escaped.txt')
    monkeypatch.setattr(fetch_jolt,'SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(ValueError,match='symbolic link' if symlink else 'leaves its dependency directory'): fetch_jolt.fetch()
    assert not (tmp_path/'escaped.txt').exists()
    assert list((tmp_path/'deps').iterdir())==[]
