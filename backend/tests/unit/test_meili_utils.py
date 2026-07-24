"""Uji logika murni integrasi Meilisearch (bebas jaringan & Mongo).

Di lingkungan test, MEILI_URL/MEILI_MASTER_KEY tidak di-set → fitur nonaktif.
Semua fungsi ber-scope/proyeksi bersifat murni; fungsi async pencarian/sinkron
harus SHORT-CIRCUIT (no-op / None) saat nonaktif tanpa menyentuh jaringan.
"""
import asyncio

import meili_utils as m


# ── Feature flag ────────────────────────────────────────────────────────────
def test_meili_nonaktif_di_test():
    # Tanpa env → nonaktif (tak ada panggilan jaringan di seluruh test).
    assert m.meili_aktif() is False


# ── Proyeksi dokumen ────────────────────────────────────────────────────────
def test_proyeksi_aset_hanya_field_terindeks():
    doc = {
        "id": "a1", "asset_code": "3.05.01", "asset_name": "Meja",
        "activity_id": "keg-1",
        # Field sensitif / non-searchable TIDAK boleh ikut:
        "purchase_price": 1000000, "pengguna_nip": "1990xxxx",
        "photos": ["base64..."], "notes": None, "brand": "",
    }
    out = m.proyeksi_dokumen("assets", doc)
    assert out["id"] == "a1"
    assert out["asset_code"] == "3.05.01"
    assert out["asset_name"] == "Meja"
    assert out["activity_id"] == "keg-1"          # filterable scope
    # None & string kosong dipangkas dari searchable:
    assert "notes" not in out
    assert "brand" not in out
    # Field sensitif tidak diindeks:
    assert "purchase_price" not in out
    assert "pengguna_nip" not in out
    assert "photos" not in out


def test_proyeksi_surat_kode_satker_selalu_ada():
    # kode_satker hilang → dinormalkan ke "" (agar filter IN [kode, ""] cocok).
    out = m.proyeksi_dokumen("surat", {"id": "s1", "perihal": "Undangan"})
    assert out == {"id": "s1", "perihal": "Undangan", "kode_satker": ""}
    # kode_satker terisi (angka) → string.
    out2 = m.proyeksi_dokumen("surat", {"id": "s2", "kode_satker": "527", "nomor": "01"})
    assert out2["kode_satker"] == "527"
    assert out2["nomor"] == "01"


def test_proyeksi_persediaan():
    out = m.proyeksi_dokumen("persediaan", {
        "id": "p1", "kode_barang": "1010301", "nama_barang": "Kertas A4",
        "stok": 50, "batches": [{"qty": 50}], "kode_satker": None})
    assert out["id"] == "p1"
    assert out["kode_barang"] == "1010301"
    assert out["nama_barang"] == "Kertas A4"
    assert out["kode_satker"] == ""   # None → ""
    # stok/batches bukan field terindeks:
    assert "stok" not in out and "batches" not in out


def test_proyeksi_invalid():
    assert m.proyeksi_dokumen("assets", {"asset_name": "tanpa id"}) is None
    assert m.proyeksi_dokumen("assets", {"id": "  "}) is None
    assert m.proyeksi_dokumen("koleksi_tak_dikenal", {"id": "x"}) is None
    assert m.proyeksi_dokumen("assets", None) is None


# ── Pembangun filter Meili ──────────────────────────────────────────────────
def test_kutip_escape():
    assert m._kutip("527") == '"527"'
    assert m._kutip('a"b') == '"a\\"b"'
    assert m._kutip("a\\b") == '"a\\\\b"'
    assert m._kutip(None) == '""'


def test_filter_in():
    assert m._filter_in("kode_satker", ["527", ""]) == 'kode_satker IN ["527", ""]'
    assert m._filter_in("activity_id", ["k1"]) == 'activity_id IN ["k1"]'


def test_filter_satker_dok():
    # User terikat → IN [kode, ""] (termasuk dokumen era-lama tanpa kode).
    assert m._filter_satker_dok({"kode_satker": "527"}) == 'kode_satker IN ["527", ""]'
    # Super-admin lintas-satker → tanpa filter.
    assert m._filter_satker_dok({"kode_satker": ""}) is None
    assert m._filter_satker_dok({}) is None
    assert m._filter_satker_dok(None) is None


# ── Short-circuit saat nonaktif (tanpa jaringan) ────────────────────────────
def test_cari_id_nonaktif_return_none():
    run = asyncio.run
    assert run(m.cari_id_aset({"kode_satker": "527"}, "", "meja")) is None
    assert run(m.cari_id_aset({}, "keg-1", "meja")) is None
    assert run(m.cari_id_surat({"kode_satker": "527"}, "undangan")) is None
    assert run(m.cari_id_persediaan({"kode_satker": "527"}, "kertas")) is None


def test_jadwalkan_nonaktif_noop():
    # Nonaktif → no-op sinkron; TIDAK melempar & tidak butuh event loop.
    assert m.jadwalkan_sync("assets", {"id": "a1", "asset_name": "Meja"}) is None
    assert m.jadwalkan_hapus("assets", "a1") is None
    assert m.jadwalkan_sync("surat", {"id": "s1"}) is None


def test_reindex_nonaktif():
    run = asyncio.run
    out = run(m.reindex_koleksi("assets"))
    assert out["terindeks"] == 0 and out["aktif"] is False
    st = run(m.status_indeks())
    assert st["aktif"] is False


# ── Registry indeks konsisten ───────────────────────────────────────────────
def test_registry_indeks():
    for koleksi, cfg in m.INDEKS.items():
        assert cfg["key"] == "id"
        assert cfg["uid"].startswith("aman_")
        assert cfg["searchable"] and cfg["filterable"]
    # Scope satker wajib bisa difilter:
    assert "activity_id" in m.INDEKS["assets"]["filterable"]
    assert "kode_satker" in m.INDEKS["surat"]["filterable"]
    assert "kode_satker" in m.INDEKS["persediaan"]["filterable"]
