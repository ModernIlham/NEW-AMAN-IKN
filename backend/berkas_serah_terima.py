"""Kelengkapan berkas yang WAJIB diserahkan bersama barangnya — LOGIKA MURNI.

Permintaan pemilik: *"biasanya apa saja yang diserahterimakan yang menyangkut
barang tersebut, mulai dari memiliki bukti kepemilikan dan yang tidak memiliki
bukti kepemilikan, dan sifat selain tanah dan bangunan dan yang tanah dan
bangunan, dll-nya baik yang di atas dan di bawah 100 juta dll. Juga perhatikan
agar PPK menyerahkan lengkap berkasnya saat serah terima barang, tidak hanya
pengadaannya saja."*

── Apa yang dilakukan modul ini, dan apa yang TIDAK ────────────────────────
YANG DILAKUKAN: menggolongkan tiap barang dari KODE BARANG dan NILAI PER
UNIT-nya, lalu menyusun daftar berkas yang lazim menyertai golongan itu —
sebagai DAFTAR PERIKSA operasional untuk PPK dan Kuasa Pengguna Barang.

YANG TIDAK DILAKUKAN: menyatakan akibat hukum. Modul ini tidak memutuskan
siapa berwenang menyetujui apa, dan tidak mencetak nomor peraturan apa pun ke
dokumen. Tiga sumbu yang dipakai — ada/tidaknya bukti kepemilikan, tanah &
bangunan vs selain itu, dan ambang Rp100 juta — memang sumbu yang berulang di
aturan BMN, tetapi di sini ia hanya MENGELOMPOKKAN dan MENGINGATKAN.
Perbedaan ini disengaja: dokumen yang ditandatangani di atas meterai tidak
boleh memuat klaim hukum yang teks aslinya belum dibaca (lihat
`docs/SITASI-DOKUMEN-RESMI.md` — sumber primer masih terblokir dari
lingkungan pengembangan).

── Kenapa daftar ini ada di dokumen serah terimanya ────────────────────────
Berkas yang tidak ikut saat serah terima hampir tak pernah menyusul. Ia baru
dicari bertahun-tahun kemudian — saat penghapusan, pemindahtanganan, atau
pemeriksaan — ketika PPK-nya sudah berpindah dan penyedianya sudah tak
terhubung. Mencetak daftarnya PADA dokumen yang keduanya tanda tangani
membuat kekurangannya terlihat di detik yang tepat.
"""

# Ambang nilai yang berulang di aturan BMN sebagai batas kewenangan. Di sini
# dipakai HANYA untuk menandai barang yang perlu perhatian lebih saat
# berkasnya dikumpulkan — bukan untuk menyatakan siapa berwenang atas apa.
AMBANG_NILAI_PERHATIAN = 100_000_000

# Berkas dasar: melekat pada SETIAP barang hasil pengadaan, apa pun
# golongannya. Inilah "tidak hanya pengadaannya saja" yang dimaksud pemilik —
# dokumen pengadaan sudah tercetak di blok tersendiri; yang di bawah ini
# menyangkut BARANGNYA.
BERKAS_DASAR = [
    "Berita Acara Serah Terima dari penyedia kepada PPK",
    "Faktur/kuitansi pembelian beserta bukti pembayaran",
    "Berita Acara Pemeriksaan/Penerimaan barang",
]

