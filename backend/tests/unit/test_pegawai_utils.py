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


def test_deteksi_identitas_semua_jenis():
    """Deteksi NIP PNS / NI PPPK / NIK / NRP POLRI / NRP TNI dari format."""
    from pegawai_utils import deteksi_identitas
    assert deteksi_identitas("195808181984041001")["jenis"] == "nip_pns"
    assert deteksi_identitas("199001012024211002")["jenis"] == "ni_pppk"
    assert deteksi_identitas("3506042503900001")["jenis"] == "nik"
    assert deteksi_identitas("80101234")["jenis"] == "nrp_polri"
    assert deteksi_identitas("531234")["jenis"] == "nrp_tni"
    # 18 digit ber-tanggal tak valid → bukan NIP
    assert deteksi_identitas("999999991984041001")["jenis"] == ""
    assert deteksi_identitas("")["jenis"] == ""
    assert deteksi_identitas("abc")["jenis"] == ""


def test_baris_identitas_ttd_dan_label_laporan():
    """Laporan: NRP berlabel NRP; NIK Non-ASN TIDAK dicetak; kosong →
    placeholder garis titik."""
    from pegawai_utils import baris_identitas_laporan, baris_identitas_ttd
    assert baris_identitas_ttd("80101234") == ["NRP. 80101234"]
    assert baris_identitas_ttd("3506042503900001") == []
    assert baris_identitas_ttd("", "NIP. ....") == ["NIP. ...."]
    assert baris_identitas_laporan("195808181984041001") == "NIP. 195808181984041001"
    assert baris_identitas_laporan("80101234", "polri") == "NRP. 80101234"
    assert baris_identitas_laporan("195808181984041001", "non_asn") == ""


def test_baris_identitas_ttd_status_non_asn():
    """Aturan blok TTD: penandatangan Non-ASN TIDAK dicetak NIP/NIK-nya
    apa pun format nomornya; placeholder "-" diperlakukan kosong."""
    from pegawai_utils import baris_identitas_ttd
    # Non-ASN dengan nomor apa pun (NIP-like, NIK, bebas) → tanpa baris
    assert baris_identitas_ttd("195808181984041001", "NIP. ....", "non_asn") == []
    assert baris_identitas_ttd("3506042503900001", "NIP. ....", "non_asn") == []
    assert baris_identitas_ttd("K-00123", "NIP. ....", "non_asn") == []
    # Status ASN → tetap dicetak dengan label yang tepat
    assert baris_identitas_ttd("195808181984041001", "", "pns") == ["NIP. 195808181984041001"]
    assert baris_identitas_ttd("80101234", "", "tni") == ["NRP. 80101234"]
    # "-" (placeholder era lama) = kosong → placeholder titik-titik
    assert baris_identitas_ttd("-", "NIP. ....") == ["NIP. ...."]


def test_info_masa_pegawai_bup():
    """BUP per UU 20/2023 (JPT 60, fungsional ahli utama 65) + TNI/POLRI +
    kontrak Non-ASN; data kurang → None (tidak menebak)."""
    from pegawai_utils import info_masa_pegawai
    jpt = info_masa_pegawai({"status_kepegawaian": "pns",
                             "kategori_pegawai": "jpt",
                             "tanggal_lahir": "1970-01-01"}, "2026-07-19")
    assert jpt["bup"] == 60 and jpt["tanggal_pensiun"] == "2030-01-01"
    utama = info_masa_pegawai({"status_kepegawaian": "pns",
                               "kategori_pegawai": "fungsional",
                               "jabatan": "Perencana Ahli Utama",
                               "tanggal_lahir": "1965-06-01"}, "2026-07-19")
    assert utama["bup"] == 65
    polri = info_masa_pegawai({"status_kepegawaian": "polri",
                               "pangkat_golongan": "Brigadir Polisi",
                               "tanggal_lahir": "1980-10-01"}, "2026-07-19")
    assert polri["bup"] == 59
    non_asn = info_masa_pegawai({"status_kepegawaian": "non_asn",
                                 "tgl_selesai_kontrak": "2026-12-31"},
                                "2026-07-19")
    assert non_asn["bup"] is None and non_asn["kontrak"]["ada"] is True
    # tanpa tanggal lahir → tidak menebak pensiun
    kosong = info_masa_pegawai({"status_kepegawaian": "pns",
                                "kategori_pegawai": "jpt"}, "2026-07-19")
    assert kosong["tanggal_pensiun"] == ""
    # akhir jabatan tercatat → sisa hari terhitung
    jab = info_masa_pegawai({"tanggal_akhir_jabatan": "2026-08-19"}, "2026-07-19")
    assert jab["sisa_hari_jabatan"] == 31


def test_validate_pegawai_field_baru():
    """Validasi kode satker 6/12 digit + kontrak Non-ASN outsourcing."""
    from pegawai_utils import validate_pegawai
    ok = validate_pegawai({"nama": "Budi", "kode_satker": "527010",
                           "kode_satker_lengkap": "527010401987",
                           "jenis_kontrak_non_asn": "outsourcing",
                           "perusahaan_penyedia": "PT Aman Jaya"})
    assert ok == []
    err = validate_pegawai({"nama": "Budi", "kode_satker_lengkap": "12345",
                            "jenis_kontrak_non_asn": "outsourcing"})
    assert any("12 digit" in e for e in err)
    assert any("perusahaan penyedia" in e.lower() for e in err)


