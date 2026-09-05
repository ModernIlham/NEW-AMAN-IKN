"""Penautan dokumen ↔ permintaan tanda tangan elektronik — SATU PINTU.

Laporan pemilik: *"Riwayat BAST di bagian kirim tanda tangan selalu berakhir
dengan TTD sudah kedaluwarsa dan seperti tidak terhubung dengan modul TTD
elektronik … agar semua tanda tangan dapat saling terhubung ke TTD elektronik
dan memudahkan pengembangan ke depannya."*

── Apa yang sebenarnya terjadi ─────────────────────────────────────────────
BAST adalah SATU-SATUNYA pintu "Kirim ke TTD" yang tidak menuliskan tautan
MAJU (`signature_request_id`) saat permintaan dibuat. LPB menulisnya, kedua
permohonan persetujuan menulisnya; BAST hanya menerima tautan BALIK — dan itu
pun baru setelah SEMUA pihak selesai meneken.

Akibatnya berantai, dan tak satu pun tampak sebagai galat:

1. Riwayat BAST tidak tahu bahwa sebuah permintaan pernah dikirim.
2. Dialog berisi tautan per penanda tangan hanya hidup di layar; begitu
   ditutup, tautannya tak bisa ditemukan lagi dari BAST.
3. Satu-satunya jalan kembali adalah modul TTD Elektronik — dan ketika orang
   akhirnya ke sana, jendela 14 hari sering sudah lewat. Yang tersisa memang
   hanya "tautan mati".

── Kenapa berkas ini ada, bukan sekadar menambal BAST ──────────────────────
Menambal BAST saja akan mengulang sejarahnya: pintu "Kirim ke TTD" BERIKUTNYA
tetap harus ingat menulis tautan majunya sendiri, dan tak ada yang menagih
bila lupa. Di sini penautannya dijadikan satu registry + satu fungsi tulis,
sehingga mendaftarkan `doc_type` baru SEKALI menyalakan seluruh rantainya:
gerbang kepemilikan, tautan maju, dan ringkasan status di layar dokumennya.

MURNI kecuali dua fungsi yang memang menyentuh Mongo (`catat_pengiriman_ttd`,
`status_ttd_dokumen`) — keduanya menerima `db` sebagai argumen agar tetap
dapat diuji tanpa server.
"""
from datetime import datetime, timedelta, timezone

from ttd_validasi import sudah_membubuhkan, sudah_terverifikasi

# doc_type → koleksi dokumennya + label untuk pesan galat.
#
# `backlink` menandai dokumen yang JUGA ditulisi saat seluruh tanda tangan
# selesai (`tt_esign_selesai_pada`, penanda cabut). Yang tidak ber-backlink
# tetap wajib ada di sini: gerbang kepemilikan `POST /ttd/permintaan` dan
# ringkasan status di layar dokumennya bekerja untuk keduanya.
TAUT_TTD = {
    "bast": {"koleksi": "bast_serah_terima", "label": "BAST", "backlink": True},
    "lpb": {"koleksi": "lpb", "label": "LPB", "backlink": True},
    "persetujuan_aset": {"koleksi": "aset_permohonan",
                         "label": "Permohonan aset", "backlink": False},
    "persetujuan_persediaan": {"koleksi": "persediaan_permohonan",
                               "label": "Permohonan persediaan",
                               "backlink": False},
    "nota_persediaan": {"koleksi": "persediaan_nota",
                        "label": "Nota Dinas persediaan", "backlink": False},
}

KUNCI_TAUT = list(TAUT_TTD)


def koleksi_taut(db, doc_type):
    """Koleksi Mongo untuk `doc_type`, atau None bila tak terdaftar."""
    info = TAUT_TTD.get(str(doc_type or ""))
    return getattr(db, info["koleksi"]) if info else None


def label_taut(doc_type) -> str:
    return (TAUT_TTD.get(str(doc_type or "")) or {}).get("label", "Dokumen")


