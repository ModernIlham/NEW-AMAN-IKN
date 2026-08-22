"""Siapa menandatangani slot mana pada dokumen — logika MURNI.

Permintaan pemilik: *"benahi kolom tanda tangan agar … sudah aktif semua bisa
memilih siapa saja yang menandatangani sesuai referensi pejabat yang sudah
ditetapkan"*, dengan pilihan **setelan satker yang bisa ditimpa per dokumen**.

── Tiga lapis, dan urutannya penting ───────────────────────────────────────
1. **Pilihan dokumen ini** — dibekukan saat dokumen terbit. Dokumen yang sudah
   ditandatangani tak boleh berganti nama penanda tangan hanya karena setelan
   satker kelak diubah.
2. **Setelan satker** — ditetapkan sekali, dipakai seluruh dokumen berikutnya.
3. **Peran pada Referensi Pejabat** — perilaku lama, dan tetap menjadi jaring
   terakhir. Satker yang belum pernah menyentuh setelan ini tak berubah
   apa pun.

── Kenapa id yang basi TIDAK mengosongkan tanda tangan ─────────────────────
Pejabat bisa dihapus atau berpindah satker setelah setelan dibuat. Bila slot
itu lalu dibiarkan kosong, dokumen resmi terbit tanpa penanda tangan — dan yang
mencetaknya tak diberi tahu apa pun. Id yang tak lagi ditemukan karena itu
JATUH ke lapis berikutnya, bukan menghasilkan kekosongan.

MURNI: tanpa Mongo/IO, seluruhnya teruji unit.
"""

# Slot tanda tangan per dokumen: label untuk layar + peran yang menjadi
# jaring terakhirnya (perilaku lama sebelum setelan ini ada).
SLOT_TTD = {
    "lpb_dibuat": {
        "label": "LPB — Dibuat oleh",
        "peran": "pengurus_barang",
        "arti": "Petugas yang menyusun Laporan Penerimaan Barang",
    },
    "lpb_diperiksa": {
        "label": "LPB — Diperiksa oleh",
        "peran": "pemeriksa_lpb",
        "arti": "Pemeriksa LPB — slot inilah yang paling sering kosong "
                "karena perannya belum pernah ditetapkan di Referensi Pejabat",
    },
    "lpb_disetujui": {
        "label": "LPB — Disetujui oleh",
        "peran": "kuasa_pengguna_barang",
        "arti": "Kuasa Pengguna Barang yang menyetujui penerimaan",
    },
}

KUNCI_SLOT = list(SLOT_TTD)


def bersihkan_penandatangan(peta) -> dict:
    """Ambil HANYA slot yang dikenal, nilainya id pejabat yang dipangkas."""
    d = peta or {}
    keluar = {}
    for k in KUNCI_SLOT:
        v = str(d.get(k) or "").strip()
        if v:
            keluar[k] = v
    return keluar


def validate_penandatangan(peta) -> list:
    """Pesan kesalahan untuk peta penanda tangan. MURNI."""
    if peta in (None, {}):
        return []
    if not isinstance(peta, dict):
        return ["Penanda tangan harus berupa peta slot → pejabat"]
    asing = [k for k in peta if k not in SLOT_TTD]
    if asing:
        return [f"Slot tanda tangan tidak dikenal: {', '.join(sorted(asing))}"]
    return []


def _cari_pejabat(daftar, pejabat_id):
    pid = str(pejabat_id or "").strip()
    if not pid:
        return None
    for p in daftar or []:
        if str((p or {}).get("id") or "") == pid:
            return p
    return None


def pilih_pejabat(slot, pilihan_dokumen, setelan_satker, daftar_pejabat,
                  jaring_terakhir=None) -> dict:
    """Pejabat untuk satu slot → dict pejabat (atau `jaring_terakhir`).

    Urutan: pilihan dokumen → setelan satker → jaring terakhir (hasil resolusi
    peran). Id yang tak lagi ditemukan DILEWATI, bukan mengosongkan slotnya.
    """
    for sumber in (pilihan_dokumen, setelan_satker):
        p = _cari_pejabat(daftar_pejabat,
                          bersihkan_penandatangan(sumber).get(slot))
        if p:
            return p
    return jaring_terakhir or {}


def asal_pilihan(slot, pilihan_dokumen, setelan_satker, daftar_pejabat) -> str:
    """Dari lapis mana slot itu terisi: "dokumen" / "satker" / "peran".

    Dipakai layar untuk menerangkan kenapa sebuah nama muncul — tanpa itu,
    operator yang mengubah setelan satker lalu melihat nama lama pada dokumen
    lama akan mengira setelannya tak tersimpan.
    """
    if _cari_pejabat(daftar_pejabat,
                     bersihkan_penandatangan(pilihan_dokumen).get(slot)):
        return "dokumen"
    if _cari_pejabat(daftar_pejabat,
                     bersihkan_penandatangan(setelan_satker).get(slot)):
        return "satker"
    return "peran"
