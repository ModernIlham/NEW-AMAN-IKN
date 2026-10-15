"""Server limits apply to new media while untouched legacy data survives."""
import asyncio
import base64
import copy

import pytest
from fastapi import HTTPException
import asset_media_limits as limits
from asset_body_limit import AssetBodyLimitMiddleware

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"synthetic").decode()
PDF = "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.7\nsynthetic").decode()


def item(**changes):
    return {"name": "STNK", "checked": True, "photos": [], "documents": [], **changes}


def test_checklist_counts_new_payload_and_owned_refs():
    limits.validate_checklist([item(photos=[PNG] * 3, documents=[{"name": "doc.pdf", "data": PDF}])])
    for payload in ([item(photos=[PNG] * 4)], [item(documents=[{"data": PDF}] * 2)],
                    [item(name=str(i)) for i in range(51)]):
        with pytest.raises(HTTPException) as error:
            limits.validate_checklist(payload)
        assert error.value.status_code == 413
    with pytest.raises(HTTPException) as foreign:
        limits.validate_checklist([item(documents=[{"gridfs_id": "foreign"}])])
    assert foreign.value.status_code == 400
    owned = [item(documents=[{"name": "owned.pdf", "gridfs_id": "owned"}])]
    limits.validate_checklist(owned, existing=owned)


def test_legacy_files_above_new_limits_survive_reorder_checkbox_and_sentinels(monkeypatch):
    monkeypatch.setattr(limits, "MAX_PDF_BYTES", 2)
    old = [item(checked=False, documents=[{"name": "old.pdf", "data": PDF}], photos=["legacy-bytes"] * 4), item(name="BPKB")]
    changed = copy.deepcopy(list(reversed(old)))
    changed[1]["checked"] = True
    limits.validate_checklist(changed, existing=old)
    lightweight = [item(photos=["__existing__:0"], documents=[{"data": "__existing__:0"}])]
    resolved = limits.resolve_checklist_for_validation(lightweight, old)
    assert resolved[0]["photos"] == ["legacy-bytes"]
    assert resolved[0]["documents"][0]["data"] == PDF
    limits.validate_checklist(resolved, existing=old)
    with pytest.raises(HTTPException):
        limits.validate_checklist([item(documents=[{"data": PDF}])])


def test_payload_byte_caps_magic_and_bson_budget(monkeypatch):
    monkeypatch.setattr(limits, "MAX_PHOTO_BYTES", 2)
    with pytest.raises(HTTPException) as oversize:
        limits.validate_main_photos([PNG])
    assert oversize.value.status_code == 413
    with pytest.raises(HTTPException) as malformed:
        limits.validate_checklist([item(documents=[{"data": {"invalid": True}}])])
    assert malformed.value.status_code == 400
    monkeypatch.setattr(limits, "MAX_CHECKLIST_BSON_BYTES", 100)
    with pytest.raises(HTTPException) as many:
        limits.validate_checklist([item(notes="x" * 5000)])
    assert many.value.status_code == 413


@pytest.mark.parametrize("header,parts,expected", [(b"11", [b"small"], 413), (None, [b"12345", b"678901"], 413),
    (None, [b"12345", b"67890"], 200)])
def test_body_cap_covers_content_length_and_chunked_upload(header, parts, expected):
    called, sent = [], []
    async def app(scope, receive, send):
        called.append((await receive())["body"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    middleware = AssetBodyLimitMiddleware(app)
    middleware.MAX_BODY_BYTES = 10
    messages = [{"type": "http.request", "body": part, "more_body": index < len(parts) - 1} for index, part in enumerate(parts)]
    async def receive():
        return messages.pop(0)
    async def send(value):
        sent.append(value)
    asyncio.run(middleware({"type": "http", "method": "PATCH", "path": "/api/assets/one", "headers":
                           [(b"content-length", header)] if header else []}, receive, send))
    assert sent[0]["status"] == expected
    assert bool(called) is (expected == 200)
    if called:
        assert called[0] == b"".join(parts)


def test_mutation_admission_is_bounded_and_released_after_completion():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        async def app(scope, receive, send):
            await receive()
            entered.set()
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})
        middleware = AssetBodyLimitMiddleware(app)
        middleware.MAX_IN_FLIGHT = 1
        scope = {"type": "http", "method": "PATCH", "path": "/api/assets/a", "headers": []}
        async def receive():
            return {"type": "http.request", "body": b"{}"}
        first_messages, second_messages = [], []
        async def first_send(message): first_messages.append(message)
        async def second_send(message): second_messages.append(message)
        first = asyncio.create_task(middleware(scope, receive, first_send))
        await entered.wait()
        await middleware(scope, receive, second_send)
        assert second_messages[0]["status"] == 429
        assert (b"retry-after", b"1") in second_messages[0]["headers"]
        release.set()
        await first
        assert first_messages[0]["status"] == 200 and middleware.in_flight == 0
    asyncio.run(run())


def test_attachment_reference_classes_cannot_be_substituted():
    owned = [item(photo_gridfs_ids=["photo"], documents=[{"name": "owned.pdf", "gridfs_id": "pdf"}])]
    for changed in ([item(photo_gridfs_ids=["pdf"])], [item(documents=[{"name": "bad.pdf", "gridfs_id": "photo"}])]):
        with pytest.raises(HTTPException) as wrong_kind:
            limits.validate_checklist(changed, existing=owned)
        assert wrong_kind.value.status_code == 400


def test_legacy_budget_cannot_grow_media_in_small_increments(monkeypatch):
    old = [item(photos=[PNG])]
    monkeypatch.setattr(limits, "MAX_CHECKLIST_BSON_BYTES", 10)
    same_media = copy.deepcopy(old)
    same_media[0]["checked"] = False
    limits.validate_checklist(same_media, existing=old)
    more_media = copy.deepcopy(old)
    more_media[0]["photos"].append(PNG)
    with pytest.raises(HTTPException) as grow:
        limits.validate_checklist(more_media, existing=old)
    assert grow.value.status_code == 413
    with pytest.raises(HTTPException) as bad_name:
        limits.resolve_checklist_for_validation([item(name={"bad": True})], old)
    assert bad_name.value.status_code == 400
    monkeypatch.setattr(limits, "ABSOLUTE_ASSET_BSON_BYTES", 100)
    with pytest.raises(HTTPException):
        limits.validate_asset_document({"notes": "x" * 150}, existing={"notes": "x" * 150})


def test_lightweight_photo_sentinel_preserves_reference_only_slot():
    old = [item(photo_gridfs_ids=["owned-photo"], photos=[])]
    resolved = limits.resolve_checklist_for_validation([item(photos=["__existing__:0"])], old)
    assert not any(resolved[0]["photos"])
    assert resolved[0]["photo_gridfs_ids"] == ["owned-photo"]
    limits.validate_checklist(resolved, existing=old)
