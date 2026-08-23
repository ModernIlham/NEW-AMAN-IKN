"""Dokumen pengadaan yang melekat pada satu register perolehan — logika MURNI.

Permintaan pemilik: *"tambahan informasi mengenai no SP/SPK, SPP/SPM (validasi
agar sesuai pengertiannya, lihat penginputan no SPM di modul inventarisasi aset
bagian SPM), UP/TUP, SPBY, No Dokumen. Dan tak lupa sifatnya apakah
kontrak/non kontrak."*

── Kenapa sifatnya menentukan kolom mana yang berlaku ──────────────────────
Pembayaran belanja negara punya DUA jalur, dan dokumennya tidak saling
bertukar:

  KONTRAK (pembayaran langsung/LS)
      SP/SPK  →  SPP-LS  →  SPM-LS  →  SP2D
      Perikatan dengan penyedia lahir dari Surat Pesanan / Surat Perintah
      Kerja; pembayarannya menempuh SPP lalu SPM.

  NON-KONTRAK (uang persediaan)
      UP/TUP  →  SPBy  →  (GUP: SPP-GUP → SPM-GUP)
      Bendahara membayar lebih dulu dengan Surat Perintah Bayar atas beban
      Uang Persediaan / Tambahan UP; SP/SPK tidak terbit.

Karena itu SP/SPK pada register non-kontrak, atau UP/TUP dan SPBy pada
register kontrak, BUKAN sekadar tak lazim — ia menyatakan dua hal yang tak
mungkin terjadi bersamaan. Pemilik memilih agar kombinasi itu DITOLAK, bukan
sekadar diperingatkan.

SPP dan SPM berlaku pada KEDUA jalur (LS maupun GUP), begitu pula No Dokumen
sebagai rujukan bebas. Keduanya karena itu tak pernah menjadi pertentangan.

── Nomor SPM ────────────────────────────────────────────────────────────────
Pengertian dan bentuknya mengikuti kolom `nomor_spm` pada modul Inventarisasi
Aset (`asset_fields.py`) — Surat Perintah Membayar, contoh 02847T/621001/2024.
Bentuknya TIDAK dipaksakan dengan regex: modul aset pun tak memaksakannya, dan
memaksa di satu tempat saja akan menolak nomor yang di tempat lain diterima.

MURNI: tanpa Mongo/IO, seluruhnya teruji unit.
"""

SIFAT_KONTRAK = "kontrak"
SIFAT_NON_KONTRAK = "non_kontrak"
SIFAT_PENGADAAN = {
    SIFAT_KONTRAK: "Kontrak (SP/SPK · SPP-LS · SPM-LS)",
    SIFAT_NON_KONTRAK: "Non-Kontrak (UP/TUP · SPBy)",
}

JENIS_UP = {"up": "UP (Uang Persediaan)", "tup": "TUP (Tambahan UP)"}

# Kolom dokumen: kunci, label, contoh, dan SIFAT yang memilikinya.
# `sifat=""` berarti berlaku pada kedua jalur.
DOKUMEN_PENGADAAN = [
    {"kunci": "no_sp_spk", "label": "No. SP/SPK", "contoh": "SPK-014/PPK/VIII/2026",
     "sifat": SIFAT_KONTRAK,
     "arti": "Surat Pesanan / Surat Perintah Kerja — perikatan dengan penyedia"},
    {"kunci": "jenis_up", "label": "UP/TUP", "contoh": "up",
     "sifat": SIFAT_NON_KONTRAK,
     "arti": "Beban Uang Persediaan atau Tambahan Uang Persediaan"},
    {"kunci": "no_spby", "label": "No. SPBy", "contoh": "SPBy-021/BP/VIII/2026",
     "sifat": SIFAT_NON_KONTRAK,
     "arti": "Surat Perintah Bayar dari bendahara pengeluaran"},
    {"kunci": "no_spp", "label": "No. SPP", "contoh": "SPP-105/LS/2026",
     "sifat": "",
     "arti": "Surat Permintaan Pembayaran — berlaku jalur LS maupun GUP"},
    {"kunci": "no_spm", "label": "No. SPM", "contoh": "02847T/621001/2024",
     "sifat": "",
     "arti": "Surat Perintah Membayar — bentuknya sama dengan kolom SPM "
             "pada Inventarisasi Aset"},
    {"kunci": "no_dokumen", "label": "No. Dokumen", "contoh": "ND-77/PBJ/2026",
     "sifat": "",
     "arti": "Rujukan dokumen lain yang menyertai perolehan ini"},
]

KUNCI_DOKUMEN = [d["kunci"] for d in DOKUMEN_PENGADAAN]
MAKS_PANJANG_DOKUMEN = 60


def bersihkan_dokumen(data) -> dict:
    """Ambil HANYA kolom dokumen yang dikenal, dipangkas spasi tepinya."""
    d = data or {}
    keluar = {k: str(d.get(k) or "").strip() for k in KUNCI_DOKUMEN}
    keluar["jenis_up"] = keluar["jenis_up"].lower()
    return keluar


def milik_sifat(sifat) -> list:
    """Kunci dokumen yang BERLAKU pada sifat tersebut (termasuk yang umum)."""
    s = str(sifat or "").strip()
    return [d["kunci"] for d in DOKUMEN_PENGADAAN
            if not d["sifat"] or d["sifat"] == s]


