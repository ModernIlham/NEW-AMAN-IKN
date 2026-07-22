"""Konten baku (murni) Berita Acara Hasil Penelitian BMN Tidak Ditemukan.

Dipakai bersama oleh generator PDF (ReportLab) DAN Word/.docx sehingga naskah
resminya SATU sumber kebenaran. Fungsi murni (tanpa Mongo/IO) → dapat diuji
unit.

Landasan format & tindak lanjut (riset praktik penatausahaan BMN DJKN/Kemenkeu
& SE PUPR 10/2023):
- Inventarisasi menghasilkan Daftar BMN Tidak Ditemukan; satker menindaklanjuti
  (PMK 118/PMK.06/2017 jo. S-115/KN/2017) → penelitian oleh Tim Internal yang
  dibentuk Kepala Satker: penelitian dokumen + peninjauan lapangan.
- Penyebab dipilah: (a) Kesalahan Pencatatan → koreksi pencatatan; (b) benar
  hilang ("Tidak Ditemukan Lainnya") → usul penghapusan (PMK 83/PMK.06/2016)
  disertai SPTJM & Surat Keterangan Kepolisian/Inspektorat; bila ada kelalaian
  → Tuntutan Ganti Rugi (TGR).
- Penanda tangan: SELURUH anggota Tim Internal Penelitian (Ketua + Anggota,
  minimal 3), diketahui/disahkan Kuasa Pengguna Barang; saksi bila ada.
"""

# Klasifikasi sebab (selaras field klasifikasi_tidak_ditemukan pada aset).
KLAS_KESALAHAN = "Kesalahan Pencatatan"
KLAS_LAINNYA = "Tidak Ditemukan Lainnya"


DASAR_HUKUM_BA = (
    "Peraturan Pemerintah Nomor 27 Tahun 2014 tentang Pengelolaan Barang Milik "
    "Negara/Daerah sebagaimana telah diubah dengan Peraturan Pemerintah Nomor "
    "28 Tahun 2020;",
    "Peraturan Menteri Keuangan mengenai Penatausahaan Barang Milik Negara "
    "(a.l. PMK Nomor 181/PMK.06/2016 dan perubahannya) serta tata cara "
    "inventarisasi Barang Milik Negara;",
    "Peraturan Menteri Keuangan Nomor 83/PMK.06/2016 tentang Tata Cara "
    "Pelaksanaan Pemusnahan dan Penghapusan Barang Milik Negara;",
    "Peraturan Menteri Keuangan Nomor 118/PMK.06/2017 dan Surat Direktur "
    "Jenderal Kekayaan Negara Nomor S-115/KN/2017 tentang tindak lanjut hasil "
    "inventarisasi Barang Milik Negara yang tidak ditemukan;",
    "Surat Tugas/Keputusan Kuasa Pengguna Barang tentang pembentukan Tim "
    "Internal Penelitian BMN Tidak Ditemukan.",
)


METODE_PENELITIAN_BA = (
    "Penelitian dokumen sumber, meliputi Kartu Identitas Barang, Buku Barang, "
    "Daftar Barang Ruangan, dokumen perolehan (SPM/SP2D, kontrak, Berita Acara "
    "Serah Terima), serta riwayat mutasi pada aplikasi SIMAN/SAKTI;",
    "Peninjauan/pengecekan fisik ke lokasi terakhir barang tercatat dan "
    "konfirmasi kepada penanggung jawab ruangan/pemegang barang;",
    "Penelusuran kemungkinan kesalahan pencatatan (pencatatan ganda, salah "
    "kode/NUP, barang telah dipindahtangankan/dihapus namun belum tercatat);",
    "Pengumpulan bukti pendukung (dokumentasi foto, keterangan saksi, dan/atau "
    "laporan kehilangan) atas barang yang benar-benar tidak ditemukan.",
)


