"""REKONSILIASI OPNAME LEWAT SCAN STIKER (Fase 11) — helper MURNI.

Tanpa I/O dan tanpa DB, supaya seluruh keputusan yang menentukan "barang ini
sebenarnya ada di mana" bisa diuji tanpa infrastruktur.

TIGA KEPUTUSAN YANG MENENTUKAN BENTUK MODUL INI
================================================

1. **Scan adalah warga kelas satu, bukan pelengkap GPS.** Stiker menempel di
   barangnya dan yang memindai adalah petugas yang sedang berdiri di depan
   barang itu. Mode gagalnya sama sekali berbeda dari GPS: tak ada hanyutan
   sinyal, tak ada pantulan dinding, tak ada masalah privasi (yang direkam
   BARANG, bukan ORANG). Karena itu kepercayaannya dipatok 0,99 — bukan angka
   hiasan, melainkan pembeda saat suatu hari sumber lain ikut bicara tentang
   aset yang sama.

2. **Scan TIDAK langsung memindahkan catatan lokasi.** Godaannya besar: sekali
   pindai, langsung perbarui. Tetapi opname adalah pemeriksaan, dan pemeriksaan
   yang serta-merta menulis ulang buku menghapus satu-satunya hal yang hendak
   dicarinya — SELISIH. Salah pindai (stiker tetangga, barang sedang dijinjing
   petugas) akan diam-diam menulis ulang custody tanpa jejak keberatan.
   Karena itu: scan MENCATAT dan MENGKLASIFIKASI; pemindahan menyusul sebagai
   tindakan terpisah yang disengaja.

3. **Scan di level yang lebih kasar BUKAN perpindahan.** Petugas memindai di
   pintu Gedung A, sementara buku mencatat barang di Ruang 305 (yang berada DI
   DALAM Gedung A). Menganggapnya "pindah" lalu menerapkannya akan MENURUNKAN
   presisi dari ruangan menjadi gedung — kehilangan informasi yang justru mahal
   dikumpulkan. Scan seperti itu MENGUKUHKAN, bukan memindahkan.
"""
import re

# Umur maksimum scan luring yang masih diterima. Antrean PWA bisa tertahan
# berhari-hari di lokasi tanpa sinyal — itu justru kasus yang hendak dilayani —
# tetapi scan bertahun dari perangkat terlantar bukan lagi bukti opname.
MAKS_UMUR_SCAN_HARI = 30
# Panjang wajar isi QR/barcode stiker. Di atas ini hampir pasti bukan kode aset
# (URL panjang, teks bebas) dan hanya akan membebani kueri.
MAKS_PANJANG_KODE = 200

_TOKEN = re.compile(r"[A-Za-z0-9._-]{4,}")
_PEMISAH = re.compile(r"[\s|;,]")


def normalisasi_kode(teks) -> str:
    """Isi QR/barcode mentah → kode yang bisa dicari.

    KEMBARAN dari `extractScannedCode` di frontend (QrScanButton.jsx) dan
    sengaja diduplikasi, bukan dipercayakan ke klien: isi QR MENTAH bisa sampai
    ke server lewat antrean luring yang menyimpan `rawValue` apa adanya, dan
    kode yang menentukan aset mana yang dicatat tak boleh bergantung pada
    ekstraksi di sisi yang bisa diubah siapa pun.

    Bersifat idempoten untuk format stiker kami: menjalankannya atas hasilnya
    sendiri mengembalikan nilai yang sama.
    """
    baku = str(teks or "").strip()[:MAKS_PANJANG_KODE]
    if not baku:
        return ""
    # Format stiker & kartu inventaris: "#<kode>" — sisanya verbatim, tanpa
    # heuristik token (kode register boleh memuat spasi/tanda baca apa pun).
    if baku.startswith("#"):
        return baku[1:].strip()
    if re.match(r"^https?://", baku, re.IGNORECASE):
        # URL: ruas path/query TERAKHIR yang menyerupai kode.
        tanpa_skema = re.sub(r"^https?://[^/]*", "", baku, flags=re.IGNORECASE)
        ruas = [x for x in re.split(r"[/?&=#]", tanpa_skema) if x]
        for kandidat in reversed(ruas):
            if re.fullmatch(r"[A-Za-z0-9._-]{4,}", kandidat):
                return kandidat
    if _PEMISAH.search(baku):
        token = _TOKEN.findall(baku)
        if token:
            return max(token, key=len)
    return baku


def kandidat_kriteria(kode: str) -> list:
    """Kode terpindai → daftar kriteria pencarian aset (bahan `$or`).

    Stiker mencetak SALAH SATU dari dua bentuk (lihat routes/stiker.py):
    `#<kode_register>` bila ada, selebihnya `#<asset_code>-<NUP>`. Server tak
    tahu bentuk mana yang dipegang, jadi KEDUANYA dicoba dan hasil yang lebih
    dari satu diserahkan ke petugas untuk dipilih — menebak salah satu diam-diam
    persis cara sebuah scan tercatat pada gerbong yang salah.
    """
    kode = str(kode or "").strip()
    if not kode:
        return []
    kriteria = [{"kode_register": kode}, {"asset_code": kode}]
    if "-" in kode:
        dasar, _, nup = kode.rpartition("-")
        dasar, nup = dasar.strip(), nup.strip()
        if dasar and nup:
            if nup == "0":
                # Stiker menulis `nup or '0'`: aset ber-NUP KOSONG tercetak
                # sebagai "-0". Mencari NUP "0" saja membuat stiker itu abadi
                # tak terpindai.
                kriteria.append({"asset_code": dasar,
                                 "NUP": {"$in": ["0", "", None]}})
            else:
                kriteria.append({"asset_code": dasar, "NUP": nup})
    return kriteria


