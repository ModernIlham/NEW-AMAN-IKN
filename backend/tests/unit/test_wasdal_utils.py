"""Uji logika murni dasbor pemantauan Wasdal (PMK 207/2021)."""
from wasdal_utils import (
    JENIS_TEMUAN, OBJEK_PER_JENIS, OBJEK_WASDAL, PEMICU_INSIDENTIL,
    SUMBER_PENERTIBAN, info_tenggat_insidentil, periode_wasdal,
    rekap_insidentil, rekap_penertiban, rekap_wasdal, sisa_hari_kerja,
    status_tenggat_penertiban, susun_temuan, tambah_hari_kerja,
    temuan_dokumen_kepemilikan, temuan_pemanfaatan, temuan_pemegang_berisiko,
    temuan_pemindahtanganan, temuan_pemusnahan, temuan_penatausahaan,
    temuan_pengamanan_pemeliharaan, temuan_penggunaan, temuan_polis_asuransi,
    validate_ba_insidentil, validate_insidentil, validate_lapor_insidentil,
    validate_penertiban, validate_selesai_penertiban,
)

HARI_INI = "2026-07-12"

ASET_LENGKAP = {"id": "a1", "asset_code": "3100102001", "NUP": "1",
                "asset_name": "PC Unit", "user": "Budi",
                "bast_file_id": "f1", "condition": "Baik",
                "purchase_price": 5_000_000,
                "koordinat_latitude": "-1.1", "koordinat_longitude": "116.9"}


def test_registry_jenis_konsisten():
    assert set(JENIS_TEMUAN) == set(OBJEK_PER_JENIS)
    assert set(OBJEK_PER_JENIS.values()) <= set(OBJEK_WASDAL)


def test_periode():
    assert periode_wasdal("2026-07-12") == {
        "tahun": 2026, "semester": 2, "label": "Semester II 2026"}
    assert periode_wasdal("2026-03-01")["semester"] == 1


def test_penggunaan():
    tanpa_bast = dict(ASET_LENGKAP, bast_file_id="")
    tanpa_user = dict(ASET_LENGKAP, id="a2", user=" ")
    hasil = temuan_penggunaan([ASET_LENGKAP, tanpa_bast, tanpa_user])
    jenis = [t["jenis"] for t in hasil]
    assert jenis == ["pemegang_tanpa_bast", "tanpa_pengguna"]
    assert "Budi" in hasil[0]["detail"]


def test_pemanfaatan():
    lengkap = {"id": "p1", "bentuk": "sewa", "pihak": "PT X",
               "berakhir": "2027-01-01", "nomor_persetujuan": "S-1",
               "nomor_perjanjian": "PJ-1", "ntpn": "N1"}
    berakhir = dict(lengkap, id="p2", berakhir="2026-01-01")
    kurang = dict(lengkap, id="p3", nomor_persetujuan="")
    hasil = temuan_pemanfaatan([lengkap, berakhir, kurang], HARI_INI)
    jenis = {t["pemanfaatan_id"]: t["jenis"] for t in hasil}
    assert jenis == {"p2": "perjanjian_berakhir",
                     "p3": "dokumen_pemanfaatan_kurang"}
    assert "persetujuan" in hasil[1]["detail"]


def test_pemanfaatan_kontribusi_tertunggak():
    # KSP kontribusi tahunan 10jt, mulai 2024, belum bayar → tunggak 2024-2026.
    ksp = {"id": "p9", "bentuk": "ksp", "pihak": "PT Y",
           "berakhir": "2030-01-01", "mulai": "2024-01-01",
           "nomor_persetujuan": "S-9", "nomor_perjanjian": "PJ-9",
           "ntpn": "N9", "kontribusi_tahunan": 10_000_000, "kontribusi": []}
    hasil = temuan_pemanfaatan([ksp], HARI_INI)
    jenis = [t["jenis"] for t in hasil]
    assert "kontribusi_tertunggak" in jenis
    t = next(t for t in hasil if t["jenis"] == "kontribusi_tertunggak")
    assert "2024" in t["detail"] and "2026" in t["detail"]
    # Tertib (semua tahun terbayar) → tanpa temuan tunggakan.
    tertib = dict(ksp, id="p10", kontribusi=[
        {"tahun": "2024"}, {"tahun": "2025"}, {"tahun": "2026"}])
    assert not [t for t in temuan_pemanfaatan([tertib], HARI_INI)
                if t["jenis"] == "kontribusi_tertunggak"]


