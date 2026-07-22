"""Referensi Pejabat & Unit Akuntansi Penatausahaan BMN — LOGIKA MURNI.

Dasar: PMK 181/PMK.06/2016 (Penatausahaan BMN). Struktur unit akuntansi
Pengguna Barang berjenjang (UAPB → UAPPB-E1 → UAPPB-W → UAKPB → UAPKPB);
di tingkat satker penanggung jawab UAKPB = Kepala Satker = **Kuasa Pengguna
Barang (KPB)**, penanda tangan LBKP/DBKP/laporan BMN & dokumen penghapusan/
BAST. Perekaman data BMN dijalankan **Petugas Penatausahaan / Operator
SIMAK-BMN** yang ditunjuk dengan SK. Modul ini menjadikan pejabat itu
sebagai REFERENSI (seperti "referensi penanda tangan" di SAKTI) agar dokumen
resmi memakai data pejabat yang benar & berlaku pada tanggalnya.
"""

# Peran pejabat dalam penatausahaan BMN (kode → uraian).
#
# CATATAN NOMENKLATUR (riset regulasi Jul 2026, terverifikasi; §11B pustaka):
# aplikasi ini untuk **BMN PUSAT** (PMK 181/2016, PMK 40/2024). Istilah
# "Pengurus Barang / Pengurus Barang Pengguna/Pembantu" & "Penyimpan Barang"
# adalah nomenklatur **Barang Milik DAERAH** (PP 27/2014 khusus "Milik Daerah";
# Permendagri 7/2024, pengganti Permendagri 19/2016) — TIDAK dikenal di
# penatausahaan BMN pusat & menyesatkan bila dipakai. Struktur resmi BMN pusat
# berbasis unit akuntansi (UAPB→UAKPB) dengan penanggung jawab **Kuasa Pengguna
# Barang (KPB)**; pelaksana teknisnya kini **Jabatan Fungsional Penata Laksana
# Barang (JFPLB)** (PermenPAN-RB 23/2018) — istilah "Operator/Petugas
# Penatausahaan / Pengelola BMN Satker" adalah sebutan praktik/role SAKTI
# (Operator–Validator–Approver), bukan definisi PMK 181/2016. Kunci
# `pengurus_barang` DIPERTAHANKAN hanya demi kompatibilitas data lama (ditandai
# "hindari"); peran BMN-pusat yang tepat ditambahkan di bawah.
PERAN_PEJABAT = {
    "pengguna_barang": "Pengguna Barang (Menteri/Pimpinan Lembaga)",
    "kuasa_pengguna_barang": "Kuasa Pengguna Barang (KPB) — Kepala Satker",
    "penatausahaan_bmn": "Petugas Penatausahaan BMN / Penata Laksana Barang (JFPLB) — Operator SIMAK-BMN/SAKTI",
    "pengelola_bmn_satker": "Pengelola BMN Satker (a.n. KPB — mis. Kasubbag Umum/Rumah Tangga)",
    "validator_bmn": "Verifikator/Validator BMN (UAKPB / role Validator SAKTI)",
    "penanggung_jawab_ruangan": "Penanggung Jawab Ruangan / Pemakai (KIR/DBR)",
    "ppk": "Pejabat Pembuat Komitmen (PPK)",
    "pemeriksa_lpb": "Pemeriksa Laporan Penerimaan Barang (LPB)",
    "pengurus_barang": "Pengurus/Penyimpan Barang (istilah Barang Milik DAERAH — hindari untuk BMN pusat)",
}