def sisa_kedaluwarsa(sg: dict, sr: dict) -> dict:
    """{kedaluwarsa, sisa_detik, perkiraan} untuk seorang penanda tangan.

    `sisa_detik` dihitung DI SERVER, bukan diserahkan ke peramban: halaman
    penanda tangan dibuka orang luar yang jam perangkatnya bisa saja meleset,
    dan tampilan "kedaluwarsa" yang salah akan membuat orang berhenti meneken
    dokumen yang sebenarnya masih sah.

    `perkiraan: True` menandai permintaan LAMA yang dibuat sebelum `token_exp`
    dicatat — angkanya diturunkan dari `created_at` dan bisa meleset bila
    linknya pernah diterbitkan ulang. UI wajib menampilkannya sebagai
    kira-kira, bukan sebagai angka pasti.

    DIPINDAH ke modul ini (dari routes/ttd.py) supaya layar dokumen — Riwayat
    BAST, Riwayat LPB — memakai angka yang SAMA PERSIS dengan modul TTD.
    Dua perhitungan sisa waktu yang berdampingan pasti akan berselisih, dan
    yang membacanya tak punya cara tahu mana yang benar.
    """
    from auth_utils import SIGN_TOKEN_EXPIRATION_DAYS
    perkiraan = False
    mentah = str((sg or {}).get("token_exp") or "").strip()
    if not mentah:
        # Permintaan era-lama: turunkan dari created_at, tandai sebagai perkiraan.
        dasar = str((sr or {}).get("created_at") or "").strip()
        if not dasar:
            return {"kedaluwarsa": None, "sisa_detik": None, "perkiraan": True}
        try:
            t0 = datetime.fromisoformat(dasar.replace("Z", "+00:00"))
        except (ValueError, TypeError, OverflowError):
            return {"kedaluwarsa": None, "sisa_detik": None, "perkiraan": True}
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        t = t0 + timedelta(days=SIGN_TOKEN_EXPIRATION_DAYS)
        perkiraan = True
    else:
        try:
            t = datetime.fromisoformat(mentah.replace("Z", "+00:00"))
        except (ValueError, TypeError, OverflowError):
            return {"kedaluwarsa": None, "sisa_detik": None, "perkiraan": True}
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    sisa = int((t - datetime.now(timezone.utc)).total_seconds())
    return {"kedaluwarsa": t.isoformat(),
            "sisa_detik": max(0, sisa), "perkiraan": perkiraan}


def kedaluwarsa_terdekat(sr: dict):
    """Batas TERCEPAT di antara penanda tangan yang BELUM meneken, atau None.

    Yang sudah meneken tak lagi relevan, dan menampilkan batas TERJAUH akan
    menyembunyikan tautan yang justru hampir mati — persis kebalikan dari
    gunanya angka ini.
    """
    belum = [s for s in (sr or {}).get("signers") or []
             if not sudah_membubuhkan(s)]
    sisa = [sisa_kedaluwarsa(s, sr) for s in belum]
    sisa = [x for x in sisa if x.get("sisa_detik") is not None]
    return min(sisa, key=lambda x: x["sisa_detik"]) if sisa else None