def test_polis_asuransi_lewat():
    lewat = {"id": "pol1", "asset_id": "a1", "asset_name": "Gedung A",
             "nomor_polis": "POL-001", "penanggung": "Konsorsium",
             "berakhir": "2026-01-01"}
    aktif = dict(lewat, id="pol2", berakhir="2027-01-01")
    tanpa = dict(lewat, id="pol3", berakhir="")
    hasil = temuan_polis_asuransi([lewat, aktif, tanpa], HARI_INI)
    assert [t["polis_id"] for t in hasil] == ["pol1"]
    assert hasil[0]["jenis"] == "polis_asuransi_lewat"
    assert "POL-001" in hasil[0]["detail"] and "2026-01-01" in hasil[0]["detail"]
    assert hasil[0]["asset_name"] == "Gedung A"
    # objek benar via susun_temuan
    per_objek = susun_temuan([], [], [], [], [], HARI_INI, polis=[lewat])
    assert any(t["jenis"] == "polis_asuransi_lewat"
               for t in per_objek["pengamanan_pemeliharaan"])


def test_pemegang_berisiko_keluar():
    """Integrasi Master Pegawai → Wasdal: pegawai keluar/pensiun yang masih
    memegang aset = temuan objek Penggunaan; pegawai aktif tidak."""
    keluar = {"id": "p1", "nama": "Sari", "nip": "111", "status": "keluar"}
    aktif = {"id": "p2", "nama": "Budi", "nip": "222", "status": "aktif"}
    pensiun_tanpa_aset = {"id": "p3", "nama": "Tono", "nip": "333",
                          "status": "pensiun"}
    peta = {"111": 2, "222": 5}  # NIP 333 tidak memegang aset
    hasil = temuan_pemegang_berisiko(
        [keluar, aktif, pensiun_tanpa_aset], peta, HARI_INI)
    assert [t["pegawai_id"] for t in hasil] == ["p1"]
    assert hasil[0]["jenis"] == "pemegang_berisiko_keluar"
    assert hasil[0]["asset_name"] == "Sari" and hasil[0]["nip"] == "111"
    assert "2 aset" in hasil[0]["detail"]
    # objek benar via susun_temuan (masuk objek penggunaan)
    per_objek = susun_temuan([], [], [], [], [], HARI_INI,
                             pegawai=[keluar], jumlah_aset_per_nip=peta)
    assert any(t["jenis"] == "pemegang_berisiko_keluar"
               for t in per_objek["penggunaan"])
    # tanpa data pegawai → tidak ada temuan & tidak error
    assert temuan_pemegang_berisiko(None, None, HARI_INI) == []


def test_perjanjian_jatuh_tempo():
    """Perjanjian berakhir ≤60 hari → peringatan dini; arah tindak lanjut
    beda antara bentuk yang dapat/tidak dapat diperpanjang (PMK 115/2020)."""
    dekat = {"id": "p1", "bentuk": "sewa", "pihak": "PT X",
             "asset_name": "Aula", "berakhir": "2026-08-15",  # 34 hari
             "nomor_persetujuan": "S-1", "nomor_perjanjian": "P-1",
             "ntpn": "N-1"}
    bgs = dict(dekat, id="p2", bentuk="bgs_bsg")
    jauh = dict(dekat, id="p3", berakhir="2027-06-01")
    hasil = temuan_pemanfaatan([dekat, bgs, jauh], HARI_INI)
    jt = {t["pemanfaatan_id"]: t for t in hasil
          if t["jenis"] == "perjanjian_jatuh_tempo"}
    assert set(jt) == {"p1", "p2"}
    assert "perpanjangan" in jt["p1"]["detail"]
    assert "tidak dapat diperpanjang" in jt["p2"]["detail"]


