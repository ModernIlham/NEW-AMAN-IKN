"""Meili HTTP submission is not acknowledgement, including async create errors."""
import asyncio
from types import SimpleNamespace

import pytest
import meili_utils as m


def response(value):
    return SimpleNamespace(json=lambda: value)


def test_submit_waits_until_index_task_succeeded(monkeypatch):
    calls = []
    async def req(method, path, **kwargs):
        calls.append((method, path))
        if method == "PUT":
            return response({"taskUid": 42})
        return response({"status": "processing" if len(calls) == 2 else "succeeded"})
    monkeypatch.setattr(m, "_req", req)
    result = asyncio.run(m._submit("PUT", "/indexes/aman_assets/documents", json=[{"id": "a"}]))
    assert result["status"] == "succeeded"
    assert calls == [("PUT", "/indexes/aman_assets/documents"), ("GET", "/tasks/42"), ("GET", "/tasks/42")]


def test_successful_submission_with_failed_task_is_not_success(monkeypatch):
    async def req(method, path, **kwargs):
        return response({"taskUid": 7} if method == "PUT" else {
            "status": "failed", "error": {"code": "invalid_document_id"}})
    monkeypatch.setattr(m, "_req", req)
    with pytest.raises(m.MeiliTaskError) as failure:
        asyncio.run(m._submit("PUT", "/documents", json=[{"id": "bad"}]))
    assert failure.value.code == "invalid_document_id"


def test_existing_index_task_still_configures_settings(monkeypatch):
    monkeypatch.setattr(m, "meili_aktif", lambda: True)
    monkeypatch.setattr(m, "INDEKS", {"assets": m.INDEKS["assets"]})
    calls = []
    async def req(method, path, **kwargs):
        calls.append((method, path))
        if method == "POST":
            return response({"taskUid": 1})
        if method == "PATCH":
            return response({"taskUid": 2})
        return response({"status": "failed", "error": {"code": "index_already_exists"}}
                        if path.endswith("/1") else {"status": "succeeded"})
    monkeypatch.setattr(m, "_req", req)
    asyncio.run(m.pastikan_indeks())
    assert ("PATCH", "/indexes/aman_assets/settings") in calls
    assert calls[-1] == ("GET", "/tasks/2")
