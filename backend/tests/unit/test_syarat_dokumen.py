"""Daftar periksa dokumen usulan BMN — tabel dan resolvernya.

Permintaan pemilik: *"carikan untuk keperluan dokumen apa saja yang
diperlukan pada saat penetapan status barang ... agar semua keperluan
dokumen untuk segala macam jenis pengusulan BMN dapat ditangani aplikasi
dengan baik ... agar pengajuan ke SIMAN V2 dari segala pengusulan kondisi
dapat dimanajemen dengan baik."*

Uji ini menjaga SATU hal di atas segalanya: daftar tidak boleh kembali
menjadi "sembilan slot wajib". Daftar sembilan butir yang beredar (dan yang
ada di tangkapan layar KPKNL) berasal dari PMK 246/2014 jo. 76/2019 — rezim
yang untuk Penggunaan sudah digantikan PMK 40/2024, yang menyusun daftarnya
BERCABANG per jenis objek.
"""
import pytest

import syarat_dokumen_utils as sd


def _kode(butir):
    return [b["kode"] for b in butir]


def _wajib(rezim, konteks=None):
    return [b["kode"] for b in sd.syarat_dokumen(rezim, konteks) if b["wajib"]]


# ── Integritas tabel ───────────────────────────────────────────────────────

def test_semua_kode_ada_di_katalog():
    """Kode yatim akan tampil sebagai kode mentah di layar pengguna."""
    for rezim, butir in sd.SYARAT.items():
        for kode, *_ in butir:
            assert kode in sd.KATALOG_DOKUMEN, f"{rezim}: {kode} tak ada di katalog"


def test_semua_sifat_dan_verifikasi_dikenal():
    for rezim, butir in sd.SYARAT.items():
        for kode, sifat, _pemicu, _dasar, verifikasi in butir:
            assert sifat in sd.SIFAT, f"{rezim}/{kode}: sifat {sifat}"
            assert verifikasi in sd.VERIFIKASI, f"{rezim}/{kode}: {verifikasi}"


def test_semua_pemicu_benar_benar_ada():
    """Pemicu salah tulis akan diam-diam membuat butirnya selalu berlaku."""
    for rezim, butir in sd.SYARAT.items():
        for kode, _sifat, pemicu, *_ in butir:
            if pemicu:
                assert pemicu in sd.PEMICU, f"{rezim}/{kode}: pemicu {pemicu}"


def test_setiap_rezim_punya_daftar():
    for kode in sd.REZIM:
        assert sd.SYARAT.get(kode), f"rezim {kode} tanpa daftar dokumen"


def test_tak_ada_butir_kembar_dalam_satu_rezim():
    for rezim, butir in sd.SYARAT.items():
        kode = [b[0] for b in butir]
        assert len(kode) == len(set(kode)), f"{rezim} punya butir kembar"


def test_setiap_butir_membawa_dasarnya():
    """Butir tanpa dasar tak bisa dipertanggungjawabkan saat ditanya."""
    for rezim, butir in sd.SYARAT.items():
        for kode, _sifat, _pemicu, dasar, _v in butir:
            assert str(dasar or "").strip(), f"{rezim}/{kode} tanpa dasar"


# ── Percabangan PSP — inti permintaan ──────────────────────────────────────

def test_pemilik_kendaraan_tidak_ditagih_sertipikat_maupun_imb():
    """Inilah kesalahan 'sembilan slot': menagih sertipikat kepada pemilik
    laptop dan IMB kepada pemilik kendaraan."""
    w = _wajib("psp", {"jenis_objek": "selain_tb",
                       "punya_dokumen_kepemilikan": True})
    assert "sertipikat" not in w
    assert "imb_pbg" not in w
    assert "dok_perolehan_bangunan" not in w
    assert "dok_kepemilikan" in w


def test_tanah_kosong_tidak_ditagih_imb():
    """PMK memecah tanah/bangunan jadi TIGA keranjang, bukan satu."""
    w = _wajib("psp", {"jenis_objek": "tanah"})
    assert "sertipikat" in w
    assert "imb_pbg" not in w
    assert "dok_perolehan_bangunan" not in w