def test_dokumen_kepemilikan_kedaluwarsa():
    lewat = {"id": "d1", "asset_id": "a1", "asset_name": "Mobil Dinas",
             "jenis": "stnk", "nomor": "STNK-9", "berlaku_sampai": "2026-05-01"}
    aktif = dict(lewat, id="d2", berlaku_sampai="2027-05-01")
    tanpa = dict(lewat, id="d3", berlaku_sampai="")  # sertipikat dll.
    hasil = temuan_dokumen_kepemilikan([lewat, aktif, tanpa], HARI_INI)
    assert [t["dok_id"] for t in hasil] == ["d1"]
    assert hasil[0]["jenis"] == "dokumen_kepemilikan_kedaluwarsa"
    assert "STNK" in hasil[0]["detail"] and "2026-05-01" in hasil[0]["detail"]
    per_objek = susun_temuan([], [], [], [], [], HARI_INI, dokumen=[lewat])
    assert any(t["jenis"] == "dokumen_kepemilikan_kedaluwarsa"
               for t in per_objek["pengamanan_pemeliharaan"])


def test_pemusnahan_belum_dihapus():
    """Aset ber-BA pemusnahan tanpa SK penghapusan = temuan lebih saji;
    yang sudah ber-SK tidak ikut."""
    ba = {"nomor_ba": "BA-01", "tanggal_ba": "2026-05-01",
          "aset": [{"asset_id": "a1", "asset_code": "305", "NUP": "1",
                    "asset_name": "Kursi Musnah"},
                   {"asset_id": "a2", "asset_code": "305", "NUP": "2",
                    "asset_name": "Meja Musnah"}]}
    hasil = temuan_pemusnahan([ba], {"a2"}, HARI_INI)
    assert [t["asset_id"] for t in hasil] == ["a1"]
    assert hasil[0]["jenis"] == "dimusnahkan_belum_dihapus"
    assert "BA-01" in hasil[0]["detail"] and "72 hari" in hasil[0]["detail"]
    # BA bertanggal depan tidak dinilai
    depan = dict(ba, tanggal_ba="2026-12-01")
    assert temuan_pemusnahan([depan], set(), HARI_INI) == []
    per_objek = susun_temuan([], [], [], [], [], HARI_INI,
                             pemusnahan=[ba], aset_ber_sk=set())
    assert sum(1 for t in per_objek["pemindahtanganan"]
               if t["jenis"] == "dimusnahkan_belum_dihapus") == 2


def test_pemindahtanganan_dan_penghapusan():
    rb = dict(ASET_LENGKAP, id="rb1", condition="Rusak Berat")
    rb_diusulkan = dict(ASET_LENGKAP, id="rb2", condition="Rusak Berat")
    usulan = [
        {"id": "u1", "asset_id": "rb2", "asset_name": "Kursi",
         "status": "diusulkan", "created_at": "2026-01-01T00:00:00"},
        {"id": "u2", "asset_id": "x9", "asset_name": "Meja",
         "status": "diproses", "created_at": "2026-07-01T00:00:00"},
    ]
    pt = [{"id": "t1", "bentuk": "penjualan_lelang", "pihak": "KPKNL",
           "status": "disetujui", "tanggal_persetujuan": "2026-01-01"}]
    hasil = temuan_pemindahtanganan([ASET_LENGKAP, rb, rb_diusulkan],
                                    usulan, pt, HARI_INI)
    jenis = sorted(t["jenis"] for t in hasil)
    # u1 berlarut (>90 hari), u2 belum; rb1 kandidat belum diusulkan,
    # rb2 sudah punya usulan aktif; t1 lewat tenggat lelang 6 bulan
    assert jenis == ["kandidat_belum_diusulkan", "tenggat_lelang",
                     "usulan_hapus_berlarut"]
    berlarut = next(t for t in hasil if t["jenis"] == "usulan_hapus_berlarut")
    assert berlarut["usulan_id"] == "u1" and "hari" in berlarut["detail"]
    kandidat = next(t for t in hasil if t["jenis"] == "kandidat_belum_diusulkan")
    assert kandidat["asset_id"] == "rb1"