# Metadata peran (menjawab "apa peran ini & bedanya"): domain rezim
# ('bmn' pusat / 'bmd' daerah), peran pada BAST ('penyerah'/'penerima'/
# 'mengetahui'/'tidak'), dan keterangan singkat berbasis regulasi. Dipakai
# endpoint referensi + penyaring penanda tangan BAST (hanya peran pengelolaan
# BMN yang layak jadi "yang menyerahkan").
PERAN_PEJABAT_META = {
    "pengguna_barang": {
        "domain": "bmn", "ttd_bast": "tidak",
        "keterangan": "Menteri/Pimpinan Lembaga (UAPB). Pemegang kewenangan "
                      "penggunaan BMN tingkat K/L; pada BAST satker diwakili "
                      "KPB — tidak menandatangani BAST internal.",
    },
    "kuasa_pengguna_barang": {
        "domain": "bmn", "ttd_bast": "penyerah",
        "keterangan": "Kepala Kantor/Satker, penanggung jawab UAKPB & pemegang "
                      "penguasaan BMN satker. Penanda tangan UTAMA: penyerah/"
                      "mengetahui BAST, serta DBKP & LBKP.",
    },
    "penatausahaan_bmn": {
        "domain": "bmn", "ttd_bast": "penyerah",
        "keterangan": "Pelaksana teknis pembukuan, inventarisasi & pelaporan "
                      "BMN — Jabatan Fungsional Penata Laksana Barang / JFPLB "
                      "(PermenPAN-RB 23/2018), Operator SIMAK-BMN/SAKTI yang "
                      "ditunjuk KPB. Dapat menyerahkan BMN 'a.n. KPB' pada "
                      "serah terima rutin. Inilah pengganti tepat 'Pengurus "
                      "Barang' untuk BMN pusat.",
    },
    "pengelola_bmn_satker": {
        "domain": "bmn", "ttd_bast": "penyerah",
        "keterangan": "Pejabat pengelola BMN satker (mis. Kasubbag Umum/Rumah "
                      "Tangga) yang menyerahkan BMN ke pegawai atas nama KPB "
                      "(KPB 'Mengetahui'). Praktik SOP internal; kewenangan "
                      "asal melekat pada KPB.",
    },
    "validator_bmn": {
        "domain": "bmn", "ttd_bast": "tidak",
        "keterangan": "Verifikator/Validator UAKPB (role Validator SAKTI): "
                      "menguji perekaman Operator. Fungsi kontrol internal, "
                      "bukan pihak dalam BAST.",
    },
    "penanggung_jawab_ruangan": {
        "domain": "bmn", "ttd_bast": "penerima",
        "keterangan": "Pegawai pemakai / penanggung jawab ruangan (tercatat di "
                      "DBR/KIR). Pihak Kedua/penerima pada serah terima internal.",
    },
    "ppk": {
        "domain": "bmn", "ttd_bast": "penerima",
        "keterangan": "Pejabat Pembuat Komitmen: menerima hasil pekerjaan dari "
                      "penyedia pada BAST PEROLEHAN (vendor→satker). BUKAN "
                      "penyerah pada serah terima internal ke pegawai.",
    },
    "pemeriksa_lpb": {
        "domain": "bmn", "ttd_bast": "tidak",
        "keterangan": "Pemeriksa Laporan Penerimaan Barang persediaan. Penanda "
                      "tangan LPB, bukan pihak dalam BAST.",
    },
    "pengurus_barang": {
        "domain": "bmd", "ttd_bast": "tidak",
        "keterangan": "Istilah Barang Milik DAERAH (PP 27/2014 khusus 'Daerah'; "
                      "Permendagri 7/2024, pengganti 19/2016) — HINDARI untuk "
                      "BMN pusat; padanannya 'Petugas Penatausahaan BMN / Penata "
                      "Laksana Barang (JFPLB)'. Dipertahankan hanya demi data lama.",
    },
}

# Status kepegawaian pejabat/pegawai (adopsi klasifikasi SIMAN-G/BKN) — kode → uraian.
STATUS_KEPEGAWAIAN = {
    "pns": "PNS",
    "cpns": "CPNS",
    "pppk": "PPPK",
    "tni": "TNI",
    "polri": "POLRI",
    "non_asn": "Non-ASN (PPNPN/Kontrak)",
}

# Jenis pelaksana jabatan struktural — RANGKAP JABATAN SEMENTARA (kode → uraian).
#
# CATATAN REGULASI (riset Jul 2026; §11B pustaka): dasar penunjukan Plt/Plh
# adalah MANDAT (UU 30/2014 tentang Administrasi Pemerintahan Ps. 14) dan
# ketentuan kepegawaian pada SE Kepala BKN No. 2/SE/VII/2019 jo. No. 1/SE/2021
# ("Kewenangan Pelaksana Tugas & Pelaksana Harian dalam Aspek Kepegawaian").
# - **Plt (Pelaksana Tugas)**: jabatan definitif LOWONG (pejabat sebelumnya
#   pensiun/mutasi/berhalangan tetap); pejabat lain ditunjuk menjalankan tugas
#   sampai pejabat definitif dilantik.
# - **Plh (Pelaksana Harian)**: pejabat definitif ADA namun berhalangan
#   SEMENTARA (cuti/dinas luar/sakit); pejabat lain menjalankan tugas harian.
# Pada NASKAH DINAS, penanda tangan menuliskan "Plt."/"Plh." di depan nama
# jabatan yang dijabat, memakai NAMA & NIP DIRINYA SENDIRI (bukan pejabat
# definitif). Rangkap jabatan: yang bersangkutan tetap memegang jabatan
# definitifnya sendiri + menjalankan jabatan yang di-Plt/Plh-kan.
JENIS_PELAKSANA = {
    "plt": "Pelaksana Tugas (Plt.)",
    "plh": "Pelaksana Harian (Plh.)",
}