def test_tanah_dan_bangunan_menagih_keduanya():
    w = _wajib("psp", {"jenis_objek": "tanah_dan_bangunan"})
    assert "sertipikat" in w and "imb_pbg" in w
    assert "dok_perolehan_bangunan" in w


def test_bangunan_saja_tidak_ditagih_sertipikat():
    w = _wajib("psp", {"jenis_objek": "bangunan"})
    assert "imb_pbg" in w
    assert "sertipikat" not in w


def test_tanpa_dokumen_kepemilikan_bast_menggantikannya():
    """Pasal 11 ayat (2) huruf d angka 2: BAST perolehan menggantikan
    dokumen kepemilikan yang tidak ada — bukan tambahan di atasnya."""
    w = _wajib("psp", {"jenis_objek": "selain_tb",
                       "punya_dokumen_kepemilikan": False})
    assert "dok_lain_bast" in w
    assert "dok_kepemilikan" not in w


def test_sptj_hanya_untuk_tanah_belum_bersertipikat():
    """DIKOREKSI terhadap teks primer (2026-09-01).

    Pembacaan sekunder menyimpulkan SPTJ adalah "pengganti dokumen apa pun
    yang tidak ada". Pasal 11 ayat (3) jauh lebih sempit: ia dikecualikan
    dari **huruf a, huruf c angka 1, dan huruf e angka 3** — ketiganya
    tentang sertipikat TANAH. SPTJ tak pernah menggantikan BPKB kendaraan
    ataupun IMB bangunan.
    """
    kendaraan = _wajib("psp", {"jenis_objek": "selain_tb",
                               "punya_dokumen_kepemilikan": False,
                               "dokumen_tidak_ada": True})
    assert "sptj" not in kendaraan, "SPTJ tak menggantikan dokumen kendaraan"

    tanah = _wajib("psp", {"jenis_objek": "tanah",
                           "tanah_tanpa_sertipikat": True})
    assert "sptj" in tanah
    # Ayat (3) berbunyi "DIGANTI", bukan "ditambah".
    assert "sertipikat" not in tanah
    # SPTJ tanah wajib DILENGKAPI dokumen pendukung — yang registry lama
    # tak punya sama sekali.
    assert "pendukung_sptj_tanah" in tanah


def test_tanah_bersertipikat_tak_diminta_sptj():
    t = _wajib("psp", {"jenis_objek": "tanah"})
    assert "sertipikat" in t and "sptj" not in t


def test_bidang_lama_dokumen_tidak_ada_masih_bermakna_untuk_tanah():
    """Catatan yang tersimpan dengan pembacaan lama tak boleh kehilangan
    maknanya — tetapi hanya bila objeknya memang bertanah."""
    t = _wajib("psp", {"jenis_objek": "tanah", "dokumen_tidak_ada": True})
    assert "sptj" in t


def test_kib_bukan_kewajiban_pada_psp():
    """Kata 'KIB' tidak ada di PMK 40/2024 — ia praktik, bukan norma."""
    butir = {b["kode"]: b for b in sd.syarat_dokumen("psp", {})}
    assert butir["kib"]["sifat"] == "anjuran"
    assert butir["kib"]["wajib"] is False


def test_bast_PENETAPAN_bukan_syarat_usulan():
    """Permintaan pemilik: output "BERITA ACARA SERAH TERIMA PENETAPAN
    STATUS PENGGUNAAN BMN" tidak diperlukan sebagai berkas usulan. Tetap
    berlaku — ia terbit SESUDAH SK ada, jadi menagihnya membalik
    sebab-akibat.

    Versi pertama uji ini KELIRU: ia memakai `dok_lain_bast` sebagai
    wakilnya, lalu menuntut butir itu tak pernah wajib. Padahal keduanya
    dokumen yang BERBEDA — `dok_lain_bast` adalah BAST **perolehan** barang
    (serah terima dari penyedia/pemegang sebelumnya), yang Pasal 11 justru
    minta di beberapa cabang. Menyamakan keduanya membuat uji ini mengunci
    kesalahan alih-alih menahannya.
    """
    # Cocokkan KEDUA frasa sekaligus. Versi pertama assertion ini hanya
    # mencari "penetapan status", dan itu menangkap `sk_psp` — Fotokopi
    # KEPUTUSAN Penetapan Status Penggunaan, yang justru WAJIB pada rezim
    # penggunaan sementara, dioperasikan pihak lain, dan alih status. SK
    # bukan BAST.
    keliru = [k for k, v in sd.KATALOG_DOKUMEN.items()
              if "berita acara" in v.lower() and "penetapan status" in v.lower()]
    assert keliru == [], f"BAST Penetapan tak boleh jadi butir: {keliru}"
    # Pembanding: SK-nya justru ADA dan memang wajib di rezim lain.
    assert "sk_psp" in _wajib("penggunaan_sementara", {})


