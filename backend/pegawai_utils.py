"""Master Pegawai (data kepegawaian menyeluruh satker) — LOGIKA MURNI.

BERBEDA dari Referensi Pejabat (`pejabat_utils.py`, khusus pejabat
penatausahaan/penanda tangan dokumen): master ini menampung **SELURUH pegawai**
satker beserta **unit kerjanya masing-masing**, mengadopsi kelengkapan data
SIMAN Modul Pegawai (SIMAN-G) / SIMPEG. Dipakai sebagai rujukan lintas modul
(mis. pemegang barang, penanggung jawab ruangan, distribusi DBR/KIR). Semua
field selain `nama` bersifat opsional. Modul murni ini teruji unit.
"""
import re

from pejabat_utils import STATUS_KEPEGAWAIAN  # klasifikasi kepegawaian bersama

# Jenis kelamin (kode → uraian).
JENIS_KELAMIN = {"L": "Laki-laki", "P": "Perempuan"}

# Jenis jabatan (adopsi klasifikasi ASN) — kode → uraian.
JENIS_JABATAN = {
    "struktural": "Struktural",
    "fungsional": "Fungsional (JF)",
    "pelaksana": "Pelaksana",
}

# Status keberadaan pegawai di satker (kode → uraian).
STATUS_PEGAWAI = {
    "aktif": "Aktif",
    "cuti": "Cuti",
    "tugas_belajar": "Tugas Belajar",
    "diperbantukan": "Diperbantukan/DPB",
    "mutasi": "Mutasi/Pindah",
    "pensiun": "Pensiun",
    "keluar": "Keluar/Berhenti",
    "nonaktif": "Nonaktif",
}

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

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TGL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
    st = str(d.get("status") or "").strip()
    if st and st not in STATUS_PEGAWAI:
        errors.append(f"Status pegawai tidak dikenal: {st}")
    email = str(d.get("email") or "").strip()
    if email and not _EMAIL_RE.match(email):
        errors.append("Format email tidak valid")
    tgl = str(d.get("tanggal_lahir") or "").strip()
    if tgl and not _TGL_RE.match(tgl):
        errors.append("Tanggal lahir harus format YYYY-MM-DD")
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
    "keterangan": "keterangan",
}

# Urutan kolom template ekspor/impor (header ramah).
HEADER_IMPOR = [
    "NIP/NIK/NRP", "Nama Lengkap", "Jenis Kelamin", "Tempat Lahir", "Tgl Lahir",
    "Status Kepegawaian", "Pangkat/Golongan", "Jabatan", "Kategori Pegawai",
    "Eselon 1", "Eselon 2", "Eselon 3", "Eselon 4", "Eselon 5",
    "No Telepon", "Email", "Nama Bank", "No Rekening",
    "Nomor Kontrak", "Tgl Mulai Kontrak", "Tgl Selesai Kontrak",
    "Status", "Keterangan",
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
    if "meninggal" in s or "wafat" in s:
        return "nonaktif"
    return "aktif"


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


def baris_impor_ke_pegawai(raw):
    """Ubah satu baris impor (dict {header: nilai}) → dokumen pegawai bersih +
    daftar peringatan lunak. MURNI (teruji unit).

    Kembalikan (doc, peringatan[]). `doc` kosong (nama="") berarti baris tak
    dapat dipakai (dilewati pemanggil)."""
    peringatan = []
    doc = {k: "" for k in (
        "nama", "nip", "jenis_kelamin", "tempat_lahir", "tanggal_lahir",
        "status_kepegawaian", "pangkat_golongan", "jabatan", "kategori_pegawai",
        "eselon1", "eselon2", "eselon3", "eselon4", "eselon5",
        "no_hp", "email", "nama_bank", "no_rekening", "nomor_kontrak",
        "tgl_mulai_kontrak", "tgl_selesai_kontrak", "keterangan",
        "sub_kategori_non_asn", "unit_kerja")}
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
        elif field in ("tanggal_lahir", "tgl_mulai_kontrak", "tgl_selesai_kontrak"):
            doc[field] = _norm_tgl(val)
        elif field == "status_kepegawaian":
            kode, sub = normalisasi_status_kepegawaian(val)
            doc["status_kepegawaian"] = kode
            if sub:
                doc["sub_kategori_non_asn"] = sub
        elif field == "status":
            doc["status"] = normalisasi_status_pegawai(val)
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
