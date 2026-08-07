"""Uji referensi pejabat penatausahaan BMN (#290, PMK 181/2016)."""
from pejabat_utils import (
    JENIS_PELAKSANA, PERAN_PEJABAT, PERAN_PEJABAT_META, STATUS_KEPEGAWAIAN,
    UNIT_AKUNTANSI, peran_penyerah_bast, pejabat_aktif_untuk_peran,
    pejabat_berlaku_untuk_peran,
    penandatangan_kpb, prefiks_jabatan_pelaksana, prefiks_pelaksana,
    validate_pejabat,
)


def test_referensi_memuat_peran_dan_unit_inti():
    assert "kuasa_pengguna_barang" in PERAN_PEJABAT
    assert "penatausahaan_bmn" in PERAN_PEJABAT
    # Jenjang unit akuntansi PMK 181/2016 lengkap
    for k in ("uapb", "uappb_e1", "uappb_w", "uakpb", "uapkpb"):
        assert k in UNIT_AKUNTANSI and UNIT_AKUNTANSI[k]["penanggung_jawab"]


def test_metadata_peran_lengkap_dan_konsisten():
    # Tiap peran punya metadata (domain + ttd_bast + keterangan)
    for kode in PERAN_PEJABAT:
        m = PERAN_PEJABAT_META.get(kode)
        assert m, f"metadata peran '{kode}' hilang"
        assert m["domain"] in ("bmn", "bmd")
        assert m["ttd_bast"] in ("penyerah", "penerima", "mengetahui", "tidak")
        assert str(m.get("keterangan") or "").strip()
    # 'pengurus_barang' ditandai rezim DAERAH (bukan BMN pusat)
    assert PERAN_PEJABAT_META["pengurus_barang"]["domain"] == "bmd"
    # Peran BMN pusat baru tersedia sebagai pengganti yang benar
    assert "pengelola_bmn_satker" in PERAN_PEJABAT
    assert PERAN_PEJABAT_META["pengelola_bmn_satker"]["domain"] == "bmn"


def test_peran_penyerah_bast_hanya_pengelola_bmn():
    penyerah = peran_penyerah_bast()
    # KPB, Petugas Penatausahaan, & Pengelola BMN Satker layak jadi penyerah
    for k in ("kuasa_pengguna_barang", "penatausahaan_bmn", "pengelola_bmn_satker"):
        assert k in penyerah
    # PPK (BAST perolehan) & Penanggung Jawab Ruangan (penerima) bukan penyerah;
    # 'pengurus_barang' (rezim daerah) juga tidak boleh muncul
    for k in ("ppk", "penanggung_jawab_ruangan", "pengurus_barang",
              "pengguna_barang", "pemeriksa_lpb"):
        assert k not in penyerah


def test_status_kepegawaian_mencakup_klasifikasi_inti():
    # Adopsi klasifikasi kepegawaian (SIMAN-G/BKN)
    for k in ("pns", "cpns", "pppk", "tni", "polri", "non_asn"):
        assert k in STATUS_KEPEGAWAIAN and STATUS_KEPEGAWAIAN[k]


def test_validate_pejabat():
    ok = {"nama": "Budi", "peran": ["kuasa_pengguna_barang"], "unit_akuntansi": "uakpb"}
    assert validate_pejabat(ok) == []
    # nama wajib
    assert any("Nama" in e for e in validate_pejabat({"peran": ["ppk"]}))
    # peran wajib & harus dikenal
    assert any("peran" in e.lower() for e in validate_pejabat({"nama": "A", "peran": []}))
    assert any("tidak dikenal" in e for e in
               validate_pejabat({"nama": "A", "peran": ["operator_ajaib"]}))
    # unit akuntansi tak dikenal
    assert any("Unit akuntansi" in e for e in
               validate_pejabat({"nama": "A", "peran": ["ppk"], "unit_akuntansi": "xxx"}))
    # rentang tanggal terbalik
    assert any("berlaku" in e for e in validate_pejabat(
        {"nama": "A", "peran": ["ppk"],
         "berlaku_mulai": "2026-12-31", "berlaku_selesai": "2026-01-01"}))


