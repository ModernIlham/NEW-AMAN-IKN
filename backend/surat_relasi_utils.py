"""Relasi ANTAR SURAT + status keberlakuan — logika murni (tanpa Mongo/IO).

Mandat pemilik: persuratan memodelkan hubungan hukum antar naskah sebagaimana
jaringan dokumen peraturan (JDIH): mencabut / mengubah / menetapkan /
melaksanakan / mendelegasikan / dibatalkan, berikut STATUS KEBERLAKUAN yang
dihitung dari hubungan itu — bukan diketik manual, supaya buku agenda tak
pernah bilang "Berlaku" untuk surat yang nyatanya sudah dicabut.

── Model data (koleksi db.surat_relasi, satu dokumen per panah) ─────────────
{id, kode_satker, dari_id, ke_id, jenis, catatan, oleh, created_at,
 dari_nomor, dari_perihal, ke_nomor, ke_perihal}   # snapshot utk tampilan

Arah SELALU aktif→pasif: `dari` MENCABUT `ke`; label pasif ("Dicabut oleh")
diturunkan dari arah, tidak disimpan ganda. Nomor surat tak pernah berubah
sehingga snapshot aman dari basi.

── Aturan keberlakuan (status_keberlakuan) ──────────────────────────────────
Prioritas dari yang paling menentukan:
1. Surat keluar berstatus "dibatalkan" → tidak_berlaku (nomornya hangus).
2. Ada relasi masuk MEMATIKAN (mencabut / membatalkan) yang PANAHNYA HIDUP
   (surat pencabutnya tidak dibatalkan / tidak ikut tercabut — dinilai
   pemanggil lewat `panah_hidup`) → tidak_berlaku.
3. Ada relasi masuk mengubah / mencabut_sebagian → diubah (tetap berlaku,
   dengan perubahan).
4. Surat keluar masih "dibooking" → draf (belum berlaku sebagai naskah).
5. Selainnya → berlaku.
"""

# Jenis relasi berarah (aktif = dari sisi surat sumber). `mematikan` =
# menjadikan surat sasaran tidak berlaku seluruhnya.
JENIS_RELASI = {
    "mencabut": {
        "aktif": "Mencabut", "pasif": "Dicabut oleh", "mematikan": True},
    "mencabut_sebagian": {
        "aktif": "Mencabut Sebagian", "pasif": "Dicabut sebagian oleh",
        "mematikan": False},
    "mengubah": {
        "aktif": "Mengubah", "pasif": "Diubah oleh", "mematikan": False},
    "menetapkan": {
        "aktif": "Menetapkan", "pasif": "Ditetapkan oleh", "mematikan": False},
    "melaksanakan": {
        "aktif": "Melaksanakan (aturan turunan)", "pasif": "Dilaksanakan oleh",
        "mematikan": False},
    "mendelegasikan": {
        "aktif": "Mendelegasikan", "pasif": "Didelegasikan oleh",
        "mematikan": False},
    "membatalkan": {
        "aktif": "Membatalkan (putusan)", "pasif": "Dibatalkan oleh",
        "mematikan": True},
}

STATUS_KEBERLAKUAN = {
    "berlaku": "Berlaku",
    "diubah": "Berlaku dengan perubahan",
    "tidak_berlaku": "Tidak Berlaku",
    "draf": "Draf (dibooking, belum sah)",
}

# Relasi yang menjadikan surat sasaran "diubah" (berlaku dengan perubahan).
_JENIS_MENGUBAH = ("mengubah", "mencabut_sebagian")


def jenis_mematikan(jenis: str) -> bool:
    return bool(JENIS_RELASI.get(jenis, {}).get("mematikan"))


def label_relasi(jenis: str, arah: str) -> str:
    """Label tampilan sebuah panah dilihat dari salah satu ujungnya:
    arah 'keluar' = surat ini pelakunya (Mencabut …), arah 'masuk' = surat
    ini sasarannya (Dicabut oleh …). Jenis asing → kode apa adanya (jujur)."""
    info = JENIS_RELASI.get(jenis)
    if not info:
        return str(jenis or "-")
    return info["aktif"] if arah == "keluar" else info["pasif"]