def test_penatausahaan():
    kosong = {"id": "a3", "asset_name": "Meja", "condition": "",
              "purchase_price": "", "koordinat_latitude": "",
              "koordinat_longitude": ""}
    hasil = temuan_penatausahaan([ASET_LENGKAP, kosong])
    assert sorted(t["jenis"] for t in hasil) == [
        "tanpa_kondisi", "tanpa_koordinat", "tanpa_nilai"]
    assert all(t["asset_id"] == "a3" for t in hasil)


def test_pengamanan_pemeliharaan():
    sengketa = dict(ASET_LENGKAP, id="s1", nomor_perkara="123/PDT/2026")
    rusak = dict(ASET_LENGKAP, id="r1", condition="Rusak Ringan")
    dirawat = dict(ASET_LENGKAP, id="r2", condition="Rusak Ringan")
    catatan = [{"asset_id": "r2", "tanggal": "2026-05-02"},
               {"asset_id": "r1", "tanggal": "2025-12-30"}]  # tahun lalu
    hasil = temuan_pengamanan_pemeliharaan(
        [ASET_LENGKAP, sengketa, rusak, dirawat], catatan, 2026)
    jenis = {t["asset_id"]: t["jenis"] for t in hasil}
    assert jenis == {"s1": "sengketa", "r1": "rusak_tanpa_pemeliharaan"}


def test_susun_dan_rekap():
    per_objek = susun_temuan(
        [dict(ASET_LENGKAP, bast_file_id="")], [], [], [], [], HARI_INI)
    assert set(per_objek) == set(OBJEK_WASDAL)
    assert [t["jenis"] for t in per_objek["penggunaan"]] == ["pemegang_tanpa_bast"]
    assert per_objek["penggunaan"][0]["label"] == JENIS_TEMUAN["pemegang_tanpa_bast"]
    r = rekap_wasdal(per_objek)
    assert r["total"] == 1 and r["per_objek"]["penggunaan"] == 1
    assert r["per_jenis"] == {"pemegang_tanpa_bast": 1}


# ── Penertiban (tenggat 15 hari kerja) ──

def test_tambah_hari_kerja():
    # Jumat 2026-07-10 + 1 hari kerja = Senin 2026-07-13 (lompat akhir pekan)
    assert tambah_hari_kerja("2026-07-10", 1) == "2026-07-13"
    # Senin 2026-07-13 + 5 hari kerja = Senin pekan berikutnya
    assert tambah_hari_kerja("2026-07-13", 5) == "2026-07-20"
    # Default 15 hari kerja = 3 pekan kalender
    assert tambah_hari_kerja("2026-07-13") == "2026-08-03"
    assert tambah_hari_kerja("bukan-tanggal") is None


def test_sisa_hari_kerja():
    assert sisa_hari_kerja("2026-07-10", "2026-07-13") == 1  # Jum → Sen
    assert sisa_hari_kerja("2026-07-13", "2026-07-13") == 0
    assert sisa_hari_kerja("2026-07-14", "2026-07-13") == 0  # sudah lewat
    assert sisa_hari_kerja("x", "2026-07-13") is None


def test_status_tenggat_penertiban():
    tiket = {"status": "berjalan", "tenggat": "2026-07-20"}
    info = status_tenggat_penertiban(tiket, "2026-07-13")
    assert info == {"lewat": False, "sisa_hari_kerja": 5}
    assert status_tenggat_penertiban(tiket, "2026-07-21")["lewat"] is True
    selesai = {"status": "selesai", "tenggat": "2026-07-01"}
    assert status_tenggat_penertiban(selesai, "2026-07-13") == {
        "lewat": False, "sisa_hari_kerja": None}


