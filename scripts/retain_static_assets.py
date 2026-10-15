#!/usr/bin/env python3
"""Pertahankan hashed static assets tab lama tanpa mengubah manifest build baru."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import stat
import tempfile
import time

LEDGER=".aman-static-retention.json"
HASHED=re.compile(r"[.-][0-9a-f]{8,64}(?:[.-]|$)")
MAX_FILES=20000
MAX_SCAN_ENTRIES=MAX_FILES*4
MAX_SCAN_DEPTH=8


def digest(path):
    result=hashlib.sha256()
    with path.open("rb") as source:
        for data in iter(lambda:source.read(65536),b""):
            result.update(data)
    return result.hexdigest()


def safe_path(root,name,must_exist=True):
    relative=PurePosixPath(name)
    if (relative.is_absolute() or str(relative)!=name or ".." in relative.parts or "\\" in name
            or not name.startswith("static/") or "?" in name or "#" in name
            or not HASHED.search(relative.name) or relative.suffix.lower()==".map"):
        raise ValueError("Static retention hanya menerima path hashed static lokal, tanpa source map")
    path=root
    for part in relative.parts:
        path=path/part
        if path.is_symlink():
            raise ValueError("Symlink static ditolak")
    if must_exist and not path.is_file():
        raise ValueError("Static asset yang dijanjikan manifest/ledger hilang")
    if path.exists() and not path.is_file():
        raise ValueError("Static asset wajib regular file")
    return path


def own_assets(root):
    manifest=root/"asset-manifest.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>8*1024*1024:
        raise ValueError("asset-manifest.json build wajib regular file berbatas")
    value=json.loads(manifest.read_text())
    names=set()
    for name in value.get("files",{}).values():
        if not isinstance(name,str) or name.startswith("//") or "://" in name:
            raise ValueError("Manifest menunjuk target eksternal")
        name=name.lstrip("/")
        if not name.startswith("static/") or Path(name).suffix.lower()==".map":
            continue
        safe_path(root,name)
        names.add(name)
    if len(names)>MAX_FILES:
        raise ValueError("Manifest melampaui batas jumlah static asset")
    return names


def read_ledger(root):
    source=root/LEDGER
    if source.is_symlink():
        raise ValueError("Ledger retention tidak aman/terlalu besar")
    if not source.exists():
        return {}
    if source.is_symlink() or not source.is_file() or source.stat().st_size>8*1024*1024:
        raise ValueError("Ledger retention tidak aman/terlalu besar")
    value=json.loads(source.read_text())
    if value.get("schema_version")!=1 or not isinstance(value.get("assets"),dict) or len(value["assets"])>MAX_FILES:
        raise ValueError("Schema/ukuran ledger tidak valid")
    for name,meta in value["assets"].items():
        safe_path(root,name,must_exist=False)
        if (not isinstance(meta,dict) or not re.fullmatch(r"[0-9a-f]{64}",str(meta.get("sha256","")))
                or not isinstance(meta.get("bytes"),int) or meta["bytes"]<0
                or not isinstance(meta.get("last_seen"),(int,float)) or not math.isfinite(meta["last_seen"]) or meta["last_seen"]<0):
            raise ValueError("Metadata ledger rusak")
    return value["assets"]


def reject_untracked_legacy_static(root,known):
    """No-ledger builds must not silently lose already-served hashed assets.

    Inspect only static/, with bounded entries/depth and no-follow directory
    descriptors. Unknown assets are not adopted or given a new grace period.
    A build with a ledger keeps the existing inheritance/expiry policy.
    """
    static_root=root/"static"
    if static_root.is_symlink():
        raise ValueError("Symlink static ditolak")
    if not static_root.exists():
        return
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
    descriptor=os.open(static_root,flags)
    stack=[]
    try:
        stack.append((descriptor,os.scandir(descriptor),("static",),0))
    except BaseException:
        os.close(descriptor)
        raise
    scanned=0
    try:
        while stack:
            parent,iterator,parts,depth=stack[-1]
            entry=next(iterator,None)
            if entry is None:
                iterator.close();os.close(parent);stack.pop()
                continue
            scanned+=1
            if scanned>MAX_SCAN_ENTRIES:
                raise ValueError("Inventaris static legacy melampaui batas jumlah entry")
            if entry.name in {".",".."} or "\\" in entry.name:
                raise ValueError("Path static legacy tidak aman")
            mode=entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                raise ValueError("Symlink static ditolak")
            relative=parts+(entry.name,)
            if stat.S_ISDIR(mode):
                if depth>=MAX_SCAN_DEPTH:
                    raise ValueError("Inventaris static legacy melampaui batas kedalaman")
                child=os.open(entry.name,flags,dir_fd=parent)
                try:
                    stack.append((child,os.scandir(child),relative,depth+1))
                except BaseException:
                    os.close(child)
                    raise
            elif stat.S_ISREG(mode):
                name=PurePosixPath(*relative).as_posix()
                if HASHED.search(entry.name) and Path(entry.name).suffix.lower()!=".map":
                    safe_path(root,name)
                    if name not in known:
                        raise ValueError("Static orphan tanpa ledger: inventarisasi sebelum deploy")
            else:
                raise ValueError("Static legacy wajib regular file/direktori")
    finally:
        for descriptor,iterator,_,_ in reversed(stack):
            iterator.close();os.close(descriptor)


def fsync_directory(path):
    """Persist rename metadata; an unsupported filesystem must fail closed."""
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def copy_atomic(source,destination,expected):
    destination.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary=tempfile.mkstemp(prefix=".retain-",dir=destination.parent)
    temporary=Path(temporary)
    try:
        copied=hashlib.sha256()
        with os.fdopen(descriptor,"wb") as output,source.open("rb") as incoming:
            for chunk in iter(lambda:incoming.read(65536),b""):
                output.write(chunk)
                copied.update(chunk)
            output.flush()
            os.fsync(output.fileno())
        if copied.hexdigest()!=expected["sha256"] or temporary.stat().st_size!=expected["bytes"]:
            raise ValueError("Static berubah saat disalin; aktivasi dibatalkan")
        temporary.chmod(0o644)
        os.replace(temporary,destination)
        fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def retain(current,staged,grace_hours=24,budget_bytes=256*1024*1024,min_free_bytes=1024*1024*1024,now=None):
    now=time.time() if now is None else now
    if not math.isfinite(grace_hours) or not 24<=grace_hours<=168 or not 1<=budget_bytes<=2*1024**3 or min_free_bytes<0:
        raise ValueError("Grace wajib24..168jam dan budget1byte..2GiB")
    current,staged=Path(current),Path(staged)
    if current.is_symlink() or staged.is_symlink() or not staged.is_dir() or current.resolve()==staged.resolve():
        raise ValueError("Build current/staged wajib direktori berbeda tanpa symlink")
    new_own=own_assets(staged)
    # A reused staging dir may contain a previous ledger. Never trust it.
    if (staged/LEDGER).exists():
        raise ValueError("Staging sudah memiliki ledger; bangun ulang build.new")
    assets={}
    sources={}
    if current.exists():
        if not current.is_dir():
            raise ValueError("Current build bukan direktori")
        ledger=read_ledger(current)
        current_own=own_assets(current)
        if not (current/LEDGER).exists():
            reject_untracked_legacy_static(current,current_own)
        assets={name:dict(meta) for name,meta in ledger.items()
                if now-meta["last_seen"]<grace_hours*3600}
        for name in current_own:
            source=safe_path(current,name)
            # Current manifest is the active release: protection starts at
            # this cutover, independent of its original build timestamp.
            assets[name]={"sha256":digest(source),"bytes":source.stat().st_size,"last_seen":now}
        for name,meta in assets.items():
            source=safe_path(current,name)
            if source.stat().st_size!=meta["bytes"] or digest(source)!=meta["sha256"]:
                raise ValueError("Static retained rusak/hilang; jangan buang grace tab lama")
            sources[name]=source
    for name in new_own:
        source=safe_path(staged,name)
        meta={"sha256":digest(source),"bytes":source.stat().st_size,"last_seen":now}
        if name in assets and assets[name]["sha256"]!=meta["sha256"]:
            raise ValueError("Nama static hash sama dengan byte berbeda")
        assets[name]=meta
    if len(assets)>MAX_FILES or sum(meta["bytes"] for meta in assets.values())>budget_bytes:
        raise ValueError("Budget retention tidak cukup untuk grace24jam; deploy ditolak tanpa menghapus protected assets")
    missing=[name for name in assets if name not in new_own]
    additional=sum(assets[name]["bytes"] for name in missing)
    if shutil.disk_usage(staged).free-additional<min_free_bytes:
        raise OSError("Disk headroom retention tidak cukup; build current dipertahankan")
    for name in missing:
        destination=safe_path(staged,name,must_exist=False)
        if destination.exists():
            if digest(destination)!=assets[name]["sha256"]:
                raise ValueError("Staged static collision")
        else:
            copy_atomic(sources[name],destination,assets[name])
    value={"schema_version":1,"grace_hours":grace_hours,"created_at":now,"assets":assets}
    descriptor,temporary=tempfile.mkstemp(prefix=".retention-ledger-",dir=staged)
    temporary=Path(temporary)
    try:
        with os.fdopen(descriptor,"w") as output:
            json.dump(value,output,sort_keys=True)
            output.flush();os.fsync(output.fileno())
        temporary.chmod(0o644)
        os.replace(temporary,staged/LEDGER)
        fsync_directory(staged)
    finally:
        temporary.unlink(missing_ok=True)
    return {"retained_files":len(missing),"total_hashed_files":len(assets),"total_bytes":sum(meta["bytes"] for meta in assets.values()),"grace_hours":grace_hours}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current",required=True)
    parser.add_argument("--staged",required=True)
    args=parser.parse_args()
    try:
        result=retain(args.current,args.staged,
            grace_hours=float(os.environ.get("AMAN_STATIC_GRACE_HOURS","24")),
            budget_bytes=int(os.environ.get("AMAN_STATIC_BUDGET_MB","256"))*1024*1024,
            min_free_bytes=int(os.environ.get("AMAN_STATIC_MIN_FREE_MB","1024"))*1024*1024)
    except Exception:
        parser.exit(1,"GAGAL: static retention tidak terverifikasi; build lama tetap dipertahankan.\n")
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
