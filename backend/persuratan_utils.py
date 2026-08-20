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

# Sifat urgensi naskah dinas — SUMBU TERSENDIRI, bukan bagian kode keamanan.
#
# Keduanya sering tertukar karena sama-sama "sifat surat", padahal menjawab
# pertanyaan berbeda: kode keamanan menjawab SIAPA BOLEH MEMBACA (Biasa/
# Terbatas/Rahasia/Sangat Rahasia), sifat urgensi menjawab SEBERAPA CEPAT
# HARUS DITINDAKLANJUTI. Satu surat bisa Biasa sekaligus Sangat Segera, dan
# menggabungkannya jadi satu daftar memaksa operator memilih salah satu.
SIFAT_URGENSI = {
    "biasa": "Biasa",
    "segera": "Segera",
    "sangat_segera": "Sangat Segera",
}
SIFAT_URGENSI_DEFAULT = "biasa"

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

# Placeholder format nomor, BESERTA nama manusianya dan contoh isinya.
#
# Keluhan pemilik: "pada format nomor kita tidak tahu nama header kepalanya
# untuk memanggil datanya". Memang: kolomnya menerima template mentah, dan
# daftar placeholder-nya hanya tertulis sebagai deretan `{...}` di keterangan
# dialog — tak ada yang menyebutkan apa artinya atau apa isinya nanti.
#
# Daftar ini dikirim ke layar supaya tiap placeholder bisa disisipkan dengan
# satu ketukan, lengkap dengan artinya. Urutannya = susunan PerANRI 5/2021,
# jadi menyisipkannya berurutan menghasilkan nomor yang sudah benar bentuknya.
PLACEHOLDER_NOMOR = [
    {"kunci": "kode_keamanan", "label": "Kode Keamanan", "contoh": "B",
     "arti": "Biasa/Terbatas/Rahasia/Sangat Rahasia — dipilih saat membooking"},
    {"kunci": "urut", "label": "Nomor Urut", "contoh": "001",
     "arti": "Nomor agenda berjalan, otomatis dari buku agenda"},
    {"kunci": "kode_klasifikasi", "label": "Kode Klasifikasi Arsip",
     "contoh": "PL.02",
     "arti": "Dari aturan otomatis atau kode bawaan; bisa diisi manual"},
    {"kunci": "kode_unit", "label": "Kode Unit", "contoh": "OIKN",
     "arti": "Kode unit kerja penerbit — diisi di pengaturan ini"},
    {"kunci": "bulan", "label": "Bulan (angka)", "contoh": "08",
     "arti": "Dua digit dari tanggal surat"},
    {"kunci": "bulan_romawi", "label": "Bulan (Romawi)", "contoh": "VIII",
     "arti": "Lazim pada naskah dinas; dari tanggal surat"},
    {"kunci": "tahun", "label": "Tahun", "contoh": "2026",
     "arti": "Empat digit dari tanggal surat"},
    # DI LUAR deret PerANRI, dan itu disengaja. Menyisipkan seluruh chip
    # berurutan harus langsung menghasilkan bentuk nomor yang benar; slot ini
    # bukan bagian dari bentuk itu, ia tambahan yang dipasang bila memang
    # diinginkan. Menaruhnya di tengah deret akan menyelipkan kode bawaan ke
    # dalam nomor setiap orang yang memakai chip berurutan — persis kekacauan
    # yang sedang dibereskan.
    {"kunci": "kode_bawaan", "label": "Kode Klasifikasi Bawaan",
     "contoh": "UM.01",
     "arti": "Kode tetap milik satker — BERDIRI SENDIRI; tidak mengisi dan "
             "tidak digantikan oleh Kode Klasifikasi Arsip"},
]

# Diturunkan dari daftar di atas, bukan ditulis ulang. Dulu keduanya berdiri
# sendiri, dan itu satu drift menunggu terjadi: placeholder baru yang lupa
# didaftarkan di sini akan disisipkan layar dengan satu ketukan lalu DITOLAK
# validator sebagai "placeholder tak dikenal" — layar dan validator saling
# membantah, dan yang salah bukan penggunanya.
_PLACEHOLDER_DIKENAL = {p["kunci"] for p in PLACEHOLDER_NOMOR}

