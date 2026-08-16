"""Unit test konten baku Berita Acara Hasil Penelitian BMN Tidak Ditemukan."""
import ba_utils


def test_klasifikasikan_tidak_ditemukan():
    aset = [
        {"klasifikasi_tidak_ditemukan": "Kesalahan Pencatatan"},
        {"klasifikasi_tidak_ditemukan": "Tidak Ditemukan Lainnya"},
        {"klasifikasi_tidak_ditemukan": ""},           # kosong → belum diklasifikasi
        {"klasifikasi_tidak_ditemukan": "Hal lain"},   # nilai di luar baku → idem
    ]
    kes, lain, belum = ba_utils.klasifikasikan_tidak_ditemukan(aset)
    assert len(kes) == 1
    # HANYA yang eksplisit "Tidak Ditemukan Lainnya" boleh dianggap hilang —
    # itulah yang memicu rekomendasi penghapusan, SPTJM, dan surat kepolisian.
    assert len(lain) == 1
    assert len(belum) == 2  # kosong + nilai di luar baku
    assert ba_utils.klasifikasikan_tidak_ditemukan([]) == ([], [], [])
    assert ba_utils.klasifikasikan_tidak_ditemukan(None) == ([], [], [])


def test_rekomendasi_tindak_lanjut_per_klasifikasi():
    # kesalahan → koreksi; hilang → penghapusan + SPTJM + TGR
    rek = ba_utils.rekomendasi_tindak_lanjut(2, 3)
    teks = " ".join(rek).lower()
    assert len(rek) == 2
    assert "koreksi pencatatan" in teks
    assert "penghapusan" in teks
    assert "sptjm" in teks
    assert "tuntutan ganti rugi" in teks or "tgr" in teks
    # hanya kesalahan
    rek_k = ba_utils.rekomendasi_tindak_lanjut(1, 0)
    assert len(rek_k) == 1 and "koreksi" in rek_k[0].lower()
    # hanya hilang
    rek_h = ba_utils.rekomendasi_tindak_lanjut(0, 5)
    assert len(rek_h) == 1 and "penghapusan" in rek_h[0].lower()
    # bersih (nol semuanya) → tetap satu paragraf pernyataan
    rek_0 = ba_utils.rekomendasi_tindak_lanjut(0, 0)
    assert len(rek_0) == 1 and "tidak terdapat" in rek_0[0].lower()


def test_rekomendasi_belum_diklasifikasi_bukan_penghapusan():
    """Yang sebabnya belum ditetapkan: penelitian dilanjutkan — BUKAN dihapus."""
    rek = ba_utils.rekomendasi_tindak_lanjut(0, 0, 4)
    assert len(rek) == 1
    teks = rek[0].lower()
    assert "4 nup" in teks
    assert "melanjutkan penelitian" in teks
    assert "belum dapat diusulkan penghapusan" in teks
    # tak boleh terbaca sebagai perintah menghapus atau mengoreksi
    assert "tidak terdapat" not in teks
    # tiga-tiganya terisi → tiga paragraf terpisah
    assert len(ba_utils.rekomendasi_tindak_lanjut(1, 2, 3)) == 3


def test_dokumen_pendukung_ba():
    # tanpa barang hilang: tanpa SPTJM & surat kepolisian
    tanpa = " ".join(ba_utils.dokumen_pendukung_ba(False)).lower()
    assert "sptjm" not in tanpa
    assert "kepolisian" not in tanpa
    # dengan barang hilang: sertakan SPTJM & Surat Keterangan Kepolisian/Inspektorat
    dgn = " ".join(ba_utils.dokumen_pendukung_ba(True)).lower()
    assert "sptjm" in dgn
    assert "kepolisian" in dgn


def test_dokumen_pendukung_belum_diklasifikasi_tak_memicu_sptjm():
    """Aset yang belum diteliti sebabnya tidak boleh menarik SPTJM & surat
    kepolisian ikut masuk daftar dokumen pendukung."""
    hanya_belum = " ".join(ba_utils.dokumen_pendukung_ba(False, True)).lower()
    assert "sptjm" not in hanya_belum
    assert "kepolisian" not in hanya_belum
    assert "kertas kerja penelitian lanjutan" in hanya_belum
    # default parameter kedua tetap False → perilaku pemanggil lama utuh
    assert ba_utils.dokumen_pendukung_ba(True) == ba_utils.dokumen_pendukung_ba(True, False)


def test_konstanta_baku_tidak_kosong():
    assert len(ba_utils.DASAR_HUKUM_BA) >= 3
    assert len(ba_utils.METODE_PENELITIAN_BA) >= 3
    assert "penelitian dokumen" in ba_utils.METODE_PENELITIAN_BA[0].lower()
    assert "peninjauan" in ba_utils.METODE_PENELITIAN_BA[1].lower()
    assert ba_utils.PENUTUP_BA.strip().startswith("Demikian")