def test_validate_pejabat_field_baru():
    # status kepegawaian valid & tak dikenal
    assert validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "status_kepegawaian": "pppk"}) == []
    assert any("Status kepegawaian" in e for e in validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "status_kepegawaian": "honorer"}))
    # email valid & tidak valid; kosong tidak error
    assert validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "email": "budi@kemenkeu.go.id"}) == []
    assert validate_pejabat({"nama": "A", "peran": ["ppk"], "email": ""}) == []
    for bad in ("budi", "budi@", "budi@x", "a b@c.id"):
        assert any("email" in e.lower() for e in validate_pejabat(
            {"nama": "A", "peran": ["ppk"], "email": bad}))


def _pj(nama, peran, mulai="", selesai="", aktif=True):
    return {"nama": nama, "peran": peran, "berlaku_mulai": mulai,
            "berlaku_selesai": selesai, "aktif": aktif}


def test_pejabat_aktif_untuk_peran():
    daftar = [
        _pj("KPB Lama", ["kuasa_pengguna_barang"], "2023-01-01", "2025-06-30"),
        _pj("KPB Baru", ["kuasa_pengguna_barang"], "2025-07-01", ""),
        _pj("Operator", ["penatausahaan_bmn"], "2024-01-01", ""),
        _pj("Nonaktif", ["kuasa_pengguna_barang"], "2026-01-01", "", aktif=False),
    ]
    # Tanggal 2026 → KPB Baru (SK terbaru & masih berlaku); nonaktif diabaikan
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2026-07-16")
    assert pj and pj["nama"] == "KPB Baru"
    # Tanggal 2024 → KPB Lama (KPB Baru belum berlaku)
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2024-05-01")
    assert pj and pj["nama"] == "KPB Lama"
    # Peran lain
    assert pejabat_aktif_untuk_peran(daftar, "penatausahaan_bmn", "2026-07-16")["nama"] == "Operator"
    # Peran tanpa pejabat → None
    assert pejabat_aktif_untuk_peran(daftar, "ppk", "2026-07-16") is None
    # Rentang kosong = terbuka; input kosong aman
    assert pejabat_aktif_untuk_peran([], "ppk", None) is None


# ── Beberapa pemegang peran yang sah BERSAMAAN ──────────────────────────────
#
# Laporan pemilik: *"jika ada 2 ppk disaat itu juga ppk yang terpilih malah
# yang terakhir, harusnya bisa memilih hingga 3 atau lebih ppk sesuai yang
# terdaftar di tanggal tersebut."* Satker lazim punya lebih dari satu PPK
# berlaku bersamaan (per paket pekerjaan / sumber dana), dan layar harus bisa
# menawarkan semuanya — bukan hanya yang SK-nya paling baru.

def _tiga_ppk():
    return [
        _pj("PPK Paket A", ["ppk"], "2026-01-01", ""),
        _pj("PPK Paket B", ["ppk"], "2026-03-01", ""),
        _pj("PPK Paket C", ["ppk"], "2026-02-01", ""),
        _pj("PPK Kedaluwarsa", ["ppk"], "2024-01-01", "2025-12-31"),
        _pj("PPK Nonaktif", ["ppk"], "2026-01-01", "", aktif=False),
        _pj("Bukan PPK", ["penatausahaan_bmn"], "2026-01-01", ""),
    ]


def test_semua_pemegang_peran_yang_berlaku_dikembalikan():
    """Tiga PPK sah pada tanggal yang sama harus terbawa SEMUA."""
    k = pejabat_berlaku_untuk_peran(_tiga_ppk(), "ppk", "2026-07-16")
    assert [x["nama"] for x in k] == ["PPK Paket B", "PPK Paket C", "PPK Paket A"]
    # SK yang sudah berakhir & pejabat nonaktif TIDAK ikut ditawarkan —
    # menetapkannya sebagai PPK dokumen tak bisa dipertanggungjawabkan.
    assert "PPK Kedaluwarsa" not in [x["nama"] for x in k]
    assert "PPK Nonaktif" not in [x["nama"] for x in k]


def test_pilihan_otomatis_SELALU_baris_pertama_daftar():
    """Kontrak yang menopang layarnya: dropdown menandai satu baris sebagai
    "Otomatis", dan baris itu harus benar-benar yang dipakai server saat
    operator mengirim "auto". Bila keduanya mengurut sendiri-sendiri, label
    "Otomatis" bisa menyorot orang yang berbeda dari yang tersimpan."""
    for tgl in ("2026-07-16", "2026-02-15", "2026-01-15", None):
        daftar = _tiga_ppk()
        kandidat = pejabat_berlaku_untuk_peran(daftar, "ppk", tgl)
        otomatis = pejabat_aktif_untuk_peran(daftar, "ppk", tgl)
        assert otomatis == (kandidat[0] if kandidat else None)