# Komposisi nomor yang lazim diminta di lapangan. Ini BUKAN konsep baru yang
# disimpan tersendiri — ia hanya cara ramah membaca & menulis dua placeholder
# pada `format_nomor`, yang tetap menjadi satu-satunya sumber kebenaran.
# Tanpa ini, memakai kode klasifikasi berarti mengetik template ber-placeholder
# dengan benar; dan salah ketik satu kurung membuat kodenya diam-diam tak
# pernah muncul di nomor mana pun.
KOMPOSISI_NOMOR = {
    "keamanan_klasifikasi": "Kode keamanan di depan + klasifikasi setelah nomor",
    "klasifikasi_depan": "Kode klasifikasi arsip DI DEPAN (menggantikan kode keamanan)",
    "keamanan_saja": "Kode keamanan saja, tanpa klasifikasi",
    "klasifikasi_saja": "Klasifikasi setelah nomor, tanpa kode keamanan",
    "tanpa": "Tanpa keamanan maupun klasifikasi",
}

# Contoh hasil tiap komposisi — dipakai layar supaya pilihannya terbaca dari
# BENTUKNYA, bukan dari namanya. Nama pilihan selalu kalah jelas dibanding
# melihat "PL.02-001/OIKN/VIII/2026" langsung.
CONTOH_KOMPOSISI = {
    "keamanan_klasifikasi": "B-001/PL.02/OIKN/VIII/2026",
    "klasifikasi_depan": "PL.02-001/OIKN/VIII/2026",
    "keamanan_saja": "B-001/OIKN/VIII/2026",
    "klasifikasi_saja": "001/PL.02/OIKN/VIII/2026",
    "tanpa": "001/OIKN/VIII/2026",
}


# Unsur tulisan milik satker sendiri — potongan teks tetap yang sering muncul
# di nomor surat (mis. "SETJEN", "UND", "/B/"). Disimpan supaya bentuk
# penulisannya konsisten: sekali ditetapkan, ia disisipkan dengan satu ketukan
# alih-alih diketik ulang — dan salah ketik satu huruf pada satu surat tidak
# lagi mungkin.
MAKS_UNSUR_KUSTOM = 20
MAKS_PANJANG_UNSUR = 24


def bersihkan_unsur_kustom(daftar) -> list:
    """Normalkan daftar unsur: dipangkas, tanpa kosong, tanpa kembar, urutan
    dipertahankan."""
    keluar, terlihat = [], set()
    for x in daftar or []:
        t = str(x if x is not None else "").strip()
        if t and t not in terlihat:
            terlihat.add(t)
            keluar.append(t)
    return keluar


def validate_unsur_kustom(daftar) -> list:
    """Daftar pesan kesalahan untuk unsur tulisan kustom.

    Kurung kurawal DITOLAK, dan itu bukan kerewelan: `{...}` adalah bahasa
    placeholder. Unsur bernama `{apa saja}` akan lolos ke `format_nomor` lalu
    ditolak validator placeholder dengan pesan yang menunjuk ke tempat yang
    SALAH — pengguna diberi tahu formatnya rusak, padahal yang perlu diperbaiki
    daftar unsurnya.
    """
    bersih = bersihkan_unsur_kustom(daftar)
    errors = []
    if len(bersih) > MAKS_UNSUR_KUSTOM:
        errors.append(f"Unsur tulisan maksimal {MAKS_UNSUR_KUSTOM}; "
                      f"terkirim {len(bersih)}")
    for u in bersih:
        if "{" in u or "}" in u:
            errors.append(f"Unsur '{u}' memuat kurung kurawal — itu penanda "
                          "placeholder, bukan tulisan biasa")
        if len(u) > MAKS_PANJANG_UNSUR:
            errors.append(f"Unsur '{u[:12]}…' terlalu panjang "
                          f"(maksimal {MAKS_PANJANG_UNSUR} karakter)")
    return errors


def _rapikan_pemisah(teks) -> str:
    """Buang pemisah kembar & pemisah menggantung di tepi."""
    out = re.sub(r"/{2,}", "/", str(teks or ""))
    out = re.sub(r"-{2,}", "-", out)
    out = re.sub(r"-/", "/", out)
    return re.sub(r"^[-/]+|[-/]+$", "", out)