# Prefiks singkat penanda jabatan pelaksana pada baris jabatan naskah dinas.
_PREFIKS_PELAKSANA = {"plt": "Plt.", "plh": "Plh."}


def prefiks_pelaksana(jenis_pelaksana) -> str:
    """"Plt. " / "Plh. " / "" (dengan spasi ekor) berdasarkan jenis pelaksana.
    Dipakai memberi awalan pada label jabatan yang sudah baku (mis. header
    "Kuasa Pengguna Barang,"). MURNI."""
    pre = _PREFIKS_PELAKSANA.get(str(jenis_pelaksana or "").strip().lower())
    return f"{pre} " if pre else ""


def prefiks_jabatan_pelaksana(jabatan, jenis_pelaksana) -> str:
    """Sisipkan "Plt."/"Plh." di depan nama jabatan bila pejabat menjabat
    sebagai pelaksana tugas/harian (rangkap jabatan sementara).

    Idempoten (tidak menggandakan bila teks jabatan sudah diawali Plt./Plh.)
    & aman untuk jabatan/jenis kosong. MURNI (teruji unit)."""
    jab = str(jabatan or "").strip()
    pre = _PREFIKS_PELAKSANA.get(str(jenis_pelaksana or "").strip().lower())
    if not pre or not jab:
        return jab
    if jab.lower().startswith(("plt.", "plt ", "plh.", "plh ")):
        return jab
    return f"{pre} {jab}"

# Format email sederhana (murni, tanpa dependensi): satu '@' & domain ber-titik.
import re as _re
_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Jenjang unit akuntansi Pengguna Barang (PMK 181/2016) — kode → detail.
UNIT_AKUNTANSI = {
    "uapb": {"uraian": "Unit Akuntansi Pengguna Barang",
             "penanggung_jawab": "Menteri/Pimpinan Lembaga"},
    "uappb_e1": {"uraian": "Unit Akuntansi Pembantu Pengguna Barang — Eselon I",
                 "penanggung_jawab": "Pejabat Eselon I"},
    "uappb_w": {"uraian": "Unit Akuntansi Pembantu Pengguna Barang — Wilayah",
                "penanggung_jawab": "Pejabat Eselon II"},
    "uakpb": {"uraian": "Unit Akuntansi Kuasa Pengguna Barang",
              "penanggung_jawab": "Kepala Kantor/Satker (Kuasa Pengguna Barang)"},
    "uapkpb": {"uraian": "Unit Akuntansi Pembantu Kuasa Pengguna Barang",
               "penanggung_jawab": "Pembantu Kuasa Pengguna Barang"},
}


def peran_penyerah_bast():
    """Kode peran yang LAYAK jadi 'yang menyerahkan' (Pihak Kesatu) pada BAST
    serah terima internal: domain BMN pusat & ber-peran BAST 'penyerah'.
    MURNI (teruji unit)."""
    return [k for k, m in PERAN_PEJABAT_META.items()
            if m.get("domain") == "bmn" and m.get("ttd_bast") == "penyerah"]