# Golongan → sifat & berkas tambahannya.
#   `tanah_bangunan`  : masuk kelompok "tanah dan/atau bangunan"
#   `bukti_kepemilikan`: golongan ini LAZIM memiliki dokumen kepemilikan
GOLONGAN_BERKAS = {
    "1": {"nama": "Persediaan", "tanah_bangunan": False,
          "bukti_kepemilikan": False,
          "berkas": ["Kartu/berita acara penerimaan gudang",
                     "Keterangan masa kedaluwarsa (bila barang berbatas waktu)"]},
    "2": {"nama": "Tanah", "tanah_bangunan": True, "bukti_kepemilikan": True,
          "berkas": ["Sertipikat hak atas tanah atas nama Pemerintah RI c.q. K/L",
                     "Dokumen perolehan (akta/pelepasan hak/putusan)",
                     "Gambar situasi/peta bidang dan batas tanah",
                     "SPPT PBB terakhir"]},
    "3": {"nama": "Peralatan dan Mesin", "tanah_bangunan": False,
          "bukti_kepemilikan": False,
          "berkas": ["Kartu garansi dan buku manual/petunjuk pengoperasian",
                     "Daftar nomor seri/identitas unit",
                     "Berita acara uji fungsi (bila dipersyaratkan kontrak)"]},
    "4": {"nama": "Gedung dan Bangunan", "tanah_bangunan": True,
          "bukti_kepemilikan": True,
          "berkas": ["IMB/PBG dan dokumen perizinan bangunan",
                     "Gambar terbangun (as-built drawing) dan spesifikasi teknis",
                     "Berita acara serah terima pekerjaan (PHO/FHO)",
                     "Jaminan pemeliharaan dan masa pemeliharaannya",
                     "Dokumen kepemilikan/penguasaan tanah tempat bangunan berdiri"]},
    "5": {"nama": "Jalan, Irigasi, dan Jaringan", "tanah_bangunan": False,
          "bukti_kepemilikan": False,
          "berkas": ["Gambar terbangun (as-built drawing) dan spesifikasi teknis",
                     "Berita acara serah terima pekerjaan (PHO/FHO)",
                     "Jaminan pemeliharaan dan masa pemeliharaannya"]},
    "6": {"nama": "Aset Tetap Lainnya", "tanah_bangunan": False,
          "bukti_kepemilikan": False,
          "berkas": ["Keterangan identitas/katalog barang"]},
    "7": {"nama": "Konstruksi Dalam Pengerjaan", "tanah_bangunan": False,
          "bukti_kepemilikan": False,
          "berkas": ["Laporan kemajuan pekerjaan dan berita acara opname",
                     "Dokumen kontrak beserta adendumnya"]},
    "8": {"nama": "Aset Tak Berwujud", "tanah_bangunan": False,
          "bukti_kepemilikan": True,
          "berkas": ["Bukti lisensi/hak cipta beserta masa berlakunya",
                     "Media instalasi, kode sumber, atau berkas serah terima digital"]},
}

# Bidang yang berkas kepemilikannya BERBEDA dari golongannya. Kendaraan
# bermotor ada di dalam "Peralatan dan Mesin" — golongan yang umumnya TANPA
# bukti kepemilikan — padahal justru kendaraanlah yang paling sering hilang
# BPKB-nya, dan tanpa BPKB ia tak bisa dijual maupun dihapuskan kelak.
BIDANG_BERKAS = {
    "302": {"nama": "Alat Angkutan", "bukti_kepemilikan": True,
            "berkas": ["BPKB atas nama Pemerintah RI c.q. K/L",
                       "STNK beserta bukti pembayaran pajak terakhir",
                       "Faktur kendaraan dan sertifikat uji tipe",
                       "Nomor rangka dan nomor mesin tercatat"]},
}


def _golongan(kode) -> str:
    k = str(kode or "").strip()
    return k[0] if k and k[0].isdigit() else ""


def _bidang(kode) -> str:
    k = str(kode or "").strip()
    return k[:3] if len(k) >= 3 and k[:3].isdigit() else ""


