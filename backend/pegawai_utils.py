"""Master Pegawai (data kepegawaian menyeluruh satker) — LOGIKA MURNI.

BERBEDA dari Referensi Pejabat (`pejabat_utils.py`, khusus pejabat
penatausahaan/penanda tangan dokumen): master ini menampung **SELURUH pegawai**
satker beserta **unit kerjanya masing-masing**, mengadopsi kelengkapan data
SIMAN Modul Pegawai (SIMAN-G) / SIMPEG. Dipakai sebagai rujukan lintas modul
(mis. pemegang barang, penanggung jawab ruangan, distribusi DBR/KIR). Semua
field selain `nama` bersifat opsional. Modul murni ini teruji unit.
"""
import re

from pejabat_utils import (  # klasifikasi & rangkap jabatan bersama
    JENIS_PELAKSANA, STATUS_KEPEGAWAIAN, prefiks_pelaksana)

# Jenis kelamin (kode → uraian).
JENIS_KELAMIN = {"L": "Laki-laki", "P": "Perempuan"}

# Jenis jabatan (adopsi klasifikasi ASN) — kode → uraian.
JENIS_JABATAN = {
    "struktural": "Struktural",
    "fungsional": "Fungsional (JF)",
    "pelaksana": "Pelaksana",
}

# Status keberadaan/kehadiran pegawai di satker (kode → uraian) — SUMBU
# LIFECYCLE (menggerakkan badge pensiun/mutasi, hitung masa, snapshot).
STATUS_PEGAWAI = {
    "aktif": "Aktif",
    "cuti": "Cuti",
    "tugas_belajar": "Tugas Belajar",
    "diperbantukan": "Diperbantukan/DPB",
    "mutasi": "Mutasi/Pindah",
    "pensiun": "Pensiun",
    "keluar": "Keluar/Berhenti",
    "meninggal": "Meninggal Dunia",
    "nonaktif": "Nonaktif",
}

# Batas waktu memberi tahu ahli waris adanya kerugian negara sejak pegawai
# diketahui meninggal dunia. Lewat batas ini tanggung jawab ahli waris HAPUS
# demi hukum (UU 1/2004 Pasal 66 ayat (2) jo. PP 38/2016) — karena itu sistem
# mendetakkan jamnya agar hak tagih negara tidak gugur karena kelalaian
# administrasi. Dihitung KALENDER (3 tahun), bukan 3×365 hari.
BATAS_LAPOR_AHLI_WARIS_TAHUN = 3

# Status kepegawaian di satker — REFERENSI SIMPEG (kode → uraian). SUMBU
# HUBUNGAN KERJA pegawai dengan satker, TERPISAH dari STATUS_PEGAWAI (sumbu
# keberadaan). Sebagian status merujuk instansi lain (perbantuan/dipekerjakan);
# pemakai melengkapi "instansi terkait" bila status tsb dipilih.
STATUS_PEGAWAI_SATKER = {
    "pns": "PNS",
    "calon_pegawai": "Calon Pegawai (CPNS)",
    "diperbantukan_pada": "Diperbantukan Pada",
    "perbantuan_dari": "Perbantuan Dari",
    "dipekerjakan_pada": "Dipekerjakan Pada",
    "dipekerjakan_dari": "Dipekerjakan Dari",
    "non_aktif": "Non Aktif",
    "pejabat_negara": "Pejabat Negara",
    "diperbantukan_swasta": "Diperbantukan ke Swasta",
}

# Status yang MERUJUK instansi/satker lain → UI menampilkan isian pelengkap
# "Instansi/Satker Terkait" (asal/tujuan perbantuan atau penugasan).
STATUS_PEGAWAI_SATKER_BERINSTANSI = frozenset({
    "diperbantukan_pada", "perbantuan_dari", "dipekerjakan_pada",
    "dipekerjakan_dari", "diperbantukan_swasta",
})

# Referensi jenjang pendidikan terakhir (kategori baku, urut jenjang) — dipakai
# sebagai pilihan dropdown form & Data Validation ekspor. Disimpan apa adanya
# sebagai teks uraian agar kompatibel data lama & impor bebas.
PENDIDIKAN = [
    "SD", "SMP", "SMU", "Diploma I", "Diploma II", "Diploma III",
    "Diploma IV", "S1", "S2", "S3", "Profesor",
]

# Kategori jabatan pegawai per UU ASN (kode → uraian) — menentukan siapa yang
# dapat menjadi pejabat/penanggung jawab BMN (adopsi pola KERJA-BARENG/SIMPEG).
KATEGORI_PEGAWAI = {
    "jpt": "Jabatan Pimpinan Tinggi (JPT)",     # Eselon I & II
    "administrator": "Jabatan Administrator",    # Eselon III
    "pengawas": "Jabatan Pengawas",              # Eselon IV
    "pelaksana": "Pejabat Pelaksana",            # Staf/Pelaksana
    "fungsional": "Jabatan Fungsional (JF)",     # Fungsional
}

# Sub-kategori pegawai Non-ASN (kode → uraian) — relevan utk penanggung jawab
# aset & pemantauan kontrak (pemegang Non-ASN berisiko saat kontrak berakhir).
SUB_KATEGORI_NON_ASN = {
    "ppnpn": "PPNPN",
    "konsultan": "Konsultan Individu",
    "tenaga_ahli": "Tenaga Ahli",
    "teknisi": "Teknisi",
    "pramubakti": "Pramubakti",
    "satpam": "Satpam",
    "supir": "Supir",
    "tenaga_pendukung": "Tenaga Pendukung",
    "magang": "Magang",
}

# Agama & status perkawinan (kelengkapan data SIMPEG; opsional).
AGAMA = {
    "islam": "Islam", "kristen": "Kristen", "katolik": "Katolik",
    "hindu": "Hindu", "buddha": "Buddha", "konghucu": "Konghucu",
    "lainnya": "Lainnya",
}
STATUS_PERKAWINAN = {
    "belum_kawin": "Belum Kawin", "kawin": "Kawin",
    "cerai_hidup": "Cerai Hidup", "cerai_mati": "Cerai Mati",
}

# Kewarganegaraan & identitas WNA (pola form KERJA-BARENG).
KEWARGANEGARAAN = {"wni": "WNI", "wna": "WNA"}
JENIS_IDENTITAS_WNA = {"paspor": "Paspor", "kitas": "KITAS", "kitap": "KITAP"}

# Pilihan pangkat/golongan MENGIKUTI status kepegawaian (referensi resmi;
# pola form KERJA-BARENG). Tetap boleh isian bebas — daftar ini utk saran.
PANGKAT_GOLONGAN = {
    "pns": [
        "Juru Muda (I/a)", "Juru Muda Tingkat I (I/b)", "Juru (I/c)",
        "Juru Tingkat I (I/d)",
        "Pengatur Muda (II/a)", "Pengatur Muda Tingkat I (II/b)",
        "Pengatur (II/c)", "Pengatur Tingkat I (II/d)",
        "Penata Muda (III/a)", "Penata Muda Tingkat I (III/b)",
        "Penata (III/c)", "Penata Tingkat I (III/d)",
        "Pembina (IV/a)", "Pembina Tingkat I (IV/b)",
        "Pembina Utama Muda (IV/c)", "Pembina Utama Madya (IV/d)",
        "Pembina Utama (IV/e)",
    ],
    "pppk": [f"Golongan {r}" for r in (
        "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII".split())],
    "tni": [
        "Prajurit Dua", "Prajurit Satu", "Prajurit Kepala",
        "Kopral Dua", "Kopral Satu", "Kopral Kepala",
        "Sersan Dua", "Sersan Satu", "Sersan Kepala", "Sersan Mayor",
        "Pembantu Letnan Dua", "Pembantu Letnan Satu",
        "Letnan Dua", "Letnan Satu", "Kapten",
        "Mayor", "Letnan Kolonel", "Kolonel",
        "Brigadir Jenderal", "Mayor Jenderal", "Letnan Jenderal", "Jenderal",
    ],
    "polri": [
        "Bhayangkara Dua", "Bhayangkara Satu", "Bhayangkara Kepala",
        "Ajun Brigadir Polisi Dua", "Ajun Brigadir Polisi Satu",
        "Ajun Brigadir Polisi",
        "Brigadir Polisi Dua", "Brigadir Polisi Satu", "Brigadir Polisi",
        "Brigadir Polisi Kepala",
        "Ajun Inspektur Polisi Dua", "Ajun Inspektur Polisi Satu",
        "Inspektur Polisi Dua", "Inspektur Polisi Satu",
        "Ajun Komisaris Polisi", "Komisaris Polisi",
        "Ajun Komisaris Besar Polisi", "Komisaris Besar Polisi",
        "Brigadir Jenderal Polisi", "Inspektur Jenderal Polisi",
        "Komisaris Jenderal Polisi", "Jenderal Polisi",
    ],
}
PANGKAT_GOLONGAN["cpns"] = PANGKAT_GOLONGAN["pns"]

# Jumlah digit rekening bank umum di Indonesia (utk PERINGATAN LUNAK —
# beberapa bank punya variasi; bank di luar daftar tidak diperiksa).
DIGIT_BANK = {
    "bri": 15, "bni": 10, "mandiri": 13, "btn": 16,
    "bsi": 10, "bank syariah indonesia": 10, "bank syariah indonesia (bsi)": 10,
    "bca": 10, "cimb niaga": 13, "danamon": 10,
}