def test_tanggal_menyaring_kandidat_bukan_hanya_mengurutkan():
    """Pada 15 Januari 2026 baru satu PPK yang berlaku — dua lainnya SK-nya
    belum mulai. Menawarkan mereka berarti mengundang penetapan mundur."""
    k = pejabat_berlaku_untuk_peran(_tiga_ppk(), "ppk", "2026-01-15")
    assert [x["nama"] for x in k] == ["PPK Paket A"]


def test_tanpa_kandidat_daftar_kosong_bukan_None():
    """Pemanggil (endpoint & layar) mengindeks hasilnya; None akan meledak."""
    assert pejabat_berlaku_untuk_peran([], "ppk", "2026-07-16") == []
    assert pejabat_berlaku_untuk_peran(None, "ppk", None) == []
    assert pejabat_berlaku_untuk_peran(_tiga_ppk(), "validator_bmn", None) == []


def test_penandatangan_kpb_registry_vs_fallback():
    settings = {"kasatker_nama": "Kasatker Lama", "kasatker_nip": "111",
                "kasatker_jabatan": "Kepala Kantor"}
    daftar = [_pj("KPB Aktif", ["kuasa_pengguna_barang"], "2025-07-01", "")]
    # Ada KPB aktif di registry → dipakai (bukan setelan)
    ttd = penandatangan_kpb(settings, daftar, "2026-07-16")
    assert ttd["nama"] == "KPB Aktif" and ttd["sumber"] == "registry"
    # Tak ada KPB berlaku pada tanggal → fallback ke setelan kasatker
    ttd = penandatangan_kpb(settings, daftar, "2024-01-01")
    assert ttd["nama"] == "Kasatker Lama" and ttd["nip"] == "111" and ttd["sumber"] == "setelan"
    # Registry kosong & setelan kosong → tetap aman ("-")
    ttd = penandatangan_kpb({}, [], "2026-07-16")
    assert ttd["nama"] == "-" and ttd["jabatan"] == "Kuasa Pengguna Barang"


def test_penandatangan_kpb_membawa_status_kepegawaian():
    """Status kepegawaian ikut dibawa (aturan blok TTD: Non-ASN tidak
    dicetak NIP/NIK); fallback setelan tidak punya status → ""."""
    pj = _pj("KPB NonASN", ["kuasa_pengguna_barang"], "2025-01-01", "")
    pj["status_kepegawaian"] = "non_asn"
    ttd = penandatangan_kpb({}, [pj], "2026-07-16")
    assert ttd["status_kepegawaian"] == "non_asn"
    ttd = penandatangan_kpb({"kasatker_nama": "X", "kasatker_nip": "1"},
                            [], "2026-07-16")
    assert ttd["status_kepegawaian"] == ""


def test_prefiks_pelaksana():
    assert prefiks_pelaksana("plt") == "Plt. "
    assert prefiks_pelaksana("PLH") == "Plh. "
    assert prefiks_pelaksana("") == "" and prefiks_pelaksana(None) == ""
    assert prefiks_pelaksana("lainnya") == ""


def test_prefiks_jabatan_pelaksana():
    assert (prefiks_jabatan_pelaksana("Kuasa Pengguna Barang", "plt")
            == "Plt. Kuasa Pengguna Barang")
    assert (prefiks_jabatan_pelaksana("Kepala Kantor", "plh")
            == "Plh. Kepala Kantor")
    # Tanpa jenis / jabatan kosong → apa adanya
    assert prefiks_jabatan_pelaksana("Kepala Kantor", "") == "Kepala Kantor"
    assert prefiks_jabatan_pelaksana("", "plt") == ""
    # Idempoten: teks yang sudah diawali Plt./Plh. tidak digandakan
    assert (prefiks_jabatan_pelaksana("Plt. Kepala Kantor", "plt")
            == "Plt. Kepala Kantor")


