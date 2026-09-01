"""SYARAT DOKUMEN USULAN BMN — satu sumber kebenaran, LOGIKA MURNI.

Permintaan pemilik: *"carikan untuk keperluan dokumen apa saja yang
diperlukan pada saat penetapan status barang ... akan tetapi tambah lagi
informasi dan peraturan yang seharusnya agar semua keperluan dokumen untuk
segala macam jenis pengusulan BMN dapat ditangani aplikasi dengan baik ...
agar pengajuan ke SIMAN V2 dari segala pengusulan kondisi dapat dimanajemen
dengan baik."*

── Kenapa ini DATA, bukan sembilan slot ter-hardcode ───────────────────────
Daftar sembilan lampiran yang beredar luas (dan yang ada di tangkapan layar
KPKNL) berasal dari **PMK 246/PMK.06/2014 jo. 76/PMK.06/2019**. Untuk rezim
Penggunaan, keduanya sudah **digantikan PMK 40 Tahun 2024**, yang menyusun
daftarnya **bercabang per jenis objek** (Pasal 11 ayat (2) huruf a–g), bukan
sebagai sembilan slot seragam. Sembilan slot wajib akan menagih sertipikat
kepada pemilik laptop dan menagih IMB kepada pemilik kendaraan.

Karena itu setiap butir di sini membawa **pemicunya sendiri**: ia wajib hanya
bila keadaannya memang menghendaki. Lihat `docs/SYARAT-DOKUMEN-USULAN-BMN.md`.

── Kejujuran bukti: tiga tingkat, bukan satu ──────────────────────────────
Sumber primer (jdih.kemenkeu.go.id, peraturan.bpk.go.id, djkn.kemenkeu.go.id)
**terblokir** dari lingkungan pengembangan — lihat `docs/SITASI-DOKUMEN-RESMI.md`.
Menyeragamkan seluruh daftar menjadi "wajib" akan menyembunyikan perbedaan
antara pasal yang sudah dibaca dan tebakan praktik. Maka setiap butir
membawa `verifikasi`:

  `terverifikasi`   — pasalnya sudah dibaca dan dikutip di dokumen repo
  `empiris_siman`   — TERBACA dari layar SIMAN V2 itu sendiri (tangkapan
                      layar pemilik). Ini bukan norma hukum, tetapi ia
                      justru yang paling menentukan apakah unggahan
                      DITERIMA sistem — dan karena itu tak boleh dibuang
  `belum_terverifikasi` — praktik lapangan/booklet KPKNL; berguna sebagai
                      anjuran, TIDAK boleh jadi gerbang yang memblokir

── Yang modul ini TIDAK lakukan ───────────────────────────────────────────
Tidak memutuskan siapa berwenang menyetujui apa, dan tidak mencetak nomor
pasal ke dokumen bermeterai. Ia menyusun DAFTAR PERIKSA. Perutean kewenangan
(ambang Rp100 juta dsb.) tinggal di tempatnya sendiri.
"""

# ── Kosakata ───────────────────────────────────────────────────────────────

#: Sifat butir. `wajib_bersyarat` sengaja dipisah dari `wajib`: ia wajib
#: HANYA saat pemicunya benar, dan menyamakannya dengan `wajib` persis
#: kesalahan "sembilan slot" yang modul ini ada untuk mencegahnya.
SIFAT = {
    "wajib": "Wajib",
    "wajib_bersyarat": "Wajib bila berlaku",
    # `muatan` BUKAN lampiran. Beberapa pasal meminta datanya ada DI DALAM
    # surat permohonan — data BMN pada Pasal 11/24/34/46/54, misalnya —
    # tanpa pernah menyebutnya sebagai berkas terpisah. Menagihnya sebagai
    # unggahan akan melaporkan "belum lengkap" untuk usulan yang sebenarnya
    # sudah benar; menghapusnya akan menyembunyikan kewajiban yang nyata.
    # Jadi ia ditampilkan, dengan keterangan DI MANA ia harus berada.
    "muatan": "Muatan surat permohonan",
    "anjuran": "Dianjurkan",
    "opsional": "Opsional",
}

VERIFIKASI = {
    "terverifikasi": "Pasal terbaca",
    "empiris_siman": "Terbaca dari layar SIMAN V2",
    "belum_terverifikasi": "Praktik lapangan — belum terverifikasi",
}

#: Jenis objek. PMK 40/2024 memecah tanah/bangunan menjadi TIGA keranjang
#: lampiran terpisah; frasa "tanah dan/atau bangunan" hanya dipakai untuk
#: objek KEWENANGAN, tidak pernah untuk lampiran. Menggabungkannya jadi satu
#: cabang akan menagih IMB kepada pemilik tanah kosong.
JENIS_OBJEK = {
    "tanah": "Tanah",
    "bangunan": "Bangunan",
    "tanah_dan_bangunan": "Tanah dan Bangunan",
    "selain_tb": "Selain Tanah dan/atau Bangunan",
}

#: Rezim usulan yang dikenal. Kunci Penggunaan sengaja sama persis dengan
#: `JENIS_PSP`/`JENIS_PROSES_PENGGUNAAN` di `penggunaan_utils.py`, dan kunci
#: pemindahtanganan sama dengan `BENTUK_PEMINDAHTANGANAN` di
#: `pemindahtanganan_utils.py` — supaya tak lahir kosakata kedua yang harus
#: dipetakan bolak-balik.
REZIM = {
    "psp": "Penetapan Status Penggunaan (PSP)",
    "penggunaan_sementara": "Penggunaan Sementara",
    "dioperasikan_pihak_lain": "Dioperasikan Pihak Lain",
    "alih_status": "Alih Status Penggunaan",
    "penggunaan_bersama": "Penggunaan Bersama",
    "hibah": "Hibah",
    "penjualan_lelang": "Penjualan (lelang KPKNL)",
    "penjualan_langsung": "Penjualan tanpa lelang (kasus khusus)",
    "tukar_menukar": "Tukar Menukar",
    "pmpp": "Penyertaan Modal Pemerintah Pusat",
    "penghapusan": "Penghapusan",
    "pemusnahan": "Pemusnahan",
    "sewa": "Pemanfaatan — Sewa",
    "pinjam_pakai": "Pemanfaatan — Pinjam Pakai",
}

# ── Katalog dokumen ────────────────────────────────────────────────────────
#
# Nama dokumen dipakai APA ADANYA sebagai label unggahan. Di mana SIMAN V2
# memakai nama tertentu, nama ITU yang dipakai (bukan padanan yang lebih
# rapi) — operator harus bisa mencocokkan satu lawan satu dengan dropdown
# "Jenis Dokumen" di SIMAN, dan nama yang "diperbaiki" justru menghambat.

