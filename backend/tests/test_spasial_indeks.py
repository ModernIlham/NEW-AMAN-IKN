"""Verifikasi RENCANA KUERI spasial — IXSCAN, bukan COLLSCAN.

Kenapa perlu test sendiri: `$geoIntersects` TETAP MEMBERI JAWABAN BENAR tanpa
indeks 2dsphere — ia hanya memindai seluruh koleksi. Jadi bug "indeks tak
terpakai" tak akan pernah muncul sebagai hasil salah, hanya sebagai endpoint
deteksi lokasi yang melambat seiring denah bertambah. Satu-satunya cara
menangkapnya adalah membaca rencana kueri.

Test ini butuh MongoDB hidup → otomatis ber-marker `integration` (lihat
tests/conftest.py) sehingga TIDAK ikut `pytest` default maupun CI. Jalankan di
lingkungan yang punya MongoDB:

    cd backend && pytest -m integration tests/test_spasial_indeks.py -v

Semua operasi memakai koleksi SEMENTARA (`spasial_node_uji_indeks`) yang dibuat
dengan definisi indeks yang sama persis seperti indexes.py lalu di-drop —
koleksi `spasial_node` sungguhan tidak pernah disentuh.
"""
import os

import pytest

pymongo = pytest.importorskip("pymongo")

KOLEKSI_UJI = "spasial_node_uji_indeks"
ORDINAL_GEDUNG = 80
SATKER = "999999"


def _kumpulkan_stage(rencana) -> list:
    """Nama semua stage di pohon winningPlan (termasuk cabang inputStage(s))."""
    hasil = []
    if not isinstance(rencana, dict):
        return hasil
    if rencana.get("stage"):
        hasil.append(rencana["stage"])
    for kunci in ("inputStage", "innerStage", "outerStage", "thenStage", "elseStage"):
        hasil.extend(_kumpulkan_stage(rencana.get(kunci)))
    for anak in rencana.get("inputStages") or []:
        hasil.extend(_kumpulkan_stage(anak))
    # MongoDB 7 SBE menaruh rencana klasik di bawah queryPlan.
    hasil.extend(_kumpulkan_stage(rencana.get("queryPlan")))
    return hasil