def test_bast_perolehan_diminta_untuk_semua_objek_kecuali_tanah():
    """KOREKSI terhadap teks primer (2026-09-01).

    "Fotokopi dokumen lain, termasuk berita acara serah terima perolehan
    barang" diminta pada huruf b angka 3 (bangunan), huruf c angka 4 (tanah
    dan bangunan), huruf d angka 1 huruf b (selain t/b YANG PUNYA dokumen
    kepemilikan — STNK atau BAST), dan huruf d angka 2 (yang tidak punya).

    Registry lama hanya menagihnya pada cabang terakhir. Akibatnya pemegang
    gedung tak pernah ditagih BAST perolehan yang pasalnya minta, dan
    kekurangannya baru ketahuan saat berkas dikembalikan Pengelola Barang.
    """
    for objek in ("bangunan", "tanah_dan_bangunan"):
        assert "dok_lain_bast" in _wajib("psp", {"jenis_objek": objek}), objek
    for punya in (True, False):
        w = _wajib("psp", {"jenis_objek": "selain_tb",
                           "punya_dokumen_kepemilikan": punya})
        assert "dok_lain_bast" in w, punya
    # Tanah berdiri sendiri TIDAK: huruf a hanya menyebut sertipikat.
    assert "dok_lain_bast" not in _wajib("psp", {"jenis_objek": "tanah"})


def test_dipa_tak_tegas_menambah_kak_rka_pok():
    """Pasal 11 ayat (2) huruf f — cabang yang registry lama tak punya."""
    tanpa = _wajib("psp", {"jenis_objek": "tanah", "untuk_pmpp": True})
    assert "dok_penganggaran_pmpp" not in tanpa
    dengan = _wajib("psp", {"jenis_objek": "tanah", "untuk_pmpp": True,
                            "dipa_tidak_tegas": True})
    assert "dok_penganggaran_pmpp" in dengan


def test_surat_keterangan_muncul_secara_bawaan():
    """Dua surat keterangan paling sering terlupa. Bawaannya MUNCUL —
    berkas usulan nyaris selalu memuat fotokopi, dan seluruh alur SIMAN V2
    adalah unggahan arsip digital."""
    w = _wajib("psp", {"jenis_objek": "selain_tb"})
    assert "ket_kebenaran_fotokopi" in w
    assert "ket_kebenaran_arsip_digital" in w


def test_surat_keterangan_hilang_bila_keadaannya_memang_tidak_ada():
    w = _wajib("psp", {"jenis_objek": "selain_tb", "ada_fotokopi": False,
                       "unggah_pindaian": False})
    assert "ket_kebenaran_fotokopi" not in w
    assert "ket_kebenaran_arsip_digital" not in w


def test_pmpp_menambah_tiga_dokumen_khusus():
    w = _wajib("psp", {"jenis_objek": "tanah_dan_bangunan", "untuk_pmpp": True,
                       "fisik_tak_dikuasai": True})
    assert {"dok_penganggaran", "reviu_apip",
            "bast_pengelolaan_sementara"} <= set(w)


def test_dasar_pendelegasian_hanya_bila_didelegasikan():
    tanpa = _wajib("psp", {"jenis_objek": "tanah"})
    assert "dasar_pendelegasian" not in tanpa
    dengan = _wajib("psp", {"jenis_objek": "tanah",
                            "penandatangan_didelegasikan": True})
    assert "dasar_pendelegasian" in dengan


# ── Rezim Penggunaan lain — jauh lebih ringan daripada PSP ─────────────────