def test_ekspor_pegawai_round_trip_impor():
    """Baris ekspor Excel harus pulih jadi dokumen yang sama saat diimpor."""
    from pegawai_utils import (HEADER_IMPOR, baris_ekspor_pegawai,
                               baris_impor_ke_pegawai)
    doc = {
        "nip": "198501012010011001", "nama": "Budi Santoso",
        "jenis_kelamin": "L", "tempat_lahir": "Jakarta",
        "tanggal_lahir": "1985-01-01", "status_kepegawaian": "pns",
        "pangkat_golongan": "Penata (III/c)", "jabatan": "Analis BMN",
        "kategori_pegawai": "pelaksana", "tmt_jabatan": "2022-01-01",
        "tanggal_akhir_jabatan": "2027-01-01",
        "eselon1": "Sekretariat", "eselon2": "Bagian Umum",
        "no_hp": "081200000000", "email": "budi@instansi.go.id",
        "npwp": "123456789012345", "pendidikan_terakhir": "S1",
        "alamat": "Jl. Merdeka 1", "nama_bank": "BRI",
        "no_rekening": "123456789012345", "kode_satker_lengkap": "012345678901",
        "status": "aktif", "keterangan": "-",
    }
    baris = baris_ekspor_pegawai(doc)
    assert len(baris) == len(HEADER_IMPOR)
    pulih, _ = baris_impor_ke_pegawai(dict(zip(HEADER_IMPOR, baris)))
    for k in ("nip", "nama", "jenis_kelamin", "tanggal_lahir",
              "status_kepegawaian", "kategori_pegawai", "tmt_jabatan",
              "tanggal_akhir_jabatan", "npwp", "alamat",
              "kode_satker_lengkap", "status"):
        assert pulih[k] == doc[k], (k, pulih[k])
    # keterangan "-" dinormalkan jadi kosong oleh impor (konvensi lama)
    assert pulih["keterangan"] == ""


def test_ekspor_non_asn_sub_kategori_pulih():
    """Non-ASN ber-sub-kategori: label sub diekspor & sub pulih saat impor."""
    from pegawai_utils import (HEADER_IMPOR, baris_ekspor_pegawai,
                               baris_impor_ke_pegawai,
                               label_ekspor_status_kepegawaian)
    doc = {"nama": "Andi", "status_kepegawaian": "non_asn",
           "sub_kategori_non_asn": "satpam",
           "jenis_kontrak_non_asn": "outsourcing",
           "perusahaan_penyedia": "PT Aman Jaya", "status": "nonaktif"}
    assert label_ekspor_status_kepegawaian(doc) == "Satpam"
    pulih, _ = baris_impor_ke_pegawai(
        dict(zip(HEADER_IMPOR, baris_ekspor_pegawai(doc))))
    assert pulih["status_kepegawaian"] == "non_asn"
    assert pulih["sub_kategori_non_asn"] == "satpam"
    assert pulih["jenis_kontrak_non_asn"] == "outsourcing"
    assert pulih["perusahaan_penyedia"] == "PT Aman Jaya"
    # Bug lama: "Nonaktif" mengandung "aktif" → dulu salah jadi aktif
    assert pulih["status"] == "nonaktif"


def test_normalisasi_kategori_dan_jenis_kontrak():
    from pegawai_utils import (normalisasi_jenis_kontrak,
                               normalisasi_kategori_pegawai)
    assert normalisasi_kategori_pegawai("Jabatan Pimpinan Tinggi (JPT)") == "jpt"
    assert normalisasi_kategori_pegawai("pengawas") == "pengawas"
    assert normalisasi_kategori_pegawai("Jabatan Fungsional (JF)") == "fungsional"
    assert normalisasi_kategori_pegawai("") == ""
    assert normalisasi_jenis_kontrak("Outsourcing (melalui perusahaan penyedia)") == "outsourcing"
    assert normalisasi_jenis_kontrak("Kontrak internal instansi (PPNPN/SPK dengan PPK)") == "internal"
    assert normalisasi_jenis_kontrak("") == ""


def test_opsi_dropdown_ekspor_semua_ternormalisasi():
    """Setiap opsi dropdown di file ekspor harus dinormalkan balik dgn benar."""
    from pegawai_utils import (KATEGORI_PEGAWAI, OPSI_DROPDOWN_EKSPOR,
                               STATUS_PEGAWAI,
                               normalisasi_jenis_kontrak,
                               normalisasi_kategori_pegawai,
                               normalisasi_status_kepegawaian,
                               normalisasi_status_pegawai)
    for v in OPSI_DROPDOWN_EKSPOR["Status Kepegawaian"]:
        kode, _sub = normalisasi_status_kepegawaian(v)
        assert kode, v
    for v in OPSI_DROPDOWN_EKSPOR["Status"]:
        assert normalisasi_status_pegawai(v) in STATUS_PEGAWAI, v
    for v in OPSI_DROPDOWN_EKSPOR["Kategori Pegawai"]:
        assert normalisasi_kategori_pegawai(v) in KATEGORI_PEGAWAI, v
    for v in OPSI_DROPDOWN_EKSPOR["Jenis Kontrak Non-ASN"]:
        assert normalisasi_jenis_kontrak(v) in ("internal", "outsourcing"), v
