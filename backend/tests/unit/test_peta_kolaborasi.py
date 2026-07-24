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
