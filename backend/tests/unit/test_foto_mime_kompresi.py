"""Hasil kompresi tetap dapat dibuka dengan Content-Type yang benar."""
import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from starlette.requests import Request

from routes import assets


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,mime", [("WEBP", "image/webp"), ("PNG", "image/png"), ("JPEG", "image/jpeg")])
async def test_checklist_mime_dari_bita_dan_etag_versi(monkeypatch, fmt, mime):
    stream = io.BytesIO()
    Image.new("RGB", (20, 30), "blue").save(stream, format=fmt)
    raw = stream.getvalue()
    owner = {"activity_id": "kegiatan", "version": 8,
             "document_checklist": [{"photos": ["data:image/jpeg;base64," + base64.b64encode(raw).decode()]}]}
    monkeypatch.setattr(assets, "db", SimpleNamespace(assets=SimpleNamespace(find_one=AsyncMock(return_value=owner))))
    access = AsyncMock()
    monkeypatch.setattr(assets, "pastikan_akses_aset", access)
    request = Request({"type": "http", "headers": []})
    response = await assets.get_asset_checklist_photo("aset", 0, 0, request, {"id": "user"})
    assert response.body == raw
    assert response.headers["content-type"] == mime
    assert response.headers["etag"] == '"cl-aset-0-p0-v8"'
    access.assert_awaited_once()


def test_budget_kuota_tidak_diulang_oleh_restore_reset():
    from backup_utils import collections_from_backup, collections_to_reset
    assert "tinify_budget" not in collections_to_reset(["tinify_budget", "assets"])
    assert "tinify_budget" not in collections_from_backup(["tinify_budget.json", "assets.json"])