def rekomendasi_tindak_lanjut(n_kesalahan, n_lainnya):
    """Daftar paragraf rekomendasi tindak lanjut per klasifikasi.

    - Kesalahan Pencatatan → koreksi pencatatan (Surat Pernyataan Koreksi).
    - Tidak Ditemukan Lainnya (benar hilang) → usul penghapusan disertai SPTJM
      & Surat Keterangan Kepolisian/Inspektorat; bila lalai → TGR.
    Mengembalikan minimal satu paragraf; bila keduanya nol → pernyataan bersih.
    """
    n_k = int(n_kesalahan or 0)
    n_l = int(n_lainnya or 0)
    out = []
    if n_k:
        out.append(
            f"Terhadap {n_k} NUP BMN yang tidak ditemukan karena KESALAHAN "
            "PENCATATAN, direkomendasikan untuk dilakukan KOREKSI PENCATATAN "
            "sesuai keadaan sebenarnya (Surat Pernyataan Koreksi Pencatatan), "
            "tanpa mengubah keberadaan fisik barang.")
    if n_l:
        out.append(
            f"Terhadap {n_l} NUP BMN yang benar-benar TIDAK DITEMUKAN, "
            "direkomendasikan untuk ditindaklanjuti dengan usul PENGHAPUSAN "
            "sesuai PMK Nomor 83/PMK.06/2016, disertai Surat Pernyataan "
            "Tanggung Jawab Mutlak (SPTJM) dari Kuasa Pengguna Barang serta "
            "Surat Keterangan dari Kepolisian dan/atau hasil pemeriksaan "
            "Aparat Pengawas Intern Pemerintah (Inspektorat). Apabila di "
            "kemudian hari ditemukan unsur kelalaian dan/atau kesengajaan, "
            "diproses melalui Tuntutan Ganti Rugi (TGR) sesuai ketentuan.")
    if not out:
        out.append(
            "Tidak terdapat BMN yang tidak ditemukan pada kegiatan ini "
            "sehingga tidak diperlukan tindak lanjut koreksi maupun "
            "penghapusan.")
    return out


def dokumen_pendukung_ba(ada_hilang):
    """Daftar dokumen pendukung yang menyertai Berita Acara.

    `ada_hilang` True → sertakan SPTJM & Surat Keterangan Kepolisian/Inspektorat
    (syarat usul penghapusan BMN hilang)."""
    docs = [
        "Rekapitulasi Hasil Inventarisasi (RHI);",
        "Daftar Barang Hasil Inventarisasi BMN Tidak Ditemukan;",
        "Dokumentasi foto lokasi dan/atau bukti penelusuran.",
    ]
    if ada_hilang:
        docs += [
            "Surat Pernyataan Tanggung Jawab Mutlak (SPTJM) dari Kuasa "
            "Pengguna Barang;",
            "Surat Keterangan dari Kepolisian dan/atau Laporan Hasil "
            "Pemeriksaan Inspektorat (untuk BMN yang benar-benar hilang).",
        ]
    return docs


PENUTUP_BA = (
    "Demikian Berita Acara Hasil Penelitian ini dibuat dengan sebenar-benarnya, "
    "dalam keadaan sadar dan tanpa tekanan dari pihak mana pun, untuk "
    "dipergunakan sebagaimana mestinya.")


def klasifikasikan_tidak_ditemukan(tidak_ditemukan):
    """Pisah aset tidak ditemukan → (kesalahan, lainnya) berdasar field
    `klasifikasi_tidak_ditemukan`. Nilai selain 'Kesalahan Pencatatan' &
    'Tidak Ditemukan Lainnya' (mis. kosong) dihitung sebagai 'lainnya' agar
    tidak hilang dari rekomendasi penghapusan."""
    kes, lain = [], []
    for a in tidak_ditemukan or []:
        k = str((a or {}).get("klasifikasi_tidak_ditemukan") or "").strip()
        if k == KLAS_KESALAHAN:
            kes.append(a)
        else:
            lain.append(a)
    return kes, lain
