"""Kebijakan per jenis penerima BMN di luar satker (PGW-10; kontrak 6.6). MURNI.

Isi terkunci PGW-00 — sumber per sel: docs/PUSTAKA-REGULASI-BMN.md §2.4d.
`skema_sah` hanya memuat skema yang menyerahkan PENGUASAAN SEMENTARA; hibah
dan pemindahtanganan lain tetap di modul Pemindahtanganan. Sel yang di
pustaka bertanda "mungkin"/"perlu verifikasi" sengaja TIDAK dimasukkan
(bawaan konservatif); menambahkannya cukup dengan mengubah tabel ini.

KERANGKA SAJA. Status PMK 115/2020 bertentangan antarsumber (pustaka §2.4d,
§14 butir 26): modul ini tidak memuat dan tidak mencetak teks pasal. BAST
penerima luar baru boleh diterbitkan setelah butir pasalnya disahkan —
lihat `NASKAH_LUAR_SIAP`.
"""

#: Gerbang penerbitan BAST penerima luar. False sampai butir pasal
#: `antar_pemerintah`/`pihak_ketiga` disusun dari regulasi yang statusnya
#: sudah diverifikasi. Tanpa butir khusus, naskah akan memakai pasal internal
#: (surat tugas atasan, sanksi kepegawaian) yang tidak berlaku bagi penerima luar.
NASKAH_LUAR_SIAP = False

PESAN_GERBANG = (
    "BAST kepada penerima di luar satker belum dapat diterbitkan: butir "
    "pasalnya menunggu verifikasi status regulasi pemanfaatan (PMK 115/2020). "
    "Data yang Anda isi sudah lolos pemeriksaan; simpan nomor dan tanggal "
    "dokumen dasarnya untuk diterbitkan nanti.")

JENIS_BAST_LUAR = {
    "penyerahan_pihak_luar": "Penyerahan Barang Milik Negara kepada Pihak di Luar Satker",
    "pengembalian_pihak_luar": "Pengembalian Barang Milik Negara dari Pihak di Luar Satker",
}

SKEMA = {
    "penggunaan_sementara": "Penggunaan sementara oleh Pengguna Barang lain",
    "pinjam_pakai": "Pinjam pakai",
    "sewa": "Sewa",
    "ksp": "Kerja sama pemanfaatan (KSP)",
    "bgs_bsg": "Bangun guna serah / bangun serah guna",
    "kspi": "Kerja sama penyediaan infrastruktur (KSPI)",
    "dioperasikan_pihak_lain": "Dioperasikan oleh pihak lain",
}

_BADAN_USAHA = ("pengurus_berwenang", "penerima_kuasa")
_DASAR_PIHAK_KETIGA = "persetujuan/penetapan Pengelola Barang dan perjanjian"


def _baris(skema, dokumen, butir, komparisi, kapasitas=_BADAN_USAHA, catatan=None):
    return {"skema_sah": list(skema), "dokumen_dasar": dokumen,
            "dokumen_dasar_wajib": bool(skema), "butir_pasal": butir,
            "komparisi": komparisi, "kapasitas_sah": list(kapasitas or ()),
            "rezim_ganti_rugi": "perjanjian" if butir else "",
            "catatan": dict(catatan or {})}


