"""Bundled font provenance, corruption handling and report escaping."""

import hashlib
import json

import pytest

import report_fonts


def test_original_font_and_license_match_release_provenance():
    metadata = json.loads((report_fonts.FONT_DIRECTORY / "metadata.json").read_text())
    font = (report_fonts.FONT_DIRECTORY / metadata["file"]).read_bytes()
    license_text = (report_fonts.FONT_DIRECTORY / metadata["license_file"]).read_bytes()
    assert len(font) == metadata["bytes"] == 876576
    assert hashlib.sha256(font).hexdigest() == metadata["sha256"] == report_fonts.INTER_SHA256
    assert hashlib.sha256(license_text).hexdigest() == metadata["license_sha256"] == report_fonts.INTER_LICENSE_SHA256
    assert metadata["upstream_commit"] == "66928797f271fed5ee428544e7229685e2d90127"
    assert metadata["modified"] is False
    assert b"SIL OPEN FONT LICENSE Version 1.1" in license_text
    assert b"Copyright 2020 The Inter Project Authors" in license_text


@pytest.mark.parametrize("filename", ["Inter.ttf", "OFL.txt"])
def test_corrupted_release_font_or_license_fails_explicitly(monkeypatch, tmp_path, filename):
    for name in ("Inter.ttf", "OFL.txt"):
        content = (report_fonts.FONT_DIRECTORY / name).read_bytes()
        (tmp_path / name).write_bytes(content + (b"corrupt" if name == filename else b""))
    report_fonts.report_font_css.cache_clear()
    monkeypatch.setattr(report_fonts, "FONT_DIRECTORY", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="release checksum"):
            report_fonts.report_font_css()
    finally:
        report_fonts.report_font_css.cache_clear()


def test_shared_jinja_font_does_not_disable_user_field_escaping():
    from routes.reports import _jinja_env

    html = _jinja_env().from_string(
        "<style>{{ report_font_css() }}</style><h1>{{ name }}</h1>"
    ).render(name='<script src="https://untrusted.invalid/evil.js"></script>')
    assert 'src: url("data:font/ttf;base64,' in html
    assert "&lt;script" in html and "<script" not in html
    assert "file://" not in html