def komposisi_format(template) -> str:
    """Komposisi yang SEDANG berlaku, dibaca dari template.

    Dua hal dibedakan, sesuai maksud pemilik: apakah kode klasifikasi arsip
    IKUT, dan apakah ia menempati POSISI DEPAN — tempat yang biasanya diisi
    kode keamanan. Posisi depan berarti berada sebelum {urut}.
    """
    f = str(template or "")
    ada_keamanan = "{kode_keamanan}" in f
    ada_klas = "{kode_klasifikasi}" in f
    if ada_keamanan and ada_klas:
        return "keamanan_klasifikasi"
    if ada_keamanan:
        return "keamanan_saja"
    if ada_klas:
        i_klas, i_urut = f.find("{kode_klasifikasi}"), f.find("{urut}")
        if i_urut < 0 or i_klas < i_urut:
            return "klasifikasi_depan"
        return "klasifikasi_saja"
    return "tanpa"


def terapkan_komposisi(template, komposisi) -> str:
    """Template dengan penempatan keamanan/klasifikasi disesuaikan pilihan.

    Bagian lain template TIDAK disentuh — kode unit, bulan, tahun, pemisah, dan
    unsur tulisan tetap milik satker apa adanya. Yang diatur hanya dua hal yang
    memang ditanyakan pemilik: apakah kode klasifikasi arsip ikut, dan apakah
    ia menempati POSISI DEPAN menggantikan kode keamanan.

    Template tanpa `{urut}` dikembalikan apa adanya: ia tak sah dan sudah
    ditolak validasi route — menyisipkan sesuatu ke dalamnya hanya akan
    menyamarkan kesalahan yang seharusnya terlihat.
    """
    f = str(template or FORMAT_NOMOR_DEFAULT)
    pilih = str(komposisi or "").strip()
    if pilih not in KOMPOSISI_NOMOR or "{urut}" not in f:
        return f

    # Bersihkan dulu keduanya, lalu pasang menurut pilihan. Membersihkan lebih
    # dulu membuat perpindahan posisi (mis. klasifikasi dari belakang ke depan)
    # tak meninggalkan salinan di tempat lamanya.
    f = f.replace("{kode_keamanan}", "").replace("{kode_klasifikasi}", "")
    f = _rapikan_pemisah(f)

    if pilih == "keamanan_klasifikasi":
        f = f.replace("{urut}", "{kode_keamanan}-{urut}/{kode_klasifikasi}", 1)
    elif pilih == "klasifikasi_depan":
        f = f.replace("{urut}", "{kode_klasifikasi}-{urut}", 1)
    elif pilih == "keamanan_saja":
        f = f.replace("{urut}", "{kode_keamanan}-{urut}", 1)
    elif pilih == "klasifikasi_saja":
        f = f.replace("{urut}", "{urut}/{kode_klasifikasi}", 1)
    return _rapikan_pemisah(f)


def peringatan_klasifikasi(format_nomor, kode_bawaan, peta) -> str:
    """'' bila aman; pesan bila nomor MEMINTA slot yang tak akan pernah terisi.

    Dua slot, dua sebab, dan sejak keduanya dipisah keduanya harus diperiksa
    SENDIRI-SENDIRI:

    - `{kode_klasifikasi}` tanpa satu pun aturan pemetaan. Inilah keadaan yang
      membuat kode klasifikasi tampak "tidak berpengaruh": template memintanya,
      katalog kodenya sudah diisi, tetapi tak satu pun aturan menunjuk salah
      satunya — nomor terbit tanpa kode itu, tanpa satu pun galat. Kode bawaan
      TIDAK lagi meredam peringatan ini; ia bukan lagi jaring pengaman slot
      ini, jadi meredamnya berarti berbohong.
    - `{kode_bawaan}` sementara kode bawaannya sendiri kosong.
    """
    f = str(format_nomor or "")
    pesan = []
    if "{kode_klasifikasi}" in f and not any(
            str((a or {}).get("kode") or "").strip() for a in peta or []):
        pesan.append(
            "Format nomor memuat {kode_klasifikasi}, tetapi belum ada aturan "
            "otomatis satu pun — nomor akan terbit TANPA kode klasifikasi "
            "kecuali diisi manual tiap kali membooking")
    if "{kode_bawaan}" in f and not str(kode_bawaan or "").strip():
        pesan.append(
            "Format nomor memuat {kode_bawaan}, tetapi Kode Klasifikasi "
            "Bawaan masih kosong — slot itu akan terbit kosong")
    return " · ".join(pesan)


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


