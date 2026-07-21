"""Test logika murni kartu pegawai (UID e-KTP) — tanpa Mongo/jaringan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kartu_utils import (  # noqa: E402
    hash_kandidat, hash_uid, kandidat_uid, label_kartu, normalisasi_uid,
    valid_uid,
)

KUNCI = b"kunci-uji"


def test_normalisasi_uid():
    # Pemisah & kapitalisasi tidak berpengaruh
    assert normalisasi_uid("04:a2:1b:7c") == "04A21B7C"
    assert normalisasi_uid(" 04-a2-1b-7c ") == "04A21B7C"
    assert normalisasi_uid("2460184112") == "2460184112"
    assert normalisasi_uid("") == ""
    assert normalisasi_uid(None) == ""
    assert normalisasi_uid("zz!!") == ""  # bukan hex/desimal


def test_kandidat_uid_hex_dan_desimal():
    # Hex 4-byte → asli + byte dibalik (reader LSB vs MSB)
    k = kandidat_uid("92A78230")
    assert "92A78230" in k and "3082A792" in k
    # Desimal (reader mode desimal) → hex BE & LE ikut jadi kandidat
    # 2460451376 = 0x92A78230
    k = kandidat_uid("2460451376")
    assert "2460451376" in k and "92A78230" in k and "3082A792" in k
    # UID sama dari reader BERBEDA format harus saling beririsan kandidat
    irisan = set(kandidat_uid("92A78230")) & set(kandidat_uid("2460451376"))
    assert irisan, "reader hex vs desimal harus tetap cocok"
    assert kandidat_uid("") == []


def test_hash_uid_deterministik_dan_tanpa_uid_mentah():
    h1 = hash_uid("04:A2:1B:7C", KUNCI)
    h2 = hash_uid("04a21b7c", KUNCI)
    assert h1 == h2 and len(h1) == 64          # normalisasi → hash sama
    assert hash_uid("04A21B7D", KUNCI) != h1   # UID beda → hash beda
    assert "04A21B7C" not in h1.upper()        # hash tak memuat UID mentah
    assert hash_uid("", KUNCI) == ""
    # Kunci beda → hash beda (keyed-hash, bukan SHA polos)
    assert hash_uid("04A21B7C", b"kunci-lain") != h1


def test_hash_kandidat_cocok_lintas_format_reader():
    daftar = hash_kandidat("92A78230", KUNCI)      # didaftarkan via reader hex
    dari_desimal = hash_kandidat("2460451376", KUNCI)  # di-tap via reader desimal
    assert set(daftar) & set(dari_desimal), \
        "hash pendaftaran harus beririsan dengan hash identifikasi"


def test_label_dan_validasi():
    assert label_kartu("04A21B7C").endswith("1B7C")
    assert "04A2" not in label_kartu("04A21B7C")   # bagian depan disamarkan
    assert valid_uid("04A21B7C") == ""
    assert valid_uid("") != ""
    assert valid_uid("123") != ""                  # terlalu pendek
    assert valid_uid("A" * 30) != ""               # terlalu panjang
