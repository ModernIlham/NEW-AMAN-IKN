"""Uji Master Pegawai (data kepegawaian menyeluruh, adopsi SIMAN-G)."""
from pegawai_utils import (
    JENIS_JABATAN, JENIS_KELAMIN, STATUS_PEGAWAI,
    is_aktif, kelompok_unit_kerja, nama_lengkap, validate_pegawai,
)


def test_referensi_konstanta_inti():
    assert set(JENIS_KELAMIN) == {"L", "P"}
    for k in ("struktural", "fungsional", "pelaksana"):
        assert k in JENIS_JABATAN
    for k in ("aktif", "mutasi", "pensiun", "nonaktif"):
        assert k in STATUS_PEGAWAI


def test_validate_pegawai_wajib_nama():
    assert any("Nama" in e for e in validate_pegawai({}))
    assert validate_pegawai({"nama": "Budi"}) == []


def test_validate_pegawai_nip():
    assert validate_pegawai({"nama": "A", "nip": "198501012010011001"}) == []  # 18 digit
    assert any("NIP" in e for e in validate_pegawai({"nama": "A", "nip": "abc"}))
    assert any("NIP" in e for e in validate_pegawai({"nama": "A", "nip": "123"}))  # < 8
    # NIP kosong tidak error
    assert validate_pegawai({"nama": "A", "nip": ""}) == []


def test_validate_pegawai_enum_dan_email():
    assert any("Jenis kelamin" in e for e in validate_pegawai({"nama": "A", "jenis_kelamin": "X"}))
    assert validate_pegawai({"nama": "A", "jenis_kelamin": "p"}) == []  # case-insensitive
    assert any("Status kepegawaian" in e for e in
               validate_pegawai({"nama": "A", "status_kepegawaian": "honorer"}))
    assert any("Jenis jabatan" in e for e in
               validate_pegawai({"nama": "A", "jenis_jabatan": "aneh"}))
    assert any("Status pegawai" in e for e in
               validate_pegawai({"nama": "A", "status": "hilang"}))
    assert any("email" in e.lower() for e in validate_pegawai({"nama": "A", "email": "budi@x"}))
    assert any("Tanggal lahir" in e for e in
               validate_pegawai({"nama": "A", "tanggal_lahir": "01-01-1985"}))


def test_nama_lengkap():
    assert nama_lengkap({"nama": "Budi"}) == "Budi"
    assert nama_lengkap({"gelar_depan": "Dr.", "nama": "Budi", "gelar_belakang": "S.E."}) == "Dr. Budi, S.E."
    assert nama_lengkap({"nama": "Sri", "gelar_belakang": "M.M."}) == "Sri, M.M."
    assert nama_lengkap({}) == ""


def test_is_aktif():
    assert is_aktif({"status": "aktif"}) is True
    assert is_aktif({}) is True  # kosong dianggap aktif
    assert is_aktif({"status": "pensiun"}) is False


def test_kelompok_unit_kerja():
    daftar = [
        {"nama": "A", "unit_kerja": "Bagian Umum"},
        {"nama": "B", "unit_kerja": "Bagian Umum"},
        {"nama": "C", "unit_kerja": "Bagian Keuangan"},
        {"nama": "D", "unit_kerja": ""},
    ]
    hasil = kelompok_unit_kerja(daftar)
    # terurut nama unit; unit kosong terakhir
    assert [g["unit_kerja"] for g in hasil] == [
        "Bagian Keuangan", "Bagian Umum", "(unit kerja belum dicatat)"]
    assert hasil[1]["jumlah"] == 2
    assert hasil[-1]["jumlah"] == 1
    assert kelompok_unit_kerja([]) == []