def test_validate_penertiban():
    ok = {"sumber": "pemantauan", "tanggal_dasar": "2026-07-10",
          "objek": "penggunaan", "uraian": "Aset dikuasai pihak ketiga"}
    assert validate_penertiban(ok) == []
    assert set(SUMBER_PENERTIBAN) == {"pemantauan", "permintaan_pengelola",
                                      "apip_bpk"}
    buruk = validate_penertiban({"sumber": "x", "objek": "y",
                                 "uraian": " ", "tanggal_dasar": "z"})
    assert len(buruk) == 4


def test_validate_selesai_dan_rekap():
    berjalan = {"status": "berjalan", "tenggat": "2026-07-01"}
    assert validate_selesai_penertiban(berjalan, {"tindak_lanjut": "Ditertibkan"}) == []
    assert validate_selesai_penertiban({"status": "selesai"},
                                       {"tindak_lanjut": ""}) != []
    r = rekap_penertiban([berjalan, {"status": "selesai"}], "2026-07-13")
    assert r == {"total": 2, "berjalan": 1, "selesai": 1, "lewat_tenggat": 1}


def test_baris_csv_penertiban():
    from wasdal_utils import HEADER_CSV_PENERTIBAN, baris_csv_penertiban
    assert baris_csv_penertiban([], "2026-07-13") == [HEADER_CSV_PENERTIBAN]
    assert baris_csv_penertiban(None, "2026-07-13") == [HEADER_CSV_PENERTIBAN]
    rows = baris_csv_penertiban([
        {"sumber": "pemantauan", "tanggal_dasar": "2026-07-10",
         "tenggat": "2026-07-20", "objek": "penggunaan",
         "uraian": "Dikuasai pihak ketiga", "status": "berjalan",
         "tindak_lanjut": "", "tanggal_selesai": "",
         "asset_code": "40101", "NUP": "2", "asset_name": "Gedung",
         "created_by": "admin"},
        # Lewat tenggat (berjalan, hari ini > tenggat)
        {"sumber": "apip_bpk", "tanggal_dasar": "2026-06-01",
         "tenggat": "2026-06-20", "status": "berjalan", "uraian": "x"},
        # Selesai → status_tenggat "Selesai"
        {"sumber": "permintaan_pengelola", "status": "selesai",
         "tenggat": "2026-07-01", "tanggal_selesai": "2026-07-05", "uraian": "y"},
    ], "2026-07-13")
    assert rows[0] == HEADER_CSV_PENERTIBAN
    # Baris 1: label sumber/status/objek + "N hk lagi"
    assert rows[1][0] == "Hasil pemantauan KPB"
    assert rows[1][3] == "5 hk lagi" and rows[1][4] == "Berjalan"
    assert rows[1][5] == "Penggunaan"  # objek diterjemahkan ke label
    # Baris 2: lewat tenggat
    assert rows[2][3] == "Lewat tenggat"
    # Baris 3: selesai
    assert rows[3][3] == "Selesai" and rows[3][4] == "Selesai"
    # Field aset hilang → string kosong
    assert rows[2][9] == "" and rows[2][11] == ""


# ── Pemantauan insidentil (10 + 5 hari kerja) ──

def test_validate_insidentil():
    ok = {"pemicu": "informasi_masyarakat", "tanggal_mulai": "2026-07-10",
          "objek": "pengamanan_pemeliharaan", "uraian": "Laporan warga"}
    assert validate_insidentil(ok) == []
    assert set(PEMICU_INSIDENTIL) == {"informasi_masyarakat",
                                      "pemberitaan_media", "hasil_audit"}
    buruk = validate_insidentil({"pemicu": "x", "objek": "y",
                                 "uraian": "", "tanggal_mulai": "z"})
    assert len(buruk) == 4


def test_transisi_insidentil():
    berjalan = {"status": "berjalan"}
    assert validate_ba_insidentil(berjalan, {
        "nomor_ba": "BA-1", "tanggal_ba": "2026-07-15", "hasil": "Sesuai"}) == []
    assert validate_ba_insidentil({"status": "dilaporkan"},
                                  {"nomor_ba": "", "tanggal_ba": "x",
                                   "hasil": ""}) != []
    ba = {"status": "ba_terbit"}
    assert validate_lapor_insidentil(ba, {"tanggal_lapor": "2026-07-16"}) == []
    assert validate_lapor_insidentil(berjalan, {"tanggal_lapor": "x"}) != []