def test_penggunaan_sementara_hanya_dua_dokumen_menurut_pasal():
    """Pasal 34 ayat (3): fotokopi SK PSP + fotokopi surat permintaan.
    Menempelkan checklist PSP ke rezim ini adalah kekeliruan yang berulang
    di banyak booklet."""
    w = _wajib("penggunaan_sementara", {"unggah_pindaian": False})
    assert set(w) == {"surat_permohonan", "sk_psp", "surat_permintaan_sementara"}


def test_dioperasikan_pihak_lain_menagih_pernyataan_pihak_lain():
    w = _wajib("dioperasikan_pihak_lain", {"unggah_pindaian": False})
    assert set(w) == {"surat_permohonan", "sk_psp",
                      "surat_permintaan_pengoperasian", "pernyataan_pihak_lain"}


def test_pungutan_ke_masyarakat_menambah_estimasi():
    w = _wajib("dioperasikan_pihak_lain",
               {"ada_pungutan_masyarakat": True, "unggah_pindaian": False})
    assert "estimasi_pungutan" in w


def test_alih_status_pernyataan_ditandatangani_penerima():
    """Titik yang sering tertukar: pernyataan kesediaan menerima
    ditandatangani calon Pengguna Barang BARU, bukan pemohon."""
    butir = {b["kode"]: b for b in sd.syarat_dokumen("alih_status", {})}
    assert butir["pernyataan_kesediaan_menerima"]["wajib"] is True
    assert "PENERIMA" in butir["pernyataan_kesediaan_menerima"]["dasar"]


def test_kspi_menambah_pernyataan_arah_sebaliknya():
    tanpa = _wajib("alih_status", {"unggah_pindaian": False})
    assert "pernyataan_kesediaan_mengalihkan" not in tanpa
    dengan = _wajib("alih_status", {"kspi": True, "unggah_pindaian": False})
    assert "pernyataan_kesediaan_mengalihkan" in dengan


# ── Hibah — daftar empiris SIMAN V2 ────────────────────────────────────────

# ── Hibah, pemusnahan, penghapusan — naik ke berdasar pasal (2026-09-01) ──
#
# Teks primer PMK 111/2016 dan PMK 83/2016 masuk pustaka lewat unduhan
# runner. Ketiganya sebelumnya bertanda `belum_terverifikasi`, sehingga
# layar menampilkan semuanya sebagai anjuran padahal pasalnya jelas.

def test_hibah_daftar_siman_ternyata_bisa_diturunkan_dari_pasal():
    """Empat butir Mandatory di layar SIMAN V2 ternyata punya dasar pasal —
    dan itu baru ketahuan setelah PMK 111/2016 dibaca."""
    butir = {b["kode"]: b for b in sd.syarat_dokumen("hibah", {})}
    for kode in ("surat_permohonan", "permintaan_hibah",
                 "data_calon_penerima_hibah"):
        assert butir[kode]["wajib"] is True, kode
        assert butir[kode]["verifikasi"] == "terverifikasi", kode
        assert "Pasal 9" in butir[kode]["dasar"], kode


def test_kib_hibah_TETAP_empiris_karena_pasal_95_tak_menyebutnya():
    """Pembeda yang membenarkan adanya tingkat bukti `empiris_siman`.

    Pasal 93 (tanah/bangunan) menyebut KIB; Pasal 95 (selain tanah/bangunan)
    TIDAK — padahal justru di layar hibah selain t/b itulah SIMAN V2
    menandainya Mandatory. Sistem meminta lebih dari pasalnya. Menaikkannya
    jadi `terverifikasi` akan mengklaim dasar yang tak ada; menurunkannya
    jadi anjuran akan membuat unggahan ditolak SIMAN.
    """
    kib = next(b for b in sd.syarat_dokumen("hibah", {}) if b["kode"] == "kib")
    assert kib["wajib"] is True
    assert kib["verifikasi"] == "empiris_siman"
    assert "Pasal 95" in kib["dasar"] and "TIDAK menyebutnya" in kib["dasar"]


def test_berita_acara_penelitian_butir_yang_SIMAN_pun_tak_sebut():
    """Pasal 93 huruf b dan Pasal 95 huruf b: hasil penelitian tim internal
    dituangkan dalam berita acara. Tak ada di daftar SIMAN maupun registry
    sebelumnya — ditemukan hanya karena pasalnya dibaca."""
    assert "berita_acara_penelitian" in _wajib("hibah", {})


