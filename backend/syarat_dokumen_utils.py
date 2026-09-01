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
    "pendukung_sptj_tanah": ("Dokumen pendukung SPTJ tanah (akta jual beli/"
                            "girik/letter C/BAST/ledger jalan, surat keterangan "
                            "lurah/camat, surat permohonan pendaftaran hak, "
                            "dan/atau dokumen penguasaan)"),
    "dok_penganggaran_pmpp": ("Fotokopi KAK, RKA-K/L, atau POK (bila DIPA tak "
                              "tegas menyatakan BMN untuk PMPP)"),
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


PEMICU = {
    f.__name__: f for f in (
        objek_tanah, objek_bangunan, objek_selain_tb, punya_dok_kepemilikan,
        tanpa_dok_kepemilikan, ada_fotokopi, unggah_pindaian, dokumen_tidak_ada,
        dokumen_hilang, penandatangan_didelegasikan, untuk_pmpp,
        fisik_tak_dikuasai, ada_pungutan_masyarakat, dalam_rangka_kspi,
        penerima_lembaga_nonpemerintah, tanah_tanpa_sertipikat,
        tanah_bersertipikat, perlu_dokumen_lain, dipa_tidak_tegas,
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
    ("permintaan_hibah", "wajib", None,
     "SIMAN V2 — ditandai Mandatory", "empiris_siman"),
    ("kib", "wajib", None,
     "SIMAN V2 — ditandai Mandatory. Catat perbedaannya dengan rezim PSP, "
     "yang pasalnya justru tidak menyebut KIB sama sekali", "empiris_siman"),
    ("surat_permohonan", "wajib", None,
     "SIMAN V2 — ditandai Mandatory", "empiris_siman"),
    ("data_calon_penerima_hibah", "wajib", None,
     "SIMAN V2 — ditandai Mandatory", "empiris_siman"),
    ("sptj", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
    ("dok_penganggaran_hibah", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
    ("sk_tim_internal", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
    ("dokumen_lainnya", "opsional", None,
     "SIMAN V2 — ditandai Opsional", "empiris_siman"),
    ("pernyataan_instansi_teknis", "anjuran", "penerima_lembaga_nonpemerintah",
     "Pustaka repo §7: penerima lembaga sosial/budaya/keagamaan/kemanusiaan/"
     "pendidikan non-komersial wajib disertai pernyataan instansi teknis — "
     "pasalnya belum terbaca", "belum_terverifikasi"),
    ("daftar_bmn", "anjuran", None, "Praktik lapangan", "belum_terverifikasi"),
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

_PENJUALAN = _KERANGKA_DASAR + (
    ("penilaian", "anjuran", None,
     "Pustaka repo §7: nilai limit berasal dari penilaian/nilai taksiran — "
     "pasalnya belum terbaca", "belum_terverifikasi"),
    ("dok_kepemilikan", "anjuran", "punya_dok_kepemilikan",
     "Praktik lapangan", "belum_terverifikasi"),
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
    "tukar_menukar": _KERANGKA_DASAR,
    "pmpp": _KERANGKA_DASAR,
    "penghapusan": _KERANGKA_DASAR,
    "pemusnahan": _KERANGKA_DASAR,
    "sewa": _KERANGKA_DASAR,
    "pinjam_pakai": _KERANGKA_DASAR,
}

#: Rezim yang seluruh butir wajibnya bertumpu pada pasal yang sudah dibaca.
#: Dipakai antarmuka untuk memutuskan apakah pantas menampilkan gerbang
#: "berkas belum lengkap" atau sekadar daftar anjuran.
REZIM_BERDASAR_PASAL = frozenset({
    "psp", "penggunaan_sementara", "dioperasikan_pihak_lain",
    "alih_status", "penggunaan_bersama",
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
