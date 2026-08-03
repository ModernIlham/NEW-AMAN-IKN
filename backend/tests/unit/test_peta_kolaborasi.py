"""Uji helper MURNI peta kolaboratif + token peta (tanpa DB/jaringan).

Fokus GERBANG AKSES: siapa boleh melihat/berkontribusi saat aktif vs setelah
masa tayang habis (tamu vs operator/admin satker terkait), dan token typ=peta.
"""
import asyncio
from datetime import datetime, timezone, timedelta


def _iso(delta_hours):
    return (datetime.now(timezone.utc) + timedelta(hours=delta_hours)).isoformat()


def _iso_wib(delta_hours):
    """Instant relatif SEKARANG, tapi dinyatakan dalam offset +07:00 (WIB)."""
    dt = datetime.now(timezone.utc) + timedelta(hours=delta_hours)
    return dt.astimezone(timezone(timedelta(hours=7))).isoformat()


def test_parse_coord():
    from routes.peta_kolaborasi import _parse_coord
    assert _parse_coord("1,5") == 1.5          # desimal koma
    assert _parse_coord("-6.2") == -6.2
    assert _parse_coord(" 106.8 ") == 106.8
    assert _parse_coord("") is None
    assert _parse_coord("abc") is None
    assert _parse_coord(None) is None


def test_kedaluwarsa():
    from routes.peta_kolaborasi import _kedaluwarsa
    assert _kedaluwarsa({"berlaku_sampai": _iso(-1)}) is True    # lampau
    assert _kedaluwarsa({"berlaku_sampai": _iso(+1)}) is False   # mendatang
    assert _kedaluwarsa({"berlaku_sampai": ""}) is False         # tak diset → tak habis


def test_kedaluwarsa_offset_non_utc():
    """Offset zona waktu (WIB +07:00) dihormati secara kronologis, bukan
    perbandingan string leksikografis (regresi temuan keamanan)."""
    from routes.peta_kolaborasi import _kedaluwarsa
    # Instant yang SAMA di WIB: 1 jam lampau → habis; 1 jam mendatang → belum.
    assert _kedaluwarsa({"berlaku_sampai": _iso_wib(-1)}) is True
    assert _kedaluwarsa({"berlaku_sampai": _iso_wib(+1)}) is False
    # Naif (tanpa tz) diperlakukan UTC.
    assert _kedaluwarsa({"berlaku_sampai": "2020-01-01T00:00:00"}) is True


def test_hitung_berlaku_plafon_base():
    """plafon_base (mis. created_at) menjepit masa tayang agar token yang sudah
    tersebar tak kedaluwarsa lebih dulu (regresi temuan keamanan)."""
    from routes.peta_kolaborasi import _hitung_berlaku
    from auth_utils import MAP_TOKEN_EXPIRATION_DAYS
    base = datetime(2026, 7, 24, 0, 0, tzinfo=timezone.utc)
    plafon = base - timedelta(days=30)   # token diterbitkan 30 hari lalu
    d = _hitung_berlaku(10_000_000, None, base, plafon)
    assert d == (plafon + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)).astimezone(timezone.utc).isoformat()


def test_hitung_berlaku_default_dan_jepit():
    from routes.peta_kolaborasi import _hitung_berlaku, _DEFAULT_JAM
    from auth_utils import MAP_TOKEN_EXPIRATION_DAYS
    base = datetime(2026, 7, 24, 0, 0, tzinfo=timezone.utc)
    # default 72 jam bila tak ada input
    d = _hitung_berlaku(None, None, base)
    assert d == (base + timedelta(hours=_DEFAULT_JAM)).isoformat()
    # durasi_jam eksplisit
    d = _hitung_berlaku(24, None, base)
    assert d == (base + timedelta(hours=24)).isoformat()
    # dijepit ke plafon token
    d = _hitung_berlaku(10_000_000, None, base)
    assert d == (base + timedelta(days=MAP_TOKEN_EXPIRATION_DAYS)).isoformat()
    # berlaku_sampai eksplisit menang atas durasi
    target = (base + timedelta(hours=5)).isoformat()
    assert _hitung_berlaku(999, target, base) == target