def test_tim_internal_wajib_tetapi_SK_nya_opsional():
    """Bedanya halus dan disengaja: pasal mewajibkan MEMBENTUK tim; SIMAN
    menandai SK-nya Opsional. Yang wajib timnya, bukan lampirannya."""
    sk = next(b for b in sd.syarat_dokumen("hibah", {})
              if b["kode"] == "sk_tim_internal")
    assert sk["sifat"] == "opsional"
    assert sk["verifikasi"] == "terverifikasi"


# ── Pemusnahan ────────────────────────────────────────────────────────────

def test_pemusnahan_laporan_kondisi_dan_foto_WAJIB_beda_dari_psp():
    """PMK 83/2016 Pasal 11 ayat (2) huruf d dan e mewajibkan keduanya.
    Pada rezim PSP mereka hanya anjuran — perbedaan yang hanya terlihat
    setelah kedua pasalnya dibaca."""
    p = {b["kode"]: b for b in sd.syarat_dokumen("pemusnahan", {})}
    assert p["laporan_kondisi"]["wajib"] is True
    assert p["foto_bmn"]["wajib"] is True
    psp = {b["kode"]: b for b in sd.syarat_dokumen("psp", {})}
    assert psp["laporan_kondisi"]["wajib"] is False
    assert psp["foto_bmn"]["wajib"] is False


def test_pemusnahan_menagih_surat_pernyataan_khususnya():
    b = next(x for x in sd.syarat_dokumen("pemusnahan", {})
             if x["kode"] == "pernyataan_pemusnahan")
    assert b["wajib"] is True
    assert "materiil" in sd.KATALOG_DOKUMEN["pernyataan_pemusnahan"]


def test_dokumen_kepemilikan_dan_penggantinya_saling_meniadakan():
    """Ayat (3): pengganti dipakai HANYA bila dokumen kepemilikannya tak ada.
    Menagih keduanya sekaligus akan menyuruh orang mengunggah dua dokumen
    untuk satu kewajiban."""
    punya = _wajib("pemusnahan", {"punya_dokumen_kepemilikan": True})
    assert "dok_kepemilikan" in punya and "dok_pengganti_kepemilikan" not in punya
    tanpa = _wajib("pemusnahan", {"punya_dokumen_kepemilikan": False})
    assert "dok_pengganti_kepemilikan" in tanpa and "dok_kepemilikan" not in tanpa


def test_kib_bersyarat_bukan_menyeluruh():
    """Pasalnya berbunyi "untuk BMN yang harus dilengkapi KIB" — bersyarat
    pada jenis barangnya."""
    tanpa = _wajib("pemusnahan", {"wajib_kib": False})
    assert "kib" not in tanpa


# ── Penghapusan ───────────────────────────────────────────────────────────

def test_penghapusan_sebab_menentukan_dokumennya():
    """Dua sebab, dua berkas yang sama sekali berbeda."""
    pt = _wajib("penghapusan", {"sebab_penghapusan": "pemindahtanganan"})
    assert "dok_pelaksanaan_pt" in pt and "putusan_pengadilan" not in pt
    pengadilan = _wajib("penghapusan", {"sebab_penghapusan": "putusan_pengadilan"})
    assert "putusan_pengadilan" in pengadilan
    assert "dok_pelaksanaan_pt" not in pengadilan


def test_penghapusan_sebab_kosong_condong_menampilkan():
    """Sebab yang belum diisi memakai yang paling lazim di satker —
    menyembunyikan butirnya akan membuat operator tak tahu ia ada."""
    assert "dok_pelaksanaan_pt" in _wajib("penghapusan", {})


def test_dokumen_pelaksanaan_menyebut_keempat_bentuknya():
    """Pasal 38 ayat (3) huruf a–d. Operator harus tahu mana yang berlaku
    untuk bentuk pemindahtanganannya."""
    nama = sd.KATALOG_DOKUMEN["dok_pelaksanaan_pt"]
    for kata in ("risalah lelang", "perjanjian penjualan", "naskah hibah", "BAST"):
        assert kata in nama, kata