def klasifikasi_scan(node_id_lama, node_id_scan, ancestors_lama=None) -> str:
    """Status satu scan terhadap catatan lokasi yang berlaku.

    - `tanpa_lokasi` — scan tak berhasil ditautkan ke node denah mana pun
      (di luar kawasan terpetakan). Tetap dicatat sebagai bukti kehadiran
      petugas + waktu, tetapi tak pernah memindahkan apa pun.
    - `baru`   — aset belum pernah ditempatkan; scan ini penempatan pertamanya.
    - `sesuai` — buku dan lapangan cocok, ATAU scan dilakukan di level yang
      lebih kasar yang MEMUAT lokasi tercatat (lihat keputusan 3 di kepala
      berkas). Keduanya sama-sama "tidak ada yang perlu dipindahkan".
    - `pindah` — lapangan berbeda dari buku; inilah satu-satunya yang layak
      diusulkan sebagai perpindahan.
    """
    lama = str(node_id_lama or "").strip()
    baru = str(node_id_scan or "").strip()
    if not baru:
        return "tanpa_lokasi"
    if not lama:
        return "baru"
    if lama == baru:
        return "sesuai"
    # Node tercatat berada DI DALAM node yang dipindai → scan mengukuhkan.
    if baru in [str(x) for x in (ancestors_lama or []) if x]:
        return "sesuai"
    return "pindah"


def scan_terakhir_per_aset(scans) -> dict:
    """Banyak scan → satu scan TERAKHIR per aset (kunci `asset_id`).

    Opname penuh pengulangan: petugas memindai ulang karena ragu, atau dua
    petugas menyisir ruangan yang sama. Yang berlaku adalah pengamatan
    TERAKHIR — memakai yang pertama akan membekukan keadaan sebelum barang
    dipindahkan di tengah kegiatan.
    """
    hasil = {}
    for s in scans or []:
        aid = str((s or {}).get("asset_id") or "")
        if not aid:
            continue
        lama = hasil.get(aid)
        if lama is None or str(s.get("pada") or "") >= str(lama.get("pada") or ""):
            hasil[aid] = s
    return hasil


def rekap_rekonsiliasi(harapan, scans) -> dict:
    """Tiga keranjang hasil opname untuk satu lingkup lokasi.

    `harapan` = aset yang MENURUT BUKU menempati lingkup ini.
    `scans`   = scan yang TERJADI di lingkup ini pada periode opname.

    - `sesuai`          — tercatat di sini dan benar-benar terpindai di sini.
    - `belum_terpindai` — tercatat di sini tetapi belum ditemukan. Inilah daftar
                          kerja yang tersisa; tanpa memisahkannya, opname
                          berakhir dengan "sudah semua?" yang tak terjawab.
    - `pindah_masuk`    — terpindai di sini padahal buku menaruhnya di tempat
                          lain (atau belum di mana pun). Inilah calon
                          perpindahan yang menunggu keputusan petugas.

    Aset yang sudah diterapkan perpindahannya otomatis berpindah keranjang ke
    `sesuai` pada pembacaan berikutnya — rekap ini menyembuhkan diri sendiri
    dan tak menyimpan status apa pun yang bisa basi.
    """
    peta_scan = scan_terakhir_per_aset(scans)
    id_harapan = {str(a.get("id") or "") for a in (harapan or []) if a}
    sesuai, belum = [], []
    for a in harapan or []:
        (sesuai if str(a.get("id") or "") in peta_scan else belum).append(a)
    pindah = [s for aid, s in peta_scan.items() if aid not in id_harapan]
    pindah.sort(key=lambda s: str(s.get("pada") or ""), reverse=True)
    return {
        "sesuai": sesuai,
        "belum_terpindai": belum,
        "pindah_masuk": pindah,
        "ringkas": {
            "harapan": len(id_harapan),
            "sesuai": len(sesuai),
            "belum_terpindai": len(belum),
            "pindah_masuk": len(pindah),
            "terpindai": len(peta_scan),
        },
    }


def persen_terkonfirmasi(ringkas: dict) -> float:
    """Porsi aset tercatat yang sudah dikukuhkan fisik (0–100, 1 desimal).

    Indikator inti opname: "berapa persen buku sudah dibuktikan". Lingkup tanpa
    aset tercatat mengembalikan 0.0, bukan 100 — ruangan kosong bukan ruangan
    yang sudah diperiksa.
    """
    harapan = int((ringkas or {}).get("harapan") or 0)
    if harapan <= 0:
        return 0.0
    return round(100.0 * int((ringkas or {}).get("sesuai") or 0) / harapan, 1)