def dimensi_deret(komposisi, deret_per_kode) -> str:
    """Sumbu pemisah deret nomor: '' (satu deret) / 'keamanan' / 'klasifikasi'.

    Deret terpisah HANYA sah bila kode pembedanya benar-benar tercetak pada
    nomor. Kalau tidak, dua surat berbeda bisa memikul nomor yang sama persis
    — dan nomor surat resmi yang kembar tak bisa diperbaiki belakangan.

    Karena itu:
    - komposisi "keamanan"    → deret per kode keamanan (B/T/R/SR);
    - komposisi "klasifikasi" → deret per kode klasifikasi arsip;
    - komposisi "keduanya"    → MATI (permintaan pemilik: kembali ke bawaan);
    - komposisi "tanpa"       → MATI, dan ini keharusan, bukan pilihan: tak ada
      kode apa pun di nomor, jadi tak ada yang membedakan 001 milik B dari 001
      milik T.
    """
    if not deret_per_kode:
        return ""
    k = str(komposisi or "").strip()
    if k == "keamanan_saja":
        return "keamanan"
    if k in ("klasifikasi_depan", "klasifikasi_saja"):
        return "klasifikasi"
    # "keamanan_klasifikasi" (dua kode) dan "tanpa" (tanpa kode) sama-sama MATI.
    return ""


def kunci_deret(dimensi, kode_keamanan="", kode_klasifikasi="") -> str:
    """Nilai kode yang memisahkan deret ('' = ikut deret tunggal).

    Klasifikasi kosong sengaja jatuh ke deret tunggal: memisahkan deret
    berdasarkan kode yang tak ada sama saja dengan tidak memisahkan, dan
    membuat kunci counter bernama '' hanya menyamarkan itu.
    """
    if dimensi == "keamanan":
        return str(kode_keamanan or "B").strip().upper()
    if dimensi == "klasifikasi":
        return str(kode_klasifikasi or "").strip()
    return ""


def periode_surat(s, reset_urut) -> str:
    """Kunci periode agenda SATU surat — '2026-08' (bulanan) / '2026' (tahunan).

    Tanggal acuannya berbeda menurut jenis, dan itu bukan kelalaian: nomor
    agenda surat KELUAR dipesan menurut `tanggal_surat` (boleh backdate),
    sedangkan surat MASUK dicatat menurut tanggal AGENDA kita — tanggal surat
    pengirim bukan tanggal pencatatan kita. Fungsi ini harus memakai tanggal
    yang sama dengan yang dipakai saat nomornya diterbitkan, kalau tidak
    urutan agenda akan menyimpang dari nomor yang sudah tercetak.

    Jatuh ke `tahun` tersimpan bila tanggalnya tak terbaca — supaya baris lama
    tetap punya tempat dalam urutan, bukan terlempar ke ujung daftar.
    """
    d = s or {}
    tgl = d.get("tanggal_surat") if d.get("jenis") == "keluar" else d.get("created_at")
    hasil = periode_urut(reset_urut, str(tgl or "")[:10])
    if hasil:
        return hasil
    tahun = d.get("tahun")
    return str(tahun) if tahun else ""


def label_agenda(s, reset_urut, dimensi="") -> str:
    """Lencana buku agenda: 'K-005/2026' (tahunan) · 'K-005/VIII/2026' (bulanan).

    Bulan WAJIB tampil pada deret bulanan. Tanpa itu nomor agenda bulan Juli
    dan bulan Agustus sama-sama tampil 'K-001/2026' — dua baris berlencana
    identik di satu layar, dan buku agenda kehilangan sifat yang paling
    mendasar: satu nomor menunjuk satu surat.

    `dimensi` (lihat `dimensi_deret`) menambahkan kode pembeda saat deret
    dipisah per kode: 'K-B-001/VIII/2026'. Itu bukan hiasan — dengan deret
    terpisah, 001 milik B dan 001 milik T memang ada bersamaan dalam satu
    bulan, dan lencana tanpa kode akan mengulang persis keambiguan yang baru
    saja ditutup. Bentuknya mencerminkan nomor suratnya sendiri (B-001/…),
    supaya keduanya terbaca sebagai hal yang sama.
    """
    d = s or {}
    awalan = "K" if d.get("jenis") == "keluar" else "M"
    urut = urut_tampil(d.get("no_agenda"), d.get("sisipan"))
    kode = kunci_deret(dimensi, d.get("kode_keamanan"), d.get("kode_klasifikasi"))
    if kode:
        awalan = f"{awalan}-{kode}"
    p = periode_surat(d, reset_urut)
    if "-" in p:
        bulan = int(p[5:7])
        return f"{awalan}-{urut}/{ROMAWI_BULAN[bulan - 1]}/{p[:4]}"
    return f"{awalan}-{urut}/{p}" if p else f"{awalan}-{urut}"


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
                 kode_unit="", kode_keamanan="B", kode_bawaan="") -> str:
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
        # SLOT TERSENDIRI. Kode bawaan tidak lagi menyelinap ke slot
        # klasifikasi arsip: yang ingin memakainya menuliskan {kode_bawaan}
        # pada formatnya, dan itu keputusan yang terlihat.
        "kode_bawaan": str(kode_bawaan or "").strip(),
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


