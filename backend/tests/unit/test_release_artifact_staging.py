"""Dua rilis, proses HTTP/venv nyata dan rollback tanpa service produksi."""
import io
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
import zipfile

import pytest
import requests

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("aman_release_manager",ROOT/"scripts/releases/manager.py")
manager=importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)

APP=r'''
import json,os
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
import release_dependency
from release_info import RELEASE_SHA
release=Path(__file__).resolve().parents[1]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  if self.path=='/api/health/deep':
   data=json.dumps({'release_sha':RELEASE_SHA,'dependency':release_dependency.VERSION}).encode()
   self.send_response(200); self.end_headers(); self.wfile.write(data); return
  name='index.html' if self.path=='/' else self.path.lstrip('/')
  path=release/'frontend/build'/name
  if not path.is_file() and name.startswith('static/'):
   # Retention design for old lazy chunks, isolated fixture consumer only.
   path=next((p/'frontend/build'/name for p in (release.parent).iterdir() if (p/'frontend/build'/name).is_file()),path)
  if not path.is_file(): self.send_error(404); return
  data=path.read_bytes(); self.send_response(200); self.end_headers(); self.wfile.write(data)
HTTPServer(('127.0.0.1',int(os.environ['PORT'])),Handler).serve_forever()
'''


def wheel(path,version):
    package="release_dependency-"+version+".dist-info"
    files={"release_dependency.py":f'VERSION="{version}"\n',
        package+"/METADATA":f"Metadata-Version: 2.1\nName: release-dependency\nVersion: {version}\n",
        package+"/WHEEL":"Wheel-Version: 1.0\nGenerator: isolated-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    files[package+"/RECORD"]="\n".join(name+",," for name in [*files,package+"/RECORD"])+"\n"
    output=path/f"release_dependency-{version}-py3-none-any.whl"
    with zipfile.ZipFile(output,"w") as archive:
        for name,data in files.items(): archive.writestr(name,data)
    return output


@pytest.fixture
def releases(tmp_path):
    repo=tmp_path/"repo"
    (repo/"backend").mkdir(parents=True)
    (repo/"backend/app.py").write_text(APP)
    shutil.copyfile(ROOT/"backend/release_info.py",repo/"backend/release_info.py")
    (repo/"backend/.env").write_text("PRIVATE_FIXTURE=staging-private-fixture\n")
    (repo/".gitignore").write_text("frontend/build/\nbackend/.env\n")
    def git(*args):
        return subprocess.check_output(["git","-C",str(repo),*args],text=True).strip()
    git("init","-q")
    git("config","user.email","fixture@example.test")
    git("config","user.name","Staging fixture")
    root=Path(tempfile.mkdtemp(prefix="aman-release-opt25-"))
    staged=[]
    archives=[]
    for number in [1,2]:
        version=f"{number}.0.0"
        (repo/"backend/requirements.txt").write_text("release-dependency=="+version+"\n")
        git("add",".")
        git("commit","-qm","release "+version)
        sha=git("rev-parse","HEAD")
        build=repo/"frontend/build"
        if build.exists(): shutil.rmtree(build)
        (build/"static/js").mkdir(parents=True)
        chunk="static/js/main."+str(number)+".js"
        (build/chunk).write_text("release "+version)
        (build/"index.html").write_text(f'<script src="/{chunk}"></script>release {version}')
        (build/"asset-manifest.json").write_text(json.dumps({"files":{"main.js":"/"+chunk,"index.html":"/index.html"},"entrypoints":[chunk]}))
        (build/"aman-release.json").write_text(json.dumps({"source_sha":sha}))
        archive=tmp_path/(sha+".tar.gz")
        manifest=manager.create_artifact(repo,build,sha,archive,{"REACT_APP_BACKEND_URL":"http://127.0.0.1"})
        digest=manager.sha256(archive.read_bytes())
        target=manager.stage_artifact(root,archive,sha,digest)
        staged.append((sha,target,version,chunk,wheel(tmp_path,version)))
        archives.append((archive,digest))
    yield root,staged,archives,repo,git
    shutil.rmtree(root,ignore_errors=True)


class Runtime:
    def __init__(self,root,staged):
        self.root,self.staged=root,staged
        self.proc=None
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            self.port=sock.getsockname()[1]
        self.host="http://127.0.0.1:"+str(self.port)
        self.prepared={}
        self.fail_prepare=False
        self.fail_restart=False
        self.fail_health=None
        shared=root/"shared"
        shared.mkdir()
        self.envfile=shared/"backend.env"
        self.envfile.write_text("PRIVATE_FIXTURE=staging-private-fixture\n")
        self.envfile.chmod(0o600)
    def prepare(self,path):
        if self.fail_prepare: raise RuntimeError("dependency install fixture failure")
        if path.name in self.prepared: return
        version=next(row for row in self.staged if row[0]==path.name)
        target=self.root/"envs"/path.name
        venv.EnvBuilder(with_pip=True).create(target)
        subprocess.run([str(target/"bin/python"),"-m","pip","install","--no-index","--no-deps",str(version[4])],check=True,capture_output=True)
        self.prepared[path.name]=target
    def restart(self,path):
        if self.proc:
            self.proc.terminate(); self.proc.wait(timeout=10)
            self.proc=None
        if self.fail_restart: raise RuntimeError("restart fixture failure")
        env=dict(os.environ,AMAN_RELEASE_SHA="0"*40,PORT=str(self.port),PRIVATE_FIXTURE="staging-private-fixture",
                 PYTHONDONTWRITEBYTECODE="1")
        self.proc=subprocess.Popen([str(self.prepared[path.name]/"bin/python"),str(path/"backend/app.py")],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                if requests.get(self.host+"/api/health/deep",timeout=.2).status_code==200: return
            except requests.RequestException: time.sleep(.02)
        raise RuntimeError("HTTP fixture failed to listen")
    def health(self,sha,path):
        if self.fail_health==sha or self.fail_health=="all": return False
        value=requests.get(self.host+"/api/health/deep",timeout=2).json()
        version=next(row[2] for row in self.staged if row[0]==sha)
        html=requests.get(self.host+"/",timeout=2).text
        manifest=requests.get(self.host+"/asset-manifest.json",timeout=2).json()
        metadata=requests.get(self.host+"/aman-release.json",timeout=2).json()
        return (value=={"release_sha":sha,"dependency":version} and "release "+version in html
            and metadata["source_sha"]==sha
            and all(requests.get(self.host+"/"+name,timeout=2).status_code==200 for name in manifest["entrypoints"]))
    def close(self):
        if self.proc:
            self.proc.terminate(); self.proc.wait(timeout=10)
            self.proc.stderr.close()


def test_two_real_http_releases_keep_old_chunk_and_roll_back_healthy_pair(releases):
    root,staged,archives,repo,git=releases
    runtime=Runtime(root,staged)
    a,b=staged
    try:
        first=manager.activate(root,a[0],runtime.prepare,runtime.restart,runtime.health)
        assert first["healthy"] and runtime.health(a[0],a[1])
        private=runtime.envfile.read_bytes()
        runtime.fail_prepare=True
        with pytest.raises(RuntimeError,match="dependency"):
            manager.activate(root,b[0],runtime.prepare,runtime.restart,runtime.health)
        assert manager.pointer(root,"current")==a[1] and runtime.health(a[0],a[1])
        runtime.fail_prepare=False
        manager.activate(root,b[0],runtime.prepare,runtime.restart,runtime.health)
        assert runtime.health(b[0],b[1]) and manager.pointer(root,"previous")==a[1]
        assert requests.get(runtime.host+"/"+a[3],timeout=2).status_code==200
        # Explicit rollback, second successful activation, then failed health.
        manager.activate(root,a[0],runtime.prepare,runtime.restart,runtime.health)
        assert runtime.health(a[0],a[1])
        runtime.fail_health=b[0]
        with pytest.raises(RuntimeError,match="terverifikasi pulih"):
            manager.activate(root,b[0],runtime.prepare,runtime.restart,runtime.health)
        assert runtime.health(a[0],a[1]) and manager.pointer(root,"current")==a[1]
        assert runtime.envfile.read_bytes()==private and runtime.envfile.stat().st_mode&0o777==0o600
        assert not (root/"RECOVERY_REQUIRED.json").exists()
        for archive,_ in archives:
            with tarfile.open(archive,"r:gz") as package:
                assert not any(".env" in Path(member.name).parts for member in package.getmembers())
                assert not any(b"staging-private-fixture" in package.extractfile(member).read() for member in package.getmembers())
    finally:
        runtime.close()


def test_failed_rollback_persists_recovery_status_and_blocks_further_activation(releases):
    root,staged,*_=releases
    a,b=staged
    # Real pointer/file transitions; failure is injected at the process boundary.
    manager.activate(root,a[0],lambda _:None,lambda _:None,lambda *_:True)
    with pytest.raises(RuntimeError,match="RECOVERY_REQUIRED"):
        manager.activate(root,b[0],lambda _:None,lambda _:None,lambda *_:False)
    assert json.loads((root/"RECOVERY_REQUIRED.json").read_text())["recovery_required"] is True
    with pytest.raises(RuntimeError,match="operator"):
        manager.activate(root,b[0],lambda _:None,lambda _:None,lambda *_:True)


def test_tamper_digest_source_and_frontend_chunk_are_rejected(releases,tmp_path):
    root,staged,archives,repo,git=releases
    archive,digest=archives[0]
    with pytest.raises(ValueError,match="Checksum"):
        manager.stage_artifact(root,archive,staged[0][0],"0"*64)
    (staged[0][1]/"backend/app.py").write_text("tampered")
    with pytest.raises(ValueError,match="Checksum"):
        manager.verify_release(staged[0][1])
    (repo/"backend/app.py").write_text("dirty source")
    with pytest.raises(ValueError,match="dirty"):
        manager.create_artifact(repo,repo/"frontend/build",git("rev-parse","HEAD"),tmp_path/"dirty.tar.gz")


def test_missing_frontend_chunk_and_nonexact_source_sha_never_package(releases,tmp_path):
    root,staged,archives,repo,git=releases
    with pytest.raises(ValueError,match="HEAD"):
        manager.create_artifact(repo,repo/"frontend/build",staged[0][0],tmp_path/"wrong-source.tar.gz")
    build=repo/"frontend/build"
    (build/staged[1][3]).unlink()
    with pytest.raises(ValueError,match="Chunk/media"):
        manager.create_artifact(repo,build,git("rev-parse","HEAD"),tmp_path/"missing-chunk.tar.gz")


@pytest.mark.parametrize("metadata",[None,{"source_sha":"0"*40}])
def test_frontend_build_must_declare_exact_source_sha(releases,tmp_path,metadata):
    root,staged,archives,repo,git=releases
    build=repo/"frontend/build"
    path=build/"aman-release.json"
    if metadata is None:path.unlink()
    else:path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match="SHA frontend"):
        manager.create_artifact(repo,build,git("rev-parse","HEAD"),tmp_path/"wrong-frontend.tar.gz")


def test_dirty_frontend_build_plugin_never_packages_under_clean_source_sha(releases,tmp_path):
    root,staged,archives,repo,git=releases
    plugin=repo/"frontend/plugins/release-manifest.js"
    plugin.parent.mkdir(parents=True)
    plugin.write_text("uncommitted build logic")
    with pytest.raises(ValueError,match="dirty"):
        manager.create_artifact(repo,repo/"frontend/build",git("rev-parse","HEAD"),tmp_path/"dirty-plugin.tar.gz")


def test_stage_idempotent_and_prepare_failure_do_not_touch_current(releases):
    root,staged,archives,repo,git=releases
    a,b=staged
    assert manager.stage_artifact(root,archives[0][0],a[0],archives[0][1])==a[1]
    manager.activate(root,a[0],lambda _:None,lambda _:None,lambda *_:True)
    prior=os.readlink(root/"current")
    def fail(_): raise RuntimeError("install failed")
    with pytest.raises(RuntimeError,match="install"):
        manager.activate(root,b[0],fail,lambda _:None,lambda *_:True)
    assert os.readlink(root/"current")==prior


def test_interruption_after_pointer_switch_compensates_to_verified_previous(releases):
    root,staged,*_=releases
    a,b=staged
    manager.activate(root,a[0],lambda _:None,lambda _:None,lambda *_:True)
    def restart(path):
        if path.name==b[0]: raise KeyboardInterrupt()
    with pytest.raises(RuntimeError,match="terverifikasi pulih"):
        manager.activate(root,b[0],lambda _:None,restart,lambda *_:True)
    assert manager.pointer(root,"current")==a[1]


def test_archive_paths_and_links_never_escape_staging(releases,tmp_path):
    root,staged,*_=releases
    archive=tmp_path/"unsafe.tar.gz"
    with tarfile.open(archive,"w:gz") as tar:
        member=tarfile.TarInfo("../escaped")
        member.size=4
        tar.addfile(member,io.BytesIO(b"evil"))
    with pytest.raises(ValueError,match="aman"):
        manager.stage_artifact(root,archive,staged[0][0],manager.sha256(archive.read_bytes()))
    assert not (root.parent/"escaped").exists()
    with pytest.raises(ValueError,match="staging khusus"):
        manager.staging_root("/var/www/inventarisasi")