def bertentangan(sifat, dok) -> list:
    """Kunci dokumen yang TERISI padahal bukan milik sifat itu. MURNI."""
    s = str(sifat or "").strip()
    if s not in SIFAT_PENGADAAN:
        # Sifat belum ditetapkan (register lama) — tak ada yang bisa
        # dipertentangkan. Menuduh data lama bertentangan hanya akan
        # mengunci operator dari register yang sudah lama benar.
        return []
    bersih = bersihkan_dokumen(dok)
    sah = set(milik_sifat(s))
    return [k for k in KUNCI_DOKUMEN if k not in sah and bersih.get(k)]


def validate_dokumen(sifat, dok) -> list:
    """Daftar pesan kesalahan dokumen pengadaan. MURNI."""
    errors = []
    s = str(sifat or "").strip()
    if s and s not in SIFAT_PENGADAAN:
        errors.append(f"Sifat pengadaan '{s}' tidak dikenal — pilih "
                      + " atau ".join(SIFAT_PENGADAAN))
    bersih = bersihkan_dokumen(dok)
    ju = bersih.get("jenis_up") or ""
    if ju and ju not in JENIS_UP:
        errors.append(f"UP/TUP '{ju}' tidak dikenal — pilih up atau tup")
    for k in KUNCI_DOKUMEN:
        if len(bersih.get(k) or "") > MAKS_PANJANG_DOKUMEN:
            label = next(d["label"] for d in DOKUMEN_PENGADAAN if d["kunci"] == k)
            errors.append(f"{label} terlalu panjang "
                          f"(maksimal {MAKS_PANJANG_DOKUMEN} karakter)")
    for k in bertentangan(s, dok):
        d = next(x for x in DOKUMEN_PENGADAAN if x["kunci"] == k)
        lawan = SIFAT_PENGADAAN[d["sifat"]].split(" (")[0]
        errors.append(
            f"{d['label']} hanya berlaku pada pengadaan {lawan} — "
            f"register ini bersifat {SIFAT_PENGADAAN[s].split(' (')[0]}")
    return errors


# Pengelompokan dokumen untuk DICETAK — bukan urutan penyimpanannya.
#
# Permintaan pemilik: *"buat informasinya teratur dan terorganisasi dengan baik
# agar rapi dan mudah dipahami."* Daftar rata enam baris memaksa pembaca
# mengingat sendiri mana yang perikatan dan mana yang pembayaran; padahal
# keduanya menjawab pertanyaan berbeda dan diperiksa oleh orang berbeda.
KELOMPOK_DOKUMEN = [
    ("Perikatan", ["no_sp_spk", "jenis_up", "no_spby"]),
    ("Pembayaran", ["no_spp", "no_spm"]),
    ("Rujukan lain", ["no_dokumen"]),
]


def kelompok_dokumen(sifat, dok) -> list:
    """[(judul_kelompok, [(label, nilai), ...])] — hanya yang TERISI.

    Kelompok yang seluruh isinya kosong TIDAK muncul, dan bila tak ada satu
    dokumen pun terisi hasilnya daftar kosong: blok yang separuhnya bertanda
    hubung membuat pembaca menghitung apa yang tak ada alih-alih membaca apa
    yang ada.

    `sifat` TIDAK ikut sebagai baris di sini — ia judul blok, bukan salah satu
    dokumennya. Pemanggil mencetaknya di kepala blok lewat `label_sifat`.
    """
    bersih = bersihkan_dokumen(dok)
    peta = {d["kunci"]: d for d in DOKUMEN_PENGADAAN}
    keluar = []
    for judul, kunci in KELOMPOK_DOKUMEN:
        isi = []
        for k in kunci:
            v = bersih.get(k) or ""
            if not v:
                continue
            isi.append((peta[k]["label"],
                        JENIS_UP.get(v, v) if k == "jenis_up" else v))
        if isi:
            keluar.append((judul, isi))
    return keluar


def label_sifat(sifat) -> str:
    """Uraian sifat pengadaan lengkap dengan jalur dokumennya, '' bila tak
    dikenal. Dipakai sebagai kepala blok dokumen pada PDF."""
    return SIFAT_PENGADAAN.get(str(sifat or "").strip(), "")


def baris_dokumen(sifat, dok) -> list:
    """Baris dokumen untuk dicetak: [(label, nilai)] — hanya yang TERISI.

    Kolom kosong tidak dicetak: blok dokumen yang separuhnya bertanda hubung
    membuat pembaca menghitung apa yang tak ada alih-alih membaca apa yang ada.
    """
    bersih = bersihkan_dokumen(dok)
    keluar = []
    s = str(sifat or "").strip()
    if s in SIFAT_PENGADAAN:
        keluar.append(("Sifat Pengadaan", SIFAT_PENGADAAN[s].split(" (")[0]))
    for d in DOKUMEN_PENGADAAN:
        v = bersih.get(d["kunci"]) or ""
        if not v:
            continue
        keluar.append((d["label"], JENIS_UP.get(v, v) if d["kunci"] == "jenis_up" else v))
    return keluar