#: Matriks terkunci 6.6 — satu baris per `jenis_instansi`.
MATRIKS = {
    "kementerian_lembaga": _baris(
        ["penggunaan_sementara"],
        "persetujuan Pengelola Barang; jangka waktu paling lama 6 bulan cukup "
        "perjanjian antar-Pengguna Barang",
        "antar_pemerintah", "atas_nama_instansi", kapasitas=()),
    **{j: _baris(["pinjam_pakai"],
                 "persetujuan Pengelola Barang dan perjanjian pinjam pakai",
                 "antar_pemerintah", "atas_nama_instansi", kapasitas=())
       for j in ("pemerintah_provinsi", "pemerintah_kabkota", "pemerintah_desa")},
    "bumn": _baris(["sewa", "ksp", "bgs_bsg", "kspi", "dioperasikan_pihak_lain"],
                   _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan"),
    "bumd": _baris(["sewa", "ksp", "bgs_bsg", "kspi"],
                   _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan"),
    "bumdes": _baris(["sewa"], _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan"),
    "badan_usaha_swasta": _baris(
        ["sewa", "ksp", "bgs_bsg", "kspi"], _DASAR_PIHAK_KETIGA, "pihak_ketiga",
        "atas_nama_badan", catatan={"kspi": "KSPI hanya bagi badan usaha berbentuk "
                                            "perseroan terbatas (PT)"}),
    "koperasi": _baris(["sewa", "kspi", "dioperasikan_pihak_lain"],
                       _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan"),
    "yayasan": _baris(["sewa", "bgs_bsg"], _DASAR_PIHAK_KETIGA, "pihak_ketiga",
                      "atas_nama_badan"),
    "satuan_pendidikan_swasta": _baris(
        ["sewa"], _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan_penyelenggara"),
    "badan_hukum_lain": _baris(["bgs_bsg", "dioperasikan_pihak_lain"],
                               _DASAR_PIHAK_KETIGA, "pihak_ketiga", "atas_nama_badan"),
    "kelompok_masyarakat": _baris([], "", "", ""),
    "perorangan": _baris(["sewa"], "persetujuan Pengelola Barang dan perjanjian sewa",
                         "pihak_ketiga", "diri_sendiri", kapasitas=("diri_sendiri",)),
    "lembaga_internasional": _baris(
        ["dioperasikan_pihak_lain"], "penetapan Pengelola Barang dan perjanjian",
        "pihak_ketiga", "atas_nama_pemerintah_organisasi"),
    "lainnya": _baris([], "", "", ""),
}

#: Pegawai internal: tak berubah dari hari ini.
KEBIJAKAN_INTERNAL = {"skema_sah": [], "dokumen_dasar": "", "dokumen_dasar_wajib": False,
                      "butir_pasal": "internal", "komparisi": "", "kapasitas_sah": [],
                      "rezim_ganti_rugi": "tgr_pegawai", "catatan": {}}


def kebijakan(jenis_instansi) -> dict:
    """Kebijakan satu jenis penerima. Kosong/tak dikenal → internal."""
    j = str(jenis_instansi or "").strip()
    if not j:
        return dict(KEBIJAKAN_INTERNAL)
    return dict(MATRIKS.get(j) or MATRIKS["lainnya"])


def _s(v) -> str:
    return str(v or "").strip()


def periksa_penyerahan(skema, jenis_instansi, kapasitas, dasar) -> list:
    """Galat yang menghalangi BAST penerima luar; [] = sah.

    `dasar` = {"nomor", "tanggal", "jangka_dari", "jangka_sampai"} dokumen
    dasarnya. Pesan menyebut dokumen yang kurang dan skema yang tersedia —
    bukan sekadar "tidak sah"."""
    j = _s(jenis_instansi)
    k = kebijakan(j)
    galat = []
    if j == "kelompok_masyarakat":
        return ["Kelompok masyarakat/ormas tidak dapat menerima penguasaan "
                "sementara BMN; penyerahannya hanya lewat hibah di modul "
                "Pemindahtanganan"]
    if j == "lainnya" or j not in MATRIKS:
        return ["Jenis penerima \"lainnya\" tidak punya skema baku — tetapkan "
                "jenis badannya di direktori, atau mintalah penetapan Pengelola "
                "Barang per kasus"]
    s = _s(skema)
    if not s:
        galat.append("Pilih skema penyerahan: " + ", ".join(
            SKEMA[x] for x in k["skema_sah"]))
    elif s not in k["skema_sah"]:
        galat.append(f"Skema \"{SKEMA.get(s, s)}\" tidak sah untuk penerima ini; "
                     "yang tersedia: " + ", ".join(SKEMA[x] for x in k["skema_sah"]))
    d = dasar or {}
    kurang = [label for kunci, label in (("nomor", "nomor dokumen dasar"),
                                         ("tanggal", "tanggal dokumen dasar"),
                                         ("jangka_dari", "awal jangka waktu"),
                                         ("jangka_sampai", "akhir jangka waktu"))
              if not _s(d.get(kunci))]
    if kurang:
        galat.append(f"Lengkapi {', '.join(kurang)} ({k['dokumen_dasar']})")
    elif _s(d.get("jangka_sampai")) < _s(d.get("jangka_dari")):
        galat.append("Akhir jangka waktu tidak boleh sebelum awalnya")
    kap = _s(kapasitas)
    if k["kapasitas_sah"]:
        if kap == "petugas":
            galat.append("Petugas/karyawan tidak sah menandatangani atas nama badan "
                         "— PIHAK KEDUA harus pengurus yang berwenang atau penerima kuasa")
        elif kap not in k["kapasitas_sah"]:
            galat.append("Kapasitas bertindak PIHAK KEDUA belum sesuai; yang sah: "
                         + ", ".join(k["kapasitas_sah"]))
    return galat


def catatan_penyerahan(skema, jenis_instansi) -> list:
    """Peringatan tak menghalangi (mis. KSPI hanya PT)."""
    c = kebijakan(jenis_instansi)["catatan"].get(_s(skema))
    return [c] if c else []


def komparisi(nama, kapasitas, jenis_instansi, instansi_nama, dasar_jenis="",
              dasar_nomor="", dasar_tanggal="", badan_penyelenggara="") -> str:
    """Kalimat "bertindak untuk dan atas nama …" pihak penerima luar.

    Hanya kalimat identitas — bukan pasal; tak merujuk peraturan mana pun."""
    k = kebijakan(jenis_instansi)["komparisi"]
    nama = _s(nama)
    if k == "diri_sendiri" or _s(kapasitas) == "diri_sendiri":
        return f"{nama}, dalam hal ini bertindak untuk diri sendiri"
    if k == "atas_nama_instansi":
        return f"{nama}, dalam hal ini bertindak untuk dan atas nama {_s(instansi_nama)}"
    badan = _s(badan_penyelenggara) if k == "atas_nama_badan_penyelenggara" else ""
    badan = badan or _s(instansi_nama)
    dasar = " ".join(x for x in (_s(dasar_jenis), f"nomor {_s(dasar_nomor)}"
                                 if _s(dasar_nomor) else "",
                                 f"tanggal {_s(dasar_tanggal)}" if _s(dasar_tanggal) else "")
                     if x)
    teks = f"{nama}, dalam hal ini bertindak untuk dan atas nama {badan}"
    return f"{teks} berdasarkan {dasar}" if dasar else teks


def ringkas_referensi() -> dict:
    """Bahan `GET /luar/referensi` untuk layar."""
    return {"skema": dict(SKEMA), "jenis_bast_luar": dict(JENIS_BAST_LUAR),
            "kebijakan_penerima": {j: kebijakan(j) for j in MATRIKS},
            "naskah_luar_siap": NASKAH_LUAR_SIAP}