def klasifikasi_barang(kode, nilai_per_unit=0) -> dict:
    """Golongkan SATU barang → sumbu-sumbu yang menentukan berkasnya.

    Barang tanpa kode barang dikembalikan apa adanya (`golongan: ""`) — bukan
    ditebak masuk golongan mana pun. Menebak di sini berarti dokumen resmi
    menuntut berkas yang tak relevan, dan pembacanya berhenti mempercayai
    seluruh daftarnya.
    """
    gol = _golongan(kode)
    info = dict(GOLONGAN_BERKAS.get(gol) or {})
    bid = _bidang(kode)
    khusus = BIDANG_BERKAS.get(bid) if info else None
    berkas = list(info.get("berkas") or [])
    if khusus:
        berkas = list(khusus["berkas"]) + berkas
    try:
        nilai = float(nilai_per_unit or 0)
    except (TypeError, ValueError):
        nilai = 0.0
    return {
        "golongan": gol,
        "nama_golongan": info.get("nama", ""),
        "bidang": bid,
        # Bidang yang aturan berkasnya BERBEDA dari golongannya harus berdiri
        # sendiri saat dikelompokkan — kalau tidak, BPKB ikut menempel pada
        # laptop yang kebetulan segolongan dengan kendaraan.
        "bidang_khusus": bid if khusus else "",
        "nama_bidang": khusus["nama"] if khusus else "",
        "tanah_bangunan": bool(info.get("tanah_bangunan")),
        "bukti_kepemilikan": bool(khusus["bukti_kepemilikan"] if khusus
                                  else info.get("bukti_kepemilikan")),
        "di_atas_ambang": nilai >= AMBANG_NILAI_PERHATIAN,
        "nilai_per_unit": nilai,
        "berkas": berkas,
    }


def _sifat(k) -> str:
    if not k.get("golongan"):
        return "Barang tanpa kode barang"
    inti = ("Tanah dan/atau bangunan" if k["tanah_bangunan"]
            else "Selain tanah dan bangunan")
    bukti = ("ber-bukti kepemilikan" if k["bukti_kepemilikan"]
             else "tanpa bukti kepemilikan")
    return f"{inti}, {bukti}"


def kelompok_berkas(barang) -> list:
    """[(judul, sifat, [berkas], [nama barang], perhatian)] — satu entri per
    golongan yang BENAR-BENAR ada pada dokumen ini.

    Dikelompokkan per golongan, bukan per barang: satu satker yang menerima 40
    laptop tak perlu membaca daftar berkas yang sama 40 kali. `perhatian`
    menandai golongan yang memuat barang bernilai ≥ ambang.
    """
    peta = {}
    for b in barang or []:
        d = b or {}
        jml = float(d.get("jumlah") or 0) or 1
        nilai = float(d.get("harga_satuan") or 0)
        if not nilai and d.get("total"):
            nilai = float(d.get("total") or 0) / jml
        k = klasifikasi_barang(d.get("kode") or d.get("kode_barang"), nilai)
        kunci = (k["golongan"] or "", k["bidang_khusus"])
        if not k["golongan"]:
            judul = "Barang tanpa kode barang"
        elif k["bidang_khusus"]:
            judul = (f"Golongan {k['golongan']} — {k['nama_golongan']}"
                     f" · Bidang {k['bidang_khusus']} — {k['nama_bidang']}")
        else:
            judul = (f"Golongan {k['golongan']} — {k['nama_golongan']}"
                     if k["nama_golongan"] else f"Golongan {k['golongan']}")
        e = peta.setdefault(kunci, {
            "judul": judul, "sifat": _sifat(k),
            "berkas": [], "barang": [], "perhatian": False,
        })
        for x in k["berkas"]:
            if x not in e["berkas"]:
                e["berkas"].append(x)
        nama = str(d.get("uraian") or d.get("nama_barang") or "").strip()
        if nama and nama not in e["barang"]:
            e["barang"].append(nama)
        if k["di_atas_ambang"]:
            e["perhatian"] = True
    keluar = []
    for kunci in sorted(peta, key=lambda x: (x[0] == "", x)):
        e = peta[kunci]
        keluar.append((e["judul"], e["sifat"],
                       BERKAS_DASAR + e["berkas"], e["barang"], e["perhatian"]))
    return keluar


def catatan_ambang(barang) -> str:
    """Kalimat penanda bila ada barang bernilai ≥ ambang, '' bila tidak.

    Disebut sebagai PENANDA PERHATIAN, bukan akibat hukum — lihat docstring
    modul.
    """
    ada = any(kelompok[4] for kelompok in kelompok_berkas(barang))
    if not ada:
        return ""
    return ("Terdapat barang dengan nilai perolehan per unit "
            f"Rp{AMBANG_NILAI_PERHATIAN:,.0f}".replace(",", ".")
            + " atau lebih — pastikan berkas kepemilikan, dokumen teknis, dan "
              "dokumen pendukung nilainya lengkap sejak serah terima ini.")
