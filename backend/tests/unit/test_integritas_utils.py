"""Uji logika murni integritas identitas aset (§5A Prinsip 1, #261)."""
from integritas_utils import FIELD_IDENTITAS, identitas_drift


def _snap(**over):
    base = {"asset_code": "3050104001", "NUP": "12", "asset_name": "Laptop"}
    base.update(over)
    return base


def test_konsisten_tak_ada_drift():
    assert identitas_drift(_snap(), _snap()) == {}


def test_satu_field_basi():
    drift = identitas_drift(_snap(NUP="12"), _snap(NUP="15"))
    assert drift == {"NUP": {"snapshot": "12", "master": "15"}}


def test_banyak_field_basi():
    drift = identitas_drift(
        _snap(asset_code="3050104001", asset_name="Laptop"),
        _snap(asset_code="3050104002", asset_name="Notebook"))
    assert set(drift) == {"asset_code", "asset_name"}
    assert drift["asset_code"] == {"snapshot": "3050104001", "master": "3050104002"}


def test_normalisasi_none_kosong_spasi_tak_drift_palsu():
    # None vs "" vs "  X  " → dinormalisasi (strip), tak dianggap basi
    snap = {"asset_code": "  3050104001  ", "NUP": None, "asset_name": "Laptop"}
    master = {"asset_code": "3050104001", "NUP": "", "asset_name": "Laptop"}
    assert identitas_drift(snap, master) == {}


def test_snapshot_atau_master_kosong_kembalikan_kosong():
    # master hilang/kosong → {} (kasus 'aset_master_hilang' ditangani pemanggil)
    assert identitas_drift(_snap(), None) == {}
    assert identitas_drift(_snap(), {}) == {}
    assert identitas_drift(None, _snap()) == {}


def test_field_identitas_tiga_kolom():
    assert FIELD_IDENTITAS == ("asset_code", "NUP", "asset_name")


# ── Deteksi drift untuk daftar aset (pemindahtanganan) — §5A gap #8 slice 2 (#263) ──
from integritas_utils import drift_identitas_daftar


def test_daftar_semua_konsisten():
    aset = [_snap(asset_id="a1"), _snap(asset_id="a2")]
    master = {"a1": _snap(), "a2": _snap()}
    assert drift_identitas_daftar(aset, master) == []


def test_daftar_snapshot_basi():
    aset = [_snap(asset_id="a1", NUP="12")]
    master = {"a1": _snap(NUP="99")}
    out = drift_identitas_daftar(aset, master)
    assert len(out) == 1
    assert out[0]["asset_id"] == "a1" and out[0]["masalah"] == "snapshot_basi"
    assert out[0]["drift"]["NUP"] == {"snapshot": "12", "master": "99"}


def test_daftar_master_hilang():
    aset = [{"asset_id": "a9", "asset_code": "30", "NUP": "1", "asset_name": "X"}]
    out = drift_identitas_daftar(aset, {})           # master_by_id kosong
    assert len(out) == 1
    assert out[0]["masalah"] == "aset_master_hilang"
    assert out[0]["snapshot"] == {"asset_code": "30", "NUP": "1", "asset_name": "X"}


def test_daftar_campuran_dan_kosong():
    assert drift_identitas_daftar([], {"a1": _snap()}) == []
    assert drift_identitas_daftar(None, {}) == []
    aset = [_snap(asset_id="ok"), _snap(asset_id="basi", asset_name="Lama"),
            {"asset_id": "hilang"}]
    master = {"ok": _snap(), "basi": _snap(asset_name="Baru")}
    out = drift_identitas_daftar(aset, master)
    masalah = {t["asset_id"]: t["masalah"] for t in out}
    assert masalah == {"basi": "snapshot_basi", "hilang": "aset_master_hilang"}


# ── Ringkasan hitungan masalah — §5A gap #8 slice 3 (#264) ──
from integritas_utils import hitung_masalah


def test_hitung_masalah():
    temuan = [
        {"asset_id": "a", "masalah": "snapshot_basi"},
        {"asset_id": "b", "masalah": "aset_master_hilang"},
        {"asset_id": "c", "masalah": "snapshot_basi"},
    ]
    assert hitung_masalah(temuan) == {"snapshot_basi": 2, "aset_master_hilang": 1}


def test_hitung_masalah_kosong_dan_aman():
    assert hitung_masalah([]) == {}
    assert hitung_masalah(None) == {}
    # entri tanpa 'masalah' diabaikan
    assert hitung_masalah([{"asset_id": "x"}, {}]) == {}


# ── Temuan identitas satu record (jadwal_pemeliharaan) — §5A gap #8 slice 4 (#265) ──
from integritas_utils import drift_identitas_tunggal


def test_tunggal_konsisten_none():
    assert drift_identitas_tunggal(_snap(), _snap()) is None


def test_tunggal_snapshot_basi():
    t = drift_identitas_tunggal(_snap(NUP="12"), _snap(NUP="99"))
    assert t["masalah"] == "snapshot_basi"
    assert t["drift"]["NUP"] == {"snapshot": "12", "master": "99"}


def test_tunggal_master_hilang():
    t = drift_identitas_tunggal(
        {"asset_code": "30", "NUP": "1", "asset_name": "X"}, None)
    assert t["masalah"] == "aset_master_hilang"
    assert t["snapshot"] == {"asset_code": "30", "NUP": "1", "asset_name": "X"}
    # master {} kosong → juga dianggap hilang
    assert drift_identitas_tunggal(_snap(), {})["masalah"] == "aset_master_hilang"


# ── Ringkasan gabungan lintas-cek (kapstone /integritas/ringkasan) — §5A gap #8 (#266) ──
from integritas_utils import gabung_temuan_integritas


def test_gabung_total_dan_per_masalah():
    bagian = [
        {"register": "usulan_penghapusan", "jumlah": 3,
         "per_masalah": {"snapshot_basi": 2, "aset_master_hilang": 1}},
        {"register": "kodefikasi_aset", "jumlah": 2,
         "per_masalah": {"golongan_tak_terdaftar": 2}},
        {"register": "jadwal_pemeliharaan", "jumlah": 0, "per_masalah": {}},
    ]
    r = gabung_temuan_integritas(bagian)
    assert r["total_temuan"] == 5
    assert r["jumlah_cek"] == 3
    assert r["jumlah_cek_bermasalah"] == 2      # jadwal (0) tak dihitung bermasalah
    assert r["per_masalah"] == {"snapshot_basi": 2, "aset_master_hilang": 1,
                                "golongan_tak_terdaftar": 2}
    assert r["bagian"] == bagian                 # diteruskan apa adanya


def test_gabung_masalah_sama_dijumlah_lintas_cek():
    bagian = [
        {"register": "pemindahtanganan", "jumlah": 1,
         "per_masalah": {"snapshot_basi": 1}},
        {"register": "psp", "jumlah": 2,
         "per_masalah": {"snapshot_basi": 2}},
    ]
    r = gabung_temuan_integritas(bagian)
    assert r["total_temuan"] == 3
    assert r["per_masalah"] == {"snapshot_basi": 3}


def test_gabung_kosong_dan_aman():
    r = gabung_temuan_integritas([])
    assert r == {"total_temuan": 0, "per_masalah": {}, "jumlah_cek": 0,
                 "jumlah_cek_bermasalah": 0, "bagian": []}
    assert gabung_temuan_integritas(None)["total_temuan"] == 0
    # entri tanpa 'per_masalah'/'jumlah' tak bikin error
    r2 = gabung_temuan_integritas([{"register": "x"}])
    assert r2["total_temuan"] == 0 and r2["jumlah_cek"] == 1