# Nomor yang DITULIS TANGAN operator pada kotak "Perkiraan nomor yang akan
# terbit". Permintaan pemilik: *"setiap contoh booking perkiraan nomornya bisa
# diedit dan di tambahkan unsur baru sesuai keinginan… ibaratnya menulis nomer
# manual"*.
#
# Batasnya sengaja sedikit. Nomor naskah dinas punya bentuk yang berbeda-beda
# antarinstansi, dan menolak bentuk yang tak kita duga sama saja mengembalikan
# kekakuan yang justru sedang dilepas. Yang ditolak hanya dua hal yang
# benar-benar merusak:
#
#   - kurung kurawal: `{...}` adalah bahasa placeholder. Nomor bertuliskan
#     `{urut}` akan terbit apa adanya ke surat resmi, dan pembacanya melihat
#     kode program di kepala surat.
#   - panjang tak wajar: nomor bukan tempat menulis kalimat, dan kolom nomor di
#     daftar, ekspor, serta kop surat punya ruang terbatas.
MAKS_PANJANG_NOMOR = 120


def bersihkan_nomor_manual(teks) -> str:
    """Rapikan nomor tulisan tangan: spasi tepi dibuang, spasi/baris baru
    beruntun diratakan jadi satu spasi.

    Baris baru dibuang bukan demi kerapian: nomor bermuatan '\n' akan
    memecah baris di kop surat, CSV, dan judul PDF — tiga tempat yang
    kerusakannya baru terlihat setelah dokumennya jadi.
    """
    return re.sub(r"\s+", " ", str(teks or "")).strip()