KATALOG_DOKUMEN = {
    "surat_permohonan": "Surat Permohonan",
    "daftar_bmn": "Daftar BMN yang diusulkan",
    "sk_psp": "Fotokopi Keputusan Penetapan Status Penggunaan BMN",
    "sertipikat": "Fotokopi sertipikat hak atas tanah",
    "imb_pbg": "Fotokopi IMB atau PBG",
    "dok_perolehan_bangunan": "Fotokopi dokumen perolehan bangunan",
    "dok_kepemilikan": "Fotokopi dokumen kepemilikan (BPKB/kapal/pesawat atau setara)",
    "dok_lain_bast": "Fotokopi dokumen lain, termasuk BAST perolehan barang",
    "ket_kebenaran_fotokopi": "Surat Keterangan Kebenaran Fotokopi",
    "ket_kebenaran_arsip_digital": "Surat Keterangan Kebenaran Arsip Digital",
    "sptj": "Surat Pernyataan Tanggung Jawab (SPTJ) bermeterai",
    "dasar_pendelegasian": "Dasar pendelegasian kewenangan penanda tangan",
    "kib": "Kartu Identitas Barang (KIB)",
    "foto_bmn": "Foto BMN",
    "laporan_kondisi": "Laporan Kondisi Barang",
    "lapor_kehilangan": "Surat laporan kehilangan dari Kepolisian",
    "dok_penganggaran": "Dokumen penganggaran (DIPA/RKA-K/L/KAK/POK)",
    "reviu_apip": "Hasil reviu/audit APIP atau BPK",
    "bast_pengelolaan_sementara": "BAST pengelolaan sementara",
    "surat_permintaan_sementara": "Fotokopi surat permintaan Penggunaan sementara",
    "surat_permintaan_pengoperasian": "Fotokopi surat permintaan pengoperasian dari Pihak Lain",
    "pernyataan_pihak_lain": "Surat pernyataan bermeterai dari Pihak Lain",
    "estimasi_pungutan": "Perhitungan estimasi biaya operasional dan besaran pungutan",
    "pernyataan_kesediaan_menerima": "Surat pernyataan kesediaan menerima pengalihan (calon Pengguna Barang baru)",
    "pernyataan_kesediaan_mengalihkan": "Surat pernyataan kesediaan mengalihkan (Pengguna Barang lama)",
    "data_kolaborator": "Data/informasi Kolaborator",
    "permintaan_hibah": ("Surat permintaan hibah/surat pernyataan bersedia "
                         "menerima hibah BMN dari calon penerima hibah"),
    "data_calon_penerima_hibah": "Data Calon Penerima Hibah",
    "dok_penganggaran_hibah": ("Dokumen Penganggaran yang menunjukkan bahwa BMN "
                              "tersebut untuk dihibahkan"),
    "sk_tim_internal": "SK Pembentukan Tim Internal",
    "pernyataan_instansi_teknis": "Surat pernyataan dari instansi teknis yang berwenang",
    "penilaian": "Laporan Penilaian / nilai taksiran",
    "berita_acara_penelitian": ("Berita acara penelitian tim internal "
                               "(data administratif + penelitian fisik)"),
    "pernyataan_pemusnahan": ("Surat Pernyataan Pengguna/Kuasa Pengguna Barang "
                             "(identitas, tanggung jawab materiil dan formil, "
                             "pernyataan BMN tak dapat digunakan/dimanfaatkan/"
                             "dipindahtangankan)"),
    "putusan_pengadilan": ("Salinan/fotokopi putusan pengadilan berkekuatan "
                          "hukum tetap, dilegalisasi pejabat berwenang"),
    "dok_pengganti_kepemilikan": ("Dokumen pengganti bukti kepemilikan (kontrak, "
                                 "akta/perjanjian jual beli, atau setara) ATAU "
                                 "Surat Pernyataan bermeterai cukup"),
    "pernyataan_kebenaran_objek": ("Surat pernyataan atas kebenaran formil dan "
                                  "materiil objek dan besaran nilai yang "
                                  "diusulkan"),
    "pernyataan_perlunya_tukar_menukar": ("Surat pernyataan tanggung jawab atas "
                                         "perlunya dilaksanakan Tukar Menukar"),
    "perda_tata_ruang": ("Peraturan daerah mengenai tata ruang wilayah atau "
                        "penataan kota"),
    "rincian_barang_pengganti": ("Rincian kebutuhan barang pengganti (tanah: luas "
                                "dan lokasi; bangunan: jenis, luas, rencana "
                                "konstruksi, sarana dan prasarana penunjang)"),
    "kajian_tim_internal": "Hasil kajian tim internal",
    "pernyataan_kesediaan_pmpp": ("Pernyataan kesediaan calon penerima Penyertaan "
                                 "Modal Pemerintah Pusat"),
    "dok_pelaksanaan_pt": ("Dokumen pelaksanaan pemindahtanganan (risalah lelang, "
                          "perjanjian penjualan, naskah hibah, dan/atau BAST "
                          "sesuai bentuknya)"),
    "pendukung_sptj_tanah": ("Dokumen pendukung SPTJ tanah (akta jual beli/"
                            "girik/letter C/BAST/ledger jalan, surat keterangan "
                            "lurah/camat, surat permohonan pendaftaran hak, "
                            "dan/atau dokumen penguasaan)"),
    "dok_penganggaran_pmpp": ("Fotokopi KAK, RKA-K/L, atau POK (bila DIPA tak "
                              "tegas menyatakan BMN untuk PMPP)"),
    # — Pemanfaatan: Sewa (KMK 213/KM.6/2021 BAB III) —
    "identitas_pemohon_sewa": "Identitas diri calon penyewa (NIK dan/atau NPWP)",
    "usulan_peruntukan_sewa": ("Usulan peruntukan Sewa mengacu jenis kegiatan "
                               "usaha (bisnis, non bisnis, sosial)"),
    "usulan_jangka_periodesitas": ("Usulan jangka waktu dan periodesitas Sewa "
                                   "(per jam/hari/bulan ≤1 tahun; per tahun >1 "
                                   "tahun)"),
    "informasi_objek_pemanfaatan": ("Informasi BMN objek Pemanfaatan — luas "
                                    "keseluruhan dan yang dimanfaatkan untuk "
                                    "tanah/bangunan; jumlah atau kapasitas "
                                    "untuk selain tanah/bangunan"),
    "kajian_rencana_sewa": ("Kajian rencana Sewa (proyeksi usaha dan proyeksi "
                            "keuangan)"),
    "usulan_faktor_penyesuai": "Usulan faktor penyesuai Sewa dalam kondisi tertentu",
    "akta_pendirian_koperasi": ("Akta pendirian yang memuat anggaran dasar "
                                "koperasi"),
    "ket_usaha_mikro": ("Surat keterangan bentuk usaha dan jumlah kekayaan "
                        "bersih (ultra mikro, mikro, kecil)"),
    "laporan_keuangan_sederhana": ("Laporan keuangan dalam bentuk sederhana "
                                   "berisi hasil penjualan"),
    "pernyataan_inisiasi_satker": ("Surat pernyataan pimpinan unit/satker bahwa "
                                   "peruntukan Sewa adalah inisiasi satker "
                                   "pengguna BMN"),
    "pernyataan_sarpras_pendidikan": ("Surat pernyataan pimpinan unit/satker "
                                      "bahwa Sewa sarana/prasarana pendidikan "
                                      "untuk keluarga ASN/TNI/Polri dan pegawai "
                                      "penunjang"),
    "ket_kegiatan_sosial": ("Dokumen dari instansi dan/atau pihak terkait yang "
                            "menjelaskan kegiatan bersifat sosial"),
    # — Pemanfaatan: Pinjam Pakai (KMK 213/KM.6/2021 BAB IV) —
    "permohonan_calon_peminjam": ("Surat permohonan Pinjam Pakai dari calon "
                                  "peminjam pakai (pertimbangan, identitas, "
                                  "tujuan, jangka waktu)"),
    "pernyataan_tak_ganggu_tusi": ("Surat pernyataan Pengguna Barang bahwa "
                                   "Pinjam Pakai tidak mengganggu pelaksanaan "
                                   "tugas dan fungsi penyelenggaraan "
                                   "pemerintahan negara"),
    "data_bmn_objek": ("Data BMN objek — kode barang, nama barang, NUP, tahun "
                       "perolehan, harga perolehan, nilai buku"),
    "keputusan_pp_sebelumnya": ("Keputusan Pinjam Pakai sebelumnya dari "
                                "Pengelola Barang"),
    "pernyataan_pp_masih_digunakan": ("Surat pernyataan peminjam pakai bahwa "
                                      "objek masih digunakan untuk menunjang "
                                      "tugas dan fungsi Pemda/Pemdes"),
    "pertimbangan_pinjam_pakai": "Pertimbangan yang mendasari permohonan Pinjam Pakai",
    "identitas_peminjam_pakai": "Identitas peminjam pakai",
    "tujuan_penggunaan_pp": "Tujuan penggunaan objek Pinjam Pakai",
    "dokumen_lainnya": "Dokumen Lainnya",
}

# ── Pemicu ─────────────────────────────────────────────────────────────────
#
# Ditulis sebagai fungsi bernama, bukan lambda di dalam tabel: namanya muncul
# di pesan kesalahan dan di uji, dan tiap pemicu bisa diuji sendiri.
#
# SEMUA pemicu memakai `konteks.get(...)` dengan bawaan yang AMAN. "Aman" di
# sini berarti condong ke MENAMPILKAN butir, bukan menyembunyikannya: butir
# yang muncul padahal tak perlu hanya merepotkan; butir yang hilang padahal
# perlu membuat berkas dikembalikan berminggu-minggu kemudian.


def _objek(konteks) -> str:
    return str((konteks or {}).get("jenis_objek") or "").strip()


def objek_tanah(konteks) -> bool:
    return _objek(konteks) in ("tanah", "tanah_dan_bangunan")


def objek_bangunan(konteks) -> bool:
    return _objek(konteks) in ("bangunan", "tanah_dan_bangunan")


def objek_selain_tb(konteks) -> bool:
    return _objek(konteks) == "selain_tb"


def punya_dok_kepemilikan(konteks) -> bool:
    return bool((konteks or {}).get("punya_dokumen_kepemilikan"))


def tanpa_dok_kepemilikan(konteks) -> bool:
    return objek_selain_tb(konteks) and not punya_dok_kepemilikan(konteks)


def ada_fotokopi(konteks) -> bool:
    """Bawaan True: berkas usulan BMN nyaris selalu memuat fotokopi."""
    k = konteks or {}
    return bool(k.get("ada_fotokopi", True))


def unggah_pindaian(konteks) -> bool:
    """Bawaan True: seluruh alur SIMAN V2 adalah unggahan arsip digital."""
    k = konteks or {}
    return bool(k.get("unggah_pindaian", True))