def test_akses_aktif_tamu_dan_user():
    from routes.peta_kolaborasi import _akses_peta
    aktif = {"status": "aktif", "berlaku_sampai": _iso(+2), "kode_satker": "527010"}
    # tamu BERLINK saat aktif → lihat + kontribusi
    assert _akses_peta(aktif, {"guest": True, "role": "tamu"}, True) == (True, True, "")
    # operator satker terkait buka dari aplikasi (tanpa token) → lihat + kontribusi
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "527010"}, False) == (True, True, "")
    # tamu TANPA link valid saat aktif → ditolak (cegah IDOR via UUID)
    assert _akses_peta(aktif, {"guest": True, "role": "tamu"}, False)[:2] == (False, False)
    # user satker BEDA tanpa link saat aktif → ditolak
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "999999"}, False)[:2] == (False, False)
    # ...tetapi pemegang link publik (satker beda) → boleh (link untuk siapa saja)
    assert _akses_peta(aktif, {"role": "operator", "kode_satker": "999999"}, True)[:2] == (True, True)


def test_akses_kedaluwarsa():
    from routes.peta_kolaborasi import _akses_peta
    habis = {"status": "aktif", "berlaku_sampai": _iso(-2), "kode_satker": "527010"}
    # tamu (bahkan pemegang link) → ditolak total pasca-kedaluwarsa
    lihat, kontrib, alasan = _akses_peta(habis, {"guest": True, "role": "tamu"}, True)
    assert lihat is False and kontrib is False and "berakhir" in alasan.lower()
    # operator satker sama → boleh LIHAT (arsip), tak boleh kontribusi
    assert _akses_peta(habis, {"role": "operator", "kode_satker": "527010"}, False)[:2] == (True, False)
    # admin satker sama → boleh lihat
    assert _akses_peta(habis, {"role": "admin", "kode_satker": "527010"}, False)[:2] == (True, False)
    # super-admin (kode_satker kosong) → boleh lihat lintas-satker
    assert _akses_peta(habis, {"role": "admin", "kode_satker": ""}, False)[:2] == (True, False)
    # viewer → ditolak
    assert _akses_peta(habis, {"role": "viewer", "kode_satker": "527010"}, False)[:2] == (False, False)
    # operator satker BEDA (walau pegang link) → ditolak pasca-kedaluwarsa
    assert _akses_peta(habis, {"role": "operator", "kode_satker": "999999"}, True)[:2] == (False, False)


def test_akses_dibatalkan():
    from routes.peta_kolaborasi import _akses_peta
    batal = {"status": "batal", "berlaku_sampai": _iso(+2), "kode_satker": "527010"}
    # dibatalkan → ditolak untuk siapa pun, termasuk operator satker & pemegang link
    lihat, kontrib, alasan = _akses_peta(batal, {"role": "admin", "kode_satker": "527010"}, True)
    assert lihat is False and kontrib is False and "batal" in alasan.lower()


def test_token_peta_round_trip():
    from auth_utils import create_map_token, require_map_token
    tok = create_map_token("share-123", "jti-abc")
    out = asyncio.run(require_map_token(token=tok))
    assert out == {"share": "share-123", "jti": "jti-abc"}


def test_token_peta_tolak_typ_lain():
    import pytest
    from fastapi import HTTPException
    from auth_utils import create_sign_token, require_map_token
    # token e-sign (typ=sign) TIDAK boleh lolos sebagai token peta.
    sign_tok = create_sign_token("sr1", "signer1", "jti1")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(require_map_token(token=sign_tok))
    assert ei.value.status_code == 401


# ── Payload publik: pagar terhadap kebocoran posisi (DPIA §6, Fase 11) ──────

def test_titik_publik_hanya_kunci_yang_diizinkan():
    """Sejak Fase 11 aplikasi menyimpan posisi perangkat yang dipegang
    PERORANGAN. Payload peta publik dapat dibuka siapa pun yang memegang tautan,
    jadi kunci yang keluar diuji EKSPLISIT — bukan diserahkan pada ingatan orang
    yang menambah field berikutnya."""
    from routes.peta_kolaborasi import KUNCI_PUBLIK_TITIK, baris_titik_publik
    aset = {"id": "a1", "asset_code": "3.05.01", "NUP": "7",
            "asset_name": "Laptop", "category": "Peralatan", "brand": "X",
            # Field yang TIDAK boleh menembus keluar:
            "lokasi_spasial": {"node_id": "sn_g1", "titik": [116.71, -1.40]},
            "pengguna": "Budi", "nip_pengguna": "1990...", "harga": 15000000,
            "photos": ["base64..."], "device_id": "dev_1",
            "koordinat_latitude": "-1.40", "koordinat_longitude": "116.71"}
    baris = baris_titik_publik(aset, -1.40, 116.71)
    assert set(baris) == set(KUNCI_PUBLIK_TITIK)
    bocor = {"lokasi_spasial", "pengguna", "nip_pengguna", "harga", "photos",
             "device_id", "koordinat_latitude", "koordinat_longitude"}
    assert not (set(baris) & bocor)