def validate_pejabat(doc):
    """Kembalikan daftar pesan error (kosong bila valid). MURNI (teruji unit)."""
    errors = []
    if not str((doc or {}).get("nama") or "").strip():
        errors.append("Nama pejabat wajib diisi")
    peran = (doc or {}).get("peran") or []
    if not isinstance(peran, list) or not peran:
        errors.append("Minimal satu peran pejabat wajib dipilih")
    else:
        tak_dikenal = [p for p in peran if p not in PERAN_PEJABAT]
        if tak_dikenal:
            errors.append(f"Peran tidak dikenal: {', '.join(map(str, tak_dikenal))}")
    ua = (doc or {}).get("unit_akuntansi")
    if ua and ua not in UNIT_AKUNTANSI:
        errors.append(f"Unit akuntansi tidak dikenal: {ua}")
    stat = str((doc or {}).get("status_kepegawaian") or "").strip()
    if stat and stat not in STATUS_KEPEGAWAIAN:
        errors.append(f"Status kepegawaian tidak dikenal: {stat}")
    jp = str((doc or {}).get("jenis_pelaksana") or "").strip().lower()
    if jp and jp not in JENIS_PELAKSANA:
        errors.append(f"Jenis pelaksana tidak dikenal: {jp}")
    email = str((doc or {}).get("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        errors.append("Format email tidak valid")
    mulai = str((doc or {}).get("berlaku_mulai") or "").strip()
    selesai = str((doc or {}).get("berlaku_selesai") or "").strip()
    if mulai and selesai and mulai > selesai:
        errors.append("Tanggal 'berlaku mulai' melewati 'berlaku selesai'")
    return errors


def _berlaku_pada(pj, per_iso):
    """True bila pejabat berlaku pada tanggal `per_iso` (rentang kosong = terbuka)."""
    if pj.get("aktif") is False:
        return False
    per = str(per_iso or "").strip()[:10]
    mulai = str(pj.get("berlaku_mulai") or "").strip()[:10]
    selesai = str(pj.get("berlaku_selesai") or "").strip()[:10]
    if per:
        if mulai and per < mulai:
            return False
        if selesai and per > selesai:
            return False
    return True


def pejabat_aktif_untuk_peran(pejabat_list, peran, per_iso=None):
    """Pejabat yang berlaku & memegang `peran` pada tanggal `per_iso`.

    Bila banyak yang cocok, pilih yang SK-nya paling baru (berlaku_mulai
    terbesar). Kembalikan dict pejabat atau None. MURNI (teruji unit).
    """
    kandidat = [
        pj for pj in (pejabat_list or [])
        if peran in (pj.get("peran") or []) and _berlaku_pada(pj, per_iso)
    ]
    if not kandidat:
        return None
    kandidat.sort(key=lambda pj: str(pj.get("berlaku_mulai") or ""), reverse=True)
    return kandidat[0]


def penandatangan_kpb(settings, pejabat_list, per_iso=None):
    """Data penanda tangan **Kuasa Pengguna Barang** untuk dokumen resmi.

    Prioritas: KPB aktif dari registry `pejabat` pada tanggal `per_iso`; bila
    tak ada, fallback ke setelan laporan (`kasatker_nama/nip/jabatan`) — jadi
    laporan lama tetap jalan. Kembalikan {nama, nip, jabatan, sumber}. MURNI.
    """
    settings = settings or {}
    pj = pejabat_aktif_untuk_peran(pejabat_list, "kuasa_pengguna_barang", per_iso)
    if pj:
        jenis = str(pj.get("jenis_pelaksana") or "").strip().lower()
        jab_dasar = str(pj.get("jabatan") or "").strip() or "Kuasa Pengguna Barang"
        return {
            "nama": str(pj.get("nama") or "").strip() or "-",
            "nip": str(pj.get("nip") or "").strip() or "-",
            # Bila KPB dijabat Plt/Plh, jabatan diberi awalan "Plt./Plh." dan
            # penanda tangan memakai nama & NIP dirinya sendiri (rangkap jabatan).
            "jabatan": prefiks_jabatan_pelaksana(jab_dasar, jenis),
            "jabatan_dasar": jab_dasar,
            "jenis_pelaksana": jenis,
            "ttd_file_id": str(pj.get("ttd_file_id") or "").strip(),
            # Status ikut dibawa agar blok TTD bisa menahan baris NIP/NIK
            # bila penandatangan Non-ASN (aturan privasi laporan).
            "status_kepegawaian": str(pj.get("status_kepegawaian") or "").strip(),
            "sumber": "registry",
        }
    return {
        "nama": str(settings.get("kasatker_nama") or "").strip() or "-",
        "nip": str(settings.get("kasatker_nip") or "").strip() or "-",
        "jabatan": str(settings.get("kasatker_jabatan") or "").strip() or "Kuasa Pengguna Barang",
        "jabatan_dasar": str(settings.get("kasatker_jabatan") or "").strip() or "Kuasa Pengguna Barang",
        "jenis_pelaksana": "",
        "ttd_file_id": str(settings.get("kasatker_ttd_file_id") or "").strip(),
        "status_kepegawaian": "",
        "sumber": "setelan",
    }