def validate_nomor_manual(teks) -> list:
    """Daftar pesan kesalahan untuk nomor tulisan tangan. Kosong = tak
    disunting, dan itu bukan kesalahan."""
    n = bersihkan_nomor_manual(teks)
    if not n:
        return []
    errors = []
    if len(n) > MAKS_PANJANG_NOMOR:
        errors.append(f"Nomor surat maksimal {MAKS_PANJANG_NOMOR} karakter; "
                      f"terkirim {len(n)}")
    if "{" in n or "}" in n:
        errors.append("Nomor memuat kurung kurawal — itu penanda placeholder, "
                      "bukan tulisan yang akan terbaca di kepala surat")
    return errors


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
    urgensi = str((d or {}).get("sifat_urgensi") or SIFAT_URGENSI_DEFAULT).strip()
    if urgensi not in SIFAT_URGENSI:
        errors.append(f"Sifat urgensi tidak dikenal: {urgensi} "
                      f"(pilih {'/'.join(SIFAT_URGENSI)})")
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
    urgensi = str((d or {}).get("sifat_urgensi") or SIFAT_URGENSI_DEFAULT).strip()
    if urgensi not in SIFAT_URGENSI:
        errors.append(f"Sifat urgensi tidak dikenal: {urgensi} "
                      f"(pilih {'/'.join(SIFAT_URGENSI)})")
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
             "Jenis Naskah", "Sifat Urgensi", "Modul", "Kegiatan", "Kode Klasifikasi",
             "Disahkan/Diterima Pada", "Keterangan"]]
    for s in items or []:
        keluar = s.get("jenis") == "keluar"
        rows.append([
            # Lencana agenda yang SAMA dengan layar (mis. "K-001/VIII/2026")
            # bila pemanggil menyediakannya. Tanpa itu buku agenda cetak dan
            # buku agenda layar menyebut nomor berbeda untuk surat yang sama —
            # dan pada deret bulanan angka mentahnya tidak unik: 001 bulan Juli
            # dan 001 bulan Agustus tak bisa dibedakan lagi di atas kertas.
            s.get("label_agenda")
            or (urut_tampil(s.get("no_agenda"), s.get("sisipan"))
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
            SIFAT_URGENSI.get(s.get("sifat_urgensi"), s.get("sifat_urgensi") or ""),
            s.get("modul"),
            s.get("nama_kegiatan") or "",
            s.get("kode_klasifikasi") or "",
            (s.get("disahkan_pada") if keluar else s.get("created_at") or "")[:10]
            if (s.get("disahkan_pada") or (not keluar and s.get("created_at"))) else "",
            s.get("keterangan") or (s.get("alasan_batal") or ""),
        ])
    return rows


def pilih_klasifikasi(peta, modul, jenis_naskah, eksplisit="") -> str:
    """Kode klasifikasi arsip untuk sebuah surat — otomatis dari pemetaan.

    Prioritas: (1) kode yang DIISI EKSPLISIT oleh pengguna; (2) aturan
    pemetaan paling SPESIFIK yang cocok — modul+jenis (skor 2) > salah
    satunya (skor 1); aturan dengan field kosong = wildcard; seri pertama
    menang saat skor sama. Tak cocok satu pun → KOSONG. MURNI.

    TIDAK ADA jaring "kode bawaan" di sini, dan itu disengaja. Permintaan
    pemilik: *"tolong bedakan Kode Klasifikasi Bawaan (fallback) berdiri
    sendiri dan Kode Klasifikasi Arsip berdiri sendiri, independent masing
    masing"*. Dulu keduanya satu nilai: kode bawaan diam-diam menempati slot
    klasifikasi arsip, sehingga nomor terbit membawa kode bawaan sambil
    layar menyebutnya "klasifikasi arsip surat ini". Dua hal berbeda dengan
    satu nama — dan yang membaca nomornya tak punya cara membedakannya.

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
    return terbaik


def sebut_cakupan(modul, jenis_naskah) -> str:
    """Cakupan sebuah aturan dalam bahasa manusia — dipakai pesan galat & UI."""
    m = str(modul or "").strip()
    j = str(jenis_naskah or "").strip()
    if m and j:
        return f"modul {m} + {j}"
    if m:
        return f"modul {m}, semua jenis naskah"
    if j:
        return f"{j}, semua modul"
    return "semua modul & semua jenis naskah"


def validate_peta_klasifikasi(peta) -> list:
    """Validasi aturan pemetaan klasifikasi → daftar pesan kesalahan.

    ATURAN "SEMUA" (modul dan jenis naskah sama-sama kosong) ADALAH SAH.
    Dulu ia ditolak dengan alasan "tak pernah spesifik" — dan itu memutus
    rantai Master Kode Klasifikasi Arsip: layar pengaturan menambahkan baris
    baru dalam keadaan kedua filternya kosong dan keterangannya sendiri
    berbunyi "kosong = berlaku untuk semua", sehingga aturan pertama yang
    dibuat siapa pun selalu ditolak 400 — SELURUH simpanan gagal, dan kode
    klasifikasi yang sudah susah payah didaftarkan tak pernah berpengaruh
    apa-apa pada nomor surat.

    Mesinnya sendiri (`pilih_klasifikasi`) selalu mendukungnya: aturan tanpa
    filter berskor 0, jadi ia menang hanya bila tak ada aturan yang lebih
    spesifik — persis makna "kode bawaan untuk sisanya". Validatorlah yang
    salah, bukan mesinnya.

    Sebagai gantinya dijaga hal yang benar-benar merugikan: aturan KEMBAR.
    `pilih_klasifikasi` memakai `skor > skor_terbaik`, sehingga di antara dua
    aturan bercakupan sama hanya yang PERTAMA yang pernah terpakai — yang di
    bawah adalah baris mati yang menyesatkan pembacanya.
    """
    errors = []
    terlihat = {}                       # cakupan → nomor aturan pertama
    for i, aturan in enumerate(peta or [], 1):
        if not str((aturan or {}).get("kode") or "").strip():
            errors.append(f"Aturan #{i}: kode klasifikasi wajib diisi")
        modul = str((aturan or {}).get("modul") or "").strip()
        jenis = str((aturan or {}).get("jenis_naskah") or "").strip()
        if modul and modul not in MODUL_AMAN:
            errors.append(f"Aturan #{i}: modul tidak dikenal: {modul}")
        kunci = (modul, jenis.casefold())
        if kunci in terlihat:
            errors.append(
                f"Aturan #{i}: cakupannya sama dengan aturan #{terlihat[kunci]} "
                f"({sebut_cakupan(modul, jenis)}) — yang di bawah tak akan "
                "pernah dipakai; hapus salah satunya")
        else:
            terlihat[kunci] = i
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
