"""Worker lama tetap melaporkan SHA saat import walau checkout sudah berubah."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("release_info_fixture",ROOT/"backend/release_info.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_import_capture_remains_old_after_checkout_changes_and_new_worker_gets_new_sha(tmp_path):
    backend=tmp_path/"backend";backend.mkdir()
    shutil.copyfile(ROOT/"backend/release_info.py",backend/"release_info.py")
    def git(*args):return subprocess.check_output(["git","-C",str(tmp_path),*args],text=True).strip()
    git("init","-q");git("config","user.email","fixture@example.test");git("config","user.name","Release fixture")
    git("add",".");git("commit","-qm","release A")
    a=git("rev-parse","HEAD")
    code='import release_info,sys,json;print(release_info.RELEASE_SHA,flush=True);sys.stdin.readline();print(release_info.RELEASE_SHA,flush=True)'
    child=subprocess.Popen([sys.executable,"-c",code],cwd=backend,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()==a
        (tmp_path/"change").write_text("release B")
        git("add",".");git("commit","-qm","release B")
        b=git("rev-parse","HEAD")
        child.stdin.write("continue\n");child.stdin.flush()
        assert child.stdout.readline().strip()==a!=b
        assert child.wait(timeout=5)==0
        new=subprocess.check_output([sys.executable,"-c","import release_info;print(release_info.RELEASE_SHA)"],cwd=backend,text=True).strip()
        assert new==b
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        child.stdin.close();child.stdout.close()


def test_immutable_manifest_validates_source_and_no_git_env_can_override_it(tmp_path):
    sha="a"*40;release=tmp_path/sha;release.mkdir()
    manifest=release/"release-manifest.json"
    manifest.write_text(json.dumps({"release_sha":sha,"source_sha":sha}))
    assert module.capture_release(release,{"AMAN_RELEASE_SHA":"b"*40})==(sha,"immutable_manifest")
    manifest.write_text(json.dumps({"release_sha":sha,"source_sha":"b"*40}))
    with pytest.raises(RuntimeError,match="tidak cocok"):
        module.capture_release(release,{})


def test_unknown_source_is_explicit_and_valid_env_only_used_without_repository(tmp_path):
    # /tmp is not part of this checkout.
    assert module.capture_release(tmp_path,{})==(None,"unknown")
    assert module.capture_release(tmp_path,{"AMAN_RELEASE_SHA":"B"*40})==("b"*40,"environment")
    assert module.capture_release(tmp_path,{"AMAN_RELEASE_SHA":"main"})==(None,"unknown")