def test_titik_publik_tetap_membawa_data_verifikasi_lapangan():
    """Pagar privasi tak boleh mengosongkan peta — kode/NUP/kondisi memang
    tujuan berbagi tautan ini."""
    from routes.peta_kolaborasi import baris_titik_publik
    b = baris_titik_publik({"id": "a1", "asset_code": "3.05", "NUP": 7,
                            "asset_name": "Laptop", "condition": "Baik"},
                           -1.40, 116.71)
    assert b["kode"] == "3.05" and b["nama"] == "Laptop"
    assert b["kondisi"] == "Baik" and (b["lat"], b["lng"]) == (-1.40, 116.71)


def test_titik_publik_aset_minim_tak_meledak():
    from routes.peta_kolaborasi import baris_titik_publik
    b = baris_titik_publik({"id": "a1"}, 0.5, 100.0)
    assert b["nama"] == "" and b["jumlah_foto"] == 0


def test_izin_kontribusi_berlaku_per_link():
    """Setelan per-link mengikat SETIAP kunjungan lewat link — termasuk
    pengunjung yang kebetulan sedang login. Regresi: dulu setiap user login
    lolos begitu saja, sehingga link 'tanpa komentar/titik' tetap bisa dipakai
    berkontribusi dan setelan tiap link jadi tak berarti."""
    from routes.peta_kolaborasi import _izin_kontribusi
    mati = {"status": "aktif", "kode_satker": "527010",
            "izinkan_titik_publik": False, "izinkan_komentar_publik": False}
    tamu = {"guest": True, "role": "tamu"}
    op = {"role": "operator", "kode_satker": "527010"}
    luar = {"role": "operator", "kode_satker": "999999"}

    # Lewat link → setelan berlaku untuk SIAPA PUN.
    assert _izin_kontribusi(mati, tamu, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(mati, op, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(mati, luar, True, "izinkan_komentar_publik") is False
    # Operator/admin satker share membuka DARI APLIKASI (tanpa token link) →
    # mengelola petanya sendiri, tak dibatasi setelan publik.
    assert _izin_kontribusi(mati, op, False, "izinkan_titik_publik") is True
    # Satker lain tanpa link tetap tak boleh.
    assert _izin_kontribusi(mati, luar, False, "izinkan_titik_publik") is False

    # Setelan menyala → semua pengunjung berlink boleh.
    hidup = dict(mati, izinkan_titik_publik=True, izinkan_komentar_publik=True)
    assert _izin_kontribusi(hidup, tamu, True, "izinkan_titik_publik") is True
    assert _izin_kontribusi(hidup, tamu, True, "izinkan_komentar_publik") is True


def test_izin_kontribusi_dua_setelan_terpisah():
    """Titik & komentar berdiri sendiri — mematikan satu tak ikut mematikan
    yang lain (tiap link punya kombinasinya sendiri)."""
    from routes.peta_kolaborasi import _izin_kontribusi
    sh = {"status": "aktif", "kode_satker": "527010",
          "izinkan_titik_publik": False, "izinkan_komentar_publik": True}
    tamu = {"guest": True, "role": "tamu"}
    assert _izin_kontribusi(sh, tamu, True, "izinkan_titik_publik") is False
    assert _izin_kontribusi(sh, tamu, True, "izinkan_komentar_publik") is True


def test_izin_kontribusi_share_lama_tanpa_field():
    """Share yang dibuat sebelum fitur toggle (field tak ada) tetap terbuka —
    tak boleh mendadak mengunci peta yang sedang berjalan."""
    from routes.peta_kolaborasi import _izin_kontribusi
    lama = {"status": "aktif", "kode_satker": "527010"}
    assert _izin_kontribusi(lama, {"guest": True}, True, "izinkan_titik_publik") is True