def test_info_tenggat_insidentil():
    # Berjalan: mulai Senin 2026-07-13 → tenggat pelaksanaan Senin 2026-07-27
    t = {"status": "berjalan", "tanggal_mulai": "2026-07-13"}
    info = info_tenggat_insidentil(t, "2026-07-20")
    assert info["tahap"] == "pelaksanaan" and info["tenggat"] == "2026-07-27"
    assert info == {"tahap": "pelaksanaan", "tenggat": "2026-07-27",
                    "lewat": False, "sisa_hari_kerja": 5}
    assert info_tenggat_insidentil(t, "2026-07-28")["lewat"] is True
    # BA terbit: tanggal BA Rabu 2026-07-15 → tenggat lapor Rabu 2026-07-22
    b = {"status": "ba_terbit", "tanggal_ba": "2026-07-15"}
    info = info_tenggat_insidentil(b, "2026-07-16")
    assert info["tahap"] == "lapor" and info["tenggat"] == "2026-07-22"
    # Dilaporkan: tanpa tenggat aktif
    assert info_tenggat_insidentil({"status": "dilaporkan"}, "2026-07-16") == {
        "tahap": None, "tenggat": None, "lewat": False, "sisa_hari_kerja": None}


def test_rekap_insidentil():
    items = [
        {"status": "berjalan", "tanggal_mulai": "2026-06-01"},   # lewat
        {"status": "ba_terbit", "tanggal_ba": "2026-07-10"},
        {"status": "dilaporkan"},
    ]
    r = rekap_insidentil(items, "2026-07-13")
    assert r == {"total": 3, "berjalan": 1, "ba_terbit": 1, "dilaporkan": 1,
                 "lewat_tenggat": 1}


def test_baris_csv_insidentil():
    from wasdal_utils import HEADER_CSV_INSIDENTIL, baris_csv_insidentil
    assert baris_csv_insidentil([], "2026-07-13") == [HEADER_CSV_INSIDENTIL]
    assert baris_csv_insidentil(None, "2026-07-13") == [HEADER_CSV_INSIDENTIL]
    rows = baris_csv_insidentil([
        # berjalan, belum lewat → "N hk lagi (pelaksanaan)"
        {"pemicu": "informasi_masyarakat", "tanggal_mulai": "2026-07-10",
         "lokasi": "Gudang A", "objek": "penggunaan", "uraian": "Laporan warga",
         "status": "berjalan", "created_by": "admin"},
        # berjalan lama → lewat tenggat pelaksanaan
        {"pemicu": "hasil_audit", "tanggal_mulai": "2026-06-01",
         "status": "berjalan", "uraian": "x"},
        # dilaporkan → status_tenggat "Selesai", tak ada tenggat aktif
        {"pemicu": "pemberitaan_media", "status": "dilaporkan",
         "nomor_ba": "BA-9", "tanggal_ba": "2026-07-01",
         "tanggal_lapor": "2026-07-05", "uraian": "y"},
    ], "2026-07-13")
    assert rows[0] == HEADER_CSV_INSIDENTIL
    # Baris 1: label pemicu/objek/status + "N hk lagi (pelaksanaan)"
    assert rows[1][0] == "Informasi masyarakat"
    assert rows[1][3] == "Penggunaan" and rows[1][5] == "Berjalan"
    assert rows[1][7].endswith("(pelaksanaan)")
    # Baris 2: lewat tenggat pelaksanaan
    assert rows[2][7] == "Lewat tenggat pelaksanaan"
    # Baris 3: dilaporkan → Selesai; tenggat aktif kosong
    assert rows[3][5] == "Dilaporkan" and rows[3][7] == "Selesai"
    assert rows[3][6] == "" and rows[3][8] == "BA-9"
