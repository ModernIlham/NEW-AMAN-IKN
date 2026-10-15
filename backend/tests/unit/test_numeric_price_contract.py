"""Monetary reader domain and exact bounds, independently from database syntax."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from asset_sorting import harga_desimal, batas_harga, urutkan_harga_aset
from routes.assets import build_asset_search_query
from routes.reports import filter_laporan_dari_map


@pytest.mark.parametrize("invalid", [None, "", " ", "abc", "Rp 2.000", "NaN", "Infinity", True, "1e9999"])
def test_invalid_historical_prices_are_zero(invalid):
    assert harga_desimal(invalid) == 0


@pytest.mark.parametrize("value", ["-1", "2", "10", "100", "9007199254740992.02", "0.01", " 10.0 ", "1e20"])
def test_price_domain_keeps_exact_finite_decimal(value):
    assert harga_desimal(value) == Decimal(value)


def test_price_ties_keep_id_ascending_in_both_directions():
    rows = [{"id": "b", "purchase_price": "10"}, {"id": "a", "purchase_price": 10},
            {"id": "c", "purchase_price": "2"}]
    assert [r["id"] for r in urutkan_harga_aset(list(rows), "price_asc")] == ["c", "a", "b"]
    assert [r["id"] for r in urutkan_harga_aset(list(rows), "price_desc")] == ["a", "b", "c"]


def test_bound_zero_and_missing_are_distinct_and_invalid_ranges_rejected():
    assert batas_harga(None) is None
    assert batas_harga(0).to_decimal() == 0
    assert len(build_asset_search_query(price_max=0)["$expr"]["$and"]) == 1
    assert len(build_asset_search_query(price_min=0)["$expr"]["$and"]) == 1
    with pytest.raises(HTTPException) as error:
        build_asset_search_query(price_min=1, price_max=0)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException):
        batas_harga("NaN")


def test_pdf_filter_preserves_zero_and_large_decimal():
    query = filter_laporan_dari_map({"price_min": "9007199254740992.01", "price_max": "9007199254740992.02"}).query
    comparisons = query["$expr"]["$and"]
    assert comparisons[0]["$gte"][1].to_decimal() == Decimal("9007199254740992.01")
    assert comparisons[1]["$lte"][1].to_decimal() == Decimal("9007199254740992.02")
    assert filter_laporan_dari_map({"price_min": 0, "price_max": 0}).query