def dokumen_tidak_ada(konteks) -> bool:
    """SPTJ adalah PENGGANTI dokumen yang tidak ada — bukan lampiran yang
    selalu wajib. Membuatnya wajib-selalu adalah kesalahan versi lama."""
    return bool((konteks or {}).get("dokumen_tidak_ada"))


def tanah_tanpa_sertipikat(konteks) -> bool:
    """Tanah yang BELUM bersertipikat — satu-satunya keadaan yang memicu SPTJ
    pada rezim PSP.

    KOREKSI atas pembacaan sekunder. Pasal 11 ayat (3) tidak berbunyi
    "pengganti dokumen apa pun yang tidak ada": ia dikecualikan secara
    spesifik dari **huruf a, huruf c angka 1, dan huruf e angka 3** — ketiganya
    tentang sertipikat TANAH. SPTJ tak pernah menggantikan BPKB kendaraan
    ataupun IMB bangunan.

    Bidang lama `dokumen_tidak_ada` tetap dibaca agar catatan yang sudah
    tersimpan dengan pembacaan lama tidak kehilangan maknanya — tetapi hanya
    bila objeknya memang bertanah.
    """
    k = konteks or {}
    if not objek_tanah(k):
        return False
    return bool(k.get("tanah_tanpa_sertipikat") or k.get("dokumen_tidak_ada"))


def tanah_bersertipikat(konteks) -> bool:
    """Kebalikan `tanah_tanpa_sertipikat` untuk objek bertanah. Dipakai agar
    sertipikat BERHENTI ditagih saat SPTJ menggantikannya — Pasal 11 ayat (3)
    menyebutnya "diganti", bukan "ditambah"."""
    return objek_tanah(konteks) and not tanah_tanpa_sertipikat(konteks)


def perlu_dokumen_lain(konteks) -> bool:
    """Objek yang pasalnya meminta "fotokopi dokumen lain, termasuk BAST".

    KOREKSI. Registry lama hanya menagihnya untuk selain-tanah/bangunan TANPA
    dokumen kepemilikan. Teks aslinya jauh lebih luas — ia diminta pada huruf
    b angka 3 (bangunan), huruf c angka 4 (tanah dan bangunan), huruf d angka
    1 huruf b (selain t/b YANG PUNYA dokumen kepemilikan: STNK atau BAST),
    dan huruf d angka 2 (yang tidak punya). Satu-satunya yang TIDAK dimintai
    adalah tanah berdiri sendiri (huruf a hanya menyebut sertipikat).

    Akibat cacat lama: pemegang gedung tak pernah ditagih BAST perolehan,
    padahal pasalnya memintanya — dan kekurangannya baru ketahuan saat berkas
    dikembalikan Pengelola Barang.
    """
    o = _objek(konteks)
    return bool(o) and o != "tanah"


def dipa_tidak_tegas(konteks) -> bool:
    """DIPA tak menyatakan tegas BMN direncanakan untuk PMPP (huruf f)."""
    return untuk_pmpp(konteks) and bool((konteks or {}).get("dipa_tidak_tegas"))


def wajib_kib(konteks) -> bool:
    """BMN yang memang harus dilengkapi Kartu Identitas Barang.

    PMK 83/2016 Pasal 11 ayat (2) huruf c dan Pasal 40 ayat (2) huruf c
    berbunyi *"untuk BMN yang harus dilengkapi dengan kartu identitas
    barang"* — bersyarat pada jenis barangnya, bukan berlaku menyeluruh.
    Bawaan True: golongan yang ber-KIB (tanah, bangunan, kendaraan) justru
    yang paling sering diusulkan.
    """
    k = konteks or {}
    return bool(k.get("wajib_kib", True))


def wajib_dok_kepemilikan(konteks) -> bool:
    """BMN yang memang harus dilengkapi dokumen kepemilikan — frasa
    bersyarat yang sama pada PMK 83/2016."""
    return punya_dok_kepemilikan(konteks)


def tanpa_dok_kepemilikan_umum(konteks) -> bool:
    """Kebalikannya, lintas rezim (bukan khusus selain tanah/bangunan seperti
    `tanpa_dok_kepemilikan` yang dipakai rezim PSP)."""
    return not punya_dok_kepemilikan(konteks)


def sebab_putusan_pengadilan(konteks) -> bool:
    return str((konteks or {}).get("sebab_penghapusan") or "") == "putusan_pengadilan"


def objek_tanah_atau_bangunan(konteks) -> bool:
    """Objek yang mengandung tanah dan/atau bangunan — frasa yang dipakai
    PMK 111/2016 untuk memisahkan tata caranya."""
    return _objek(konteks) in ("tanah", "bangunan", "tanah_dan_bangunan")


def sebab_pemindahtanganan(konteks) -> bool:
    """Sebab penghapusan yang paling lazim di satker. Bawaan bila tak diisi:
    condong MENAMPILKAN butirnya."""
    s = str((konteks or {}).get("sebab_penghapusan") or "").strip()
    return s in ("", "pemindahtanganan")


def dokumen_hilang(konteks) -> bool:
    return bool((konteks or {}).get("dokumen_hilang"))


def penandatangan_didelegasikan(konteks) -> bool:
    return bool((konteks or {}).get("penandatangan_didelegasikan"))


def untuk_pmpp(konteks) -> bool:
    return bool((konteks or {}).get("untuk_pmpp"))


def fisik_tak_dikuasai(konteks) -> bool:
    return untuk_pmpp(konteks) and bool((konteks or {}).get("fisik_tak_dikuasai"))


def ada_pungutan_masyarakat(konteks) -> bool:
    return bool((konteks or {}).get("ada_pungutan_masyarakat"))


def dalam_rangka_kspi(konteks) -> bool:
    return bool((konteks or {}).get("kspi"))


def penerima_lembaga_nonpemerintah(konteks) -> bool:
    return bool((konteks or {}).get("penerima_lembaga_nonpemerintah"))


def pemohon_pihak_ketiga(konteks) -> bool:
    """Jalur permohonan Sewa dari CALON PENYEWA langsung ke Pengelola Barang.
    KMK 213/KM.6/2021 BAB III memisahkannya dari jalur Pengguna Barang, dan
    hanya jalur ini yang menagih identitas diri (NIK/NPWP)."""
    return bool((konteks or {}).get("pemohon_pihak_ketiga"))


def sewa_lebih_5_tahun(konteks) -> bool:
    """Kajian rencana Sewa hanya ditagih untuk jangka waktu lebih dari lima
    tahun; menagihnya pada sewa pendek akan membebani tanpa dasar."""
    try:
        return float((konteks or {}).get("jangka_waktu_sewa_tahun") or 0) > 5
    except (TypeError, ValueError):
        return False


def _kelompok_usaha(konteks) -> str:
    return str((konteks or {}).get("kelompok_usaha") or "").strip().lower()


def sewa_koperasi(konteks) -> bool:
    return _kelompok_usaha(konteks) == "koperasi"


def sewa_usaha_mikro(konteks) -> bool:
    return _kelompok_usaha(konteks) in ("ultra_mikro", "mikro", "kecil")


def sewa_kegiatan_sosial(konteks) -> bool:
    return _kelompok_usaha(konteks) == "sosial"


def sewa_inisiasi_pengguna(konteks) -> bool:
    return bool((konteks or {}).get("sewa_inisiasi_pengguna"))


def sewa_sarpras_pendidikan(konteks) -> bool:
    return bool((konteks or {}).get("sewa_sarpras_pendidikan"))


def perpanjangan(konteks) -> bool:
    """Perpanjangan jangka waktu, bukan permohonan baru. Lampirannya berbeda:
    keputusan sebelumnya dan pernyataan objek masih digunakan."""
    return bool((konteks or {}).get("perpanjangan"))


PEMICU = {
    f.__name__: f for f in (
        objek_tanah, objek_bangunan, objek_selain_tb, punya_dok_kepemilikan,
        tanpa_dok_kepemilikan, ada_fotokopi, unggah_pindaian, dokumen_tidak_ada,
        dokumen_hilang, penandatangan_didelegasikan, untuk_pmpp,
        fisik_tak_dikuasai, ada_pungutan_masyarakat, dalam_rangka_kspi,
        penerima_lembaga_nonpemerintah, tanah_tanpa_sertipikat,
        tanah_bersertipikat, perlu_dokumen_lain, dipa_tidak_tegas,
        wajib_kib, wajib_dok_kepemilikan, tanpa_dok_kepemilikan_umum,
        sebab_putusan_pengadilan, sebab_pemindahtanganan,
        objek_tanah_atau_bangunan,
        pemohon_pihak_ketiga, sewa_lebih_5_tahun, sewa_koperasi,
        sewa_usaha_mikro, sewa_kegiatan_sosial, sewa_inisiasi_pengguna,
        sewa_sarpras_pendidikan, perpanjangan,
    )
}


