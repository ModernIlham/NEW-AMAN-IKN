"""Exact NUP filtering must narrow the source dataset before pagination."""
import asyncio
from unittest.mock import AsyncMock

import mongomock
import pytest
from fastapi import HTTPException

import routes.assets as ra


@pytest.mark.parametrize("query_nup", ["1", "001"])
def test_exact_nup_matches_legacy_numeric_and_zero_padded_text_only(query_nup):
    collection = mongomock.MongoClient().db.assets
    collection.insert_many([
        {"id": "text", "NUP": "1", "asset_name": "Laptop"},
        {"id": "number", "NUP": 1, "asset_name": "Laptop"},
        {"id": "padded", "NUP": "0001", "asset_name": "Laptop"},
        {"id": "eleven", "NUP": "11", "asset_name": "Laptop"},
        {"id": "price", "NUP": "101", "asset_name": "Laptop 1", "purchase_price": 1},
        {"id": "array", "NUP": [1, "1"], "asset_name": "Laptop"},
        {"id": "other-name", "NUP": "1", "asset_name": "Chair"},
    ])
    q = ra.build_asset_search_query(search="Laptop", nup=query_nup)
    assert {a["id"] for a in collection.find(q)} == {"text", "number", "padded"}


@pytest.mark.parametrize("value", ["abc", "-1", "1.5", "1$", "1 " * 21, "1" * 21])
def test_invalid_nup_does_not_turn_into_an_unfiltered_search(value):
    with pytest.raises(HTTPException) as error:
        ra.build_asset_search_query(nup=value)
    assert error.value.status_code == 400


def test_long_text_nup_does_not_overflow_mongo_int64():
    from bson import BSON
    q = ra.build_asset_search_query(nup="9" * 20)
    BSON.encode(q)
    assert len(q["$and"][0]["$or"]) == 1


@pytest.mark.parametrize("nup,complete", [("1", False), ("", True)])
def test_picker_and_exact_nup_do_not_truncate_using_search_index(monkeypatch, nup, complete):
    monkeypatch.setattr(ra, "cari_id_aset", AsyncMock(return_value=["first-only"]))
    monkeypatch.setattr(ra, "pastikan_akses_kegiatan_id", AsyncMock())
    monkeypatch.setattr(ra, "scope_query_aset", AsyncMock(side_effect=lambda _user, query: query))
    query = asyncio.run(ra.kueri_aset_terlihat({}, search="Laptop", nup=nup, pencarian_lengkap=complete))
    ra.cari_id_aset.assert_not_awaited()
    assert "id" not in query