def validate_relasi(dari: dict, ke: dict, jenis: str,
                    sudah_ada: list = ()) -> str:
    """'' bila sah; selain itu pesan penolakan (bahasa pengguna).

    `dari`/`ke` = dokumen surat; `sudah_ada` = relasi yang telah tercatat
    di antara keduanya (dua arah) untuk menolak duplikat & panah bolak-balik
    yang saling meniadakan.
    """
    if jenis not in JENIS_RELASI:
        return (f"Jenis relasi tidak dikenal: {jenis} "
                f"(pilihan: {', '.join(JENIS_RELASI)})")
    if not dari or not ke:
        return "Surat sumber/sasaran tidak ditemukan"
    if dari.get("id") == ke.get("id"):
        return "Surat tidak dapat berelasi dengan dirinya sendiri"
    if str(dari.get("status") or "") == "dibatalkan":
        return ("Surat sumber sudah dibatalkan (nomor hangus) — tidak dapat "
                "menjadi dasar relasi; terbitkan surat baru")
    for r in (sudah_ada or []):
        if (r.get("dari_id") == dari.get("id")
                and r.get("ke_id") == ke.get("id")
                and r.get("jenis") == jenis):
            return "Relasi yang sama sudah tercatat"
        # Dua surat saling mematikan = keadaan tak terputuskan (A mencabut B
        # dan B mencabut A) — tolak panah kedua.
        if (jenis_mematikan(jenis) and jenis_mematikan(r.get("jenis"))
                and r.get("dari_id") == ke.get("id")
                and r.get("ke_id") == dari.get("id")):
            return ("Surat sasaran tercatat mencabut/membatalkan surat "
                    "sumber — dua surat tidak boleh saling mematikan")
    return ""


def status_keberlakuan(surat: dict, relasi_masuk: list,
                       panah_hidup=None) -> str:
    """Status keberlakuan TERHITUNG sebuah surat.

    `relasi_masuk` = dokumen surat_relasi dengan ke_id == surat.id;
    `panah_hidup(r) -> bool` menilai apakah panah masih berlaku (surat
    pencabutnya sendiri belum dibatalkan/dicabut) — None = semua dianggap
    hidup (uji murni / pemanggil sudah menyaring).
    """
    s = dict(surat or {})
    if s.get("jenis") == "keluar" and s.get("status") == "dibatalkan":
        return "tidak_berlaku"
    hidup = [r for r in (relasi_masuk or [])
             if panah_hidup is None or panah_hidup(r)]
    if any(jenis_mematikan(r.get("jenis")) for r in hidup):
        return "tidak_berlaku"
    if any(r.get("jenis") in _JENIS_MENGUBAH for r in hidup):
        return "diubah"
    if s.get("jenis") == "keluar" and s.get("status") == "dibooking":
        return "draf"
    return "berlaku"


def baris_timeline(surat: dict, relasi_keluar: list, relasi_masuk: list) -> list:
    """Butir timeline satu surat, terurut waktu: kelahiran + transisi status
    (dari `riwayat` surat) + tiap panah relasi (dua arah) dengan labelnya.

    Setiap butir: {tanggal, teks, jenis: 'status'|'relasi', arah?, surat_id?,
    nomor?} — `surat_id`/`nomor` = ujung lain panah agar UI bisa menaut.
    """
    butir = []
    for h in (surat or {}).get("riwayat") or []:
        butir.append({
            "tanggal": str(h.get("tanggal") or ""),
            "jenis": "status",
            "teks": ("Status: " + str(h.get("status") or "-")
                     + (f" — {h.get('catatan')}" if h.get("catatan") else "")),
        })
    for r in (relasi_keluar or []):
        butir.append({
            "tanggal": str(r.get("created_at") or ""),
            "jenis": "relasi", "arah": "keluar",
            "surat_id": r.get("ke_id"), "nomor": r.get("ke_nomor") or "",
            "teks": (f"{label_relasi(r.get('jenis'), 'keluar')} "
                     f"{r.get('ke_nomor') or r.get('ke_id') or '-'}"
                     + (f" — {r.get('catatan')}" if r.get("catatan") else "")),
        })
    for r in (relasi_masuk or []):
        butir.append({
            "tanggal": str(r.get("created_at") or ""),
            "jenis": "relasi", "arah": "masuk",
            "surat_id": r.get("dari_id"), "nomor": r.get("dari_nomor") or "",
            "teks": (f"{label_relasi(r.get('jenis'), 'masuk')} "
                     f"{r.get('dari_nomor') or r.get('dari_id') or '-'}"
                     + (f" — {r.get('catatan')}" if r.get("catatan") else "")),
        })
    return sorted(butir, key=lambda b: b["tanggal"])