def ringkas_status_ttd(sr: dict) -> dict:
    """Ringkasan satu permintaan untuk DITEMPELKAN pada dokumennya. MURNI.

    `perlu_terbit_ulang` adalah inti laporan pemilik: permintaan yang masih
    menunggu tetapi tautannya sudah mati BUKAN jalan buntu — tautannya bisa
    diterbitkan ulang. Selama layar tak pernah mengatakannya, "kedaluwarsa"
    terbaca sebagai akhir cerita.
    """
    if not sr:
        return {}
    tanda = sr.get("signers") or []
    membubuhkan = sum(1 for s in tanda if sudah_membubuhkan(s))
    selesai = sum(1 for s in tanda if sudah_terverifikasi(s))
    batas = kedaluwarsa_terdekat(sr)
    mati = bool(batas) and int(batas.get("sisa_detik") or 0) <= 0
    dibatalkan = sr.get("status") == "batal"
    semua = bool(tanda) and selesai == len(tanda) and sr.get("status") == "selesai"
    return {
        "id": sr.get("id", ""),
        "judul": sr.get("judul", ""),
        "status": sr.get("status", ""),
        "jumlah": len(tanda),
        "membubuhkan_jumlah": membubuhkan,
        "selesai_jumlah": selesai,
        "semua_selesai": semua,
        "dikirim_pada": sr.get("created_at", ""),
        "kedaluwarsa_terdekat": batas,
        "perlu_terbit_ulang": bool(mati and not semua and not dibatalkan),
    }


async def catat_pengiriman_ttd(db, doc_type, doc_ref, sr_id) -> bool:
    """Tautan MAJU dokumen → permintaan, ditulis SAAT PERMINTAAN DIBUAT.

    Bukan saat selesai diteken: justru selama menunggu itulah layar dokumen
    perlu bisa menunjukkan tautannya, statusnya, dan tombol terbitkan ulang.

    Mengembalikan False bila `doc_type` tak terdaftar atau `doc_ref` kosong —
    permintaan TTD tetap sah, hanya tak bertaut (mis. dokumen unggahan bebas).
    """
    ref = str(doc_ref or "").strip()
    koleksi = koleksi_taut(db, doc_type)
    if koleksi is None or not ref or not str(sr_id or "").strip():
        return False
    await koleksi.update_one(
        {"id": ref},
        {"$set": {"signature_request_id": str(sr_id),
                  "tt_dikirim_pada": datetime.now(timezone.utc).isoformat()}})
    return True


async def status_ttd_dokumen(db, doc_type, doc_refs) -> dict:
    """{doc_ref: ringkasan} untuk sehalaman dokumen — SATU kueri, bukan N.

    Dipakai daftar/riwayat dokumen. Bila satu dokumen pernah dikirim lebih
    dari sekali, yang diambil permintaan TERBARU: itulah yang tautannya masih
    mungkin hidup, dan itulah yang dimaksud orang saat bertanya "sudah
    ditandatangani belum?".
    """
    refs = [str(r).strip() for r in (doc_refs or []) if str(r or "").strip()]
    if not refs or str(doc_type or "") not in TAUT_TTD:
        return {}
    kursor = db.signature_requests.find(
        {"doc_type": str(doc_type), "doc_ref": {"$in": refs}},
        {"_id": 0, "id": 1, "judul": 1, "status": 1, "doc_ref": 1,
         "created_at": 1, "signers": 1}).sort("created_at", 1)
    keluar = {}
    async for sr in kursor:
        # Terurut menaik → yang terbaru menimpa yang lama.
        keluar[str(sr.get("doc_ref"))] = ringkas_status_ttd(sr)
    return keluar


async def lampirkan_status_ttd(db, doc_type, items, kunci="id", field="ttd"):
    """Tempelkan ringkasan status TTD ke tiap item daftar — SATU kueri.

    Empat daftar dokumen memerlukan potongan yang sama persis (Riwayat BAST,
    Riwayat LPB, dua daftar permohonan persetujuan). Ditulis sekali di sini
    supaya daftar KELIMA tak perlu menyalinnya — dan supaya tak ada yang
    diam-diam memakai kunci atau nama field yang berbeda, yang membuat
    layarnya sunyi tanpa satu pun galat.

    Mengembalikan `items` yang sama (diubah di tempat) agar dapat dirangkai.
    """
    daftar = list(items or [])
    peta = await status_ttd_dokumen(
        db, doc_type, [str((it or {}).get(kunci) or "") for it in daftar])
    for it in daftar:
        it[field] = peta.get(str((it or {}).get(kunci) or "")) or None
    return daftar
