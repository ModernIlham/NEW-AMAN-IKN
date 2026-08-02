#!/usr/bin/env python3
"""Backfill `kode_satker` kosong pada dokumen modul Penggunaan/BAST di VPS.

KENAPA. `scope_query_field_satker` sengaja meloloskan dokumen ber-`kode_satker`
kosong (kompatibilitas data era lama) — akibatnya SK PSP / tiket idle / tiket
proses / BAST yang pernah dibuat super-admin pusat TANPA "Satker Aktif"
terstempel "" dan tampil di register SEMUA satker (kebocoran yang dilaporkan
pemilik pada halaman aset pemegang, bagian Penetapan Status Penggunaan).
Sisi tulisnya sudah ditutup (stempel efektif diderivasi dari kegiatan aset);
skrip ini merapikan dokumen LAMA yang telanjur kosong.

CARA KERJA. Untuk tiap dokumen ber-`kode_satker` kosong, kode satker
diderivasi dari aset yang dirujuknya: asset_id/asset_ids/aset[].asset_id →
assets.activity_id → inventory_activities.kode_satker (kode pertama yang
terisi menang). Dokumen yang tak terderivasi (aset yatim) dilaporkan, tidak
disentuh.

Pakai (di VPS, virtualenv backend):
    python3 scripts/backfill_kode_satker_dokumen.py            # DRY-RUN (aman)
    python3 scripts/backfill_kode_satker_dokumen.py --terapkan # tulis beneran

Baca MONGO_URL & DB_NAME dari environment (fallback .env backend bila ada).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _muat_env():
    """Isi MONGO_URL/DB_NAME dari backend/.env bila belum ada di environment."""
    jalur = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if not os.path.exists(jalur):
        return
    for baris in open(jalur, encoding="utf-8", errors="ignore"):
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        k, _, v = baris.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("MONGO_URL", "DB_NAME") and k not in os.environ:
            os.environ[k] = v


# Koleksi → cara mengambil daftar asset_id dari satu dokumen.
KOLEKSI = {
    "psp": lambda d: [a.get("asset_id") for a in d.get("aset") or []],
    "bmn_idle": lambda d: [d.get("asset_id")],
    "penggunaan_proses": lambda d: [a.get("asset_id") for a in d.get("aset") or []],
    "bast_serah_terima": lambda d: list(d.get("asset_ids") or []),
}

Q_KOSONG = {"$or": [{"kode_satker": {"$in": ["", None]}},
                    {"kode_satker": {"$exists": False}}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--terapkan", action="store_true",
                    help="tulis perubahan (tanpa ini: dry-run)")
    args = ap.parse_args()

    _muat_env()
    from pymongo import MongoClient
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    nama_db = os.environ.get("DB_NAME", "test_database")
    db = MongoClient(url)[nama_db]

    # Cache aset→kegiatan→kode_satker agar hemat query.
    cache_aset, cache_kegiatan = {}, {}

    def kode_dari_aset(asset_id):
        aid = str(asset_id or "").strip()
        if not aid:
            return ""
        if aid not in cache_aset:
            a = db.assets.find_one({"id": aid}, {"_id": 0, "activity_id": 1})
            cache_aset[aid] = str((a or {}).get("activity_id") or "").strip()
        act_id = cache_aset[aid]
        if not act_id:
            return ""
        if act_id not in cache_kegiatan:
            act = db.inventory_activities.find_one(
                {"id": act_id}, {"_id": 0, "kode_satker": 1})
            cache_kegiatan[act_id] = str((act or {}).get("kode_satker") or "").strip()
        return cache_kegiatan[act_id]

    mode = "TERAPKAN" if args.terapkan else "DRY-RUN"
    print(f"== Backfill kode_satker dokumen ({mode}) — db={nama_db} ==")
    total_isi = total_gagal = 0
    for nama, ambil_ids in KOLEKSI.items():
        kosong = list(db[nama].find(Q_KOSONG, {"_id": 0}))
        isi = gagal = 0
        for d in kosong:
            kode = ""
            for aid in ambil_ids(d):
                kode = kode_dari_aset(aid)
                if kode:
                    break
            if not kode:
                gagal += 1
                print(f"  [?] {nama} id={d.get('id')} — aset yatim, "
                      f"tak terderivasi (biarkan, rapikan manual)")
                continue
            isi += 1
            if args.terapkan:
                db[nama].update_one({"id": d.get("id")},
                                    {"$set": {"kode_satker": kode}})
            else:
                print(f"  [+] {nama} id={d.get('id')} → {kode}")
        print(f"{nama}: {len(kosong)} kosong → {isi} terisi, {gagal} yatim")
        total_isi += isi
        total_gagal += gagal

    # Surat booking otomatis dari BAST yang ikut terstempel kosong: warisi
    # kode_satker BAST-nya (setelah BAST terisi di atas).
    kosong_surat = list(db.surat.find(
        {**Q_KOSONG, "referensi": "BAST"}, {"_id": 0, "id": 1}))
    isi_surat = 0
    for s in kosong_surat:
        b = db.bast_serah_terima.find_one(
            {"surat_id": s.get("id"),
             "kode_satker": {"$nin": ["", None]}}, {"_id": 0, "kode_satker": 1})
        if not b:
            continue
        isi_surat += 1
        if args.terapkan:
            db.surat.update_one({"id": s.get("id")},
                                {"$set": {"kode_satker": b["kode_satker"]}})
        else:
            print(f"  [+] surat id={s.get('id')} → {b['kode_satker']}")
    print(f"surat (booking BAST): {len(kosong_surat)} kosong → {isi_surat} terisi")

    print(f"\nTOTAL: {total_isi + isi_surat} terisi, {total_gagal} yatim. "
          + ("Perubahan DITULIS." if args.terapkan
             else "Dry-run — jalankan ulang dengan --terapkan untuk menulis."))


if __name__ == "__main__":
    main()
