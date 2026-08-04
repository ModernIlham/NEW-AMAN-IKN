"""Logika murni PERSURATAN — registrasi & penomoran naskah dinas lintas modul.

Acuan (pustaka §12): Peraturan ANRI No. 5/2021 (Pedoman Umum Tata Naskah
Dinas) — susunan nomor naskah dinas korespondensi eksternal memuat:
(a) kategori klasifikasi keamanan (B/T/R/SR), (b) nomor naskah (urut dalam
satu tahun takwim), (c) kode klasifikasi arsip, (d) bulan, (e) tahun.
Praktik kearsipan: buku agenda KEMBAR (agenda surat keluar & surat masuk
terpisah, nomor urut masing-masing per periode); nomor yang sudah dipesan
(booking) lalu batal TIDAK didaur ulang — dicatat berstatus batal agar
urutan tetap utuh dan setiap celah nomor dapat dijelaskan.

Dua kelonggaran praktik lapangan (permintaan pemilik):
- **Reset bulanan** — deret nomor urut kembali ke 001 tiap pergantian bulan
  (setelan per satker; pilihan tahunan tetap tersedia sesuai PerANRI).
- **Nomor sisipan (backdate)** — surat yang lupa dibooking dan baru dibuat
  belakangan diberi nomor menempel di belakang nomor terakhir pada tanggal
  itu: 005 → 005.01 (lalu 005.02, dst.) sehingga urutan agenda tetap
  kronologis tanpa menomori ulang arsip.

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

# Pola reset nomor urut agenda (setelan per satker).
RESET_URUT = {
    "bulanan": "Bulanan — nomor kembali ke 001 tiap awal bulan",
    "tahunan": "Tahunan — deret satu tahun takwim (PerANRI 5/2021)",
}
RESET_URUT_DEFAULT = "bulanan"

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


def periode_urut(reset_urut, tanggal_iso) -> str:
    """Kunci periode deret nomor: '2026' (tahunan) / '2026-08' (bulanan).

    Nilai reset selain "tahunan" jatuh ke bulanan (bawaan baru). Tanggal yang
    tak terbaca → '' — fungsi murni tak tahu "sekarang", jadi salah pakai
    harus TERLIHAT, bukan diam-diam menomori periode yang keliru (route
    selalu mengisi tanggal default hari ini sebelum memanggil).
    """
    bulan, tahun = _bulan_tahun(tanggal_iso)
    if tahun is None:
        return ""
    if str(reset_urut or "").strip() == "tahunan":
        return str(tahun)
    return f"{tahun}-{bulan:02d}"


def urut_tampil(no_agenda, sisipan=0) -> str:
    """Tampilan nomor urut agenda: 15 → '015'; sisipan 1 → '015.01'."""
    dasar = f"{int(no_agenda or 0):03d}"
    try:
        s = int(sisipan or 0)
    except (TypeError, ValueError):
        s = 0
    return f"{dasar}.{s:02d}" if s > 0 else dasar


def validate_format_reset(reset_urut, format_nomor) -> str:
    """'' bila serasi; pesan bila reset bulanan tanpa unsur bulan di format.

    Tanpa {bulan}/{bulan_romawi} pada format, deret bulanan menerbitkan
    nomor yang SAMA PERSIS tiap bulan (B-001/UN/2026 terbit lagi bulan
    berikutnya) — duplikat nomor resmi yang tak bisa diperbaiki belakangan.
    """
    if str(reset_urut or "").strip() == "tahunan":
        return ""
    f = str(format_nomor or FORMAT_NOMOR_DEFAULT)
    if "{bulan}" in f or "{bulan_romawi}" in f:
        return ""
    return ("Reset bulanan membutuhkan {bulan} atau {bulan_romawi} pada "
            "format nomor — tanpa itu nomor yang sama terbit ulang tiap bulan")


def bangun_nomor(template, urut, tanggal_iso, kode_klasifikasi="",
                 kode_unit="", kode_keamanan="B") -> str:
    """Rakit nomor surat dari template ber-placeholder.

    {urut} tampil 3 digit ber-nol-depan (015) sesuai praktik agenda; `urut`
    berupa STRING dipakai apa adanya — jalur nomor sisipan mengirim "005.01"
    yang sudah dirakit `urut_tampil`. Bagian yang kosong dirapikan (dobel '/'
    dan '-' tepi dibuang) agar template umum tetap menghasilkan nomor sah
    walau kode unit/klasifikasi belum diisi.
    """
    bulan, tahun = _bulan_tahun(tanggal_iso)
    nilai = {
        "kode_keamanan": str(kode_keamanan or "B").strip().upper(),
        "urut": urut if isinstance(urut, str) else f"{int(urut):03d}",
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


def validate_surat_keluar(d, today_iso="") -> list:
    """Validasi payload booking surat keluar → daftar pesan kesalahan.

    `today_iso` (opsional, YYYY-MM-DD): mengaktifkan aturan nomor sisipan —
    sisipan WAJIB bertanggal (itulah tanggal backdate-nya) dan tanggalnya
    tak boleh di masa depan (sisipan ada justru untuk surat yang telat
    dibooking, bukan untuk memesan masa depan).
    """
    errors = []
    if not str((d or {}).get("perihal") or "").strip():
        errors.append("Perihal wajib diisi")
    keamanan = str((d or {}).get("kode_keamanan") or "B").strip().upper()
    if keamanan not in KODE_KEAMANAN:
        errors.append(f"Kode keamanan tidak dikenal: {keamanan} (pilih {'/'.join(KODE_KEAMANAN)})")
    modul = str((d or {}).get("modul") or "").strip()
    if modul and modul not in MODUL_AMAN:
        errors.append(f"Modul tidak dikenal: {modul}")
    tgl = str((d or {}).get("tanggal_surat") or "").strip()[:10]
    if tgl and _bulan_tahun(tgl) == (None, None):
        errors.append("Tanggal surat tidak valid (YYYY-MM-DD)")
    if (d or {}).get("sisipan"):
        if not tgl:
            errors.append("Nomor sisipan membutuhkan Tanggal Surat "
                          "(tanggal backdate surat yang lupa dibooking)")
        elif today_iso and tgl > str(today_iso)[:10]:
            errors.append("Tanggal nomor sisipan tidak boleh di masa depan")
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
    rows = [["No Agenda", "Jenis", "Status", "Keberlakuan", "Nomor Surat",
             "Nomor Eksternal", "Tanggal Surat", "Perihal", "Dari/Kepada",
             "Jenis Naskah", "Modul", "Kegiatan", "Kode Klasifikasi",
             "Disahkan/Diterima Pada", "Keterangan"]]
    for s in items or []:
        keluar = s.get("jenis") == "keluar"
        rows.append([
            # Nomor sisipan tampil "5.01" agar buku agenda ekspor tetap
            # kronologis; baris biasa memakai angka mentahnya (tak berubah).
            (urut_tampil(s.get("no_agenda"), s.get("sisipan"))
             if s.get("sisipan") else s.get("no_agenda")),
            "Keluar" if keluar else "Masuk",
            (STATUS_KELUAR if keluar else STATUS_MASUK).get(
                s.get("status"), s.get("status")),
            # Diisi pemanggil (stempel keberlakuan terhitung); item tanpa
            # stempel — pemanggil lama / uji murni — tampil kosong, bukan
            # mengarang "Berlaku".
            s.get("keberlakuan_label") or "",
            s.get("nomor"),
            s.get("nomor_eksternal") or "",
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


def pilih_klasifikasi(peta, modul, jenis_naskah, eksplisit="", default="") -> str:
    """Kode klasifikasi arsip untuk sebuah surat — otomatis dari pemetaan.

    Prioritas: (1) kode yang DIISI EKSPLISIT oleh pengguna; (2) aturan
    pemetaan paling SPESIFIK yang cocok — modul+jenis (skor 2) > salah
    satunya (skor 1); aturan dengan field kosong = wildcard; seri pertama
    menang saat skor sama; (3) kode klasifikasi bawaan pengaturan. MURNI.

    peta: list {modul, jenis_naskah, kode} dari pengaturan persuratan.
    """
    eksplisit = str(eksplisit or "").strip()
    if eksplisit:
        return eksplisit
    modul = str(modul or "").strip()
    jenis = str(jenis_naskah or "").strip().casefold()
    terbaik, skor_terbaik = "", -1
    for aturan in peta or []:
        a_modul = str(aturan.get("modul") or "").strip()
        a_jenis = str(aturan.get("jenis_naskah") or "").strip().casefold()
        kode = str(aturan.get("kode") or "").strip()
        if not kode:
            continue
        if a_modul and a_modul != modul:
            continue
        if a_jenis and a_jenis != jenis:
            continue
        skor = (1 if a_modul else 0) + (1 if a_jenis else 0)
        if skor > skor_terbaik:
            terbaik, skor_terbaik = kode, skor
    return terbaik or str(default or "").strip()


def validate_peta_klasifikasi(peta) -> list:
    """Validasi aturan pemetaan klasifikasi → daftar pesan kesalahan."""
    errors = []
    for i, aturan in enumerate(peta or [], 1):
        if not str((aturan or {}).get("kode") or "").strip():
            errors.append(f"Aturan #{i}: kode klasifikasi wajib diisi")
        modul = str((aturan or {}).get("modul") or "").strip()
        if modul and modul not in MODUL_AMAN:
            errors.append(f"Aturan #{i}: modul tidak dikenal: {modul}")
        if not modul and not str((aturan or {}).get("jenis_naskah") or "").strip():
            errors.append(f"Aturan #{i}: isi minimal modul atau jenis naskah "
                          "(keduanya kosong = aturan tak pernah spesifik)")
    return errors


# ── Scoping per-satker: master klasifikasi & asal-usul pengaturan ────────────

# Field pengaturan penomoran yang ikut resolusi overlay satker → global.
FIELD_PENGATURAN = ("format_nomor", "kode_unit", "kode_klasifikasi_default",
                    "peta_klasifikasi", "reset_urut")


def _terisi(v) -> bool:
    """Nilai yang dianggap MENGISI pada overlay ('' / None / [] = kosong)."""
    return v not in ("", None, [])


def sumber_pengaturan(dok_global, dok_satker) -> dict:
    """Peta field → asal nilai efektifnya: 'satker' | 'global' | 'bawaan'.

    Dipakai UI pengaturan untuk menunjukkan field mana yang khusus satker ini
    dan mana yang warisan Universal — tanpa ini admin satker tak bisa
    membedakan "kode unit saya OIKN" dari "kode unit semua orang OIKN".
    """
    g, s = dict(dok_global or {}), dict(dok_satker or {})
    out = {}
    for f in FIELD_PENGATURAN:
        out[f] = ("satker" if _terisi(s.get(f))
                  else "global" if _terisi(g.get(f)) else "bawaan")
    return out


def gabung_klasifikasi(milik_bersama, milik_satker) -> list:
    """Master klasifikasi EFEKTIF satu satker: entri satker menimpa entri
    Bersama yang berkode sama; sisanya digabung, terurut kode.

    Pola yang sama dengan overlay pengaturan (`_pengaturan`) — satker cukup
    menambah/menimpa kode yang berbeda, sisanya mewarisi daftar Bersama.
    """
    peta = {}
    for k in (milik_bersama or []):
        kode = str((k or {}).get("kode") or "").strip()
        if kode:
            peta[kode] = k
    for k in (milik_satker or []):
        kode = str((k or {}).get("kode") or "").strip()
        if kode:
            peta[kode] = k          # entri satker menang
    return sorted(peta.values(), key=lambda k: str(k.get("kode") or ""))