def periksa_rekening(nama_bank, no_rekening):
    """Peringatan LUNAK bila jumlah digit rekening tak lazim utk bank tsb.

    Kembalikan string peringatan (kosong bila cocok/tak diperiksa). Bank
    tak dikenal atau rekening kosong → tidak diperiksa. MURNI (teruji)."""
    bank = str(nama_bank or "").strip().lower()
    digit = re.sub(r"\D", "", str(no_rekening or ""))
    if not bank or not digit:
        return ""
    harus = DIGIT_BANK.get(bank)
    if harus is None or len(digit) == harus:
        return ""
    return (f"No. rekening {str(nama_bank).strip()} lazimnya {harus} digit "
            f"(saat ini {len(digit)} digit) — periksa kembali")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TGL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Pemisah umum penulisan nomor identitas (spasi/titik/strip) — dibuang
# sebelum deteksi jenis nomor agar NIK/NIP berformat tetap terkenali.
_RE_PEMISAH_NOMOR = re.compile(r"[\s.\-]")

# KODE LOKASI BMN — 20 karakter: 18 digit angka + 2 huruf kewenangan.
#
#   126 | 01 | 1600 | 691778 | 000 | KP
#    ↑     ↑     ↑       ↑       ↑    ↑
#    │     │     │       │       │    └─ Kewenangan (KP/KD/TP/DK)
#    │     │     │       │       └────── Sub-satker (000 bila tak ada)
#    │     │     │       └────────────── Satker (6 digit)
#    │     │     └────────────────────── Wilayah (4 digit)
#    │     └──────────────────────────── Eselon I (2 digit)
#    └────────────────────────────────── Pengguna Barang (3 digit)
#
# Huruf kewenangan TIDAK dibatasi ke empat kode di atas: daftar itu bisa
# bertambah di aturan berikutnya, dan menolak kode sah membuat pengguna
# terkunci dari data yang benar. Yang dijaga adalah BENTUKNYA.
RE_KODE_SATKER_LENGKAP = re.compile(r"^\d{18}[A-Z]{2}$")


def normalisasi_kode_satker_lengkap(nilai) -> str:
    """Rapikan tulisan kode lokasi BMN tanpa membuang huruf kewenangannya.

    Pemisah yang lazim ditulis manusia (spasi, titik, strip) dibuang, huruf
    dinaikkan jadi kapital. TIDAK memaksa hasilnya sah — memaksa di sini
    menyembunyikan salah ketik yang seharusnya dilaporkan validator.
    """
    teks = str(nilai or "").strip().upper()
    return re.sub(r"[^0-9A-Z]", "", teks)


def kode_satker_lengkap_sah(nilai) -> bool:
    """True bila kode berbentuk 18 digit + 2 huruf.

    Kode 12 digit era-lama SENGAJA tidak lagi diterima: ia bukan kode lokasi
    BMN yang utuh, dan membiarkannya lolos berarti dua bentuk berbeda hidup
    berdampingan di kolom yang sama — persis keadaan yang membuat kolom ini
    tak bisa dipakai untuk mencocokkan data lintas modul.
    """
    return bool(RE_KODE_SATKER_LENGKAP.match(str(nilai or "").strip().upper()))