def test_hibah_masih_cocok_dengan_bentuk_layar_siman():
    """Empat Mandatory SIMAN tetap wajib, dan yang Opsional tetap opsional.

    Yang DIPERIKSA di sini bentuknya, bukan tingkat buktinya. Versi pertama
    uji ini menuntut keempatnya `empiris_siman` — dan itu jadi salah begitu
    PMK 111/2016 masuk pustaka dan ternyata mendasari tiga di antaranya.
    Uji yang mengunci "belum ada dasarnya" akan menahan penemuan dasarnya.
    """
    butir = {b["kode"]: b for b in sd.syarat_dokumen("hibah", {})}
    for kode in ("permintaan_hibah", "kib", "surat_permohonan",
                 "data_calon_penerima_hibah"):
        assert butir[kode]["wajib"] is True, kode
    for kode in ("sptj", "sk_tim_internal", "dokumen_lainnya"):
        assert butir[kode]["sifat"] == "opsional", kode
    # `dok_penganggaran_hibah` Opsional di SIMAN, tetapi Pasal 94
    # mewajibkannya bila BMN memang diadakan untuk dihibahkan.
    assert butir["dok_penganggaran_hibah"]["sifat"] == "wajib_bersyarat"


def test_kib_wajib_pada_hibah_tetapi_hanya_anjuran_pada_psp():
    """Perbedaan nyata antara norma dan sistem: pasal PSP tak menyebut KIB
    sama sekali, sedangkan SIMAN menandainya Mandatory untuk hibah.
    Menyeragamkan keduanya akan salah di salah satu sisi."""
    psp = {b["kode"]: b for b in sd.syarat_dokumen("psp", {})}
    hibah = {b["kode"]: b for b in sd.syarat_dokumen("hibah", {})}
    assert psp["kib"]["wajib"] is False
    assert hibah["kib"]["wajib"] is True


# ── Kejujuran bukti ────────────────────────────────────────────────────────

def test_rezim_yang_pasalnya_belum_terbaca_ditandai_jujur():
    """Sumber primer PMK 111/2016 & PMK 115/2020 terblokir dari lingkungan
    pengembangan. Butir wajibnya boleh ada sebagai kerangka kerja, tetapi
    TIDAK boleh mengaku terverifikasi."""
    # `penghapusan` dan `pemusnahan` KELUAR dari daftar ini pada 2026-09-01:
    # PMK 83/2016 masuk pustaka dan pasalnya dibaca.
    for rezim in ("penjualan_lelang", "penjualan_langsung", "tukar_menukar",
                  "pmpp", "sewa", "pinjam_pakai"):
        assert rezim not in sd.REZIM_BERDASAR_PASAL
        for b in sd.syarat_dokumen(rezim, {}):
            assert b["verifikasi"] != "terverifikasi", f"{rezim}/{b['kode']}"


def test_rezim_berdasar_pasal_tak_punya_butir_wajib_yang_sekadar_tebakan():
    """Yang diklaim berdasar pasal tak boleh punya satu pun butir wajib yang
    `belum_terverifikasi`.

    Premisnya DIPERTAJAM (2026-09-01). Versi pertama menuntut setiap butir
    wajib bertanda `terverifikasi` — dan itu terlalu keras: KIB pada rezim
    hibah wajib karena SIMAN V2 menuntutnya, bukan karena pasalnya, sebab
    Pasal 95 memang tak menyebutnya. `empiris_siman` bukan tebakan; ia
    bacaan langsung dari sistem yang justru menentukan diterima atau
    tidaknya unggahan. Yang dilarang adalah praktik lapangan yang belum
    terverifikasi menjadi gerbang.
    """
    for rezim in sd.REZIM_BERDASAR_PASAL:
        for b in sd.syarat_dokumen(rezim, {}):
            if b["sifat"] in ("wajib", "wajib_bersyarat"):
                assert b["verifikasi"] != "belum_terverifikasi", \
                    f"{rezim}/{b['kode']} wajib tetapi belum terverifikasi"


