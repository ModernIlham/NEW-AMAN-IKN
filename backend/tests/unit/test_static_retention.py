"""Tablama fetch hashedlazy lewat docrootbaru, expiry/budget/fault tidakhapusaktif."""
import importlib.util
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import shutil
import threading

import pytest
import requests

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("static_retention",ROOT/"scripts/retain_static_assets.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def build(root,version):
    (root/"static/js").mkdir(parents=True)
    name=f"static/js/dashboard.{version*8}.chunk.js"
    data=("old lazy dashboard" if version=="a" else "new lazy dashboard").encode()
    (root/name).write_bytes(data)
    (root/"index.html").write_text("index "+version)
    (root/"asset-manifest.json").write_text(json.dumps({"files":{"lazy":"/"+name}}))
    (root/"static/js"/("dashboard."+version*8+".chunk.js.map")).write_text("private source map not retained")
    return name,data


def test_old_browser_lazy_chunk_works_after_new_docroot_then_rollback(tmp_path):
    current=tmp_path/"build"
    staged=tmp_path/"build.new"
    a,old=build(current,"a")
    b,new=build(staged,"b")
    manifest=(staged/"asset-manifest.json").read_bytes()
    result=module.retain(current,staged,now=100000,min_free_bytes=0)
    assert result["retained_files"]==1
    assert (staged/"asset-manifest.json").read_bytes()==manifest
    assert not (staged/(a+".map")).exists()
    current.rename(tmp_path/"build.old")
    staged.rename(current)
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(current)))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        origin="http://127.0.0.1:"+str(server.server_port)
        assert requests.get(origin+"/"+a,timeout=2).content==old
        assert requests.get(origin+"/"+b,timeout=2).content==new
        assert requests.get(origin+"/",timeout=2).text=="index b"
        shutil.rmtree(current)
        (tmp_path/"build.old").rename(current)
        assert requests.get(origin+"/"+a,timeout=2).content==old
        assert requests.get(origin+"/",timeout=2).text=="index a"
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)


def test_repeated_releases_do_not_extend_inherited_grace_forever(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b";c=tmp_path/"c";d=tmp_path/"d"
    name,_=build(a,"a")
    name_b,_=build(b,"b")
    build(c,"c");build(d,"d")
    module.retain(a,b,now=100000,min_free_bytes=0)
    module.retain(b,c,now=100000+23*3600,min_free_bytes=0)
    assert (c/name).exists()
    ledger=json.loads((c/module.LEDGER).read_text())["assets"]
    assert ledger[name]["last_seen"]==100000
    assert ledger[name_b]["last_seen"]==100000+23*3600
    module.retain(c,d,now=100000+25*3600,min_free_bytes=0)
    assert not (d/name).exists() and (d/name_b).exists()


@pytest.mark.parametrize("fault",["budget","space","copy","ledger","directory"])
def test_failed_stage_never_mutates_current_or_manifest_and_never_claims_complete(tmp_path,monkeypatch,fault):
    a=tmp_path/"a";b=tmp_path/"b"
    name,old=build(a,"a");build(b,"b")
    manifest=(b/"asset-manifest.json").read_bytes()
    if fault=="space":
        monkeypatch.setattr(module.shutil,"disk_usage",lambda _:shutil._ntuple_diskusage(100,90,10))
    if fault=="copy":
        def fail(*args): raise OSError("ENOSPC injected")
        monkeypatch.setattr(module,"copy_atomic",fail)
    if fault=="ledger":
        original=module.os.replace
        def fail(source,dest):
            if Path(dest).name==module.LEDGER: raise OSError("ENOSPC ledger injected")
            return original(source,dest)
        monkeypatch.setattr(module.os,"replace",fail)
    if fault=="directory":
        def fail(*args): raise OSError("Directory fsync unsupported injected")
        monkeypatch.setattr(module,"fsync_directory",fail)
    with pytest.raises((ValueError,OSError)):
        module.retain(a,b,now=100000,budget_bytes=1 if fault=="budget" else 1024,min_free_bytes=100 if fault=="space" else 0)
    assert (a/name).read_bytes()==old
    assert (b/"asset-manifest.json").read_bytes()==manifest
    assert not (b/module.LEDGER).exists()
    assert not list(b.rglob(".retain-*")) and not list(b.glob(".retention-ledger-*"))


def test_ledger_directory_sync_failure_never_reports_verified_stage(tmp_path,monkeypatch):
    a=tmp_path/"a";b=tmp_path/"b"
    name,old=build(a,"a");build(b,"b")
    synced=[]
    original=module.fsync_directory
    def fail_at_ledger(path):
        synced.append(path)
        if path==b: raise OSError("Ledger directory fsync injected")
        return original(path)
    monkeypatch.setattr(module,"fsync_directory",fail_at_ledger)
    with pytest.raises(OSError,match="Ledger directory"):
        module.retain(a,b,now=100000,min_free_bytes=0)
    assert synced==[b/"static/js",b]
    assert (a/name).read_bytes()==old
    assert not list(b.rglob(".retain-*")) and not list(b.glob(".retention-ledger-*"))


def test_symlink_and_missing_protected_asset_fail_closed(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b"
    name,_=build(a,"a");build(b,"b")
    (a/name).unlink()
    (a/name).symlink_to(b/"index.html")
    with pytest.raises(ValueError,match="Symlink"):
        module.retain(a,b,now=100000,min_free_bytes=0)
    (a/name).unlink()
    with pytest.raises(ValueError,match="hilang"):
        module.retain(a,b,now=100000,min_free_bytes=0)


def test_hash_name_collision_and_grace_reduction_fail_closed(tmp_path):
    a=tmp_path/"a";b=tmp_path/"b"
    name,_=build(a,"a");build(b,"a")
    (b/name).write_bytes(b"different bytes same hashed path")
    with pytest.raises(ValueError,match="hash sama"):
        module.retain(a,b,now=100000,min_free_bytes=0)
    with pytest.raises(ValueError,match="Grace"):
        module.retain(a,b,grace_hours=1)
