"""Uji Master Pegawai (data kepegawaian menyeluruh, adopsi SIMAN-G)."""
from pegawai_utils import (
    JENIS_JABATAN, JENIS_KELAMIN, KATEGORI_PEGAWAI, STATUS_PEGAWAI,
    baris_impor_ke_pegawai, bersihkan_nip, is_aktif, kelompok_unit_kerja,
    nama_lengkap, normalisasi_status_kepegawaian, normalisasi_status_pegawai,
    pegawai_perlu_serah_terima, rekap_eselon, status_kontrak,
    unit_kerja_terdalam, validate_pegawai,
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


# ── Pengayaan (adopsi KERJA-BARENG/SIMPEG) ───────────────────────────────────

def test_bersihkan_nip():
    assert bersihkan_nip("7371122602960002.0") == "7371122602960002"
    assert bersihkan_nip("198501012010011001") == "198501012010011001"
    assert bersihkan_nip("-") == ""
    assert bersihkan_nip("") == ""
    assert bersihkan_nip(None) == ""
    # karakter arah tak terlihat dibuang
    assert bersihkan_nip("‭198501012010011001‬") == "198501012010011001"


def test_normalisasi_status_kepegawaian():
    assert normalisasi_status_kepegawaian("PNS") == ("pns", "")
    assert normalisasi_status_kepegawaian("CPNS") == ("cpns", "")
    assert normalisasi_status_kepegawaian("PPPK") == ("pppk", "")
    assert normalisasi_status_kepegawaian("Konsultan Individual")[0] == "non_asn"
    assert normalisasi_status_kepegawaian("Konsultan Individual")[1] == "konsultan"
    assert normalisasi_status_kepegawaian("Tenaga Pendukung") == ("non_asn", "tenaga_pendukung")
    assert normalisasi_status_kepegawaian("Honorer") == ("non_asn", "")
    assert normalisasi_status_kepegawaian("") == ("", "")


def test_normalisasi_status_pegawai():
    assert normalisasi_status_pegawai("AKTIF") == "aktif"
    assert normalisasi_status_pegawai("KELUAR") == "keluar"
    assert normalisasi_status_pegawai("MUTASI KELUAR") == "mutasi"
    assert normalisasi_status_pegawai("Pensiun") == "pensiun"
    assert normalisasi_status_pegawai("MENINGGAL") == "nonaktif"
    assert normalisasi_status_pegawai("") == "aktif"


def test_status_kontrak():
    habis = status_kontrak({"tgl_selesai_kontrak": "2026-06-30"}, "2026-07-18")
    assert habis["ada"] and habis["habis"] and habis["sisa_hari"] == -18
    segera = status_kontrak({"tgl_selesai_kontrak": "2026-08-01"}, "2026-07-18")
    assert segera["segera"] and not segera["habis"] and segera["sisa_hari"] == 14
    jauh = status_kontrak({"tgl_selesai_kontrak": "2027-01-01"}, "2026-07-18")
    assert jauh["ada"] and not jauh["segera"] and not jauh["habis"]
    assert status_kontrak({}, "2026-07-18")["ada"] is False
    # tanggal rusak → tidak crash
    assert status_kontrak({"tgl_selesai_kontrak": "bukan-tgl"}, "2026-07-18")["ada"] is False


def test_unit_kerja_terdalam():
    assert unit_kerja_terdalam({"eselon1": "Ked X", "eselon2": "Dir Y"}) == "Dir Y"
    assert unit_kerja_terdalam({"eselon1": "Ked X"}) == "Ked X"
    assert unit_kerja_terdalam({"unit_kerja": "Bagian Umum"}) == "Bagian Umum"
    assert unit_kerja_terdalam({}) == ""


def test_rekap_eselon():
    daftar = [{"eselon1": "A"}, {"eselon1": "A"}, {"eselon1": "B"}, {"eselon1": ""}]
    hasil = rekap_eselon(daftar, "eselon1")
    assert hasil[0] == {"unit": "A", "jumlah": 2}
    assert hasil[-1]["unit"] == "(belum dicatat)"


def test_baris_impor_ke_pegawai():
    raw = {
        "NIP/NIK/NRP": "7371122602960002.0", "Nama Lengkap": "A Khalil",
        "Status Kepegawaian": "Konsultan Individual",
        "Eselon 1": "Kedeputian X", "Eselon 2": "Direktorat Y",
        "Jenis Kelamin": "Laki-laki", "Status": "AKTIF",
        "Tgl Selesai Kontrak": "31/12/2026",
    }
    doc, peringatan = baris_impor_ke_pegawai(raw)
    assert doc["nip"] == "7371122602960002"
    assert doc["nama"] == "A Khalil"
    assert doc["status_kepegawaian"] == "non_asn"
    assert doc["sub_kategori_non_asn"] == "konsultan"
    assert doc["jenis_kelamin"] == "L"
    assert doc["status"] == "aktif"
    assert doc["eselon1"] == "Kedeputian X" and doc["eselon2"] == "Direktorat Y"
    # unit_kerja efektif = eselon terdalam
    assert doc["unit_kerja"] == "Direktorat Y"
    # tanggal dd/mm/yyyy dinormalkan
    assert doc["tgl_selesai_kontrak"] == "2026-12-31"


def test_baris_impor_nama_kosong_dilewati():
    doc, peringatan = baris_impor_ke_pegawai({"NIP/NIK/NRP": "123"})
    assert doc["nama"] == "" and any("Nama kosong" in p for p in peringatan)


def test_kategori_pegawai_konstanta():
    for k in ("jpt", "administrator", "pengawas", "pelaksana", "fungsional"):
        assert k in KATEGORI_PEGAWAI
    assert "keluar" in STATUS_PEGAWAI


def test_periksa_rekening_dan_referensi_baru():
    from pegawai_utils import (DIGIT_BANK, JENIS_IDENTITAS_WNA,
                               KEWARGANEGARAAN, PANGKAT_GOLONGAN,
                               periksa_rekening)
    # cocok → tanpa peringatan; beda → peringatan lunak; tak dikenal → kosong
    assert periksa_rekening("BRI", "1" * 15) == ""
    assert "15 digit" in periksa_rekening("BRI", "12345")
    assert periksa_rekening("Bank Antah", "12345") == ""
    assert periksa_rekening("", "12345") == ""
    assert periksa_rekening("BNI", "") == ""
    # pemisah non-digit diabaikan saat menghitung
    assert periksa_rekening("BNI", "12-3456-7890") == ""
    assert DIGIT_BANK["mandiri"] == 13
    assert set(KEWARGANEGARAAN) == {"wni", "wna"}
    assert set(JENIS_IDENTITAS_WNA) == {"paspor", "kitas", "kitap"}
    # pangkat mengikuti status; CPNS = daftar PNS
    assert "Penata (III/c)" in PANGKAT_GOLONGAN["pns"]
    assert PANGKAT_GOLONGAN["cpns"] == PANGKAT_GOLONGAN["pns"]
    assert len(PANGKAT_GOLONGAN["pppk"]) == 17
    assert "Kolonel" in PANGKAT_GOLONGAN["tni"]
    assert "Komisaris Polisi" in PANGKAT_GOLONGAN["polri"]


def test_pegawai_perlu_serah_terima():
    pegawai = [
        {"id": "1", "nama": "Keluar Pegang", "nip": "111", "status": "keluar"},
        {"id": "2", "nama": "Aktif Pegang", "nip": "222", "status": "aktif"},
        {"id": "3", "nama": "Keluar Kosong", "nip": "333", "status": "keluar"},
        {"id": "4", "nama": "Tanpa NIP", "nip": "", "status": "keluar"},
        {"id": "5", "nama": "Kontrak Habis", "nip": "555", "status": "aktif",
         "tgl_selesai_kontrak": "2026-06-30"},
        {"id": "6", "nama": "Pensiun Banyak", "nip": "666", "status": "pensiun"},
        {"id": "7", "nama": "Cuti Pegang", "nip": "777", "status": "cuti"},
    ]
    aset = {"111": 2, "222": 3, "555": 1, "666": 5, "777": 4}
    hasil = pegawai_perlu_serah_terima(pegawai, aset, "2026-07-18")
    ids = [h["id"] for h in hasil]
    # aktif & cuti aman; keluar tanpa aset tidak masuk; urut jumlah desc
    assert ids == ["6", "1", "5"]
    assert hasil[0]["jumlah_aset"] == 5 and "pensiun" in hasil[0]["alasan"].lower()
    assert "kontrak berakhir" in hasil[2]["alasan"].lower()
    assert pegawai_perlu_serah_terima([], {}, "2026-07-18") == []