def test_hanya_kib_hibah_yang_wajib_tanpa_dasar_pasal():
    """Pengecualian di atas harus TETAP satu-satunya. Kalau butir lain ikut
    menyelinap jadi `empiris_siman` yang wajib, longgarnya premis tadi
    berubah jadi pintu masuk."""
    empiris_wajib = [
        f"{r}/{b['kode']}" for r in sd.REZIM_BERDASAR_PASAL
        for b in sd.syarat_dokumen(r, {})
        if b["sifat"] in ("wajib", "wajib_bersyarat")
        and b["verifikasi"] == "empiris_siman"
    ]
    assert empiris_wajib == ["hibah/kib"], empiris_wajib


# ── Kelengkapan ────────────────────────────────────────────────────────────

def test_kelengkapan_menghitung_yang_wajib_saja():
    k = sd.kelengkapan_dokumen(
        "penggunaan_sementara",
        ["surat_permohonan", "sk_psp", "surat_permintaan_sementara"],
        {"unggah_pindaian": False})
    assert k["lengkap"] is True
    assert k["jumlah_wajib"] == 3 and k["jumlah_terpenuhi"] == 3
    assert k["kurang"] == []


def test_lampiran_tanpa_jenis_tidak_dianggap_memenuhi():
    """Menebak jenis dari nama berkas akan melaporkan "lengkap" untuk
    berkas yang belum tentu benar — dan kekurangan baru ketahuan saat
    berkas dikembalikan.

    `di_luar_daftar` ikut diperiksa, dan itu BUKAN kelengkapan: tanpa
    penyaringan, lampiran warisan (yang memang belum punya jenis) akan
    dilaporkan sebagai "berkas berjenis di luar daftar" — tuduhan yang
    salah, atas berkas yang tidak bersalah apa pun. Memeriksa
    `jumlah_terpenuhi` saja tidak menangkapnya, sebab tak ada butir
    berkode kosong yang bisa terpenuhi.
    """
    k = sd.kelengkapan_dokumen("penggunaan_sementara", ["", "  ", None],
                               {"unggah_pindaian": False})
    assert k["jumlah_terpenuhi"] == 0
    assert k["lengkap"] is False
    assert k["di_luar_daftar"] == []


def test_berkas_di_luar_daftar_dilaporkan_bukan_dibuang():
    k = sd.kelengkapan_dokumen("penggunaan_sementara", ["sertipikat"],
                               {"unggah_pindaian": False})
    assert k["di_luar_daftar"] == ["sertipikat"]


def test_butir_tak_berlaku_tetap_ditampilkan():
    """Menyembunyikan butir membuat operator tak pernah tahu ia ada, dan
    tak bisa menyadari bahwa jawabannyalah yang membuatnya hilang."""
    butir = sd.syarat_dokumen("psp", {"jenis_objek": "selain_tb"})
    sertipikat = next(b for b in butir if b["kode"] == "sertipikat")
    assert sertipikat["berlaku"] is False
    assert sertipikat["wajib"] is False
    assert sertipikat["pemicu"] == "tanah_bersertipikat"


def test_rezim_tak_dikenal_menghasilkan_daftar_kosong_bukan_meledak():
    k = sd.kelengkapan_dokumen("entah_apa", ["surat_permohonan"], {})
    assert k["butir"] == [] and k["jumlah_wajib"] == 0
    assert k["lengkap"] is True


# ── Pilihan dropdown ───────────────────────────────────────────────────────

def test_pilihan_menaruh_wajib_di_atas_dan_lainnya_di_bawah():
    pilihan = sd.jenis_pilihan("hibah", {})
    assert pilihan[0]["sifat"] == "wajib"
    assert pilihan[-1]["kode"] == "dokumen_lainnya"


def test_pilihan_menyembunyikan_yang_tak_berlaku():
    """Berbeda dari daftar periksa: dropdown unggahan hanya menawarkan yang
    memang relevan, supaya orang tak mengunggah IMB untuk kendaraan."""
    kode = [p["kode"] for p in sd.jenis_pilihan("psp", {"jenis_objek": "selain_tb"})]
    assert "imb_pbg" not in kode
    assert "sertipikat" not in kode


@pytest.mark.parametrize("rezim", sorted(sd.REZIM))
def test_setiap_rezim_menawarkan_dokumen_lainnya(rezim):
    """Jalan keluar wajib ada: daftar mana pun akan meleset suatu saat."""
    kode = [p["kode"] for p in sd.jenis_pilihan(rezim, {})]
    assert "dokumen_lainnya" in kode
