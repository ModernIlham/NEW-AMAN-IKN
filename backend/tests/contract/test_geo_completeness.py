"""Geo exports are complete at the budget and reject overflow before rendering."""
import io
import uuid
import zipfile
from xml.etree import ElementTree

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.mark.parametrize("format", ["kml", "kmz", "shp"])
@pytest.mark.parametrize("count", [1, 2, 3])
async def test_actual_geo_renderers_are_complete_or_explicitly_reject(contract, monkeypatch, format, count):
    from routes import exports
    monkeypatch.setattr(exports, "MAX_GEO_FEATURES", 2)
    category = "geo-complete-" + uuid.uuid4().hex
    rows = [{"id": f"{category}-{i}", "asset_code": category, "NUP": str(i), "asset_name": f"Point{i}",
        "category": category, "activity_id": "contract-activity-a", "koordinat_latitude": "-1.2",
        "koordinat_longitude": "116.8", "photos": "malformed legacy", "photo_gridfs_ids": None}
        for i in range(count)]
    # Invalid coordinates and a foreign satker must not consume valid-point budget.
    rows.extend([{"id": category + "-invalid", "asset_code": category, "NUP": "invalid",
        "category": category, "activity_id": "contract-activity-a", "koordinat_latitude": "NaN", "koordinat_longitude": "116.8"},
        {"id": category + "-foreign", "asset_code": category, "NUP": "foreign", "category": category,
         "activity_id": "contract-activity-b", "koordinat_latitude": "-1.2", "koordinat_longitude": "116.8"}])
    await contract.db.assets.insert_many(rows)
    response = await contract.http.get("/api/export/geo", headers=contract.headers["a"], params={"format": format, "category": category})
    if count > 2:
        assert response.status_code == 413, response.text
        assert response.headers["content-type"].startswith("application/json")
        return
    assert response.status_code == 200, response.text[:300]
    if format in {"kml", "kmz"}:
        data = response.content
        if format == "kmz":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                data = archive.read("doc.kml")
        root = ElementTree.fromstring(data)
        assert len(root.findall(".//{http://www.opengis.net/kml/2.2}Placemark")) == count
    else:
        import shapefile
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            reader = shapefile.Reader(shp=io.BytesIO(archive.read("peta_aset.shp")),
                shx=io.BytesIO(archive.read("peta_aset.shx")), dbf=io.BytesIO(archive.read("peta_aset.dbf")))
            assert len(reader.shapes()) == count


async def test_geo_selection_overflow_rejects_instead_of_silent_subset(contract, monkeypatch):
    from routes import exports
    monkeypatch.setattr(exports, "MAX_GEO_SELECTED_IDS", 2)
    response = await contract.http.get("/api/export/geo", headers=contract.headers["a"], params={"ids": "one,two,three"})
    assert response.status_code == 413, response.text
