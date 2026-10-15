"""Pre-activation native ABI/font proof without DB or network access."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "scripts/releases/runtime_native_smoke.py"
FONT = ROOT / "backend/assets/fonts/Inter.ttf"


def _module():
    spec = importlib.util.spec_from_file_location("native_smoke_under_test", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_untrusted_font_rejected_before_renderer_import(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith(("reportlab", "weasyprint", "fontTools"))
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    font = tmp_path / "Inter.ttf"
    font.write_bytes(b"untrusted font")
    with pytest.raises(ValueError, match="checksum"):
        _module().smoke(font)


def test_font_symlink_rejected(tmp_path):
    font = tmp_path / "Inter.ttf"
    font.symlink_to(FONT)
    with pytest.raises(ValueError, match="regular file"):
        _module().smoke(font)


def test_native_roundtrip_embeds_pinned_inter_with_network_denied():
    code = """
import importlib.util,json,socket,sys
def denied(*args,**kwargs):raise AssertionError('Network access forbidden')
socket.create_connection=denied
socket.socket.connect=denied
spec=importlib.util.spec_from_file_location('native_probe',sys.argv[1])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
print(json.dumps(module.smoke(sys.argv[2])))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(HELPER), str(FONT)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    proof = json.loads(result.stdout)
    assert proof["ok"] is True
    assert proof["font_sha256"] == _module().INTER_SHA256
    assert proof["a4_points"] == pytest.approx([595.275591, 841.889764], abs=0.1)
    assert proof["inter_width_points"] == pytest.approx(110.964844, abs=0.01)
    assert proof["pdf_pages"] == proof["xlsx_rows"] == proof["docx_paragraphs"] == proof["pptx_slides"] == 1
    assert set(proof["artifacts"]) == {"reportlab_pdf", "weasy_pdf", "xlsx", "docx", "pptx"}
    assert all(0 < artifact["bytes"] < 1_000_000 for artifact in proof["artifacts"].values())
    assert "http" not in result.stdout and str(ROOT) not in result.stdout