@pytest.fixture(scope="module")
def koleksi():
    url = os.environ.get("MONGO_URL")
    nama_db = os.environ.get("DB_NAME")
    if not url or not nama_db:
        pytest.skip("MONGO_URL/DB_NAME tidak diset — test rencana kueri dilewati")
    klien = pymongo.MongoClient(url, serverSelectionTimeoutMS=5000)
    try:
        klien.admin.command("ping")
    except Exception as e:  # pragma: no cover - hanya saat MongoDB mati
        pytest.skip(f"MongoDB tak terjangkau: {e}")
    kol = klien[nama_db][KOLEKSI_UJI]
    kol.drop()

    # Definisi indeks HARUS cermin indexes.py — bila di sana berubah, salinan
    # ini ikut diubah, dan test inilah yang membuktikan perubahannya manjur.
    kol.create_index([("geometry", "2dsphere")], name="geometry_2dsphere")
    kol.create_index([("kode_satker", 1), ("ordinal_level", 1)], name="satker_level")
    kol.create_index([("parent_id", 1), ("lantai.ordinal", 1)], name="lantai_ordinal")
    kol.create_index("parent_id", name="parent")

    # Data cukup banyak agar planner tak sekadar memilih COLLSCAN karena koleksi
    # mungil. Poligon berpetak 0,01° di sekitar IKN.
    dok = []
    for i in range(400):
        x = 116.5 + (i % 20) * 0.01
        y = -1.5 + (i // 20) * 0.01
        dok.append({
            "id": f"uji-{i}", "kode_satker": SATKER, "status": "aktif",
            "tipe": "GEDUNG", "ordinal_level": ORDINAL_GEDUNG, "nama": f"Gedung {i}",
            "parent_id": "uji-induk",
            "geometry": {"type": "Polygon", "coordinates": [[
                [x, y], [x + 0.01, y], [x + 0.01, y + 0.01], [x, y + 0.01], [x, y]]]},
        })
    for i in range(40):
        dok.append({
            "id": f"uji-lantai-{i}", "kode_satker": SATKER, "status": "aktif",
            "tipe": "LANTAI", "ordinal_level": 90, "nama": f"Lantai {i}",
            "parent_id": "uji-gedung", "lantai": {"ordinal": i - 3},
        })
    kol.insert_many(dok)
    yield kol
    kol.drop()
    klien.close()


TITIK = {"type": "Point", "coordinates": [116.555, -1.455]}
SCOPE = {"kode_satker": {"$in": [SATKER, "", None]}}


def test_lokasi_di_titik_memakai_indeks_geo(koleksi):
    """Kueri inti "tancap titik → rantai wilayah" wajib lewat indeks 2dsphere."""
    rencana = koleksi.find({
        **SCOPE, "status": "aktif",
        "ordinal_level": {"$lte": ORDINAL_GEDUNG},
        "geometry": {"$geoIntersects": {"$geometry": TITIK}},
    }).sort("ordinal_level", 1).explain()
    stage = _kumpulkan_stage(rencana["queryPlanner"]["winningPlan"])
    assert "IXSCAN" in stage, f"rencana tanpa IXSCAN: {stage}"
    assert "COLLSCAN" not in stage, f"rencana memindai seluruh koleksi: {stage}"


def test_ruangan_di_titik_memakai_indeks(koleksi):
    rencana = koleksi.find({
        **SCOPE, "parent_id": "uji-induk", "tipe": "GEDUNG", "status": "aktif",
        "geometry": {"$geoIntersects": {"$geometry": TITIK}},
    }).explain()
    stage = _kumpulkan_stage(rencana["queryPlanner"]["winningPlan"])
    assert "IXSCAN" in stage, f"rencana tanpa IXSCAN: {stage}"
    assert "COLLSCAN" not in stage, f"rencana memindai seluruh koleksi: {stage}"


def test_geojson_viewport_memakai_indeks_geo(koleksi):
    """bbox peta → $geoIntersects poligon kotak."""
    kotak = {"type": "Polygon", "coordinates": [[
        [116.50, -1.50], [116.70, -1.50], [116.70, -1.30], [116.50, -1.30], [116.50, -1.50]]]}
    rencana = koleksi.find({
        **SCOPE, "status": "aktif",
        "ordinal_level": {"$lte": ORDINAL_GEDUNG},
        "geometry": {"$geoIntersects": {"$geometry": kotak}},
    }).explain()
    stage = _kumpulkan_stage(rencana["queryPlanner"]["winningPlan"])
    assert "IXSCAN" in stage, f"rencana tanpa IXSCAN: {stage}"
    assert "COLLSCAN" not in stage, f"rencana memindai seluruh koleksi: {stage}"


def test_daftar_lantai_terurut_tanpa_sort_memori(koleksi):
    """Switcher lantai mengurutkan `lantai.ordinal`; indeks majemuk
    (parent_id, lantai.ordinal) harus MENYEDIAKAN urutannya, bukan diurut ulang
    di memori — SORT in-memory kena plafon 32 MB pada gedung besar."""
    rencana = koleksi.find({
        **SCOPE, "parent_id": "uji-gedung", "tipe": "LANTAI",
        "status": {"$ne": "dihapus"},
    }).sort("lantai.ordinal", 1).explain()
    stage = _kumpulkan_stage(rencana["queryPlanner"]["winningPlan"])
    assert "IXSCAN" in stage, f"rencana tanpa IXSCAN: {stage}"
    assert "COLLSCAN" not in stage, f"rencana memindai seluruh koleksi: {stage}"
    assert "SORT" not in stage, f"urutan lantai diurut di memori, bukan dari indeks: {stage}"


def test_hasil_geo_benar_bukan_sekadar_cepat(koleksi):
    """Rencana bagus tak ada gunanya bila jawabannya salah — pastikan titik uji
    memang jatuh di petak yang benar (dan urutan koordinat lon-lat tak terbalik)."""
    cocok = list(koleksi.find(
        {**SCOPE, "geometry": {"$geoIntersects": {"$geometry": TITIK}}},
        {"_id": 0, "id": 1}))
    assert len(cocok) == 1, f"titik uji harusnya memotong tepat 1 petak, dapat {len(cocok)}"
