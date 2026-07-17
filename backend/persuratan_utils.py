"""Logika murni PERSURATAN — registrasi & penomoran naskah dinas lintas modul.

Acuan (pustaka §12): Peraturan ANRI No. 5/2021 (Pedoman Umum Tata Naskah
Dinas) — susunan nomor naskah dinas korespondensi eksternal memuat:
(a) kategori klasifikasi keamanan (B/T/R/SR), (b) nomor naskah (urut dalam
satu tahun takwim), (c) kode klasifikasi arsip, (d) bulan, (e) tahun.
Praktik kearsipan: buku agenda KEMBAR (agenda surat keluar & surat masuk
terpisah, nomor urut masing-masing per tahun); nomor yang sudah dipesan
(booking) lalu batal TIDAK didaur ulang — dicatat berstatus batal agar
urutan tetap utuh dan setiap celah nomor dapat dijelaskan.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
import re

# Kategori klasifikasi keamanan naskah dinas (PerANRI 5/2021).
KODE_KEAMANAN = {
    "B": "Biasa",
    "T": "Terbatas",
    "R": "Rahasia",
    "SR": "Sangat Rahasia",
}

# Jenis naskah yang lazim terbit dari modul-modul AMAN (referensi dropdown;
# nilai lain tetap diterima sebagai teks bebas).
JENIS_NASKAH = (
    "Berita Acara", "Laporan", "Surat Pernyataan", "Surat Keputusan",
    "Surat Tugas", "Nota Dinas", "Surat Undangan", "Surat Keterangan",
    "Surat Biasa", "Daftar/Lampiran", "Lainnya",
)

# Modul AMAN asal surat (untuk penyaringan agenda lintas modul).
MODUL_AMAN = (
    "inventarisasi", "persediaan", "pembukuan", "pelaporan", "penggunaan",
    "pengamanan", "pemeliharaan", "penilaian", "perencanaan", "penganggaran",
    "pengadaan", "pemanfaatan", "pemindahtanganan", "pemusnahan",
    "penghapusan", "wasdal", "umum",
)

STATUS_KELUAR = {
    "dibooking": "Dibooking (draf — nomor sudah dipesan)",
    "disahkan": "Disahkan (surat final ditandatangani)",
    "dibatalkan": "Dibatalkan (nomor hangus, tidak didaur ulang)",
}
TRANSISI_KELUAR = {
    "dibooking": {"disahkan", "dibatalkan"},
    "disahkan": set(),      # final — koreksi lewat surat baru/ralat
    "dibatalkan": set(),
}

STATUS_MASUK = {
    "diterima": "Diterima",
    "diproses": "Diproses/disposisi",
    "selesai": "Selesai ditindaklanjuti",
}
TRANSISI_MASUK = {
    "diterima": {"diproses", "selesai"},
    "diproses": {"selesai"},
    "selesai": set(),
}

ROMAWI_BULAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
                "XI", "XII")

# Format nomor bawaan — susunan PerANRI 5/2021 (keamanan-urut/klasifikasi/
# unit/bulan/tahun). Dapat diubah lewat pengaturan persuratan.
FORMAT_NOMOR_DEFAULT = "{kode_keamanan}-{urut}/{kode_klasifikasi}/{kode_unit}/{bulan_romawi}/{tahun}"

_PLACEHOLDER_DIKENAL = {"kode_keamanan", "urut", "kode_klasifikasi",
                        "kode_unit", "bulan", "bulan_romawi", "tahun"}


def _bulan_tahun(tanggal_iso):
    s = str(tanggal_iso or "").strip()[:10]
    m = re.match(r"^(\d{4})-(\d{2})", s)
    if not m:
        return None, None
    tahun, bulan = int(m.group(1)), int(m.group(2))
    if not 1 <= bulan <= 12:
        return None, None
    return bulan, tahun


def placeholder_tak_dikenal(template) -> list:
    """Placeholder {x} pada template yang tidak dikenali (untuk validasi)."""
    return [p for p in re.findall(r"\{(\w+)\}", str(template or ""))
            if p not in _PLACEHOLDER_DIKENAL]


def bangun_nomor(template, urut, tanggal_iso, kode_klasifikasi="",
                 kode_unit="", kode_keamanan="B") -> str:
    """Rakit nomor surat dari template ber-placeholder.

    {urut} tampil 3 digit ber-nol-depan (015) sesuai praktik agenda; bagian
    yang kosong dirapikan (dobel '/' dan '-' tepi dibuang) agar template
    umum tetap menghasilkan nomor sah walau kode unit/klasifikasi belum
    diisi.
    """
    bulan, tahun = _bulan_tahun(tanggal_iso)
    nilai = {
        "kode_keamanan": str(kode_keamanan or "B").strip().upper(),
        "urut": f"{int(urut):03d}",
        "kode_klasifikasi": str(kode_klasifikasi or "").strip(),
        "kode_unit": str(kode_unit or "").strip(),
        "bulan": f"{bulan:02d}" if bulan else "",
        "bulan_romawi": ROMAWI_BULAN[bulan - 1] if bulan else "",
        "tahun": str(tahun) if tahun else "",
    }
    out = str(template or FORMAT_NOMOR_DEFAULT)
    for k, v in nilai.items():
        out = out.replace("{" + k + "}", v)
    out = re.sub(r"/{2,}", "/", out)          # bagian kosong → '//' dirapikan
    out = re.sub(r"^[-/]+|[-/]+$", "", out)   # pemisah menggantung di tepi
    return out


def validate_surat_keluar(d) -> list:
    """Validasi payload booking surat keluar → daftar pesan kesalahan."""
    errors = []
    if not str((d or {}).get("perihal") or "").strip():
        errors.append("Perihal wajib diisi")
    keamanan = str((d or {}).get("kode_keamanan") or "B").strip().upper()
    if keamanan not in KODE_KEAMANAN:
        errors.append(f"Kode keamanan tidak dikenal: {keamanan} (pilih {'/'.join(KODE_KEAMANAN)})")
    modul = str((d or {}).get("modul") or "").strip()
    if modul and modul not in MODUL_AMAN:
        errors.append(f"Modul tidak dikenal: {modul}")
    tgl = str((d or {}).get("tanggal_surat") or "").strip()
    if tgl and _bulan_tahun(tgl) == (None, None):
        errors.append("Tanggal surat tidak valid (YYYY-MM-DD)")
    return errors


def validate_surat_masuk(d) -> list:
    """Validasi payload agenda surat masuk → daftar pesan kesalahan."""
    errors = []
    if not str((d or {}).get("nomor_surat") or "").strip():
        errors.append("Nomor surat (dari pengirim) wajib diisi")
    if not str((d or {}).get("pengirim") or "").strip():
        errors.append("Pengirim wajib diisi")
    if not str((d or {}).get("perihal") or "").strip():
        errors.append("Perihal wajib diisi")
    return errors


def validate_transisi(status_lama, status_baru, jenis) -> str:
    """'' bila transisi sah; selain itu pesan kesalahan."""
    peta = TRANSISI_KELUAR if jenis == "keluar" else TRANSISI_MASUK
    if status_baru not in peta.get(status_lama, set()):
        return (f"Transisi '{status_lama}' → '{status_baru}' tidak diizinkan "
                f"untuk surat {jenis}")
    return ""


def baris_agenda_csv(items) -> list:
    """Baris buku agenda (list of list) untuk ekspor CSV — kolom praktik
    buku agenda kembar."""
    rows = [["No Agenda", "Jenis", "Status", "Nomor Surat", "Tanggal Surat",
             "Perihal", "Dari/Kepada", "Jenis Naskah", "Modul", "Kegiatan",
             "Kode Klasifikasi", "Disahkan/Diterima Pada", "Keterangan"]]
    for s in items or []:
        keluar = s.get("jenis") == "keluar"
        rows.append([
            s.get("no_agenda"),
            "Keluar" if keluar else "Masuk",
            (STATUS_KELUAR if keluar else STATUS_MASUK).get(
                s.get("status"), s.get("status")),
            s.get("nomor"),
            s.get("tanggal_surat"),
            s.get("perihal"),
            s.get("tujuan") if keluar else s.get("pengirim"),
            s.get("jenis_naskah"),
            s.get("modul"),
            s.get("nama_kegiatan") or "",
            s.get("kode_klasifikasi") or "",
            (s.get("disahkan_pada") if keluar else s.get("created_at") or "")[:10]
            if (s.get("disahkan_pada") or (not keluar and s.get("created_at"))) else "",
            s.get("keterangan") or (s.get("alasan_batal") or ""),
        ])
    return rows
