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
    "nonaktif": "Nonaktif",
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
