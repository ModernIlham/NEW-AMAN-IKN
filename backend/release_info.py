"""Identitas source yang ditangkap sekali saat worker mengimpor aplikasi.

Jangan membaca Git HEAD per-request: checkout bisa berubah saat worker lama
masih hidup. Artifact immutable diverifikasi deploy sebelum module diimpor.
"""
import json
import os
from pathlib import Path
import re
import subprocess

FULL_SHA=re.compile(r"[0-9a-f]{40}")


def capture_release(root=None,environment=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parent.parent
    environment=os.environ if environment is None else environment
    manifest=root/"release-manifest.json"
    if FULL_SHA.fullmatch(root.name) and manifest.exists():
        if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>8*1024*1024:
            raise RuntimeError("Immutable release manifest tidak aman")
        value=json.loads(manifest.read_text())
        if value.get("release_sha")!=root.name or value.get("source_sha")!=root.name:
            raise RuntimeError("Immutable release source SHA tidak cocok")
        return root.name,"immutable_manifest"
    try:
        value=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],
            stderr=subprocess.DEVNULL,text=True,timeout=1).strip()
        if FULL_SHA.fullmatch(value):
            return value,"git_at_import"
    except (OSError,subprocess.SubprocessError):
        pass
    supplied=environment.get("AMAN_RELEASE_SHA","").lower()
    if FULL_SHA.fullmatch(supplied):
        return supplied,"environment"
    return None,"unknown"


RELEASE_SHA,RELEASE_SOURCE=capture_release()