def validate_pegawai(doc):
    """Kembalikan daftar pesan error (kosong bila valid). MURNI (teruji unit)."""
    d = doc or {}
    errors = []
    if not str(d.get("nama") or "").strip():
        errors.append("Nama pegawai wajib diisi")
    nip = str(d.get("nip") or "").strip()
    if nip and (not nip.isdigit() or not (8 <= len(nip) <= 20)):
        errors.append("NIP harus 8–20 digit angka")
    jk = str(d.get("jenis_kelamin") or "").strip().upper()
    if jk and jk not in JENIS_KELAMIN:
        errors.append("Jenis kelamin harus L atau P")
    stat = str(d.get("status_kepegawaian") or "").strip()
    if stat and stat not in STATUS_KEPEGAWAIAN:
        errors.append(f"Status kepegawaian tidak dikenal: {stat}")
    jj = str(d.get("jenis_jabatan") or "").strip()
    if jj and jj not in JENIS_JABATAN:
        errors.append(f"Jenis jabatan tidak dikenal: {jj}")
    jp = str(d.get("jenis_pelaksana") or "").strip().lower()
    if jp and jp not in JENIS_PELAKSANA:
        errors.append(f"Jenis pelaksana tidak dikenal: {jp}")
    st = str(d.get("status") or "").strip()
    if st and st not in STATUS_PEGAWAI:
        errors.append(f"Status pegawai tidak dikenal: {st}")
    # Status "Meninggal Dunia" WAJIB bertanggal — tanpa tanggal, jam 3 tahun
    # pemberitahuan ahli waris tak bisa dihitung dan serah terima BMN almarhum
    # kehilangan dasarnya (Peraturan BKN 3/2020: surat keterangan meninggal
    # memuat nomor akta & tanggal kematian).
    tgl_wafat = str(d.get("tanggal_meninggal") or "").strip()[:10]
    if st == "meninggal" and not tgl_wafat:
        errors.append("Tanggal meninggal wajib diisi bila status Meninggal Dunia")
    if tgl_wafat and not _TGL_RE.match(tgl_wafat):
        errors.append("Tanggal meninggal harus berformat YYYY-MM-DD")
    tgl_lapor = str(d.get("pemberitahuan_ahli_waris_tanggal") or "").strip()[:10]
    if tgl_lapor and not _TGL_RE.match(tgl_lapor):
        errors.append("Tanggal pemberitahuan ahli waris harus berformat YYYY-MM-DD")
    sps = str(d.get("status_pegawai_satker") or "").strip()
    if sps and sps not in STATUS_PEGAWAI_SATKER:
        errors.append(f"Status pegawai (satker) tidak dikenal: {sps}")
    email = str(d.get("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        errors.append("Format email tidak valid")
    tgl = str(d.get("tanggal_lahir") or "").strip()
    if tgl and not _TGL_RE.match(tgl):
        errors.append("Tanggal lahir harus format YYYY-MM-DD")
    # Penghubung satker & kontrak Non-ASN (W3)
    ksl = str(d.get("kode_satker_lengkap") or "").strip()
    if ksl and not kode_satker_lengkap_sah(ksl):
        errors.append("Kode satker lengkap harus 20 karakter "
                      "(18 digit + 2 huruf kewenangan, cth. 126011600691778000KP)")
    ks = str(d.get("kode_satker") or "").strip()
    if ks and (not ks.isdigit() or len(ks) != 6):
        errors.append("Kode satker harus 6 digit angka")
    jk_na = str(d.get("jenis_kontrak_non_asn") or "").strip().lower()
    if jk_na and jk_na not in JENIS_KONTRAK_NON_ASN:
        errors.append("Jenis kontrak Non-ASN harus internal/outsourcing")
    if (jk_na == "outsourcing"
            and not str(d.get("perusahaan_penyedia") or "").strip()):
        errors.append("Nama perusahaan penyedia wajib diisi untuk outsourcing")
    return errors


def nama_lengkap(pegawai):
    """Gabungan gelar depan + nama + gelar belakang (untuk tampilan). MURNI."""
    p = pegawai or {}
    depan = str(p.get("gelar_depan") or "").strip()
    nama = str(p.get("nama") or "").strip()
    belakang = str(p.get("gelar_belakang") or "").strip()
    hasil = (f"{depan} {nama}").strip()
    if belakang:
        hasil = f"{hasil}, {belakang}"
    return hasil


def is_aktif(pegawai):
    """True bila pegawai berstatus aktif (status kosong dianggap aktif). MURNI."""
    st = str((pegawai or {}).get("status") or "aktif").strip() or "aktif"
    return st == "aktif"


def is_meninggal(pegawai):
    """True bila pegawai berstatus Meninggal Dunia. MURNI.

    Dipisah dari `is_aktif` karena perlakuannya BERBEDA dari nonaktif biasa:
    almarhum tak dapat menerima serah terima maupun menandatangani apa pun,
    sehingga transaksi baru kepadanya harus DITOLAK (bukan sekadar diperingatkan)."""
    return str((pegawai or {}).get("status") or "").strip() == "meninggal"


def info_kewajiban_ahli_waris(pegawai, hari_ini_iso):
    """Jam hukum pemberitahuan ahli waris atas kerugian negara. MURNI (teruji unit).

    Dasar: UU 1/2004 Pasal 66 ayat (2) jo. PP 38/2016 — bila pegawai meninggal
    dunia, tuntutan ganti kerugian beralih ke ahli waris (terbatas kekayaan yang
    berasal dari almarhum), TETAPI tanggung jawab itu HAPUS apabila dalam 3 tahun
    sejak yang bersangkutan diketahui meninggal, ahli waris TIDAK DIBERI TAHU oleh
    pejabat berwenang. Yang menghentikan jam adalah PEMBERITAHUAN RESMI — bukan
    kembalinya barang.

    Kembalikan {berlaku, tanggal_meninggal, batas_lapor, hari_sejak_wafat,
    sisa_hari, tingkat, sudah_diberitahu, peringatan}. `berlaku` False bila
    pegawai bukan berstatus meninggal / tanggal wafat tak sah — pemanggil cukup
    memeriksa flag ini. `tingkat`: "selesai" (sudah diberitahu) | "pantau" |
    "segera" (≤180 hari) | "kritis" (≤90 hari) | "lewat" (kedaluwarsa)."""
    from datetime import date

    kosong = {"berlaku": False, "tanggal_meninggal": "", "batas_lapor": "",
              "hari_sejak_wafat": None, "sisa_hari": None, "tingkat": "",
              "sudah_diberitahu": False, "peringatan": ""}
    p = pegawai or {}
    if not is_meninggal(p):
        return kosong
    wafat = str(p.get("tanggal_meninggal") or "").strip()[:10]
    if not _TGL_RE.match(wafat):
        return kosong
    hari = str(hari_ini_iso or "").strip()[:10]
    if not _TGL_RE.match(hari):
        return kosong
    try:
        d_wafat = date.fromisoformat(wafat)
        d_hari = date.fromisoformat(hari)
    except (ValueError, OverflowError):
        return kosong
    # Batas = 3 tahun KALENDER sejak wafat (29 Feb → 28 Feb pada tahun biasa).
    try:
        d_batas = d_wafat.replace(year=d_wafat.year + BATAS_LAPOR_AHLI_WARIS_TAHUN)
    except ValueError:
        d_batas = d_wafat.replace(year=d_wafat.year + BATAS_LAPOR_AHLI_WARIS_TAHUN,
                                  day=28)
    sisa = (d_batas - d_hari).days
    sudah = bool(str(p.get("pemberitahuan_ahli_waris_tanggal") or "").strip())
    hasil = {
        "berlaku": True, "tanggal_meninggal": wafat,
        "batas_lapor": d_batas.isoformat(),
        "hari_sejak_wafat": (d_hari - d_wafat).days,
        "sisa_hari": sisa, "sudah_diberitahu": sudah,
    }
    if sudah:
        hasil["tingkat"] = "selesai"
        hasil["peringatan"] = ""
    elif sisa < 0:
        hasil["tingkat"] = "lewat"
        hasil["peringatan"] = (
            f"Batas pemberitahuan ahli waris terlewat {abs(sisa)} hari — "
            "hak tagih negara hapus demi hukum; dokumentasikan")
    elif sisa <= 90:
        hasil["tingkat"] = "kritis"
        hasil["peringatan"] = (
            f"SEGERA — tersisa {sisa} hari untuk memberi tahu ahli waris; "
            "lewat batas, hak tagih negara hapus")
    elif sisa <= 180:
        hasil["tingkat"] = "segera"
        hasil["peringatan"] = (
            f"Tersisa {sisa} hari untuk memberi tahu ahli waris secara resmi")
    else:
        hasil["tingkat"] = "pantau"
        hasil["peringatan"] = (
            f"Batas pemberitahuan ahli waris {d_batas.isoformat()} "
            f"({sisa} hari lagi)")
    return hasil


def snapshot_pemegang_aset(pegawai) -> dict:
    """Snapshot identitas pemegang untuk field aset (`user` = nama lengkap,
    `pengguna_jabatan`, `pengguna_melekat_ke` = unit kerja efektif) dari
    dokumen pegawai master. Dipakai menyegarkan data pemegang pada aset yang
    dipegang (mis. setelah kenaikan pangkat/perpindahan unit) — TANPA menyentuh
    BAST historis. MURNI (teruji unit)."""
    p = pegawai or {}
    return {
        "user": nama_lengkap(p) or str(p.get("nama") or "").strip(),
        "pengguna_jabatan": str(p.get("jabatan") or "").strip(),
        "pengguna_melekat_ke": (str(p.get("unit_kerja") or "").strip()
                                or unit_kerja_terdalam(p)),
    }


def beda_snapshot_pemegang(asset, target) -> dict:
    """Field snapshot pemegang pada `asset` yang BERBEDA dari `target`
    (hanya field non-kosong pada target yang diperiksa — data master kosong
    tidak menghapus snapshot lama). Nama dibandingkan ternormalkan (spasi
    ganda/kapital diabaikan). Kembalikan {field: nilai_baru}; kosong = sudah
    sinkron. MURNI & idempoten (teruji unit)."""
    beda = {}
    for k, v in (target or {}).items():
        v = str(v or "").strip()
        if not v:
            continue
        lama = str((asset or {}).get(k) or "").strip()
        if k == "user":
            if " ".join(lama.split()).lower() != " ".join(v.split()).lower():
                beda[k] = v
        elif lama != v:
            beda[k] = v
    return beda


def rangkap_jabatan_pelaksana(pegawai) -> str:
    """Label rangkap jabatan struktural sementara pegawai — mis.
    "Plt. Kepala Bagian Umum" / "Plh. Kepala Kantor". Kosong bila pegawai
    bukan Plt/Plh. Memakai `jabatan_pelaksana` (jabatan yang di-Plt/Plh-kan);
    bila kosong, jatuh ke `jabatan` definitif. MURNI (teruji unit).

    Ini melengkapi jabatan DEFINITIF (`jabatan`): pegawai tetap memegang
    jabatannya sendiri + menjalankan jabatan yang di-Plt/Plh-kan (rangkap)."""
    p = pegawai or {}
    jenis = str(p.get("jenis_pelaksana") or "").strip().lower()
    if jenis not in JENIS_PELAKSANA:
        return ""
    jab = (str(p.get("jabatan_pelaksana") or "").strip()
           or str(p.get("jabatan") or "").strip())
    if not jab:
        return ""
    return f"{prefiks_pelaksana(jenis)}{jab}".strip()


def kelompok_unit_kerja(pegawai_list):
    """Kelompokkan pegawai per unit kerja (rekap). MURNI (teruji unit).

    Kembalikan list `[{unit_kerja, jumlah, pegawai:[...]}]` terurut nama unit;
    pegawai tanpa unit dikumpulkan sebagai "(unit kerja belum dicatat)" di akhir.
    """
    tanpa = "(unit kerja belum dicatat)"
    peta = {}
    for p in (pegawai_list or []):
        uk = str((p or {}).get("unit_kerja") or "").strip() or tanpa
        peta.setdefault(uk, []).append(p)

    def _key(uk):
        return (1, "") if uk == tanpa else (0, uk.lower())

    return [
        {"unit_kerja": uk, "jumlah": len(peta[uk]), "pegawai": peta[uk]}
        for uk in sorted(peta, key=_key)
    ]


def pegawai_perlu_serah_terima(pegawai_list, jumlah_aset_per_nip, hari_ini_iso):
    """Pegawai BERISIKO yang masih memegang aset — perlu serah terima BMN.

    Berisiko = status keberadaan bukan aktif/cuti/tugas_belajar (keluar,
    mutasi, pensiun, nonaktif, diperbantukan) ATAU kontrak Non-ASN sudah/akan
    habis (≤30 hari). Hanya pegawai ber-NIP yang tercatat memegang ≥1 aset
    (peta `jumlah_aset_per_nip`) yang dikembalikan. MURNI (teruji unit).

    Kembalikan [{id, nama, nip, status, jumlah_aset, alasan}] terurut jumlah
    aset terbanyak dulu (pola alert "pemegang keluar" KERJA-BARENG).
    """
    aman = {"aktif", "cuti", "tugas_belajar"}
    hasil = []
    for p in (pegawai_list or []):
        nip = str((p or {}).get("nip") or "").strip()
        if not nip:
            continue
        jumlah = int((jumlah_aset_per_nip or {}).get(nip) or 0)
        if jumlah <= 0:
            continue
        st = str(p.get("status") or "aktif").strip() or "aktif"
        alasan = []
        if st not in aman:
            alasan.append(f"status {STATUS_PEGAWAI.get(st, st)}")
        k = status_kontrak(p, hari_ini_iso)
        if k["habis"] or k["segera"]:
            alasan.append(k["peringatan"].lower())
        if not alasan:
            continue
        hasil.append({
            "id": p.get("id"), "nama": p.get("nama"), "nip": nip,
            "status": st, "jumlah_aset": jumlah,
            "alasan": "; ".join(alasan),
        })
    hasil.sort(key=lambda h: -h["jumlah_aset"])
    return hasil


def rekap_eselon(pegawai_list, field="eselon1"):
    """Rekap jumlah pegawai per satuan unit Eselon (default Eselon 1). MURNI.

    Kembalikan `[{unit, jumlah}]` terurut nama; kosong dikumpulkan di akhir."""
    tanpa = "(belum dicatat)"
    peta = {}
    for p in (pegawai_list or []):
        u = str((p or {}).get(field) or "").strip() or tanpa
        peta[u] = peta.get(u, 0) + 1

    def _key(u):
        return (1, "") if u == tanpa else (0, u.lower())

    return [{"unit": u, "jumlah": peta[u]} for u in sorted(peta, key=_key)]


def unit_kerja_terdalam(pegawai):
    """Unit kerja efektif = Eselon terdalam yang terisi (5→1), fallback
    field `unit_kerja`. Dipakai agar rekap & tampilan tetap punya satu label
    unit meski data berjenjang. MURNI."""
    p = pegawai or {}
    for f in ("eselon5", "eselon4", "eselon3", "eselon2", "eselon1"):
        v = str(p.get(f) or "").strip()
        if v:
            return v
    return str(p.get("unit_kerja") or "").strip()


def status_kontrak(pegawai, hari_ini_iso):
    """Status kontrak Non-ASN untuk pemantauan (pemegang aset berisiko saat
    kontrak berakhir). MURNI (teruji unit).

    Kembalikan {ada, tgl_selesai, sisa_hari, habis, segera, peringatan}.
    `sisa_hari` negatif = sudah lewat. `segera` = ≤30 hari lagi. Tanpa tgl
    selesai → {ada: False}."""
    from datetime import date

    p = pegawai or {}
    selesai = str(p.get("tgl_selesai_kontrak") or "").strip()[:10]
    if not _TGL_RE.match(selesai):
        return {"ada": False, "tgl_selesai": "", "sisa_hari": None,
                "habis": False, "segera": False, "peringatan": ""}
    hari = str(hari_ini_iso or "").strip()[:10]
    if not _TGL_RE.match(hari):
        return {"ada": True, "tgl_selesai": selesai, "sisa_hari": None,
                "habis": False, "segera": False, "peringatan": ""}
    try:
        d_selesai = date.fromisoformat(selesai)
        d_hari = date.fromisoformat(hari)
    except ValueError:
        return {"ada": True, "tgl_selesai": selesai, "sisa_hari": None,
                "habis": False, "segera": False, "peringatan": ""}
    sisa = (d_selesai - d_hari).days
    habis = sisa < 0
    segera = 0 <= sisa <= 30
    if habis:
        peringatan = f"Kontrak berakhir {abs(sisa)} hari lalu"
    elif segera:
        peringatan = f"Kontrak berakhir dalam {sisa} hari"
    else:
        peringatan = ""
    return {"ada": True, "tgl_selesai": selesai, "sisa_hari": sisa,
            "habis": habis, "segera": segera, "peringatan": peringatan}


# ── Normalisasi impor Excel/CSV (data lapangan sering "kotor") ───────────────

# Pemetaan header kolom (fleksibel) → field pegawai. Kunci di-lower & di-strip.
KOLOM_IMPOR = {
    "nip/nik/nrp": "nip", "nip": "nip", "nip/nrp": "nip", "nik": "nip",
    "nama lengkap": "nama", "nama": "nama",
    "jenis kelamin": "jenis_kelamin",
    "tempat lahir": "tempat_lahir",
    "tgl lahir": "tanggal_lahir", "tanggal lahir": "tanggal_lahir",
    "status kepegawaian": "status_kepegawaian",
    "pangkat/golongan": "pangkat_golongan", "pangkat / golongan": "pangkat_golongan",
    "jabatan": "jabatan",
    "jenis pelaksana (plt/plh)": "jenis_pelaksana",
    "jenis pelaksana": "jenis_pelaksana", "plt/plh": "jenis_pelaksana",
    "jabatan pelaksana (rangkap)": "jabatan_pelaksana",
    "jabatan pelaksana": "jabatan_pelaksana", "jabatan rangkap": "jabatan_pelaksana",
    "kategori pegawai": "kategori_pegawai",
    "eselon 1": "eselon1", "eselon 2": "eselon2", "eselon 3": "eselon3",
    "eselon 4": "eselon4", "eselon 5": "eselon5",
    "no telepon": "no_hp", "no. telepon": "no_hp", "no hp": "no_hp",
    "email": "email",
    "nama bank": "nama_bank",
    "no rekening": "no_rekening", "no. rekening": "no_rekening",
    "nomor kontrak": "nomor_kontrak",
    "tgl mulai kontrak": "tgl_mulai_kontrak",
    "tgl selesai kontrak": "tgl_selesai_kontrak",
    "status": "status",
    "status pegawai": "status_pegawai_satker",
    "status pegawai (satker)": "status_pegawai_satker",
    "keterangan": "keterangan",
    "tmt jabatan": "tmt_jabatan",
    "tgl akhir jabatan": "tanggal_akhir_jabatan",
    "npwp": "npwp",
    "pendidikan terakhir": "pendidikan_terakhir",
    "alamat": "alamat",
    "jenis kontrak non-asn": "jenis_kontrak_non_asn",
    "jenis kontrak non asn": "jenis_kontrak_non_asn",
    "perusahaan penyedia": "perusahaan_penyedia",
    "kode satker lengkap": "kode_satker_lengkap",
    "unit kerja": "unit_kerja",
    "gelar depan": "gelar_depan",
    "gelar belakang": "gelar_belakang",
    # ── Kelengkapan diri (SIMPEG) ──
    "agama": "agama",
    "status perkawinan": "status_perkawinan",
    "kewarganegaraan": "kewarganegaraan",
    "jenis identitas wna": "jenis_identitas_wna",
    "nomor identitas wna": "nomor_identitas_wna",
    "no identitas wna": "nomor_identitas_wna",
    # ── Jabatan & organisasi ──
    "jenis jabatan": "jenis_jabatan",
    "eselon (teks)": "eselon", "eselon": "eselon",
    "unit organisasi": "unit_organisasi",
    "unit organisasi / satker": "unit_organisasi",
    "instansi/satker terkait": "status_pegawai_instansi",
    "instansi terkait": "status_pegawai_instansi",
    # ── Kelengkapan status Meninggal Dunia & ahli waris ──
    "tgl meninggal": "tanggal_meninggal",
    "tanggal meninggal": "tanggal_meninggal",
    "nomor akta kematian": "nomor_akta_kematian",
    "no akta kematian": "nomor_akta_kematian",
    "penyebab meninggal": "penyebab_meninggal",
    "ahli waris - nama": "ahli_waris_nama", "ahli waris nama": "ahli_waris_nama",
    "ahli waris - hubungan": "ahli_waris_hubungan",
    "ahli waris hubungan": "ahli_waris_hubungan",
    "ahli waris - kontak": "ahli_waris_kontak",
    "ahli waris kontak": "ahli_waris_kontak",
    "tgl pemberitahuan ahli waris": "pemberitahuan_ahli_waris_tanggal",
    "nomor pemberitahuan ahli waris": "pemberitahuan_ahli_waris_nomor",
}

# Urutan kolom template ekspor/impor (header ramah).
#
# CAKUPAN: seluruh field yang dapat diisi lewat form Master Pegawai, dengan DUA
# pengecualian yang disengaja — keduanya bukan kelalaian:
#
#   * `sub_kategori_non_asn` — sudah pulang-pergi lewat kolom "Status
#     Kepegawaian" (ekspor menulis label subnya, mis. "Satpam"; impor
#     memulihkannya jadi non_asn + satpam). Kolom terpisah akan menciptakan dua
#     sumber untuk satu nilai, yang bisa saling bertentangan.
#   * `kode_satker` — dicap server dari satker pengimpor demi isolasi data
#     (lihat `impor_pegawai`), jadi kolomnya akan diabaikan diam-diam. Kodenya
#     sudah tercantum di nama berkas ekspor.
#
# Uji `test_pegawai_cakupan_ekspor.py` menagih kesetaraan ini agar field form
# baru tak lagi bisa lahir tanpa kolomnya.
HEADER_IMPOR = [
    "NIP/NIK/NRP", "Nama Lengkap", "Gelar Depan", "Gelar Belakang",
    "Jenis Kelamin", "Tempat Lahir", "Tgl Lahir",
    "Agama", "Status Perkawinan",
    "Kewarganegaraan", "Jenis Identitas WNA", "Nomor Identitas WNA",
    "Status Kepegawaian", "Pangkat/Golongan", "Jabatan", "Jenis Jabatan",
    "Jenis Pelaksana (Plt/Plh)", "Jabatan Pelaksana (Rangkap)",
    "Kategori Pegawai",
    "TMT Jabatan", "Tgl Akhir Jabatan",
    "Eselon 1", "Eselon 2", "Eselon 3", "Eselon 4", "Eselon 5",
    "Eselon (Teks)",
    "Unit Kerja", "Unit Organisasi",
    "No Telepon", "Email", "NPWP", "Pendidikan Terakhir", "Alamat",
    "Nama Bank", "No Rekening",
    "Nomor Kontrak", "Tgl Mulai Kontrak", "Tgl Selesai Kontrak",
    "Jenis Kontrak Non-ASN", "Perusahaan Penyedia", "Kode Satker Lengkap",
    "Status Pegawai", "Instansi/Satker Terkait", "Status",
    "Tgl Meninggal", "Nomor Akta Kematian", "Penyebab Meninggal",
    "Ahli Waris - Nama", "Ahli Waris - Hubungan", "Ahli Waris - Kontak",
    "Tgl Pemberitahuan Ahli Waris", "Nomor Pemberitahuan Ahli Waris",
    "Keterangan",
]


def bersihkan_nip(nilai):
    """Bersihkan NIP dari artefak Excel (mis. '...0002.0' float, spasi tak
    terlihat, tanda '-'). Kembalikan digit saja bila mengandung angka. MURNI."""
    s = str(nilai or "").strip()
    if s in ("", "-", "None", "nan"):
        return ""
    # Buang karakter kontrol/arah (U+202D dst.) & spasi
    s = "".join(ch for ch in s if ch.isprintable() and not ch.isspace())
    if s.endswith(".0"):
        s = s[:-2]
    # Bila seluruhnya kombinasi digit + pemisah → sisakan digit
    digit = re.sub(r"\D", "", s)
    if digit and len(digit) >= 8:
        return digit
    return s if s not in ("-",) else ""


def normalisasi_status_kepegawaian(nilai):
    """Petakan status kepegawaian bebas → (kode kanonik, sub_kategori_non_asn).

    Data lapangan bercampur ("Tenaga Pendukung", "Konsultan Individu" dsb.);
    yang bukan ASN/TNI/POLRI dipetakan ke 'non_asn' dengan sub-kategori bila
    dikenali. MURNI (teruji unit)."""
    s = str(nilai or "").strip().lower()
    if not s:
        return "", ""
    langsung = {"pns": "pns", "cpns": "cpns", "pppk": "pppk", "p3k": "pppk",
                "tni": "tni", "polri": "polri"}
    if s in langsung:
        return langsung[s], ""
    # Sub-kategori Non-ASN dari teks.
    for kode, ur in SUB_KATEGORI_NON_ASN.items():
        if ur.lower() in s or kode.replace("_", " ") in s:
            return "non_asn", kode
    if "konsultan" in s:
        return "non_asn", "konsultan"
    if "tenaga pendukung" in s or "pendukung" in s:
        return "non_asn", "tenaga_pendukung"
    if "tenaga ahli" in s:
        return "non_asn", "tenaga_ahli"
    if any(k in s for k in ("non-asn", "non asn", "honorer", "kontrak",
                            "ppnpn", "outsourc", "pramubakti", "magang")):
        return "non_asn", ""
    return "non_asn", ""


def normalisasi_status_pegawai(nilai):
    """Petakan status keberadaan bebas → kode STATUS_PEGAWAI. Kosong → 'aktif'.
    MURNI (teruji unit)."""
    s = str(nilai or "").strip().lower().replace("_", " ")
    if not s:
        return "aktif"
    # "Nonaktif" mengandung substring "aktif" — periksa lebih dulu.
    if "nonaktif" in s or "non aktif" in s or "non-aktif" in s:
        return "nonaktif"
    if "aktif" in s:
        return "aktif"
    # "MUTASI KELUAR" → mutasi (dicek sebelum 'keluar' karena memuatnya).
    if "mutasi" in s or "pindah" in s:
        return "mutasi"
    if "pensiun" in s:
        return "pensiun"
    if "keluar" in s or "berhenti" in s or "resign" in s:
        return "keluar"
    if "tugas belajar" in s:
        return "tugas_belajar"
    if "diperbantukan" in s or "dpb" in s:
        return "diperbantukan"
    if "cuti" in s:
        return "cuti"
    # Kematian punya KELAS SENDIRI (dulu dipetakan ke 'nonaktif' sehingga
    # informasinya hilang) — perlakuan administratifnya berbeda: butuh akta
    # kematian, ahli waris, dan menjalankan jam 3 tahun pemberitahuan.
    if "meninggal" in s or "wafat" in s or "almarhum" in s:
        return "meninggal"
    return "aktif"


def normalisasi_status_pegawai_satker(nilai):
    """Petakan status pegawai (SIMPEG) bebas → kode STATUS_PEGAWAI_SATKER.
    Menerima kode maupun uraian (mis. 'Diperbantukan Pada'). Kosong/asing → "".
    MURNI (teruji unit)."""
    s = str(nilai or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low in STATUS_PEGAWAI_SATKER:
        return low
    for kode, ur in STATUS_PEGAWAI_SATKER.items():
        if low == ur.lower():
            return kode
    if low == "cpns" or "calon pegawai" in low:
        return "calon_pegawai"
    return ""


def normalisasi_kode_referensi(nilai, peta):
    """Kode ATAU uraian → kode referensi; kosong/asing → "". MURNI.

    Satu penormal untuk seluruh enum sederhana (agama, status perkawinan,
    kewarganegaraan, jenis identitas WNA, jenis jabatan) — semuanya berpola
    sama, dan menyalinnya lima kali hanya menambah tempat untuk melenceng.

    Nilai asing dikosongkan, BUKAN disimpan apa adanya: `validate_pegawai`
    menolak kode di luar daftar, dan penolakan itu membuang SELURUH baris
    pegawai saat impor massal. Kehilangan satu sel lebih ringan daripada
    kehilangan satu orang.
    """
    s = str(nilai or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low in peta:
        return low
    for kode, uraian in peta.items():
        if low == str(uraian).strip().lower():
            return kode
    return ""


def _norm_jk(nilai):
    s = str(nilai or "").strip().lower()
    if s.startswith("l") or "laki" in s or s == "m":
        return "L"
    if s.startswith("p") or "perempuan" in s or s == "f" or "wanita" in s:
        return "P"
    return ""


def _norm_tgl(nilai):
    """Normalkan tanggal → 'YYYY-MM-DD' bila terdeteksi; jika tak jelas kosong."""
    s = str(nilai or "").strip()
    if s in ("", "-", "None"):
        return ""
    if _TGL_RE.match(s[:10]):
        return s[:10]
    # dd/mm/yyyy atau dd-mm-yyyy
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""


def normalisasi_kategori_pegawai(nilai):
    """Petakan kategori jabatan (kode ATAU label) → kode KATEGORI_PEGAWAI.
    Tak dikenal → apa adanya (lower) agar tidak menghilangkan data. MURNI."""
    s = str(nilai or "").strip().lower()
    if not s:
        return ""
    if s in KATEGORI_PEGAWAI:
        return s
    for kode, label in KATEGORI_PEGAWAI.items():
        if label.lower() == s or kode in s:
            return kode
    if "pimpinan tinggi" in s or "jpt" in s:
        return "jpt"
    if "administrator" in s:
        return "administrator"
    if "pengawas" in s:
        return "pengawas"
    if "fungsional" in s:
        return "fungsional"
    if "pelaksana" in s:
        return "pelaksana"
    return s


def normalisasi_jenis_kontrak(nilai):
    """Petakan jenis kontrak Non-ASN bebas → 'internal'/'outsourcing'/''."""
    s = str(nilai or "").strip().lower()
    if not s:
        return ""
    if "outsourc" in s or "penyedia" in s or "pihak ketiga" in s:
        return "outsourcing"
    if "internal" in s or "ppnpn" in s or "spk" in s or "instansi" in s:
        return "internal"
    return ""


def normalisasi_jenis_pelaksana(nilai):
    """Petakan teks bebas → kode jenis pelaksana ('plt'/'plh'/''). Mengenali
    'Plt', 'Plt.', 'Pelaksana Tugas', 'Plh', 'Pelaksana Harian'. MURNI."""
    s = str(nilai or "").strip().lower().rstrip(".")
    if not s:
        return ""
    if s in ("plt", "plt.") or "pelaksana tugas" in s:
        return "plt"
    if s in ("plh", "plh.") or "pelaksana harian" in s:
        return "plh"
    return ""


# Field impor yang cukup dinormalkan lewat peta referensinya sendiri.
_ENUM_IMPOR = {
    "agama": AGAMA,
    "status_perkawinan": STATUS_PERKAWINAN,
    "kewarganegaraan": KEWARGANEGARAAN,
    "jenis_identitas_wna": JENIS_IDENTITAS_WNA,
    "jenis_jabatan": JENIS_JABATAN,
}


# Field yang DITURUNKAN dari field lain saat impor: bila sumbernya dipasok
# baris, turunannya ikut terhitung dipasok. Tanpa ini `sub_kategori_non_asn`
# (dari Status Kepegawaian) dan `unit_kerja` (dari Eselon terdalam) akan
# dianggap "tak dipasok" lalu tak pernah ikut diperbarui.
_TURUNAN_IMPOR = {
    "status_kepegawaian": ("sub_kategori_non_asn",),
    "eselon1": ("unit_kerja",), "eselon2": ("unit_kerja",),
    "eselon3": ("unit_kerja",), "eselon4": ("unit_kerja",),
    "eselon5": ("unit_kerja",),
}


def field_dipasok_baris(raw) -> set:
    """Field yang BENAR-BENAR dipasok satu baris impor (header dikenal DAN
    selnya terisi). MURNI.

    Dibutuhkan karena `baris_impor_ke_pegawai` selalu mengembalikan SELURUH
    ~54 field — yang tak ada di berkas berisi string kosong. Menulis dokumen
    itu apa adanya dengan `$set` menimpa data yang sudah ada di master dengan
    kosong: NPWP, rekening, dan blok ahli waris lenyap hanya karena kolomnya
    tak ikut di berkas impor.

    Bahaya khusus `status`: `baris_impor_ke_pegawai` mengisinya "aktif" sebagai
    default, bukan sebagai data. Tanpa daftar ini, mengimpor berkas tanpa kolom
    Status akan MENGHIDUPKAN KEMBALI pegawai yang berstatus meninggal.
    """
    dipasok = set()
    for header, nilai in (raw or {}).items():
        field = KOLOM_IMPOR.get(str(header or "").strip().lower())
        if not field:
            continue
        if str(nilai if nilai is not None else "").strip() == "":
            continue
        dipasok.add(field)
        dipasok.update(_TURUNAN_IMPOR.get(field, ()))
    return dipasok


def _norm_kunci(v) -> str:
    """Normalisasi nilai untuk kunci identitas: huruf kecil, spasi tunggal."""
    return " ".join(str(v or "").strip().lower().split())


def kunci_dedup_pegawai(doc) -> tuple:
    """Kunci identitas untuk mengenali BARIS-BARIS YANG MERUJUK ORANG SAMA.

    Berjenjang, dari yang paling kuat ke yang paling lemah:

      1. ``("nip", nip)`` — identitas resmi, paling dapat dipercaya.
      2. ``("wna", jenis, nomor)`` — pegawai WNA ber-KITAS/KITAP.
      3. ``("lahir", nama, tanggal_lahir)`` — tanpa NIP tetapi tanggal lahirnya
         diketahui; nama + tanggal lahir praktis unik.
      4. ``("jabatan", nama, unit_kerja, jabatan, status_kepegawaian)`` — jalan
         terakhir untuk pegawai tanpa identitas apa pun. Sengaja MEMAKAI BANYAK
         unsur: memakai nama saja akan menggabungkan dua orang berbeda yang
         kebetulan senama, dan itu lebih buruk daripada duplikat.

    ``None`` bila nama kosong (baris tak dapat dipakai).

    Tanpa kunci ini, baris tanpa NIP SELALU disisipkan sebagai orang baru —
    mengimpor ulang berkas yang sama menggandakan mereka setiap kali.
    """
    d = doc or {}
    nip = str(d.get("nip") or "").strip()
    if nip:
        return ("nip", nip)
    nomor_wna = str(d.get("nomor_identitas_wna") or "").strip()
    if nomor_wna:
        return ("wna", _norm_kunci(d.get("jenis_identitas_wna")), nomor_wna)
    nama = _norm_kunci(d.get("nama"))
    if not nama:
        return None
    lahir = str(d.get("tanggal_lahir") or "").strip()
    if lahir:
        return ("lahir", nama, lahir)
    return ("jabatan", nama, _norm_kunci(d.get("unit_kerja")),
            _norm_kunci(d.get("jabatan")), _norm_kunci(d.get("status_kepegawaian")))


def gabung_baris_pegawai(dasar, dipasok_dasar, tambahan, dipasok_tambahan):
    """Gabung DUA baris impor yang merujuk orang yang sama → (doc, dipasok).

    Nilai dari baris berikutnya menang HANYA untuk field yang benar-benar
    dipasoknya. Ini yang membuat dua baris saling melengkapi: satu membawa
    NPWP, satu membawa nama bank + nomor rekening, hasilnya satu orang dengan
    keduanya — bukan dua baris yang masing-masing setengah.
    """
    doc = dict(dasar or {})
    for field in (dipasok_tambahan or set()):
        if field in (tambahan or {}):
            doc[field] = tambahan[field]
    return doc, set(dipasok_dasar or set()) | set(dipasok_tambahan or set())


def baris_impor_ke_pegawai(raw):
    """Ubah satu baris impor (dict {header: nilai}) → dokumen pegawai bersih +
    daftar peringatan lunak. MURNI (teruji unit).

    Kembalikan (doc, peringatan[]). `doc` kosong (nama="") berarti baris tak
    dapat dipakai (dilewati pemanggil)."""
    peringatan = []
    doc = {k: "" for k in (
        "nama", "nip", "jenis_kelamin", "tempat_lahir", "tanggal_lahir",
        "status_kepegawaian", "pangkat_golongan", "jabatan",
        "jenis_pelaksana", "jabatan_pelaksana", "kategori_pegawai",
        "eselon1", "eselon2", "eselon3", "eselon4", "eselon5",
        "no_hp", "email", "nama_bank", "no_rekening", "nomor_kontrak",
        "tgl_mulai_kontrak", "tgl_selesai_kontrak", "keterangan",
        "sub_kategori_non_asn", "unit_kerja", "gelar_depan", "gelar_belakang",
        "tmt_jabatan", "tanggal_akhir_jabatan", "npwp",
        "pendidikan_terakhir", "alamat", "jenis_kontrak_non_asn",
        "perusahaan_penyedia", "kode_satker_lengkap", "status_pegawai_satker",
        "agama", "status_perkawinan", "kewarganegaraan",
        "jenis_identitas_wna", "nomor_identitas_wna",
        "jenis_jabatan", "eselon", "unit_organisasi",
        "status_pegawai_instansi",
        "tanggal_meninggal", "nomor_akta_kematian", "penyebab_meninggal",
        "ahli_waris_nama", "ahli_waris_hubungan", "ahli_waris_kontak",
        "pemberitahuan_ahli_waris_tanggal",
        "pemberitahuan_ahli_waris_nomor")}
    doc["status"] = "aktif"
    for header, nilai in (raw or {}).items():
        field = KOLOM_IMPOR.get(str(header or "").strip().lower())
        if not field:
            continue
        val = str(nilai if nilai is not None else "").strip()
        if val in ("None", "-"):
            val = ""
        if field == "nip":
            doc["nip"] = bersihkan_nip(nilai)
        elif field == "jenis_kelamin":
            doc["jenis_kelamin"] = _norm_jk(val)
        elif field in ("tanggal_lahir", "tgl_mulai_kontrak",
                       "tgl_selesai_kontrak", "tmt_jabatan",
                       "tanggal_akhir_jabatan", "tanggal_meninggal",
                       "pemberitahuan_ahli_waris_tanggal"):
            doc[field] = _norm_tgl(val)
        elif field in _ENUM_IMPOR:
            doc[field] = normalisasi_kode_referensi(val, _ENUM_IMPOR[field])
        elif field == "status_kepegawaian":
            kode, sub = normalisasi_status_kepegawaian(val)
            doc["status_kepegawaian"] = kode
            if sub:
                doc["sub_kategori_non_asn"] = sub
        elif field == "status":
            doc["status"] = normalisasi_status_pegawai(val)
        elif field == "status_pegawai_satker":
            doc["status_pegawai_satker"] = normalisasi_status_pegawai_satker(val)
        elif field == "kategori_pegawai":
            doc["kategori_pegawai"] = normalisasi_kategori_pegawai(val)
        elif field == "jenis_pelaksana":
            doc["jenis_pelaksana"] = normalisasi_jenis_pelaksana(val)
        elif field == "jenis_kontrak_non_asn":
            doc["jenis_kontrak_non_asn"] = normalisasi_jenis_kontrak(val)
        elif field == "kode_satker_lengkap":
            # DULU `re.sub(r"\D", "", val)` — membuang SEMUA non-digit. Sejak
            # kolom ini memuat kode lokasi BMN 20 karakter, penyaringan itu
            # memakan huruf kewenangannya: `126011600691778000KP` masuk
            # sebagai 18 digit, lalu ditolak validator sebagai "bukan 20
            # karakter". Impor massal gagal karena pembersihnya sendiri.
            doc["kode_satker_lengkap"] = normalisasi_kode_satker_lengkap(val)
        else:
            doc[field] = val
    # Unit kerja efektif dari Eselon terdalam bila unit_kerja kosong.
    if not doc["unit_kerja"]:
        doc["unit_kerja"] = unit_kerja_terdalam(doc)
    if not doc["nama"]:
        peringatan.append("Nama kosong — baris dilewati")
    if doc["nip"] and (not doc["nip"].isdigit() or not (8 <= len(doc["nip"]) <= 20)):
        peringatan.append(f"NIP '{doc['nip']}' bukan 8–20 digit — disimpan apa adanya")
    return doc, peringatan


# ---------------------------------------------------------------------------
# Identitas pintar & masa kerja (riset 2026-07): NIP PNS/NI PPPK 18 digit
# (Perka BKN 22/2007; digit 13-14 PPPK = frekuensi mulai 21), NRP POLRI
# 8 digit (YYMM lahir + urut), NRP TNI tidak seragam (5-7 digit — jangan
# validasi ketat), NIK 16 digit (digit 7-12 tanggal lahir; perempuan +40).
# BUP: UU ASN 20/2023 Ps.55 (JPT 60; administrator/pengawas/pelaksana 58;
# fungsional ahli utama 65, ahli madya 60, lainnya 58 — PP 11/2017 jo.
# 17/2020), UU TNI 3/2025 (tamtama/bintara 55, perwira 58, pati 60-63),
# UU Polri 5/2026 (tamtama/bintara 59, perwira 60). Fungsi murni.
# ---------------------------------------------------------------------------

JENIS_KONTRAK_NON_ASN = {
    "internal": "Kontrak internal instansi (PPNPN/SPK dengan PPK)",
    "outsourcing": "Outsourcing (melalui perusahaan penyedia)",
}


def _tgl_valid(y, m, d) -> bool:
    from datetime import date as _date
    try:
        _date(int(y), int(m), int(d))
        return True
    except ValueError:
        return False


def deteksi_identitas(nomor) -> dict:
    """Kenali jenis nomor identitas dari formatnya → {jenis, label, keterangan}.

    Deteksi untuk SARAN/label (bukan validasi keras — NRP TNI tidak seragam):
    18 digit ber-tanggal valid → NIP PNS (digit 13-14 = 01-12) / NI PPPK
    (13-14 ≥ 21); 16 digit → NIK (Non-ASN); 8 digit ber-bulan valid → NRP
    POLRI; 5-7 digit → kemungkinan NRP TNI; selain itu → tidak dikenal.
    """
    n = str(nomor or "").strip()
    if not n.isdigit():
        return {"jenis": "", "label": "No. Identitas", "keterangan": ""}
    if len(n) == 18 and _tgl_valid(n[0:4], n[4:6], n[6:8]):
        blok = n[12:14]
        if "01" <= blok <= "12":
            return {"jenis": "nip_pns", "label": "NIP",
                    "keterangan": "NIP PNS (18 digit — lahir "
                                  f"{n[6:8]}-{n[4:6]}-{n[0:4]}, TMT CPNS {n[12:14]}/{n[8:12]})"}
        if blok >= "21":
            return {"jenis": "ni_pppk", "label": "NI PPPK",
                    "keterangan": f"Nomor Induk PPPK (frekuensi kontrak ke-{int(blok) - 20})"}
        return {"jenis": "nip", "label": "NIP", "keterangan": "NIP 18 digit"}
    if len(n) == 16:
        return {"jenis": "nik", "label": "NIK",
                "keterangan": "NIK (16 digit — pegawai Non-ASN)"}
    if len(n) == 8 and "01" <= n[2:4] <= "12":
        return {"jenis": "nrp_polri", "label": "NRP",
                "keterangan": "NRP POLRI (8 digit — tahun+bulan lahir + no. register)"}
    if 5 <= len(n) <= 7:
        return {"jenis": "nrp_tni", "label": "NRP",
                "keterangan": "Kemungkinan NRP TNI (format tidak seragam — konfirmasi manual)"}
    return {"jenis": "", "label": "No. Identitas", "keterangan": ""}


def _abad_dua_digit(yy: int, tahun_kini: int) -> int:
    """Terka tahun 4-digit dari 2-digit (NIK) memakai pivot tahun berjalan:
    yy ≤ (tahun_kini % 100) → 20yy (kelahiran belum lampau seabad), selain itu
    19yy. Mis. tahun_kini 2026 (pivot 26): '05'→2005, '98'→1998, '26'→2026."""
    pivot = tahun_kini % 100
    return (2000 + yy) if yy <= pivot else (1900 + yy)


def urai_identitas(nomor, tahun_kini: int = None) -> dict:
    """Urai DATA TERSTRUKTUR yang PASTI dapat diturunkan dari nomor identitas —
    untuk auto-isi form Master Pegawai. Hanya isi yang deterministik:

    - NIP PNS / NI PPPK (18 digit): tanggal_lahir (digit 1-8 YYYYMMDD),
      jenis_kelamin (digit 15: 1=L, 2=P), tmt_cpns (digit 9-14 YYYYMM → 'YYYY-MM',
      hanya PNS). Sumber: Perka BKN 22/2007.
    - NIK (16 digit): tanggal_lahir (digit 7-12 DDMMYY; PEREMPUAN tanggal+40),
      jenis_kelamin (tanggal>40 → P), wilayah_kode (digit 1-6). Tahun 2-digit
      diterka via pivot tahun berjalan.
    - NRP POLRI (8 digit): hanya isyarat tahun+bulan lahir (tanpa tanggal/gender)
      → TIDAK auto-isi tanggal penuh (partial), field dibiarkan kosong.
    - NRP TNI / tak dikenal: nihil (format tidak seragam — jangan tebak).

    `terisi` = daftar field yang berhasil diturunkan (untuk info UI). Fungsi
    murni & deterministik bila `tahun_kini` diberikan (untuk unit test)."""
    if tahun_kini is None:
        from datetime import date as _d
        tahun_kini = _d.today().year
    n = str(nomor or "").strip()
    hasil = {"jenis": "", "tanggal_lahir": "", "jenis_kelamin": "",
             "tmt_cpns": "", "wilayah_kode": "", "sumber": "", "terisi": []}
    if not n.isdigit():
        return hasil
    jenis = deteksi_identitas(n).get("jenis", "")
    hasil["jenis"] = jenis
    if jenis in ("nip_pns", "ni_pppk", "nip") and len(n) == 18 \
            and _tgl_valid(n[0:4], n[4:6], n[6:8]):
        hasil["tanggal_lahir"] = f"{n[0:4]}-{n[4:6]}-{n[6:8]}"
        hasil["terisi"].append("tanggal_lahir")
        jk = n[14]
        if jk in ("1", "2"):
            hasil["jenis_kelamin"] = "L" if jk == "1" else "P"
            hasil["terisi"].append("jenis_kelamin")
        if jenis == "nip_pns" and "01" <= n[12:14] <= "12":
            hasil["tmt_cpns"] = f"{n[8:12]}-{n[12:14]}"  # YYYY-MM
            hasil["terisi"].append("tmt_cpns")
        hasil["sumber"] = "NIP"
    elif jenis == "nik" and len(n) == 16:
        dd = int(n[6:8])
        perempuan = dd > 40
        hari = dd - 40 if perempuan else dd
        tahun = _abad_dua_digit(int(n[10:12]), tahun_kini)
        if _tgl_valid(tahun, n[8:10], hari):  # hanya bila tanggal masuk akal
            hasil["tanggal_lahir"] = f"{tahun:04d}-{n[8:10]}-{hari:02d}"
            hasil["terisi"].append("tanggal_lahir")
            hasil["jenis_kelamin"] = "P" if perempuan else "L"
            hasil["terisi"].append("jenis_kelamin")
        hasil["wilayah_kode"] = n[0:6]
        hasil["sumber"] = "NIK"
    elif jenis == "nrp_polri":
        hasil["sumber"] = "NRP POLRI"  # parsial — tak cukup untuk auto-isi
    return hasil


def label_nomor_identitas(nomor, status_kepegawaian="") -> str:
    """Label pendek utk laporan: 'NIP'/'NI PPPK'/'NRP'/'' (kosong).

    Non-ASN TIDAK menampilkan NIK di laporan (privasi — permintaan pemilik);
    kembalikan "" agar pemanggil melewatkan barisnya. Nomor berformat NIK
    juga DITAHAN apa pun statusnya — termasuk ASN yang NIP-nya belum
    tercatat di master (masih NIK) dan TNI/POLRI: area ttd cukup nama.
    Deteksi mengabaikan pemisah umum (spasi/titik/strip) supaya NIK
    '3506 0425 0390 0001' tidak lolos sebagai nomor tak dikenal.
    """
    st = str(status_kepegawaian or "").strip().lower()
    if st == "non_asn":
        return ""
    det = deteksi_identitas(_RE_PEMISAH_NOMOR.sub("", str(nomor or "")))
    if det["jenis"] == "nik":
        return ""  # NIK = identitas penduduk, bukan utk dicetak di laporan
    if st in ("tni", "polri"):
        return "NRP"
    return det["label"] if det["jenis"] else ("NIP" if str(nomor or "").strip() else "")


def baris_identitas_laporan(nomor, status_kepegawaian="") -> str:
    """Baris 'NIP. xxx' utk blok ttd laporan — label mengikuti jenis nomor;
    kosong bila tidak layak dicetak (Non-ASN/NIK/kosong)."""
    n = str(nomor or "").strip()
    if not n:
        return ""
    label = label_nomor_identitas(n, status_kepegawaian)
    return f"{label}. {n}" if label else ""


# BUP (batas usia pensiun) dalam TAHUN per kombinasi status × jabatan.
def _bup_tahun(pegawai) -> int:
    p = pegawai or {}
    st = str(p.get("status_kepegawaian") or "").strip().lower()
    kat = str(p.get("kategori_pegawai") or "").strip().lower()
    jab = str(p.get("jabatan") or "").lower()
    pangkat = str(p.get("pangkat_golongan") or "").lower()
    if st in ("pns", "cpns", "pppk"):
        if kat == "jpt":
            return 60
        if kat == "fungsional":
            if "utama" in jab or "utama" in pangkat:
                return 65
            if "madya" in jab or "madya" in pangkat:
                return 60
            return 58
        return 58  # administrator/pengawas/pelaksana
    if st == "tni":
        perwira = any(x in pangkat for x in (
            "let", "kapten", "mayor", "kolonel", "jenderal", "laksamana",
            "marsekal", "brigadir jenderal", "laksma", "marsma"))
        return 58 if perwira else 55  # pati 60-63 tidak dibedakan (konservatif)
    if st == "polri":
        perwira = any(x in pangkat for x in (
            "ipda", "iptu", "akp", "kompol", "akbp", "kombes", "brigjen",
            "irjen", "komjen", "jenderal"))
        return 60 if perwira else 59
    return 0  # Non-ASN/tak dikenal: tidak ada BUP (pakai kontrak)


def durasi_terbilang(dari_iso, sampai_iso) -> dict:
    """Durasi antara dua tanggal (YYYY-MM-DD) → {hari, label}. Label gaya
    "3 tahun 2 bulan" (komponen nol dilewati; kurang dari 1 bulan → "N hari").
    `dari` > `sampai` atau tanggal tak valid → {hari: None, label: ""}.
    MURNI (teruji unit)."""
    from calendar import monthrange
    from datetime import date

    d1 = str(dari_iso or "").strip()[:10]
    d2 = str(sampai_iso or "").strip()[:10]
    if not (_TGL_RE.match(d1) and _TGL_RE.match(d2)):
        return {"hari": None, "label": ""}
    try:
        a = date.fromisoformat(d1)
        b = date.fromisoformat(d2)
    except ValueError:
        return {"hari": None, "label": ""}
    if a > b:
        return {"hari": None, "label": ""}
    hari_total = (b - a).days
    tahun = b.year - a.year
    bulan = b.month - a.month
    harik = b.day - a.day
    if harik < 0:
        bulan -= 1
        pm = b.month - 1 or 12
        py = b.year if b.month - 1 else b.year - 1
        harik += monthrange(py, pm)[1]
    if bulan < 0:
        tahun -= 1
        bulan += 12
    bagian = []
    if tahun:
        bagian.append(f"{tahun} tahun")
    if bulan:
        bagian.append(f"{bulan} bulan")
    if not bagian:
        bagian.append(f"{harik} hari")
    return {"hari": hari_total, "label": " ".join(bagian)}


def info_masa_pegawai(pegawai, hari_ini_iso) -> dict:
    """Info masa utk baris daftar: pensiun (ASN/TNI/POLRI), akhir jabatan,
    kontrak (Non-ASN) → {label_identitas, bup, tanggal_pensiun,
    sisa_hari_pensiun, akhir_jabatan, sisa_hari_jabatan, kontrak{...}}.

    Semua nilai None/"" bila datanya tidak lengkap — tidak menebak."""
    from datetime import date

    p = pegawai or {}
    det = deteksi_identitas(p.get("nip"))
    out = {"label_identitas": det["label"], "jenis_identitas": det["jenis"],
           "bup": None, "tanggal_pensiun": "", "sisa_hari_pensiun": None,
           "akhir_jabatan": "", "sisa_hari_jabatan": None}
    hari = str(hari_ini_iso or "").strip()[:10]
    try:
        d_hari = date.fromisoformat(hari)
    except ValueError:
        d_hari = None
    # Pensiun: tanggal_lahir + BUP (akhir bulan ulang tahun disederhanakan
    # ke tanggal ulang tahun — perkiraan, angka final SK BKN/instansi).
    bup = _bup_tahun(p)
    lahir = str(p.get("tanggal_lahir") or "").strip()[:10]
    if bup and _TGL_RE.match(lahir):
        try:
            d_lahir = date.fromisoformat(lahir)
            d_pensiun = d_lahir.replace(year=d_lahir.year + bup)
            out["bup"] = bup
            out["tanggal_pensiun"] = d_pensiun.isoformat()
            if d_hari:
                out["sisa_hari_pensiun"] = (d_pensiun - d_hari).days
        except ValueError:
            pass
    # Akhir periode jabatan (bila dicatat)
    akhir_jab = str(p.get("tanggal_akhir_jabatan") or "").strip()[:10]
    if _TGL_RE.match(akhir_jab):
        out["akhir_jabatan"] = akhir_jab
        if d_hari:
            try:
                out["sisa_hari_jabatan"] = (
                    date.fromisoformat(akhir_jab) - d_hari).days
            except ValueError:
                pass
    # Masa kerja DALAM jabatan: TMT Jabatan → hari ini (kolom "menjabat sejak").
    # TMT = tanggal MULAI memangku jabatan; dipasangkan dengan Akhir Periode
    # Jabatan bila jabatan berbatas waktu.
    tmt = str(p.get("tmt_jabatan") or "").strip()[:10]
    out["tmt_jabatan"] = tmt if _TGL_RE.match(tmt) else ""
    out["masa_jabatan"] = (durasi_terbilang(tmt, hari)
                           if (out["tmt_jabatan"] and d_hari)
                           else {"hari": None, "label": ""})
    out["kontrak"] = status_kontrak(p, hari_ini_iso)
    return out


# Label baris identitas pada garis tanda tangan yang MASIH KOSONG.
#
# Permintaan pemilik: *"pastikan di semua generate PDF bagian NIP/NIK/NRP dapat
# otomatis terdeteksi."* Untuk nomor yang ADA, deteksinya sudah berjalan lewat
# `label_nomor_identitas` (NIP / NI PPPK / NRP, dan NIK ditahan demi privasi).
# Yang belum: garis tanda tangan KOSONG — yang diisi tangan setelah dicetak —
# memakai label "NIP." yang dipatok. Penanda tangan Non-ASN (NIK) atau
# TNI/POLRI (NRP) jadi diminta menuliskan nomornya di bawah label yang salah,
# dan tak ada satu pun jalur kode yang bisa mendeteksinya: nomornya memang
# belum ada saat PDF dicetak.
#
# Jalan keluarnya bukan menebak, melainkan tidak menebak: satu label netral
# yang benar untuk ketiganya.
PLACEHOLDER_IDENTITAS = "NIP/NIK/NRP. ................"


def baris_identitas_ttd(nomor, placeholder="", status_kepegawaian="") -> list:
    """Baris identitas utk blok tanda tangan PDF (list utk 'after').

    Label mengikuti jenis nomor (NIP/NI PPPK/NRP); penandatangan Non-ASN
    ATAU nomor berformat NIK TIDAK dicetak apa pun statusnya (privasi —
    list kosong; termasuk ASN yang di master masih tercatat NIK, belum
    NIP: cukup nama). Nomor kosong → placeholder titik-titik bila
    diberikan (konvensi garis ttd)."""
    n = str(nomor or "").strip()
    if not n or n in ("-", "--"):
        return [placeholder] if placeholder else []
    b = baris_identitas_laporan(n, status_kepegawaian)
    return [b] if b else []


# ---------------------------------------------------------------------------
# Ekspor Excel Master Pegawai (W7) — header = HEADER_IMPOR sehingga hasil
# ekspor dapat DIIMPOR KEMBALI (round-trip) setelah diedit. Semua label
# ekspor dipilih agar normalisasi impor mengembalikannya ke kode semula.
# ---------------------------------------------------------------------------

def label_ekspor_status_kepegawaian(doc) -> str:
    """Label status kepegawaian untuk sel ekspor — round-trip aman.

    ASN/TNI/POLRI → label resmi; non_asn ber-sub-kategori → label sub
    (mis. 'Satpam') agar sub-kategorinya ikut pulih saat impor ulang."""
    d = doc or {}
    kode = str(d.get("status_kepegawaian") or "").strip().lower()
    if kode == "non_asn":
        sub = str(d.get("sub_kategori_non_asn") or "").strip().lower()
        if sub in SUB_KATEGORI_NON_ASN:
            return SUB_KATEGORI_NON_ASN[sub]
        return STATUS_KEPEGAWAIAN["non_asn"]
    return STATUS_KEPEGAWAIAN.get(kode, str(d.get("status_kepegawaian") or ""))


def baris_ekspor_pegawai(doc) -> list:
    """Satu baris ekspor selaras urutan HEADER_IMPOR. MURNI (teruji round-trip
    lewat baris_impor_ke_pegawai)."""
    d = doc or {}

    def g(k):
        return str(d.get(k) or "").strip()

    def label(k, peta):
        """Kode → uraian; nilai kosong tetap kosong (bukan uraian pertama)."""
        return peta.get(g(k).lower(), "")

    _pel = {"plt": "Plt.", "plh": "Plh."}.get(g("jenis_pelaksana").lower(), "")
    return [
        g("nip"), g("nama"), g("gelar_depan"), g("gelar_belakang"),
        g("jenis_kelamin"), g("tempat_lahir"),
        g("tanggal_lahir")[:10],
        label("agama", AGAMA), label("status_perkawinan", STATUS_PERKAWINAN),
        label("kewarganegaraan", KEWARGANEGARAAN),
        label("jenis_identitas_wna", JENIS_IDENTITAS_WNA),
        g("nomor_identitas_wna"),
        label_ekspor_status_kepegawaian(d),
        g("pangkat_golongan"), g("jabatan"),
        label("jenis_jabatan", JENIS_JABATAN),
        _pel, g("jabatan_pelaksana"),
        KATEGORI_PEGAWAI.get(g("kategori_pegawai").lower(),
                             g("kategori_pegawai")),
        g("tmt_jabatan")[:10], g("tanggal_akhir_jabatan")[:10],
        g("eselon1"), g("eselon2"), g("eselon3"), g("eselon4"), g("eselon5"),
        g("eselon"),
        g("unit_kerja"), g("unit_organisasi"),
        g("no_hp"), g("email"), g("npwp"), g("pendidikan_terakhir"),
        g("alamat"), g("nama_bank"), g("no_rekening"),
        g("nomor_kontrak"), g("tgl_mulai_kontrak")[:10],
        g("tgl_selesai_kontrak")[:10],
        JENIS_KONTRAK_NON_ASN.get(g("jenis_kontrak_non_asn").lower(), ""),
        g("perusahaan_penyedia"), g("kode_satker_lengkap"),
        STATUS_PEGAWAI_SATKER.get(g("status_pegawai_satker").lower(), ""),
        g("status_pegawai_instansi"),
        STATUS_PEGAWAI.get(g("status").lower(), g("status") or "Aktif"),
        g("tanggal_meninggal")[:10], g("nomor_akta_kematian"),
        g("penyebab_meninggal"),
        g("ahli_waris_nama"), g("ahli_waris_hubungan"), g("ahli_waris_kontak"),
        g("pemberitahuan_ahli_waris_tanggal")[:10],
        g("pemberitahuan_ahli_waris_nomor"),
        g("keterangan"),
    ]


# Opsi dropdown per header (untuk Data Validation di file ekspor) — semua
# nilai di sini harus dinormalkan balik dengan benar oleh impor.
OPSI_DROPDOWN_EKSPOR = {
    "Jenis Kelamin": ["L", "P"],
    "Jenis Pelaksana (Plt/Plh)": ["Plt.", "Plh."],
    "Status Kepegawaian": (
        [STATUS_KEPEGAWAIAN[k] for k in ("pns", "cpns", "pppk", "tni", "polri")]
        + [STATUS_KEPEGAWAIAN["non_asn"]]
        + list(SUB_KATEGORI_NON_ASN.values())),
    "Kategori Pegawai": list(KATEGORI_PEGAWAI.values()),
    "Jenis Kontrak Non-ASN": ["Internal instansi (PPNPN/SPK)",
                              "Outsourcing (melalui perusahaan penyedia)"],
    "Nama Bank": ["BRI", "BNI", "Mandiri", "BTN", "BSI", "BCA",
                  "CIMB Niaga", "Danamon"],
    "Pendidikan Terakhir": list(PENDIDIKAN),
    "Status Pegawai": list(STATUS_PEGAWAI_SATKER.values()),
    "Status": list(STATUS_PEGAWAI.values()),
    "Agama": list(AGAMA.values()),
    "Status Perkawinan": list(STATUS_PERKAWINAN.values()),
    "Kewarganegaraan": list(KEWARGANEGARAAN.values()),
    "Jenis Identitas WNA": list(JENIS_IDENTITAS_WNA.values()),
    "Jenis Jabatan": list(JENIS_JABATAN.values()),
}

# Kolom yang wajib berformat TEKS di Excel (menghindari artefak float NIP).
# Semua kolom bernomor yang boleh berawalan nol atau melebihi 15 digit —
# tanpa ini Excel mengubahnya jadi float dan angkanya rusak diam-diam.
KOLOM_TEKS_EKSPOR = {"NIP/NIK/NRP", "No Telepon", "NPWP", "No Rekening",
                     "Nomor Kontrak", "Kode Satker Lengkap",
                     "Nomor Identitas WNA", "Ahli Waris - Kontak",
                     "Nomor Akta Kematian", "Nomor Pemberitahuan Ahli Waris"}