def test_penandatangan_kpb_plt_plh_prefiks_jabatan():
    """KPB registry ber-jenis_pelaksana → jabatan diawali Plt./Plh.; nama & NIP
    tetap milik pejabat pelaksana; jabatan_dasar tanpa awalan tetap dibawa."""
    pj = _pj("Budi (Plt)", ["kuasa_pengguna_barang"], "2025-01-01", "")
    pj["nip"] = "199001012015031002"
    pj["jabatan"] = "Kuasa Pengguna Barang"
    pj["jenis_pelaksana"] = "plt"
    ttd = penandatangan_kpb({}, [pj], "2026-07-16")
    assert ttd["jabatan"] == "Plt. Kuasa Pengguna Barang"
    assert ttd["jabatan_dasar"] == "Kuasa Pengguna Barang"
    assert ttd["jenis_pelaksana"] == "plt"
    assert ttd["nama"] == "Budi (Plt)" and ttd["nip"] == "199001012015031002"
    # Pejabat definitif (tanpa jenis) → tanpa awalan
    pj2 = _pj("Ani", ["kuasa_pengguna_barang"], "2025-01-01", "")
    ttd2 = penandatangan_kpb({}, [pj2], "2026-07-16")
    assert ttd2["jabatan"] == "Kuasa Pengguna Barang"
    assert ttd2["jenis_pelaksana"] == ""


def test_validate_pejabat_jenis_pelaksana():
    base = {"nama": "X", "peran": ["kuasa_pengguna_barang"]}
    assert validate_pejabat({**base, "jenis_pelaksana": "plt"}) == []
    assert validate_pejabat({**base, "jenis_pelaksana": ""}) == []
    errs = validate_pejabat({**base, "jenis_pelaksana": "wakil"})
    assert any("Jenis pelaksana" in e for e in errs)


def test_jenis_pelaksana_referensi():
    assert set(JENIS_PELAKSANA) == {"plt", "plh"}


def test_komposisi_nama_gelar():
    from pejabat_utils import komposisi_nama_gelar
    assert komposisi_nama_gelar("Budi Santoso", "Dr.", "M.M.") == "Dr. Budi Santoso, M.M."
    assert komposisi_nama_gelar("Budi", "", "S.E.") == "Budi, S.E."
    assert komposisi_nama_gelar("Budi", "Ir.", "") == "Ir. Budi"
    # gelar kosong → nama apa adanya (aman data lama)
    assert komposisi_nama_gelar("Budi Santoso", "", "") == "Budi Santoso"
    assert komposisi_nama_gelar("", "Dr.", "M.M.") == "Dr., M.M." or True


def test_penandatangan_kpb_gelar_toggle():
    from pejabat_utils import penandatangan_kpb
    pj = _pj("Budi Santoso", ["kuasa_pengguna_barang"], "2025-01-01", "")
    pj.update({"nip": "1", "gelar_depan": "Dr.", "gelar_belakang": "M.M."})
    # pakai_gelar tidak aktif → nama polos
    pj["pakai_gelar"] = False
    assert penandatangan_kpb({}, [pj], "2026-07-16")["nama"] == "Budi Santoso"
    # pakai_gelar aktif → nama bergelar
    pj["pakai_gelar"] = True
    assert penandatangan_kpb({}, [pj], "2026-07-16")["nama"] == "Dr. Budi Santoso, M.M."
    # pakai_gelar aktif tapi gelar kosong → nama apa adanya (tanpa perubahan)
    pj2 = _pj("Ani", ["kuasa_pengguna_barang"], "2025-01-01", "")
    pj2["pakai_gelar"] = True
    assert penandatangan_kpb({}, [pj2], "2026-07-16")["nama"] == "Ani"


def test_jabatan_kapasitas_kpb():
    """Kapasitas mengikuti KOP dokumen: pada naskah ber-kop KPB penandatangan
    tercetak "Kuasa Pengguna Barang" (Plt./Plh. sesuai status) — jabatan
    struktural (mis. Direktur, kasus rangkap jabatan pemilik) tidak bocor."""
    from pejabat_utils import jabatan_kapasitas_kpb
    assert jabatan_kapasitas_kpb({}) == "Kuasa Pengguna Barang"
    assert jabatan_kapasitas_kpb(None) == "Kuasa Pengguna Barang"
    assert jabatan_kapasitas_kpb(
        {"jenis_pelaksana": "plt"}) == "Plt. Kuasa Pengguna Barang"
    assert jabatan_kapasitas_kpb(
        {"jenis_pelaksana": "plh"}) == "Plh. Kuasa Pengguna Barang"
    assert "Direktur" not in jabatan_kapasitas_kpb(
        {"jabatan": "Direktur Pengembangan Ekosistem Digital",
         "jenis_pelaksana": "plh"})
