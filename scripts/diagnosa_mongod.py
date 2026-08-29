#!/usr/bin/env python3
"""Diagnosa mongod — HANYA MEMBACA. Dipipe ke VPS oleh workflow "Diagnosa
mongod" (.github/workflows/diagnosa-mongod.yml).

KENAPA ADA. Inventaris 29 Agustus 2026 menemukan `mongod` memakai **93,1%
CPU** terus-menerus pada mesin 2 vCPU — beban 1,00 datar di jendela 1/5/15
menit selama berminggu-minggu. `docs/OPTIMASI-VPS.md` §2 butir 1 menyebutnya
"belum teridentifikasi" sejak awal Agustus, dan dua dugaan sebelumnya sudah
terbantah (job WebP, cache Redis yang jatuh ke Mongo). Menyetel WiredTiger
atau menghapus indeks tanpa tahu query mana yang membakarnya adalah tebakan
ketiga.

ATURAN KERAS — dilanggar berarti alat diagnosis berubah jadi alat perusak:

1. TIDAK MENULIS APA PUN ke basis data. Tanpa insert/update/delete, tanpa
   createIndex/dropIndex, tanpa setProfilingLevel (mengubah konfigurasi
   server), tanpa $out/$merge (menulis koleksi), tanpa killOp/shutdown.
   Ia harus aman dijalankan pada produksi tengah hari.
2. TIDAK MENCETAK NILAI DATA. `currentOp` membawa dokumen `command` lengkap
   berisi nilai filter — NIP, kode satker, nama orang. Yang dicetak hanya
   BENTUK query: namespace, jenis operasi, lama jalan, dan `planSummary`
   (mis. `COLLSCAN` atau `IXSCAN { activity_id: 1 }` — nama indeks, bukan
   nilainya). Keluaran ini masuk ke log GitHub Actions.
3. TIDAK MENCETAK KREDENSIAL. `MONGO_URL` memuat sandi; ia dipakai untuk
   menyambung dan tidak pernah keluar ke mana pun.

backend/tests/unit/test_diagnosa_mongod.py menagih ketiganya.

Pakai (di VPS):  /var/www/inventarisasi/backend/venv/bin/python scripts/diagnosa_mongod.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Berapa koleksi terbesar yang diperiksa indeksnya. Semua koleksi akan
# membuat keluaran tak terbaca; yang kecil tak pernah jadi sumber beban CPU.
TERATAS = 8
# Ambang "operasi ini lama" untuk currentOp, dalam detik.
AMBANG_DETIK = 1


def _angka(n, desimal: int = 0) -> str:
    """Format Indonesia: titik ribuan, koma desimal.

    Versi pertama menulis `f"{x:,.1f}".replace(",", ".")` dan menghasilkan
    **`3.458.0 MB`** — dua titik dengan arti berbeda dalam satu angka, tak
    terbaca sebagai apa pun. Penukarannya harus lewat penanda sementara.
    """
    try:
        teks = f"{float(n):,.{desimal}f}"
    except (TypeError, ValueError):
        return "?"
    return teks.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _mb(byte) -> str:
    try:
        return f"{_angka(float(byte) / 1024 / 1024, 1)} MB"
    except (TypeError, ValueError):
        return "?"


def ringkas_server_status(doc: dict) -> list[str]:
    """Angka-angka server yang menjawab 'apakah ini beban query atau bukan'."""
    d = doc or {}
    wt = ((d.get("wiredTiger") or {}).get("cache") or {})
    antre = ((d.get("globalLock") or {}).get("currentQueue") or {})
    opc = d.get("opcounters") or {}
    kon = d.get("connections") or {}
    baris = [
        "| Aspek | Bacaan |",
        "|---|---|",
        f"| Uptime mongod | {d.get('uptime', '?')} detik |",
        f"| Koneksi terpakai | {kon.get('current', '?')} (tersedia {kon.get('available', '?')}) |",
        f"| Cache WiredTiger | {_mb(wt.get('bytes currently in the cache'))}"
        f" dari {_mb(wt.get('maximum bytes configured'))} |",
        f"| Halaman dibaca ke cache | {wt.get('pages read into cache', '?')} |",
        f"| Antrean baca / tulis | {antre.get('readers', '?')} / {antre.get('writers', '?')} |",
    ]
    for k in ("query", "insert", "update", "delete", "getmore", "command"):
        if k in opc:
            baris.append(f"| opcounter `{k}` | {_angka(opc[k])} |")
    return baris


def ringkas_current_op(doc: dict) -> list[str]:
    """Operasi yang SEDANG berjalan — bentuknya saja, tanpa nilai filter.

    `planSummary` inilah yang menjawab pertanyaannya: `COLLSCAN` berarti
    seluruh koleksi dipindai baris-per-baris, dan itulah yang membakar CPU.
    """
    ops = (doc or {}).get("inprog") or []
    if not ops:
        return ["_Tak ada operasi aktif yang berjalan ≥"
                f" {AMBANG_DETIK} detik saat dibaca._"]
    baris = ["| Namespace | Operasi | Detik | Rencana | Yield |", "|---|---|---|---|---|"]
    for o in ops[:20]:
        baris.append(
            f"| `{o.get('ns', '?')}` | {o.get('op', '?')} "
            f"| {o.get('secs_running', '?')} "
            f"| `{o.get('planSummary', '—')}` "
            f"| {o.get('numYields', '?')} |"
        )
    if len(ops) > 20:
        baris.append(f"| … | … | … | {len(ops) - 20} operasi lain | … |")
    return baris


def ringkas_index_stats(nama: str, stats: list) -> list[str]:
    """Indeks yang TAK PERNAH dipakai membebani tiap tulis tanpa imbalan.

    `accesses.ops` dihitung sejak mongod terakhir restart — nol pada server
    yang baru saja naik TIDAK berarti indeksnya sia-sia. Uptime dicetak di
    bagian Server supaya angka ini bisa dibaca dengan benar.
    """
    if not stats:
        return [f"_`{nama}`: tak ada data indeks._"]
    baris = [f"**`{nama}`**", "", "| Indeks | Dipakai (ops) |", "|---|---|"]
    for s in sorted(stats, key=lambda x: (x.get("accesses") or {}).get("ops", 0)):
        ops = (s.get("accesses") or {}).get("ops", 0)
        tanda = " ⚠ tak pernah" if ops == 0 else ""
        baris.append(f"| `{s.get('name', '?')}` | {_angka(ops)}{tanda} |")
    baris.append("")
    return baris


def ringkas_beban(status: dict) -> list[str]:
    """Bentuk bebannya: berapa query per detik, dan apakah ia memakai indeks.

    Ini menjawab pertanyaan yang `currentOp` TIDAK bisa jawab. Bacaan
    29 Agustus 2026 menemukan 6.943.415 query dalam 17 jam — 112 per detik,
    terus-menerus, pada pukul 06:49 pagi waktu setempat saat tak seorang pun
    memakai aplikasi. Tetapi `currentOp` hanya menangkap operasi yang SEDANG
    berjalan; query yang selesai dalam 8 milidetik tak akan pernah tertangkap
    betapa pun seringnya ia diulang. Angka kumulatif di sinilah yang melihatnya.

    `scannedObjects / returned` adalah tanda pindai-koleksi yang klasik:
    membaca 44.000 dokumen untuk mengembalikan satu berarti tak ada indeks
    yang menolong, dan pada koleksi yang muat di cache itu menjadi beban CPU
    murni tanpa satu pun I/O — persis gejala yang terbaca.
    """
    d = status or {}
    m = d.get("metrics") or {}
    qe = m.get("queryExecutor") or {}
    dok = m.get("document") or {}
    uptime = d.get("uptime") or 0
    opc = d.get("opcounters") or {}
    baris = ["| Ukuran | Bacaan |", "|---|---|"]
    if uptime:
        q = opc.get("query", 0)
        tulis = sum(opc.get(k, 0) for k in ("insert", "update", "delete"))
        baris.append(f"| Query per detik (rata-rata) | **{_angka(q / uptime, 1)}** |")
        baris.append(f"| Tulis per detik (rata-rata) | {_angka(tulis / uptime, 3)} |")
    dipindai = qe.get("scannedObjects")
    dikembalikan = dok.get("returned")
    baris.append(f"| Dokumen dipindai | {_angka(dipindai)} |")
    baris.append(f"| Kunci indeks dipindai | {_angka(qe.get('scanned'))} |")
    baris.append(f"| Dokumen dikembalikan | {_angka(dikembalikan)} |")
    if dipindai and dikembalikan:
        rasio = dipindai / dikembalikan
        nilai = f"**{_angka(rasio, 1)} : 1**"
        if rasio > 100:
            nilai += " ⚠ pindai-koleksi"
        baris.append(f"| Dipindai per dokumen dikembalikan | {nilai} |")
    cs = qe.get("collectionScans") or {}
    if cs:
        baris.append(f"| Pindai koleksi (total) | {_angka(cs.get('total'))} |")
    return baris


def ringkas_top(doc: dict) -> list[str]:
    """SIAPA yang memakan waktu mongod — per namespace, langsung.

    `db.adminCommand({top: 1})` menyimpan akumulasi waktu per koleksi sejak
    server naik. Inilah satu-satunya bacaan yang MENYEBUT NAMA sumber beban
    tanpa harus kebetulan menangkap query-nya sedang berjalan.
    """
    total = (doc or {}).get("totals") or {}
    baris_ns = []
    for ns, v in total.items():
        # `totals` memuat satu kunci `note` bernilai STRING di samping tiap
        # namespace; pemeriksaan tipe ini yang menyaringnya. Penjaga eksplisit
        # `ns == "note"` sempat ada di sini dan terbukti mati — mutasi yang
        # mencabutnya lolos semua uji, karena `isinstance` sudah bekerja.
        if not isinstance(v, dict):
            continue
        t = v.get("total") or {}
        baris_ns.append((t.get("time", 0), t.get("count", 0), ns, v))
    if not baris_ns:
        return ["_`top` tak memberi data._"]
    baris_ns.sort(reverse=True)
    jumlah_waktu = sum(b[0] for b in baris_ns) or 1
    keluar = ["| Namespace | Bagian waktu | Waktu (detik) | Operasi | Query | Perintah |",
              "|---|---|---|---|---|---|"]
    for waktu, jml, ns, v in baris_ns[:12]:
        q = ((v.get("queries") or {}).get("count", 0))
        c = ((v.get("commands") or {}).get("count", 0))
        bagian = waktu / jumlah_waktu * 100
        tebal = "**" if bagian >= 20 else ""
        keluar.append(
            f"| `{ns}` | {tebal}{_angka(bagian, 1)}%{tebal} "
            f"| {_angka(waktu / 1_000_000, 1)} | {_angka(jml)} "
            f"| {_angka(q)} | {_angka(c)} |"
        )
    return keluar


def ringkas_coll_stats(nama: str, doc: dict) -> list[str]:
    d = doc or {}
    return [
        f"| `{nama}` | {_angka(d.get('count'))}"
        f" | {_mb(d.get('size'))} | {_mb(d.get('storageSize'))} "
        f"| {d.get('nindexes', '?')} | {_mb(d.get('totalIndexSize'))} |"
    ]


def _judul(t: str) -> None:
    print(f"\n## {t}\n")


def main() -> int:
    # .env dibaca HANYA untuk menyambung. Nilainya tak pernah dicetak.
    akar = Path("/var/www/inventarisasi/backend")
    try:
        from dotenv import load_dotenv
        load_dotenv(akar / ".env")
    except ImportError:
        pass
    url = os.environ.get("MONGO_URL")
    nama_db = os.environ.get("DB_NAME")
    if not url or not nama_db:
        print("::error::MONGO_URL / DB_NAME tak terbaca dari backend/.env")
        return 1

    from pymongo import MongoClient
    klien = MongoClient(url, serverSelectionTimeoutMS=8000, connectTimeoutMS=8000)
    db = klien[nama_db]

    _judul("Server")
    try:
        print("\n".join(ringkas_server_status(db.command("serverStatus"))))
    except Exception as e:  # noqa: BLE001 — satu bagian gagal tak boleh
        print(f"_Gagal membaca serverStatus: {type(e).__name__}._")

    _judul("Bentuk beban")
    try:
        print("\n".join(ringkas_beban(db.command("serverStatus"))))
    except Exception as e:  # noqa: BLE001
        print(f"_Gagal membaca metrics: {type(e).__name__}._")

    _judul("Waktu mongod per koleksi")
    print("> Akumulasi sejak mongod naik. Baris teratas adalah sumber beban "
          "yang sebenarnya — ia tak perlu tertangkap sedang berjalan.\n")
    try:
        print("\n".join(ringkas_top(klien.admin.command("top"))))
    except Exception as e:  # noqa: BLE001
        print(f"_Gagal membaca top: {type(e).__name__}._")

    _judul(f"Operasi aktif ≥ {AMBANG_DETIK} detik")
    try:
        print("\n".join(ringkas_current_op(klien.admin.command(
            "currentOp", **{"active": True, "secs_running": {"$gte": AMBANG_DETIK}}))))
    except Exception as e:  # noqa: BLE001
        print(f"_Gagal membaca currentOp: {type(e).__name__}._")

    _judul("Koleksi terbesar")
    ukuran = []
    try:
        for nama in db.list_collection_names():
            if nama.startswith("system."):
                continue
            try:
                ukuran.append((db.command("collStats", nama), nama))
            except Exception:  # noqa: BLE001
                continue
        ukuran.sort(key=lambda x: x[0].get("storageSize", 0), reverse=True)
    except Exception as e:  # noqa: BLE001
        print(f"_Gagal mendaftar koleksi: {type(e).__name__}._")
    if ukuran:
        print("| Koleksi | Dokumen | Data | Di disk | Indeks | Ukuran indeks |")
        print("|---|---|---|---|---|---|")
        for doc, nama in ukuran[:TERATAS]:
            print("\n".join(ringkas_coll_stats(nama, doc)))

    _judul("Pemakaian indeks")
    print("> `Dipakai (ops)` dihitung sejak mongod terakhir restart — nol pada "
          "server yang baru naik BUKAN berarti indeksnya sia-sia. Bandingkan "
          "dengan uptime di bagian Server.\n")
    for _doc, nama in ukuran[:TERATAS]:
        try:
            stats = list(db[nama].aggregate([{"$indexStats": {}}]))
        except Exception as e:  # noqa: BLE001
            print(f"_`{nama}`: gagal — {type(e).__name__}._\n")
            continue
        print("\n".join(ringkas_index_stats(nama, stats)))

    _judul("Profiler")
    try:
        p = db.command("profile", -1)
        print(f"Level `{p.get('was', '?')}`, ambang lambat "
              f"`{p.get('slowms', '?')}` ms, sampling `{p.get('sampleRate', '?')}`.")
        print("\n> Skrip ini TIDAK menyalakan profiler — itu mengubah konfigurasi "
              "server. Bila perlu, nyalakan sendiri sebentar lalu matikan lagi.")
    except Exception as e:  # noqa: BLE001
        print(f"_Gagal membaca status profiler: {type(e).__name__}._")

    klien.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
