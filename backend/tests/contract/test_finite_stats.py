"""Legacy NaN and Infinity cannot poison HTTP JSON or numeric totals."""
from decimal import Decimal
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_stats_and_analytics_reject_nonfinite_source_as_zero(contract):
    activity = "finite-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a"})
    values = ["NaN", "Infinity", "-Infinity", float("nan"), float("inf"), "abc", None, "",
              "2", 10, "9007199254740992.01", "9007199254740992.02"]
    await contract.db.assets.insert_many([{"id": f"{activity}-{i}", "asset_code": f"{activity}-{i}",
        "activity_id": activity, "NUP": "1", "category": "finite", "eselon1": "finite", "purchase_price": value,
        "asset_name": "Finite", "status": "Aktif"} for i, value in enumerate(values)])
    stats = await contract.http.get("/api/assets/stats", headers=contract.headers["a"], params={"activity_id": activity})
    assert stats.status_code == 200, stats.text
    expected = Decimal("18014398509481996.03")
    assert Decimal(stats.json()["total_value_exact"]) == expected
    assert stats.json()["total_assets"] == len(values)
    analytics = await contract.http.get("/api/assets/analytics", headers=contract.headers["a"], params={"activity_id": activity})
    assert analytics.status_code == 200, analytics.text
    for field in ("by_category", "by_eselon"):
        assert Decimal(analytics.json()[field][0]["value_exact"]) == expected
    assert "NaN" not in stats.text and "Infinity" not in analytics.text

    activities = await contract.http.get("/api/inventory-activities", headers=contract.headers["a"])
    assert activities.status_code == 200, activities.text
    listed = next(row for row in activities.json() if row["id"] == activity)
    assert Decimal(listed["total_value_exact"]) == expected
    linked = await contract.http.post("/api/inventory-activities", headers=contract.headers["a"], json={
        "nomor_surat": "S-" + activity, "nama_kegiatan": "Kegiatan linked finite", "kode_satker": "99000a",
        "nama_satker": "Satker sintetis a", "asset_ids": [f"{activity}-{i}" for i in range(len(values))]})
    assert linked.status_code == 200, linked.text
    assert Decimal(linked.json()["total_value_exact"]) == expected
    detail = await contract.http.get("/api/inventory-activities/" + linked.json()["id"], headers=contract.headers["a"])
    assert detail.status_code == 200, detail.text
    assert Decimal(detail.json()["total_value_exact"]) == expected
    recap = await contract.http.get(f"/api/inventory-activities/{activity}/rekapitulasi", headers=contract.headers["a"])
    assert recap.status_code == 200, recap.text
    assert "NaN" not in recap.text and "Infinity" not in recap.text


@pytest.mark.parametrize("price", ["1e6144", "1e-6176"])
async def test_decimal_values_beyond_json_float_range_remain_exact_text(contract, price):
    activity = "finite-large-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a"})
    await contract.db.assets.insert_one({"id": activity + "-a", "asset_code": activity, "NUP": "1",
        "activity_id": activity, "purchase_price": price, "category": "large"})
    stats = await contract.http.get("/api/assets/stats", headers=contract.headers["a"], params={"activity_id": activity})
    assert stats.status_code == 200, stats.text
    assert isinstance(stats.json()["total_value"], str)
    assert Decimal(stats.json()["total_value"]) == Decimal(price)


async def test_aggregate_overflow_never_becomes_zero_on_linked_create(contract):
    activity = "finite-overflow-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a"})
    ids = [activity + "-1", activity + "-2"]
    await contract.db.assets.insert_many([{"id": aid, "asset_code": aid, "NUP": "1", "activity_id": activity,
        "purchase_price": "9e6144"} for aid in ids])
    try:
        stats = await contract.http.get("/api/assets/stats", headers=contract.headers["a"], params={"activity_id": activity})
        assert stats.status_code == 413, stats.text
        linked = await contract.http.post("/api/inventory-activities", headers=contract.headers["a"], json={
            "nomor_surat": "S-" + activity, "nama_kegiatan": "Overflow ditolak", "kode_satker": "99000a", "nama_satker": "Satker sintetis a", "asset_ids": ids})
        assert linked.status_code == 413, linked.text
        assert not await contract.db.inventory_activities.find_one({"nomor_surat": "S-" + activity})
    finally:
        await contract.db.assets.delete_many({"activity_id": activity})
        await contract.db.inventory_activities.delete_one({"id": activity})
