"""Uji "Satker Aktif" (act-as-satker) untuk super-admin.

Titik kritis-keamanan: header X-Satker-Aktif hanya boleh berpengaruh untuk
super-admin PUSAT; user yang terikat satker WAJIB diabaikan (tak boleh
menyamar). Otoritas super-admin harus tetap terjaga saat bertindak sebagai
satker (agar tak terkunci dari backup/restore).
"""
import asyncio

import auth_utils as au


def _run(coro):
    return asyncio.run(coro)


def _mock_satker_ada(monkeypatch, kode_terdaftar):
    async def fake(kode):
        return kode in kode_terdaftar
    monkeypatch.setattr(au, "_satker_terdaftar", fake)


def test_superadmin_pusat_act_as_menstempel_satker(monkeypatch):
    _mock_satker_ada(monkeypatch, {"527"})
    user = {"id": "u1", "role": "admin", "kode_satker": ""}
    hasil = _run(au._terapkan_satker_aktif(user, "527"))
    # kode_satker tersuntik → scoping & stempel ikut satker 527
    assert hasil["kode_satker"] == "527"
    assert hasil["_satker_aktif"] == "527"
    # …tetapi OTORITAS tetap super-admin
    assert au.is_super_admin(hasil) is True


def test_user_terikat_satker_TIDAK_bisa_menyamar(monkeypatch):
    """Keamanan: admin satker A mengirim X-Satker-Aktif=B → DIABAIKAN."""
    _mock_satker_ada(monkeypatch, {"A", "B"})
    user = {"id": "u2", "role": "admin", "kode_satker": "A"}
    hasil = _run(au._terapkan_satker_aktif(user, "B"))
    assert hasil["kode_satker"] == "A"        # tetap A, tak berubah
    assert "_satker_aktif" not in hasil
    assert au.is_super_admin(hasil) is False


def test_kode_tak_terdaftar_diabaikan_bukan_ditolak(monkeypatch):
    _mock_satker_ada(monkeypatch, {"527"})
    user = {"id": "u3", "role": "admin", "kode_satker": ""}
    hasil = _run(au._terapkan_satker_aktif(user, "999"))
    assert hasil["kode_satker"] == ""         # jatuh ke lintas-satker biasa
    assert "_satker_aktif" not in hasil
    assert au.is_super_admin(hasil) is True    # tetap super-admin lintas satker


def test_tanpa_header_tetap_lintas_satker(monkeypatch):
    _mock_satker_ada(monkeypatch, {"527"})
    user = {"id": "u4", "role": "admin", "kode_satker": ""}
    hasil = _run(au._terapkan_satker_aktif(user, ""))
    assert hasil["kode_satker"] == ""
    assert au.is_super_admin(hasil) is True


def test_viewer_tak_terpengaruh(monkeypatch):
    _mock_satker_ada(monkeypatch, {"527"})
    user = {"id": "u5", "role": "viewer", "kode_satker": ""}
    hasil = _run(au._terapkan_satker_aktif(user, "527"))
    assert hasil["kode_satker"] == ""         # bukan admin → tak act-as


def test_is_super_admin_hormati_penanda_asli():
    # Dokumen biasa (tanpa penanda) dihitung dari role+kode_satker.
    assert au.is_super_admin({"role": "admin", "kode_satker": ""}) is True
    assert au.is_super_admin({"role": "admin", "kode_satker": "527"}) is False
    # Penanda _super_admin_asli MENANG (sesi act-as).
    assert au.is_super_admin(
        {"role": "admin", "kode_satker": "527", "_super_admin_asli": True}) is True


def test_field_efemeral_dibuang(monkeypatch):
    """KEAMANAN (temuan tinjauan): dokumen user dari DB (mis. hasil restore
    backup pihak luar) TAK BOLEH menyelundupkan `_super_admin_asli`.
    `_buang_efemeral` membuangnya sehingga is_super_admin tak teracuni."""
    poisoned = {
        "id": "x", "role": "viewer", "kode_satker": "A",
        "_super_admin_asli": True, "_satker_aktif": "Z", "_kode_satker_asli": "",
    }
    bersih = au._buang_efemeral(dict(poisoned))
    assert "_super_admin_asli" not in bersih
    assert "_satker_aktif" not in bersih
    assert "_kode_satker_asli" not in bersih
    # Tanpa penanda, viewer bukan super-admin — backdoor gagal.
    assert au.is_super_admin(bersih) is False