# ── Tabel syarat per rezim ─────────────────────────────────────────────────
#
# Bentuk tiap butir: (kode, sifat, pemicu|None, dasar, verifikasi)
# `pemicu=None` berarti berlaku tanpa syarat pada rezim itu.
#
# ── Mengapa BAST-PSP TIDAK ada di sini ────────────────────────────────────
# Permintaan pemilik: *"untuk output BERITA ACARA SERAH TERIMA PENETAPAN
# STATUS PENGGUNAAN BARANG MILIK NEGARA harusnya tidak diperlukan."* Itu
# benar menurut teksnya: Pasal 11 ayat (2) tidak pernah meminta BAST sebagai
# lampiran yang berdiri sendiri. BAST muncul di sana hanya sebagai
# `dok_lain_bast` — PENGGANTI dokumen kepemilikan yang tidak ada. BAST PSP
# yang dicetak AMAN adalah dokumen serah terima INTERNAL kepada pemegang,
# terbit SESUDAH SK-nya ada; ia bukan berkas yang diunggah untuk memperoleh
# SK itu. Menagihnya sebagai syarat akan membalik urutan sebab-akibat.

_PSP = (
    ("surat_permohonan", "wajib", None,
     "PMK 40/2024 Pasal 11 ayat (1)", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 40/2024 Pasal 11 ayat (1) — data BMN adalah MUATAN permohonan; "
     "PMK tidak menyebutnya sebagai lampiran terpisah", "terverifikasi"),
    # `tanah_bersertipikat`, bukan `objek_tanah`: ayat (3) menyebut sertipikat
    # DIGANTI SPTJ bila tanahnya belum bersertipikat — bukan ditambah.
    ("sertipikat", "wajib_bersyarat", "tanah_bersertipikat",
     "PMK 40/2024 Pasal 11 ayat (2) huruf a dan huruf c angka 1",
     "terverifikasi"),
    ("imb_pbg", "wajib_bersyarat", "objek_bangunan",
     "PMK 40/2024 Pasal 11 ayat (2) huruf b angka 1 dan huruf c angka 2",
     "terverifikasi"),
    ("dok_perolehan_bangunan", "wajib_bersyarat", "objek_bangunan",
     "PMK 40/2024 Pasal 11 ayat (2) huruf b angka 2 dan huruf c angka 3",
     "terverifikasi"),
    ("dok_kepemilikan", "wajib_bersyarat", "punya_dok_kepemilikan",
     "PMK 40/2024 Pasal 11 ayat (2) huruf d angka 1", "terverifikasi"),
    # KOREKSI (teks primer, 2026-09-01): diminta pada huruf b angka 3, huruf c
    # angka 4, huruf d angka 1 huruf b, DAN huruf d angka 2 — semua objek
    # kecuali tanah yang berdiri sendiri. Registry lama hanya menagihnya untuk
    # selain-t/b tanpa dokumen kepemilikan, sehingga pemegang gedung tak
    # pernah ditagih BAST perolehan yang pasalnya minta.
    ("dok_lain_bast", "wajib_bersyarat", "perlu_dokumen_lain",
     "PMK 40/2024 Pasal 11 ayat (2) huruf b angka 3, huruf c angka 4, huruf d "
     "angka 1 huruf b (STNK/BAST), dan huruf d angka 2", "terverifikasi"),
    # KOREKSI: SPTJ khusus TANAH belum bersertipikat, bukan pengganti dokumen
    # apa pun yang hilang. Ayat (3) dikecualikan dari huruf a, huruf c angka 1,
    # dan huruf e angka 3 — ketiganya tentang sertipikat tanah.
    ("sptj", "wajib_bersyarat", "tanah_tanpa_sertipikat",
     "PMK 40/2024 Pasal 11 ayat (3) — menggantikan sertipikat pada tanah yang "
     "belum bersertipikat; ditandatangani pejabat struktural, bermeterai cukup",
     "terverifikasi"),
    ("pendukung_sptj_tanah", "wajib_bersyarat", "tanah_tanpa_sertipikat",
     "PMK 40/2024 Pasal 11 ayat (3) huruf a–d — SPTJ tanah wajib DILENGKAPI "
     "dokumen ini (\"dan/atau\": salah satunya sudah memenuhi)",
     "terverifikasi"),
    ("ket_kebenaran_fotokopi", "wajib_bersyarat", "ada_fotokopi",
     "PMK 40/2024 Pasal 11 ayat (2) huruf g — berlaku atas fotokopi pada "
     "huruf a sampai huruf f, dari pejabat struktural K/L bersangkutan",
     "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "wajib_bersyarat", "unggah_pindaian",
     "PMK 40/2024 Pasal 73 ayat (1) huruf a — nama baku dokumennya belum "
     "ditetapkan; konfirmasikan judulnya ke KPKNL", "terverifikasi"),
    ("dasar_pendelegasian", "wajib_bersyarat", "penandatangan_didelegasikan",
     "PMK 40/2024 Pasal 7 ayat (6)–(7)", "terverifikasi"),
    ("dok_penganggaran", "wajib_bersyarat", "untuk_pmpp",
     "PMK 40/2024 Pasal 11 ayat (2) huruf e", "terverifikasi"),
    ("reviu_apip", "wajib_bersyarat", "untuk_pmpp",
     "PMK 40/2024 Pasal 11 ayat (2) huruf e", "terverifikasi"),
    ("bast_pengelolaan_sementara", "wajib_bersyarat", "fisik_tak_dikuasai",
     "PMK 40/2024 Pasal 11 ayat (2) huruf e angka 7", "terverifikasi"),
    ("dok_penganggaran_pmpp", "wajib_bersyarat", "dipa_tidak_tegas",
     "PMK 40/2024 Pasal 11 ayat (2) huruf f — bila DIPA tak tegas menyatakan "
     "BMN direncanakan untuk PMPP", "terverifikasi"),
    # ANJURAN, bukan wajib-bersyarat: sumbernya satu blog praktisi, dan
    # PMK 40/2024 tak menyebutnya. Menaikkannya jadi wajib akan menahan
    # usulan atas dasar yang teksnya sendiri tak pernah minta.
    ("lapor_kehilangan", "anjuran", "dokumen_hilang",
     "Tidak disebut PMK 40/2024; praktik lapangan", "belum_terverifikasi"),
    ("kib", "anjuran", None,
     "Kata 'KIB'/'Kartu Identitas Barang' TIDAK ada di PMK 40/2024. Tetap "
     "praktik penatausahaan, bukan lampiran yang diwajibkan pasal ini",
     "belum_terverifikasi"),
    ("foto_bmn", "anjuran", None,
     "PMK 40/2024 Pasal 13 memberi Pengelola wewenang pengecekan lapangan, "
     "sehingga foto memperlancar — fotonya sendiri tidak diwajibkan",
     "belum_terverifikasi"),
    ("laporan_kondisi", "anjuran", None,
     "Tidak disebut PMK 40/2024; praktik SIMAK-BMN/SAKTI",
     "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "empiris_siman"),
)

_PENGGUNAAN_SEMENTARA = (
    ("surat_permohonan", "wajib", None,
     "PMK 40/2024 Pasal 34 ayat (1)", "terverifikasi"),
    ("sk_psp", "wajib", None,
     "PMK 40/2024 Pasal 34 ayat (3) huruf a", "terverifikasi"),
    ("surat_permintaan_sementara", "wajib", None,
     "PMK 40/2024 Pasal 34 ayat (3) huruf b", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 40/2024 Pasal 34 ayat (2) huruf a — MUATAN permohonan, bukan "
     "lampiran mandiri", "terverifikasi"),
    ("kib", "anjuran", None, "Checklist praktik KPKNL", "belum_terverifikasi"),
    ("ket_kebenaran_fotokopi", "anjuran", "ada_fotokopi",
     "Kewajiban tekstualnya melekat pada Pasal 11 (rezim PSP), bukan Pasal 34",
     "belum_terverifikasi"),
    ("ket_kebenaran_arsip_digital", "wajib_bersyarat", "unggah_pindaian",
     "PMK 40/2024 Pasal 73 ayat (1) huruf a — berlaku lintas rezim",
     "terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "empiris_siman"),
)

_DIOPERASIKAN = (
    ("surat_permohonan", "wajib", None,
     "PMK 40/2024 Pasal 24 ayat (1)", "terverifikasi"),
    ("sk_psp", "wajib", None,
     "PMK 40/2024 Pasal 24 ayat (3) huruf a", "terverifikasi"),
    ("surat_permintaan_pengoperasian", "wajib", None,
     "PMK 40/2024 Pasal 24 ayat (3) huruf b", "terverifikasi"),
    ("pernyataan_pihak_lain", "wajib", None,
     "PMK 40/2024 Pasal 24 ayat (3) huruf c jo. ayat (4) — memuat 5 hal: "
     "tujuan pengoperasian; kesediaan menanggung biaya pengamanan dan "
     "pemeliharaan; kesediaan menyetor ke kas negara; tidak mengalihkan; "
     "mengembalikan saat Penggunaan berakhir", "terverifikasi"),
    ("estimasi_pungutan", "wajib_bersyarat", "ada_pungutan_masyarakat",
     "PMK 40/2024 Pasal 24 ayat (2) huruf f", "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "wajib_bersyarat", "unggah_pindaian",
     "PMK 40/2024 Pasal 73 ayat (1) huruf a", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 40/2024 Pasal 24 ayat (2) huruf a — MUATAN permohonan",
     "terverifikasi"),
    ("foto_bmn", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
    ("laporan_kondisi", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "empiris_siman"),
)

_ALIH_STATUS = (
    ("surat_permohonan", "wajib", None,
     "PMK 40/2024 Pasal 54 ayat (1)", "terverifikasi"),
    ("sk_psp", "wajib", None,
     "PMK 40/2024 Pasal 54 ayat (3) huruf a", "terverifikasi"),
    ("pernyataan_kesediaan_menerima", "wajib", None,
     "PMK 40/2024 Pasal 54 ayat (3) huruf b — ditandatangani PENERIMA "
     "(calon Pengguna Barang baru), bukan pemohon", "terverifikasi"),
    ("pernyataan_kesediaan_mengalihkan", "wajib_bersyarat", "dalam_rangka_kspi",
     "PMK 40/2024 Pasal 59 ayat (2) — khusus Kerja Sama Penyediaan "
     "Infrastruktur; arahnya berlawanan dengan pernyataan penerima",
     "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "wajib_bersyarat", "unggah_pindaian",
     "PMK 40/2024 Pasal 73 ayat (1) huruf a", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 40/2024 Pasal 54 ayat (2) huruf a — MUATAN permohonan meliputi "
     "jenis, nilai perolehan, lokasi, luas, dan tahun perolehan",
     "terverifikasi"),
    ("dok_kepemilikan", "anjuran", "punya_dok_kepemilikan",
     "Checklist praktik KPKNL (±11 butir) — sumbernya paling lemah",
     "belum_terverifikasi"),
    ("kib", "anjuran", None, "Checklist praktik KPKNL", "belum_terverifikasi"),
    ("foto_bmn", "anjuran", None, "Checklist praktik KPKNL", "belum_terverifikasi"),
    ("laporan_kondisi", "anjuran", None, "Checklist praktik KPKNL",
     "belum_terverifikasi"),
    ("dasar_pendelegasian", "wajib_bersyarat", "penandatangan_didelegasikan",
     "PMK 40/2024 Pasal 7 ayat (6)–(7)", "terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "empiris_siman"),
)

_PENGGUNAAN_BERSAMA = (
    ("surat_permohonan", "wajib", None,
     "PMK 40/2024 Pasal 46 — diajukan tertulis oleh Eminen", "terverifikasi"),
    ("data_kolaborator", "muatan", None,
     "PMK 40/2024 Pasal 46 — MUATAN permohonan Eminen", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 40/2024 Pasal 46 — MUATAN permohonan Eminen", "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "wajib_bersyarat", "unggah_pindaian",
     "PMK 40/2024 Pasal 73 ayat (1) huruf a", "terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "empiris_siman"),
)

# ── Hibah ──────────────────────────────────────────────────────────────────
# Daftar ini TERBACA dari layar SIMAN V2 (tangkapan layar pemilik, dropdown
# "Jenis Dokumen" pada dialog Kelengkapan Dokumen untuk hibah selain tanah
# dan bangunan), lengkap dengan penanda Mandatory/Opsional milik SIMAN
# sendiri. Statusnya `empiris_siman`, bukan `terverifikasi`: ia bukan kutipan
# pasal. Tetapi justru daftar inilah yang menentukan apakah unggahan
# DITERIMA — jadi ia dipakai apa adanya, termasuk nama panjangnya.
_HIBAH = (
    ("surat_permohonan", "wajib", None,
     "PMK 111/2016 Pasal 93 huruf c (tanah/bangunan) dan Pasal 95 huruf c "
     "(selain tanah/bangunan) — diajukan Pengguna Barang kepada Pengelola "
     "Barang; SIMAN V2 juga menandainya Mandatory", "terverifikasi"),
    ("permintaan_hibah", "wajib", None,
     "PMK 111/2016 Pasal 93 huruf c dan Pasal 95 huruf c — permohonan "
     "DISERTAI surat pernyataan kesediaan menerima Hibah dari calon "
     "penerima; SIMAN V2 menandainya Mandatory", "terverifikasi"),
    ("data_calon_penerima_hibah", "wajib", None,
     "PMK 111/2016 Pasal 93 huruf a angka 1 huruf c dan Pasal 95 huruf a "
     "angka 1 huruf b — identitas calon penerima diteliti tim internal; "
     "SIMAN V2 menandainya Mandatory", "terverifikasi"),
    ("berita_acara_penelitian", "wajib", None,
     "PMK 111/2016 Pasal 93 huruf a angka 2 jo. huruf b, dan Pasal 95 huruf "
     "a angka 2 jo. huruf b — hasil penelitian tim internal dituangkan dalam "
     "berita acara dan disampaikan kepada Pengguna Barang. TIDAK ada di "
     "daftar SIMAN V2 maupun registry sebelumnya", "terverifikasi"),
    # KIB: disebut Pasal 93 untuk TANAH/BANGUNAN, tetapi TIDAK disebut Pasal
    # 95 untuk selain tanah/bangunan — padahal SIMAN V2 menandainya Mandatory
    # justru pada layar hibah selain t/b. Keduanya dipertahankan apa adanya:
    # inilah alasan tingkat bukti `empiris_siman` dipisahkan dari pasal.
    ("kib", "wajib", None,
     "PMK 111/2016 Pasal 93 huruf a angka 1 huruf a dan b menyebut KIB untuk "
     "tanah/bangunan; Pasal 95 (selain tanah/bangunan) TIDAK menyebutnya, "
     "namun SIMAN V2 tetap menandainya Mandatory di layar hibah selain t/b — "
     "sistem meminta lebih dari pasalnya", "empiris_siman"),
    ("dok_penganggaran_hibah", "wajib_bersyarat", "dipa_tidak_tegas",
     "PMK 111/2016 Pasal 94 — BMN yang sejak awal pengadaannya dimaksudkan "
     "untuk dihibahkan menambah persyaratan dokumen penganggaran; SIMAN V2 "
     "menandainya Opsional", "terverifikasi"),
    ("sk_tim_internal", "opsional", None,
     "PMK 111/2016 Pasal 93 huruf a dan Pasal 95 huruf a mewajibkan Pengguna "
     "Barang MEMBENTUK tim internal; SK-nya sendiri ditandai Opsional oleh "
     "SIMAN V2 — yang wajib timnya, bukan lampiran SK-nya", "terverifikasi"),
    ("dok_kepemilikan", "muatan", "punya_dok_kepemilikan",
     "PMK 111/2016 Pasal 93 huruf c dan Pasal 95 huruf c — bukti kepemilikan "
     "atau dokumen setara adalah MUATAN permohonan", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 111/2016 Pasal 93 huruf c dan Pasal 95 huruf c — jenis/spesifikasi, "
     "tahun perolehan, nilai perolehan, dan lokasi/data teknis adalah MUATAN "
     "permohonan", "terverifikasi"),
    ("sptj", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
    ("pernyataan_instansi_teknis", "anjuran", "penerima_lembaga_nonpemerintah",
     "Pustaka repo §7: penerima lembaga sosial/budaya/keagamaan/kemanusiaan/"
     "pendidikan non-komersial wajib disertai pernyataan instansi teknis — "
     "pasalnya belum terbaca", "belum_terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
)

# ── PEMUSNAHAN: [F] PMK 83/2016 Pasal 11 ──────────────────────────────────
_PEMUSNAHAN = (
    ("surat_permohonan", "wajib", None,
     "PMK 83/2016 Pasal 11 ayat (1) — diajukan Pengguna Barang kepada "
     "Pengelola Barang", "terverifikasi"),
    ("pernyataan_pemusnahan", "wajib", None,
     "PMK 83/2016 Pasal 11 ayat (2) huruf a", "terverifikasi"),
    ("dok_kepemilikan", "wajib_bersyarat", "wajib_dok_kepemilikan",
     "PMK 83/2016 Pasal 11 ayat (2) huruf b — untuk BMN yang harus "
     "dilengkapi dokumen kepemilikan", "terverifikasi"),
    ("dok_pengganti_kepemilikan", "wajib_bersyarat", "tanpa_dok_kepemilikan_umum",
     "PMK 83/2016 Pasal 11 ayat (3) — pengganti bila dokumen kepemilikannya "
     "tidak ada", "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "PMK 83/2016 Pasal 11 ayat (2) huruf c — untuk BMN yang harus "
     "dilengkapi kartu identitas barang", "terverifikasi"),
    # Keduanya WAJIB di sini, sedangkan pada rezim PSP hanya anjuran. Beda
    # yang nyata, dan hanya terlihat setelah kedua pasalnya dibaca.
    ("laporan_kondisi", "wajib", None,
     "PMK 83/2016 Pasal 11 ayat (2) huruf d", "terverifikasi"),
    ("foto_bmn", "wajib", None,
     "PMK 83/2016 Pasal 11 ayat (2) huruf e — foto TERKINI", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 83/2016 Pasal 11 ayat (1) huruf b — tahun perolehan, identitas "
     "barang, nilai perolehan dan/atau nilai buku adalah MUATAN permohonan",
     "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── PENGHAPUSAN: [F] PMK 83/2016 Pasal 38 dan Pasal 40 ────────────────────
_PENGHAPUSAN = (
    ("surat_permohonan", "wajib", None,
     "PMK 83/2016 Pasal 40 ayat (1) untuk sebab putusan pengadilan; untuk "
     "sebab pemindahtanganan yang disampaikan adalah LAPORAN Penghapusan "
     "(Pasal 38 ayat (3))", "terverifikasi"),
    ("dok_pelaksanaan_pt", "wajib_bersyarat", "sebab_pemindahtanganan",
     "PMK 83/2016 Pasal 38 ayat (3) huruf a–d — risalah lelang dan/atau BAST "
     "(penjualan lelang), perjanjian penjualan dan/atau BAST (tanpa lelang), "
     "BAST (tukar menukar/PMPP), naskah hibah dan/atau BAST (hibah)",
     "terverifikasi"),
    ("putusan_pengadilan", "wajib_bersyarat", "sebab_putusan_pengadilan",
     "PMK 83/2016 Pasal 40 ayat (2) huruf a", "terverifikasi"),
    ("dok_kepemilikan", "wajib_bersyarat", "wajib_dok_kepemilikan",
     "PMK 83/2016 Pasal 40 ayat (2) huruf b", "terverifikasi"),
    ("dok_pengganti_kepemilikan", "wajib_bersyarat", "tanpa_dok_kepemilikan_umum",
     "PMK 83/2016 Pasal 40 ayat (3)", "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "PMK 83/2016 Pasal 40 ayat (2) huruf c", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 83/2016 Pasal 40 ayat (1) huruf b — MUATAN permohonan",
     "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── Rezim yang pasalnya BELUM terbaca ──────────────────────────────────────
#
# Sumber primer PMK 111/2016 jo. 165/2021 (pemindahtanganan), PMK 115/2020
# (pemanfaatan), dan aturan penghapusan/pemusnahan TERBLOKIR dari lingkungan
# pengembangan. Godaannya adalah mengarang daftar yang "masuk akal"; itu
# persis yang menghasilkan sembilan slot wajib.
#
# Yang dilakukan sebagai gantinya: kerangka DASAR yang benar-benar berulang
# di semua rezim usulan BMN — surat permohonan, daftar BMN, dan dua surat
# keterangan kebenaran — seluruhnya bertanda `belum_terverifikasi` sehingga
# antarmuka menampilkannya sebagai ANJURAN, bukan gerbang. Operator tetap
# mendapat daftar periksa yang berguna, tanpa aplikasi berpura-pura tahu.
_KERANGKA_DASAR = (
    ("surat_permohonan", "wajib", None,
     "Berulang di seluruh rezim usulan BMN", "belum_terverifikasi"),
    ("daftar_bmn", "wajib", None,
     "Berulang di seluruh rezim usulan BMN", "belum_terverifikasi"),
    ("ket_kebenaran_fotokopi", "anjuran", "ada_fotokopi",
     "Praktik lapangan", "belum_terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("kib", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
    ("foto_bmn", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
    ("laporan_kondisi", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── PENJUALAN: [F] PMK 111/2016 Pasal 32 (tanah/bangunan) & 33 (selain) ──
_PENJUALAN = (
    ("surat_permohonan", "wajib", None,
     "PMK 111/2016 Pasal 32 huruf e dan Pasal 33 huruf g — diajukan Pengguna "
     "Barang kepada Pengelola Barang", "terverifikasi"),
    ("pernyataan_kebenaran_objek", "wajib", None,
     "PMK 111/2016 Pasal 32 huruf e angka 3 (kebenaran MATERIIL) dan Pasal 33 "
     "huruf g angka 4 (kebenaran FORMIL DAN MATERIIL objek serta besaran "
     "nilai)", "terverifikasi"),
    ("berita_acara_penelitian", "wajib", None,
     "PMK 111/2016 Pasal 32 huruf a angka 2 jo. huruf d, dan Pasal 33 huruf a "
     "angka 2 jo. huruf f — penelitian data administratif dan fisik dituangkan "
     "dalam berita acara", "terverifikasi"),
    # Penilaian hanya melekat pada Pengguna Barang untuk SELAIN tanah/bangunan;
    # pada tanah/bangunan Penilaian dimohonkan PENGELOLA kepada Penilai
    # (Pasal 32 huruf f angka 4), jadi ia bukan lampiran pemohon.
    ("penilaian", "wajib_bersyarat", "objek_selain_tb",
     "PMK 111/2016 Pasal 33 huruf c–e jo. huruf g angka 3 — hasil Penilaian "
     "jadi dasar penetapan nilai limit Penjualan", "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "PMK 111/2016 Pasal 32 huruf a angka 1 — data tanah dan bangunan "
     "sebagaimana tercantum dalam Kartu Identitas Barang", "terverifikasi"),
    ("imb_pbg", "wajib_bersyarat", "objek_bangunan",
     "PMK 111/2016 Pasal 32 huruf a angka 1 huruf b — dokumen pendukung "
     "seperti Izin Mendirikan Bangunan", "terverifikasi"),
    ("sk_psp", "muatan", "objek_selain_tb",
     "PMK 111/2016 Pasal 33 huruf a angka 1 — keputusan penetapan status "
     "penggunaan termasuk data administratif yang diteliti", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 111/2016 Pasal 32 huruf e angka 1–2 dan Pasal 33 huruf g angka 2 — "
     "data administratif serta nilai perolehan/nilai buku adalah MUATAN "
     "permohonan", "terverifikasi"),
    ("sk_tim_internal", "opsional", None,
     "PMK 111/2016 Pasal 32 huruf b dan Pasal 33 huruf b — Pengguna Barang "
     "DAPAT membentuk tim internal. Berbeda dari rezim hibah, yang "
     "mewajibkannya (Pasal 93/95 huruf a)", "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── TUKAR MENUKAR: [F] PMK 111/2016 Pasal 77 ─────────────────────────────
_TUKAR_MENUKAR = (
    ("surat_permohonan", "wajib", None,
     "PMK 111/2016 Pasal 77 huruf a — permohonan persetujuan kepada Pengelola "
     "Barang", "terverifikasi"),
    ("pernyataan_perlunya_tukar_menukar", "wajib", None,
     "PMK 111/2016 Pasal 77 huruf a angka 2 — ditandatangani Pengguna Barang "
     "atau pejabat struktural yang diberi kuasa", "terverifikasi"),
    ("perda_tata_ruang", "wajib_bersyarat", "objek_tanah_atau_bangunan",
     "PMK 111/2016 Pasal 77 huruf a angka 3", "terverifikasi"),
    ("rincian_barang_pengganti", "wajib", None,
     "PMK 111/2016 Pasal 77 huruf a angka 5 — inilah pembeda pokok tukar "
     "menukar dari bentuk pemindahtanganan lain", "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "PMK 111/2016 Pasal 77 huruf a angka 4 — data BMN yang DILEPAS "
     "sebagaimana tercantum dalam Kartu Identitas Barang", "terverifikasi"),
    ("imb_pbg", "wajib_bersyarat", "objek_bangunan",
     "PMK 111/2016 Pasal 77 huruf a angka 4 huruf b", "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 111/2016 Pasal 77 huruf a angka 1 dan 4 — penjelasan/pertimbangan "
     "dan data administratif BMN yang dilepas", "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── PMPP: [F] PMK 111/2016 (BAB VI, tata cara pada Pengguna Barang) ──────
_PMPP = (
    ("surat_permohonan", "wajib", None,
     "PMK 111/2016 BAB VI — permohonan persetujuan kepada Pengelola Barang "
     "memuat penjelasan/pertimbangan", "terverifikasi"),
    ("kajian_tim_internal", "wajib", None,
     "PMK 111/2016 BAB VI huruf c angka 2 — hasil kajian tim internal",
     "terverifikasi"),
    ("penilaian", "wajib_bersyarat", "objek_selain_tb",
     "PMK 111/2016 BAB VI huruf c angka 3 — hasil Penilaian BMN selain tanah "
     "dan/atau bangunan yang TELAH DITETAPKAN Pengguna Barang; untuk tanah "
     "dan/atau bangunan, Penilaian dimohonkan Pengelola kepada Penilai",
     "terverifikasi"),
    ("pernyataan_kesediaan_pmpp", "wajib", None,
     "PMK 111/2016 BAB VI huruf c angka 4 — pernyataan kesediaan calon "
     "penerima menerima PMPP yang berasal dari BMN", "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "PMK 111/2016 BAB VI huruf c angka 1 — kelengkapan data administratif",
     "terverifikasi"),
    ("daftar_bmn", "muatan", None,
     "PMK 111/2016 BAB VI huruf c angka 1", "terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── SEWA: [F] KMK 213/KM.6/2021 BAB III ─────────────────────────────────
#
# PMK 115/2020 **Pasal 96** mendelegasikan tata cara pelaksanaannya kepada
# "Keputusan Menteri Keuangan yang ditandatangani oleh Direktur Jenderal atas
# nama Menteri Keuangan". Daftar dokumennya karena itu memang tidak ada di
# batang tubuh PMK-nya — bukan karena belum dibaca, melainkan karena bukan di
# sana tempatnya. KMK pelaksananya adalah **213/KM.6/2021**, dan naskahnya
# masuk pustaka pada unduhan kesembilan (2026-09-01).
#
# CATATAN BENTUK. BAB III sama sekali tidak memakai kata "dilampiri": seluruh
# butir permohonan Sewa adalah **muatan surat**, bukan berkas yang diunggah.
# Karena itu hampir semuanya bersifat `muatan`. Yang benar-benar berupa
# lampiran hanyalah dokumen pendukung faktor penyesuai — dan semuanya
# bersyarat.
_SEWA = (
    ("surat_permohonan", "wajib", None,
     "KMK 213/KM.6/2021 BAB III — Sewa diajukan calon penyewa atau Pengguna "
     "Barang kepada Pengelola Barang", "terverifikasi"),
    ("identitas_pemohon_sewa", "muatan", "pemohon_pihak_ketiga",
     "KMK 213/KM.6/2021 BAB III huruf a angka 1) — identitas diri (NIK "
     "dan/atau NPWP); hanya pada jalur permohonan calon penyewa",
     "terverifikasi"),
    ("usulan_peruntukan_sewa", "muatan", None,
     "KMK 213/KM.6/2021 BAB III huruf a angka 2) — mengacu jenis kegiatan "
     "usaha (bisnis, non bisnis, sosial)", "terverifikasi"),
    ("usulan_jangka_periodesitas", "muatan", None,
     "KMK 213/KM.6/2021 BAB III huruf a angka 3) dan 4) — jangka waktu Sewa "
     "dan periodesitas bila diusulkan", "terverifikasi"),
    ("informasi_objek_pemanfaatan", "muatan", None,
     "KMK 213/KM.6/2021 BAB III huruf a angka 6); pada jalur Pengguna Barang "
     "angka 4) merinci luas tanah/bangunan keseluruhan dan yang disewakan, "
     "atau jumlah/kapasitas untuk selain tanah/bangunan", "terverifikasi"),
    ("kajian_rencana_sewa", "wajib_bersyarat", "sewa_lebih_5_tahun",
     "KMK 213/KM.6/2021 BAB III jalur Pengguna Barang angka 2) — proyeksi "
     "usaha dan proyeksi keuangan, untuk Sewa berjangka waktu LEBIH DARI 5 "
     "(lima) tahun", "terverifikasi"),
    ("usulan_faktor_penyesuai", "opsional", None,
     "KMK 213/KM.6/2021 BAB III huruf a angka 7) — 'jika ada'",
     "terverifikasi"),
    # Dokumen pendukung faktor penyesuai — satu-satunya LAMPIRAN sungguhan di
    # rezim Sewa, dan tiap butirnya melekat pada kelompok usaha tertentu.
    ("akta_pendirian_koperasi", "wajib_bersyarat", "sewa_koperasi",
     "KMK 213/KM.6/2021 BAB III angka 1 huruf a — syarat faktor penyesuai 50% "
     "(koperasi primer) atau 75% (koperasi sekunder)", "terverifikasi"),
    ("ket_usaha_mikro", "wajib_bersyarat", "sewa_usaha_mikro",
     "KMK 213/KM.6/2021 BAB III angka 1 huruf b angka 1) — syarat faktor "
     "penyesuai 25% bagi pelaku usaha perorangan ultra mikro, mikro, dan kecil",
     "terverifikasi"),
    ("laporan_keuangan_sederhana", "wajib_bersyarat", "sewa_usaha_mikro",
     "KMK 213/KM.6/2021 BAB III angka 1 huruf b angka 2) — laporan keuangan "
     "sederhana berisi hasil penjualan", "terverifikasi"),
    ("pernyataan_inisiasi_satker", "wajib_bersyarat", "sewa_inisiasi_pengguna",
     "KMK 213/KM.6/2021 BAB III angka 2 huruf b — syarat faktor penyesuai 15% "
     "karena peruntukan Sewa diinisiasi Pengguna Barang untuk mendukung tugas "
     "dan fungsi", "terverifikasi"),
    ("pernyataan_sarpras_pendidikan", "wajib_bersyarat",
     "sewa_sarpras_pendidikan",
     "KMK 213/KM.6/2021 BAB III angka 2 huruf c — syarat faktor penyesuai 10% "
     "untuk sarana dan prasarana pendidikan keluarga ASN/TNI/Polri dan pegawai "
     "penunjang", "terverifikasi"),
    ("ket_kegiatan_sosial", "wajib_bersyarat", "sewa_kegiatan_sosial",
     "KMK 213/KM.6/2021 BAB III angka 3 — syarat faktor penyesuai 2,5% untuk "
     "kegiatan sosial; diterbitkan instansi dan/atau pihak terkait",
     "terverifikasi"),
    # Penilaian BUKAN lampiran pemohon: KMK-nya menugaskan PENGELOLA BARANG
    # yang menunjuk Penilai. Tetap ditampilkan sebagai keterangan supaya
    # operator tak menyiapkannya sendiri dengan sia-sia.
    ("penilaian", "anjuran", None,
     "KMK 213/KM.6/2021 BAB III huruf b angka 3) — Penilaian ditugaskan "
     "PENGELOLA BARANG kepada Penilai, bukan lampiran pemohon; bila BMN sudah "
     "masuk daftar tarif pokok Sewa, besarannya memakai daftar itu",
     "terverifikasi"),
    ("ket_kebenaran_fotokopi", "anjuran", "ada_fotokopi",
     "Praktik lapangan", "belum_terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

# ── PINJAM PAKAI: [F] KMK 213/KM.6/2021 BAB IV ──────────────────────────
#
# Berbeda dari Sewa, BAB IV MEMANG memakai kata "dilampiri" — jadi di sini
# ada berkas yang benar-benar diunggah, dan pembedaan `muatan` vs `wajib`
# mengikuti teksnya, bukan selera.
_PINJAM_PAKAI = (
    ("surat_permohonan", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV — Pengguna Barang mengajukan permohonan "
     "persetujuan Pinjam Pakai kepada Pengelola Barang", "terverifikasi"),
    ("pertimbangan_pinjam_pakai", "muatan", None,
     "KMK 213/KM.6/2021 BAB IV huruf a angka 1) — pertimbangan yang mendasari "
     "permohonan", "terverifikasi"),
    ("identitas_peminjam_pakai", "muatan", None,
     "KMK 213/KM.6/2021 BAB IV huruf a angka 2)", "terverifikasi"),
    ("tujuan_penggunaan_pp", "muatan", None,
     "KMK 213/KM.6/2021 BAB IV huruf a angka 3)", "terverifikasi"),
    ("informasi_objek_pemanfaatan", "muatan", None,
     "KMK 213/KM.6/2021 BAB IV huruf a angka 4) — rincian data BMN, termasuk "
     "luas tanah dan lokasi tanah dan/atau bangunan bila objeknya tanah "
     "dan/atau bangunan", "terverifikasi"),
    ("usulan_jangka_periodesitas", "muatan", None,
     "KMK 213/KM.6/2021 BAB IV huruf a angka 5) — jangka waktu; paling lama 5 "
     "(lima) tahun sejak perjanjian ditandatangani", "terverifikasi"),
    # — Lampiran sungguhan: "dilampiri dengan" —
    ("permohonan_calon_peminjam", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV huruf b angka 1) — dilampiri surat permohonan "
     "dari calon peminjam pakai (Pemerintah Daerah atau Pemerintah Desa)",
     "terverifikasi"),
    ("pernyataan_tak_ganggu_tusi", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV huruf b angka 2) — pernyataan Pengguna Barang "
     "bahwa Pinjam Pakai tidak mengganggu pelaksanaan tugas dan fungsi "
     "penyelenggaraan pemerintahan negara", "terverifikasi"),
    ("data_bmn_objek", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV huruf b angka 3) huruf a) — kode barang, nama "
     "barang, NUP, tahun perolehan, harga perolehan, nilai buku",
     "terverifikasi"),
    ("kib", "wajib_bersyarat", "wajib_kib",
     "KMK 213/KM.6/2021 BAB IV huruf b angka 3) huruf b) — 'jika BMN didukung "
     "dengan KIB'", "terverifikasi"),
    ("foto_bmn", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV huruf b angka 3) huruf c) — foto atas objek "
     "Pinjam Pakai", "terverifikasi"),
    # — Diperiksa pada penelitian administrasi Pengelola Barang —
    ("sk_psp", "wajib", None,
     "KMK 213/KM.6/2021 BAB IV angka 2 huruf e — keputusan penetapan status "
     "penggunaan atas BMN yang akan menjadi objek Pinjam Pakai; termasuk "
     "dokumen yang diteliti Pengelola Barang", "terverifikasi"),
    ("dok_kepemilikan", "wajib_bersyarat", "wajib_dok_kepemilikan",
     "KMK 213/KM.6/2021 BAB IV angka 2 huruf d angka 1) — bukti kepemilikan "
     "atau dokumen yang dipersamakan", "terverifikasi"),
    # — Perpanjangan: lampirannya berbeda —
    ("keputusan_pp_sebelumnya", "wajib_bersyarat", "perpanjangan",
     "KMK 213/KM.6/2021 BAB IV — permohonan perpanjangan dilampiri keputusan "
     "Pinjam Pakai sebelumnya; diterima paling lambat 2 (dua) bulan sebelum "
     "jangka waktu berakhir", "terverifikasi"),
    ("pernyataan_pp_masih_digunakan", "wajib_bersyarat", "perpanjangan",
     "KMK 213/KM.6/2021 BAB IV — pernyataan peminjam pakai bahwa objek masih "
     "digunakan untuk menunjang tugas dan fungsi Pemda/Pemdes",
     "terverifikasi"),
    ("ket_kebenaran_fotokopi", "anjuran", "ada_fotokopi",
     "Praktik lapangan", "belum_terverifikasi"),
    ("ket_kebenaran_arsip_digital", "anjuran", "unggah_pindaian",
     "Praktik lapangan untuk unggahan arsip digital", "belum_terverifikasi"),
    ("dokumen_lainnya", "opsional", None, "—", "belum_terverifikasi"),
)

SYARAT = {
    "psp": _PSP,
    "penggunaan_sementara": _PENGGUNAAN_SEMENTARA,
    "dioperasikan_pihak_lain": _DIOPERASIKAN,
    "alih_status": _ALIH_STATUS,
    "penggunaan_bersama": _PENGGUNAAN_BERSAMA,
    "hibah": _HIBAH,
    "penjualan_lelang": _PENJUALAN,
    "penjualan_langsung": _PENJUALAN,
    "tukar_menukar": _TUKAR_MENUKAR,
    "pmpp": _PMPP,
    "penghapusan": _PENGHAPUSAN,
    "pemusnahan": _PEMUSNAHAN,
    "sewa": _SEWA,
    "pinjam_pakai": _PINJAM_PAKAI,
}

#: Rezim yang seluruh butir wajibnya bertumpu pada pasal yang sudah dibaca.
#: Dipakai antarmuka untuk memutuskan apakah pantas menampilkan gerbang
#: "berkas belum lengkap" atau sekadar daftar anjuran.
REZIM_BERDASAR_PASAL = frozenset({
    "psp", "penggunaan_sementara", "dioperasikan_pihak_lain",
    "alih_status", "penggunaan_bersama",
    # Naik setelah teks primernya masuk pustaka (2026-09-01): PMK 111/2016
    # Pasal 93 & 95 untuk hibah; PMK 83/2016 Pasal 11, 38, dan 40 untuk
    # pemusnahan dan penghapusan.
    "hibah", "pemusnahan", "penghapusan",
    # Naik 2026-09-01 putaran kedua: PMK 111/2016 Pasal 32, 33, 77, dan BAB VI.
    "penjualan_lelang", "penjualan_langsung", "tukar_menukar", "pmpp",
    # Naik 2026-09-01 putaran ketiga, DUA REZIM TERAKHIR. PMK 115/2020 Pasal
    # 96 mendelegasikan tata caranya ke KMK, dan KMK itu — 213/KM.6/2021 —
    # akhirnya masuk pustaka. BAB III memuat tata cara Sewa, BAB IV Pinjam
    # Pakai. Sampai naskahnya benar-benar terbaca, keduanya sengaja ditahan
    # di `belum_terverifikasi` selama lima putaran unduhan.
    "sewa", "pinjam_pakai",
})


# ── Resolver ───────────────────────────────────────────────────────────────

def _berlaku(pemicu, konteks) -> bool:
    if not pemicu:
        return True
    fn = PEMICU.get(pemicu)
    if fn is None:                     # pemicu salah tulis di tabel
        return True                    # condong menampilkan, bukan menyembunyikan
    return bool(fn(konteks))


def syarat_dokumen(rezim: str, konteks=None) -> list:
    """Daftar periksa dokumen untuk satu rezim usulan, sudah dinilai keadaannya.

    Mengembalikan SELURUH butir rezim itu — termasuk yang pemicunya tidak
    terpenuhi, dengan `berlaku=False`. Sengaja: menyembunyikan butir membuat
    operator tak pernah tahu ia ada, dan tak bisa menyadari bahwa jawabannya
    atas satu pertanyaan keadaanlah yang membuatnya hilang.
    """
    konteks = konteks or {}
    hasil = []
    for kode, sifat, pemicu, dasar, verifikasi in SYARAT.get(rezim, ()):
        berlaku = _berlaku(pemicu, konteks)
        hasil.append({
            "kode": kode,
            "nama": KATALOG_DOKUMEN.get(kode, kode),
            "sifat": sifat,
            "sifat_label": SIFAT.get(sifat, sifat),
            "berlaku": berlaku,
            # Wajib EFEKTIF = wajib tanpa syarat, atau wajib-bersyarat yang
            # syaratnya terpenuhi. Inilah yang dihitung kelengkapan.
            "wajib": bool(berlaku and sifat in ("wajib", "wajib_bersyarat")),
            "pemicu": pemicu or "",
            "dasar": dasar,
            "verifikasi": verifikasi,
            "verifikasi_label": VERIFIKASI.get(verifikasi, verifikasi),
        })
    return hasil


def kelengkapan_dokumen(rezim: str, terunggah, konteks=None) -> dict:
    """Ringkas kelengkapan: berapa butir wajib terpenuhi, mana yang kurang.

    `terunggah` = kumpulan kode jenis dokumen yang sudah ada berkasnya.
    Lampiran tanpa `jenis` (warisan sebelum fitur ini) TIDAK dihitung
    memenuhi butir mana pun — menebak jenisnya dari nama berkas akan
    melaporkan lengkap untuk berkas yang belum tentu benar.
    """
    punya = {str(k) for k in (terunggah or []) if str(k or "").strip()}
    butir = syarat_dokumen(rezim, konteks)
    wajib = [b for b in butir if b["wajib"]]
    kurang = [b for b in wajib if b["kode"] not in punya]
    return {
        "rezim": rezim,
        "rezim_label": REZIM.get(rezim, rezim),
        "berdasar_pasal": rezim in REZIM_BERDASAR_PASAL,
        "butir": butir,
        "jumlah_wajib": len(wajib),
        "jumlah_terpenuhi": len(wajib) - len(kurang),
        "lengkap": not kurang,
        "kurang": [{"kode": b["kode"], "nama": b["nama"]} for b in kurang],
        # Berkas yang jenisnya di luar daftar rezim ini — bukan kesalahan,
        # tetapi layak ditampilkan agar operator sadar ia tak dihitung.
        "di_luar_daftar": sorted(punya - {b["kode"] for b in butir}),
    }


def jenis_pilihan(rezim: str, konteks=None) -> list:
    """Pilihan dropdown "Jenis Dokumen" untuk satu rezim, urut seperti SIMAN:
    yang wajib dulu, lalu anjuran, lalu opsional; "Dokumen Lainnya" terakhir."""
    urut = {"wajib": 0, "wajib_bersyarat": 1, "muatan": 2, "anjuran": 3,
            "opsional": 4}
    butir = [b for b in syarat_dokumen(rezim, konteks) if b["berlaku"]]
    butir.sort(key=lambda b: (b["kode"] == "dokumen_lainnya",
                              urut.get(b["sifat"], 9), b["nama"]))
    return [{"kode": b["kode"], "nama": b["nama"], "sifat": b["sifat"],
             "sifat_label": b["sifat_label"], "wajib": b["wajib"]} for b in butir]
