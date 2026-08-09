"""Database index creation — extracted from server.py to break the circular
import with routes/backup.py (which re-creates indexes after a restore).

Any module that needs to (re)build indexes should import from here, NOT from
`server`.
"""
import logging

from db import db

logger = logging.getLogger(__name__)


# ── SATU INDEKS GAGAL TIDAK BOLEH MEMBATALKAN SISANYA (temuan C31) ──────────
#
# Seluruh badan `create_indexes()` dulu berada di dalam SATU `try/except`, dan
# `except`-nya hanya mencatat satu baris log. Artinya satu `create_index` yang
# melempar akan melompati SEMUA definisi setelahnya — 105 indeks di antaranya
# berada setelah titik rapuh terakhir. Sistem tetap hidup dan tetap menjawab,
# hanya saja separuh kuerinya berubah jadi pemindaian koleksi penuh, tanpa satu
# pun layar yang bisa menunjukkannya.
#
# Bahwa ini bukan hipotesis terlihat dari kompensasi di sekitarnya: ada tiga
# blok yang men-drop indeks era lama justru karena data produksi lama pernah
# melanggar keunikan. `create_index` idempoten, jadi risikonya tidak menyala
# tiap boot — ia menyala pada boot PERTAMA setelah indeks unik baru ditambahkan.
# Itu yang membuatnya mendesak, bukan sebaliknya.
#
# `_idx` menangkap per indeks, mencatat koleksi + nama + alasannya, lalu
# MELANJUTKAN. Daftar gagalnya dibaca /api/health/deep sehingga kegagalan
# parsial menjadi TERLIHAT — bukan sekadar satu baris di log yang tak dibaca.
_KEGAGALAN_INDEKS: list = []


async def _idx(coll, *a, **kw):
    """Buat satu indeks; catat & lanjut bila gagal. TIDAK PERNAH melempar.

    KARENA tidak pernah melempar, helper ini HARAM dipakai untuk percobaan
    `unique=True` yang butuh fallback: kegagalannya tertelan dan koleksi
    berakhir tanpa indeks sama sekali — sementara pembacanya mengira sudah
    terlindungi. Percobaan unik ditulis `create_index` mentah di dalam
    `try:`, dengan `_idx` hanya di cabang fallback (lihat blok satker).
    """
    nama = kw.get("name") or (a[0] if a else "?")
    try:
        await coll.create_index(*a, **kw)
    except Exception as e:
        _KEGAGALAN_INDEKS.append({
            "koleksi": getattr(coll, "name", "?"),
            "indeks": str(nama),
            "galat": str(e)[:200],
        })
        logger.error("Indeks GAGAL dibuat: %s.%s — %s",
                     getattr(coll, "name", "?"), nama, e)


async def _rapikan_duplikat_satker() -> int:
    """Gabung dokumen master satker ber-kode sama menjadi SATU. Idempoten.

    MENGGABUNG, bukan sekadar menghapus: field kop yang kosong pada penyintas
    ditambal dari kembarannya sebelum kembarannya dihapus — dua admin bisa
    mengisi kop pada dua dokumen berbeda tanpa pernah tahu, dan `delete_many`
    polos membuang persis data yang determinismenya hendak diselamatkan C32.
    Penyintas dipilih DETERMINISTIK penuh (kop terlengkap → created_at
    tertua → _id terkecil); tanpa tie-break penuh, dedupe cuma memindahkan
    nondeterminisme dari waktu-baca ke waktu-dedupe.
    """
    LINDUNGI = {"_id", "id", "kode_satker", "created_at"}
    n_hapus = 0
    pipeline = [{"$group": {"_id": "$kode_satker", "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}}]
    kode_ganda = [g["_id"] async for g in db.satker.aggregate(pipeline)]
    for kode in kode_ganda:
        docs = await db.satker.find({"kode_satker": kode}).to_list(1000)
        docs.sort(key=lambda d: (
            -sum(1 for k, v in d.items()
                 if k not in LINDUNGI and isinstance(v, str) and v.strip()),
            str(d.get("created_at") or "~"), str(d["_id"])))
        simpan, buang = docs[0], docs[1:]
        tambal = {}
        for d in buang:
            for k, v in d.items():
                if k in LINDUNGI or k in tambal:
                    continue
                if (simpan.get(k) in (None, "", [], {})
                        and v not in (None, "", [], {})):
                    tambal[k] = v
        if tambal:
            await db.satker.update_one({"_id": simpan["_id"]},
                                       {"$set": tambal})
        res = await db.satker.delete_many(
            {"_id": {"$in": [d["_id"] for d in buang]}})
        n_hapus += res.deleted_count
        logger.warning(
            "Dedupe master satker %s: %d duplikat digabung ke %s "
            "(field ditambal: %s)", kode, res.deleted_count,
            simpan.get("id"), sorted(tambal) or "-")
    return n_hapus


def kegagalan_indeks() -> list:
    """Salinan daftar indeks yang gagal dibuat pada pembuatan terakhir.

    Dibaca /api/health/deep. Salinan, bukan referensi: pemanggil tak boleh
    bisa mengosongkan catatan kegagalan hanya dengan memutasi hasilnya.
    """
    return list(_KEGAGALAN_INDEKS)


async def create_indexes() -> None:
    """Create database indexes for optimized query performance."""
    _KEGAGALAN_INDEKS.clear()
    try:
        try:
            await db.assets.drop_index("asset_code_1")
        except Exception:
            pass
        try:
            await db.assets.drop_index("asset_code_1_NUP_1_activity_id_1")
        except Exception:
            pass

        # KRITIS: semua jalur panas (GET/PUT/PATCH/DELETE /assets/{id}, stream
        # foto, lock, batch) mencari lewat field "id" (uuid aplikasi) — tanpa
        # indeks ini SETIAP lookup adalah full collection scan.
        try:
            await db.assets.create_index("id", unique=True, name="unique_asset_id")
        except Exception:
            # Data lama dengan id ganda: tetap buat indeks non-unik agar lookup cepat
            await db.assets.create_index("id", name="asset_id_lookup")
        await _idx(db.assets, 
            [("asset_code", 1), ("NUP", 1), ("activity_id", 1)],
            unique=True, name="unique_asset_code_nup_activity"
        )
        await _idx(db.assets, [("kode_register", 1), ("activity_id", 1)], name="kode_register_activity")
        await _idx(db.assets, "asset_name")
        await _idx(db.assets, "category")
        await _idx(db.assets, "created_at")
        # Filter rentang TANGGAL BELI (purchase_date) di daftar aset & ekspor
        # geo — tanpa indeks, range filter = full collection scan.
        await _idx(db.assets, "purchase_date")
        await _idx(db.assets, [("activity_id", 1), ("purchase_date", 1)])
        await _idx(db.assets, "location")
        await _idx(db.assets, "serial_number")
        await _idx(db.assets, "status")
        await _idx(db.assets, "activity_id")
        await _idx(db.assets, [("category", 1), ("created_at", -1)])
        await _idx(db.assets, [("status", 1), ("category", 1)])
        await _idx(db.assets, [("category", 1), ("asset_name", 1)])
        await _idx(db.assets, [("activity_id", 1), ("created_at", -1)])
        await _idx(db.assets, [("activity_id", 1), ("category", 1), ("created_at", -1)])
        # Offline snapshot delta sync: /assets/offline-snapshot filters by
        # activity_id + updated_at > since
        await _idx(db.assets, [("activity_id", 1), ("updated_at", -1)])
        # Snapshot feed sort {created_at:-1, id:1} — tanpa tiebreak id di indeks,
        # Mongo melakukan in-memory sort seluruh aset kegiatan di tiap halaman.
        await _idx(db.assets, [("activity_id", 1), ("created_at", -1), ("id", 1)])
        # Offline snapshot KEYSET (PR-OPT-G): paginasi cursor {id > c} sort {id:1}
        # difilter activity_id → seek O(log n), ganti $skip O(skip). Indeks ini
        # melayani prefix activity_id + range/sort id tanpa in-memory sort.
        await _idx(db.assets, [("activity_id", 1), ("id", 1)], name="snapshot_keyset_activity_id")
        try:
            await db.assets.create_index([
                ("asset_name", "text"), ("asset_code", "text"),
                ("serial_number", "text"), ("location", "text"), ("brand", "text")
            ])
        except Exception:
            pass
        await _idx(db.categories, "id", unique=True)
        await _idx(db.categories, "label")
        await _idx(db.categories, "kode_aset")
        await _idx(db.users, "username", unique=True)
        await _idx(db.users, "id", unique=True)
        await _idx(db.audit_logs, [("activity_id", 1), ("timestamp", -1)])
        await _idx(db.audit_logs, [("asset_id", 1), ("timestamp", -1)])
        await _idx(db.audit_logs, "timestamp")
        # Filter "Log Sistem"/per-aksi panel audit menyaring by action —
        # tanpa indeks ini tiap filter adalah COLLSCAN koleksi log terbesar.
        await _idx(db.audit_logs, [("action", 1), ("timestamp", -1)])
        # Row locks TTL index - auto-expires after expires_at
        await _idx(db.row_locks, "asset_id", unique=True)
        await _idx(db.row_locks, "expires_at", expireAfterSeconds=0)
        # Polling lock per kegiatan membaca row_locks langsung via activity_id
        await _idx(db.row_locks, "activity_id")
        # OTP store TTL index - auto-cleanup after 10min
        await _idx(db.otp_store, "email", unique=True)
        await _idx(db.otp_store, "created_at", expireAfterSeconds=660)
        # Pemantauan kuota email Resend: satu doc per (lingkup, periode) —
        # upsert $inc harian/bulanan andal & bebas duplikat.
        await _idx(db.email_usage, 
            [("lingkup", 1), ("periode", 1)], unique=True, name="email_usage_key")
        # Peta kolaboratif: share per-kegiatan + kontribusi (titik/komentar).
        await _idx(db.peta_shares, "id", unique=True, name="peta_share_id")
        await _idx(db.peta_shares, [("activity_id", 1), ("created_at", -1)],
                                          name="peta_share_activity")
        await _idx(db.peta_kolaborasi, "id", unique=True, name="peta_kontrib_id")
        await _idx(db.peta_kolaborasi, [("share_id", 1), ("created_at", 1)],
                                              name="peta_kontrib_share")
        # Idempotency keys TTL index - auto-cleanup after 24h (offline queues can
        # replay far beyond 5 minutes; keys must stay reserved until then)
        await _idx(db.idempotency_keys, "key", unique=True)
        try:
            # Older deployments created this TTL with 300s under the auto name —
            # drop it so the 24h TTL below can be created without option conflict
            await db.idempotency_keys.drop_index("created_at_1")
        except Exception:
            pass
        await _idx(db.idempotency_keys, 
            "created_at", expireAfterSeconds=86400, name="idem_created_at_ttl_24h"
        )
        # DEDUP IDEMPOTENSI PERMANEN (temuan audit G3): dokumen aset menyimpan
        # idem_key sejak dibuat, dan indeks unik PARSIAL ini menjadikannya
        # penanda anti-kembar yang tak pernah kedaluwarsa — cache respons 24 jam
        # di atas hanyalah jalur cepat. Parsial (hanya dokumen ber-idem_key
        # string) agar jutaan aset lama tanpa field itu tidak dianggap kembar.
        await _idx(db.assets, 
            "idem_key", unique=True, name="idem_key_unik",
            partialFilterExpression={"idem_key": {"$type": "string"}},
        )
        # Inventory activity indexes — required for fast list sort and satker filters
        # (without these the /inventory-activities and /satker-list calls do full COLLSCAN,
        # which is why the activity list page loaded slowly on deployed data).
        await _idx(db.inventory_activities, [("created_at", -1)])
        await _idx(db.inventory_activities, "kode_satker")
        await _idx(db.inventory_activities, "nama_satker")
        await _idx(db.inventory_activities, "nomor_surat")
        # Pengesahan lock guard: setiap mutasi aset melakukan satu lookup
        # {"id": ..., "status_pengesahan": "disahkan"} — id harus ber-indeks.
        await _idx(db.inventory_activities, "id", unique=True)

        # Master Satker (temuan C32): koleksi ini penjaga keunikan de-facto —
        # `find_one({"kode_satker": kode})` dipakai shared_utils (kop laporan),
        # auth_utils (validasi pengikatan akun), dan users.py. Tanpa indeks
        # unik, dua worker/dua admin bisa melahirkan dua master satu kode dan
        # kop dokumen resmi jadi tak deterministik. Dedupe DULU, baru unik.
        try:
            await _rapikan_duplikat_satker()
        except Exception as e:
            logger.error("Dedupe master satker gagal (indeks unik akan "
                         "jatuh ke fallback): %s", e)
        # Fallback boot lalu dibuang dulu: MongoDB menolak indeks kunci-sama
        # bernama-beda (IndexOptionsConflict 85) — tanpa drop ini, satu boot
        # yang pernah jatuh ke fallback MENGUNCI koleksi di non-unik selamanya.
        try:
            await db.satker.drop_index("satker_kode_lookup")
        except Exception:
            pass
        try:
            await db.satker.create_index("kode_satker", unique=True,
                                         name="satker_kode_unik")
        except Exception:
            # Masih ada duplikat yang tak terapikan otomatis: tetap beri
            # indeks agar lookup tak COLLSCAN, dan CATAT agar tampil di
            # /api/health/deep (pelaporannya terbukti hidup — uji perilaku
            # test_health_deep_perilaku.py).
            _KEGAGALAN_INDEKS.append({
                "koleksi": "satker", "indeks": "satker_kode_unik",
                "galat": "duplikat kode_satker tersisa — indeks unik ditunda"})
            await _idx(db.satker, "kode_satker", name="satker_kode_lookup")

        # komentar_aset (temuan C32): jalur daftar/hapus keduanya COLLSCAN,
        # dan `usulan_id` adalah penjaga idempotensi persetujuan usulan peta.
        await _idx(db.komentar_aset, "id", unique=True,
                   name="komentar_aset_id")
        await _idx(db.komentar_aset, [("activity_id", 1), ("created_at", 1)],
                   name="komentar_aset_kegiatan_waktu")
        # PARSIAL: `usulan_id` bisa "" untuk komentar non-usulan; unik polos
        # menolak yang kedua. Pola sama dengan idem_key_unik di bawah.
        try:
            await db.komentar_aset.create_index(
                "usulan_id", unique=True, name="komentar_usulan_unik",
                partialFilterExpression={"usulan_id": {"$gt": ""}})
        except Exception:
            await _idx(db.komentar_aset, "usulan_id",
                       name="komentar_usulan_lookup")
        # Kartu inventarisasi: riwayat pengesahan dicari per identitas aset
        await _idx(db.inventory_history, "kode_register")
        await _idx(db.inventory_history, [("asset_code", 1), ("NUP", 1)])
        await _idx(db.inventory_history, "activity_id")
        # Kodefikasi referensi barang: kode unik; list per level/induk
        await _idx(db.kodefikasi, "kode", unique=True)
        await _idx(db.kodefikasi, [("level", 1), ("kode", 1)])
        await _idx(db.kodefikasi, "parent_kode")
        # Persediaan: identitas (kode+NUP) unik PER SATKER (REVIEW-9 R3 —
        # selaras dup-check aplikasi di create_persediaan). Indeks unik GLOBAL
        # era lama dilepas dulu: tanpa ini insert satker lain yang lolos
        # dup-check per-satker meledak DuplicateKeyError 500.
        try:
            await db.persediaan.drop_index("kode_barang_1_nup_1")
        except Exception:
            pass
        await _idx(db.persediaan, 
            [("kode_satker", 1), ("kode_barang", 1), ("nup", 1)], unique=True)
        await _idx(db.persediaan, "id", unique=True)
        await _idx(db.persediaan, [("nama_barang", 1), ("kode_barang", 1)])
        # Jurnal transaksi persediaan: riwayat per barang, terbaru dulu
        await _idx(db.transaksi_persediaan, [("persediaan_id", 1), ("timestamp", -1)])
        await _idx(db.transaksi_persediaan, "timestamp")
        # Daftar Transaksi (filter kode → kunci `jenis`) & derivasi daftar
        # usang/rusak/tak dikuasai ({jenis: {$in: ...}}) — tanpa ini keduanya
        # memindai koleksi penuh.
        await _idx(db.transaksi_persediaan, [("jenis", 1), ("timestamp", -1)])
        # Pemeliharaan: riwayat per aset terbaru dulu; daftar global per tanggal
        await _idx(db.pemeliharaan, [("asset_id", 1), ("tanggal", -1)])
        await _idx(db.pemeliharaan, [("tanggal", -1), ("created_at", -1)])
        await _idx(db.pemeliharaan, "id", unique=True)
        # Jadwal pemeliharaan berkala: akses per aset + jalur id
        await _idx(db.jadwal_pemeliharaan, "asset_id")
        await _idx(db.jadwal_pemeliharaan, "id", unique=True)
        # Usulan penghapusan: cek usulan aktif per aset + daftar per status
        await _idx(db.usulan_penghapusan, [("asset_id", 1), ("status", 1)])
        await _idx(db.usulan_penghapusan, "id", unique=True)
        # Referensi masa manfaat penyusutan: satu entri per kelompok
        await _idx(db.masa_manfaat, "kode", unique=True)
        # Register pemanfaatan: urut jatuh tempo + jalur id
        await _idx(db.pemanfaatan, "berakhir")
        await _idx(db.pemanfaatan, "id", unique=True)
        # Usulan pemanfaatan/perpanjangan: cek usulan aktif per induk + id
        await _idx(db.pemanfaatan_usulan, [("pemanfaatan_id", 1), ("status", 1)])
        await _idx(db.pemanfaatan_usulan, "id", unique=True)
        # Register BA pemusnahan: urut tanggal + jalur id
        await _idx(db.pemusnahan, "tanggal_ba")
        await _idx(db.pemusnahan, "id", unique=True)
        # Usulan pemusnahan: cek duplikat aset dalam usulan berjalan + id
        await _idx(db.pemusnahan_usulan, [("aset.asset_id", 1), ("status", 1)])
        await _idx(db.pemusnahan_usulan, "id", unique=True)
        # Register pemindahtanganan: daftar per status + jalur id
        await _idx(db.pemindahtanganan, "status")
        await _idx(db.pemindahtanganan, "id", unique=True)
        # Register penganggaran: daftar per status/tahun + jalur id
        await _idx(db.penganggaran, [("status", 1), ("tahun_anggaran", 1)])
        await _idx(db.penganggaran, "id", unique=True)
        # Register perolehan pengadaan: urut tanggal BAST + jalur id
        await _idx(db.pengadaan, "tanggal_bast")
        await _idx(db.pengadaan, "id", unique=True)
        # Tiket BMN idle: cek duplikat aktif per aset + jalur id
        await _idx(db.bmn_idle, [("asset_id", 1), ("status", 1)])
        await _idx(db.bmn_idle, "id", unique=True)
        # Henti guna mandiri: cek tiket dihentikan aktif per aset + id
        await _idx(db.henti_guna, [("asset_id", 1), ("status", 1)])
        await _idx(db.henti_guna, "id", unique=True)
        # Register SK penetapan penggunaan: urut tanggal + jalur id
        await _idx(db.psp, "tanggal_sk")
        await _idx(db.psp, "id", unique=True)
        # Keterangan PSP per aset di daftar inventarisasi: SETIAP halaman daftar
        # aset (dan tiap halaman snapshot luring) menanyakan "SK mana yang
        # mencakup 50 id ini". Tanpa indeks multikey ini pertanyaan itu memindai
        # seluruh register pada tiap muat halaman.
        await _idx(db.psp, "aset.asset_id")
        # Tiket penertiban wasdal: daftar per status/tenggat + jalur id
        await _idx(db.penertiban, [("status", 1), ("tenggat", 1)])
        await _idx(db.penertiban, "id", unique=True)
        # Pemantauan insidentil wasdal: daftar per status + jalur id
        await _idx(db.pemantauan_insidentil, [("status", 1), ("tanggal_mulai", 1)])
        await _idx(db.pemantauan_insidentil, "id", unique=True)
        # Periode pelaporan: identitas unik per tahun+semester PER SATKER
        # (REVIEW-9 R15). Tiap satker menutup bukunya sendiri, jadi 2026-S1
        # sah dimiliki banyak satker. Indeks unik GLOBAL era lama dilepas dulu
        # — tanpa itu satker kedua yang lolos dup-check per-satker meledak
        # DuplicateKeyError 500 (pola sama seperti persediaan di atas).
        try:
            await db.periode_pelaporan.drop_index("kunci_unik_1")
        except Exception:
            pass
        await _idx(db.periode_pelaporan, 
            [("kode_satker", 1), ("kunci_unik", 1)], unique=True)
        await _idx(db.periode_pelaporan, "id", unique=True)
        # Kalender penganggaran: urut tenggat + jalur id
        await _idx(db.penganggaran_kalender, "tanggal")
        await _idx(db.penganggaran_kalender, "id", unique=True)
        # Register kasus pengamanan: kasus aktif per aset + jalur id
        await _idx(db.pengamanan_kasus, [("asset_id", 1), ("status", 1)])
        await _idx(db.pengamanan_kasus, "id", unique=True)
        # Arsip dokumen kepemilikan: daftar per aset + jalur id
        await _idx(db.pengamanan_dokumen, "asset_id")
        await _idx(db.pengamanan_dokumen, "id", unique=True)
        # Checklist pengamanan: satu per aset + jalur id
        await _idx(db.pengamanan_checklist, "asset_id", unique=True)
        await _idx(db.pengamanan_checklist, "id", unique=True)
        # Register polis asuransi BMN: daftar per aset/berakhir + jalur id
        await _idx(db.pengamanan_polis, [("asset_id", 1), ("berakhir", 1)])
        await _idx(db.pengamanan_polis, "id", unique=True)
        # Register usulan RKBMN per unit: daftar per tahun/status + jalur id
        await _idx(db.perencanaan_usulan, [("tahun_rkbmn", 1), ("status", 1)])
        await _idx(db.perencanaan_usulan, "id", unique=True)
        # Tiket proses alih status/penggunaan sementara: per status + jalur id
        await _idx(db.penggunaan_proses, [("jenis_proses", 1), ("status", 1)])
        await _idx(db.penggunaan_proses, "id", unique=True)
        # Register koreksi nilai penilaian: per aset/tanggal + jalur id
        await _idx(db.penilaian_koreksi, [("asset_id", 1), ("tanggal_dokumen", -1)])
        await _idx(db.penilaian_koreksi, "id", unique=True)
        # ── Indeks tambahan hasil audit performa (#409) ──
        # SIMAN: panel ringkasan menghitung 4x count per status; daftar selisih.
        await _idx(db.assets, "siman.status")
        await _idx(db.assets, [("activity_id", 1), ("siman.status", 1)])
        # Pemegang aset: rekap per NIP (Master Pegawai) & daftar aset per
        # pegawai; filter pengguna pada daftar aset (kolom "user").
        await _idx(db.assets, "pengguna_nip")
        await _idx(db.assets, "user")
        # Persuratan: buku agenda (filter jenis/status, urut tahun+no_agenda)
        # + jalur id pada setiap operasi surat/BAST/LPB (dulu COLLSCAN penuh).
        await _idx(db.surat, "id", unique=True)
        await _idx(db.surat, [("jenis", 1), ("status", 1)])
        await _idx(db.surat, [("jenis", 1), ("tahun", -1), ("no_agenda", -1)])
        # Penomoran per PERIODE + nomor sisipan: seed counter bulanan dan
        # pencarian jangkar sisipan menyaring per tanggal_surat dalam satu
        # tahun — tanpa indeks ini keduanya memindai seluruh buku agenda.
        await _idx(db.surat, [("jenis", 1), ("tahun", 1),
                                     ("tanggal_surat", 1)])
        # Relasi antar surat: keberlakuan massal per halaman (ke_id $in) +
        # timeline per surat (dari_id) — keduanya dipanggil di daftar agenda.
        await _idx(db.surat_relasi, "id", unique=True)
        await _idx(db.surat_relasi, "dari_id")
        await _idx(db.surat_relasi, "ke_id")
        # Master Pegawai: cek bentrok NIP saat impor massal + daftar per satker.
        await _idx(db.pegawai, "id", unique=True)
        await _idx(db.pegawai, "nip")
        await _idx(db.pegawai, [("kode_satker", 1), ("nama", 1)])
        # Kartu pegawai (UID e-KTP): lookup tap→pegawai via hash kandidat.
        # UNIK (multikey) menutup balapan dua admin mendaftarkan kartu sama
        # bersamaan; fallback non-unik bila data lama telanjur duplikat.
        try:
            await db.pegawai.create_index("kartu_uid_hashes", unique=True,
                                          sparse=True,
                                          name="unique_kartu_uid_hashes")
        except Exception:
            await db.pegawai.create_index("kartu_uid_hashes",
                                          name="kartu_uid_hashes_lookup")
        # Master Pejabat & Ruangan & Unit Kerja: jalur id (dipakai TTD/lookup).
        await _idx(db.pejabat, "id", unique=True)
        await _idx(db.ruangan, "id", unique=True)
        await _idx(db.unit_kerja, "id", unique=True)
        # Register impor SIMAN: riwayat terbaru dulu.
        await _idx(db.siman_imports, "waktu")
        # Register e-sign: daftar per pembuat, terbaru dulu.
        await _idx(db.signature_requests, "id", unique=True)
        await _idx(db.signature_requests, [("created_by", 1), ("created_at", -1)])

        # ── Indeks paginasi daftar yang belum tertutup (audit perf lanjutan) ──
        # Koleksi tumbuh yang DULU tanpa indeks kunci-sort → Mongo sort di memori
        # tiap halaman (COLLSCAN + in-memory sort), makin lambat seiring data.
        # Buku Barang (mutasi_bmn): daftar global urut tanggal buku; riwayat per
        # aset (KIB/timeline/LBP) urut tanggal buku.
        await _idx(db.mutasi_bmn, [("tanggal_buku", -1), ("created_at", -1)])
        await _idx(db.mutasi_bmn, [("asset_id", 1), ("tanggal_buku", -1)])
        # Riwayat LPB (db.lpb): daftar urut created_at + unduh ulang per id.
        try:
            await db.lpb.create_index("id", unique=True, name="unique_lpb_id")
        except Exception:
            await db.lpb.create_index("id", name="lpb_id_lookup")
        await _idx(db.lpb, [("created_at", -1)])
        # BAST serah terima: daftar urut created_at, lihat/unduh per id, badge
        # riwayat per aset (asset_ids multikey).
        try:
            await db.bast_serah_terima.create_index("id", unique=True, name="unique_bast_id")
        except Exception:
            await db.bast_serah_terima.create_index("id", name="bast_id_lookup")
        await _idx(db.bast_serah_terima, [("created_at", -1)])
        await _idx(db.bast_serah_terima, "asset_ids")
        # Buku agenda surat: sort {tahun,no_agenda} saat filter `jenis` TIDAK
        # dipakai — indeks (jenis,tahun,no_agenda) yang ada tak melayani sort ini.
        await _idx(db.surat, [("tahun", -1), ("no_agenda", -1)])
        # Job latar bersama (jobs.py): lookup per job_id + TTL auto-hapus dokumen
        # job > 7 hari (created_at BSON datetime) agar koleksi tak menumpuk.
        await _idx(db.background_jobs, "job_id", unique=True)
        await _idx(db.background_jobs, "created_at", expireAfterSeconds=7 * 86400)
        # Pusat Unduhan (routes/unduhan.py): lookup per id, daftar per pemilik
        # terbaru-dulu, dan TTL PER-DOKUMEN pada `hapus_pada` (dibuat + 30 hari,
        # expireAfterSeconds=0 = hapus tepat saat nilainya lewat) — hasil unduhan
        # "terurai jadi nol setelah 1 bulan"; blob GridFS-nya disapu
        # bersihkan_unduhan_kedaluwarsa() di loop pemeliharaan jobs.py.
        await _idx(db.unduhan, "unduhan_id", unique=True)
        await _idx(db.unduhan, [("dibuat_oleh", 1), ("created_at", -1)])
        await _idx(db.unduhan, "hapus_pada", expireAfterSeconds=0)
        # ── Indeks kunci-sort/filter daftar aset yang belum tertutup (audit perf) ──
        # get_assets menawarkan sort price/condition/eselon1 (dengan tiebreak id)
        # dan filter condition/eselon/stiker_status/inventory_status. Tanpa indeks,
        # sort GLOBAL (tanpa activity_id) = in-memory sort → berisiko gagal pada
        # dataset besar (batas sort agregasi), dan filter = partial scan.
        # purchase_price PALING berisiko (satu-satunya sort tanpa indeks apa pun).
        await _idx(db.assets, [("purchase_price", 1), ("id", 1)], name="sort_price_id")
        await _idx(db.assets, [("condition", 1), ("id", 1)], name="sort_condition_id")
        await _idx(db.assets, [("eselon1", 1), ("id", 1)], name="sort_eselon1_id")
        # Filter status lazim per-kegiatan (RHI/DBHI, cetak stiker).
        await _idx(db.assets, [("activity_id", 1), ("inventory_status", 1)])
        await _idx(db.assets, [("activity_id", 1), ("stiker_status", 1)])
        # ── Filter berat daftar aset per-kegiatan (analisis beban VPS 2026-08) ──
        # mongotop VPS menunjuk query assets dengan kombinasi activity_id +
        # location/eselon1/eselon2/condition/status sebagai pemakan CPU utama.
        # Indeks tunggal location/status/condition sudah ada tetapi planner
        # memilih indeks activity_id lalu MENYARING sisanya baris-per-baris —
        # kombinasi di bawah membuat filter selesai di indeks. eselon2 bahkan
        # belum berindeks sama sekali.
        await _idx(db.assets, [("activity_id", 1), ("condition", 1)])
        await _idx(db.assets, [("activity_id", 1), ("location", 1)])
        await _idx(db.assets, [("activity_id", 1), ("eselon1", 1)])
        await _idx(db.assets, [("activity_id", 1), ("eselon2", 1)])
        await _idx(db.assets, [("activity_id", 1), ("status", 1)])
        # GridFS: pembersih artifact-ekspor yatim (jobs.py) memindai fs.files pada
        # metadata.job_id tiap jam — tanpa indeks = COLLSCAN penuh, makin lambat
        # seiring bertambahnya foto. sparse: hanya dokumen ber-metadata.job_id.
        try:
            await db["fs.files"].create_index("metadata.job_id", sparse=True,
                                              name="gridfs_job_artifact")
        except Exception:
            pass
        # Sama untuk artifact Pusat Unduhan (routes/unduhan.py): sapuan retensi
        # memindai metadata.unduhan_id — tanpa indeks = COLLSCAN koleksi foto.
        try:
            await db["fs.files"].create_index("metadata.unduhan_id",
                                              sparse=True,
                                              name="gridfs_unduhan_artifact")
        except Exception:
            pass
        # Konverter WebP latar: mencari foto aset JPEG yang belum dikonversi
        # (metadata.content_type == "image/jpeg"). Tanpa indeks = COLLSCAN
        # fs.files tiap siklus; makin lambat seiring bertambahnya foto.
        try:
            await db["fs.files"].create_index("metadata.content_type",
                                              name="gridfs_content_type")
        except Exception:
            pass
        # Backup/restore single-flight: gerbang ATOMIK "hanya satu job aktif".
        # Unique HANYA untuk dokumen yang MEMBAWA active_lock (job queued/running);
        # job terminal meng-$unset lock → keluar dari index → slot terbuka lagi.
        # partialFilterExpression {$exists:true} kompatibel semua versi MongoDB
        # (hindari $in yang butuh MongoDB 6.0+). Cegah dua restore konkuren
        # merusak DB (wipe + reimport berselang).
        await _idx(db.backup_jobs, 
            "active_lock", unique=True,
            partialFilterExpression={"active_lock": {"$exists": True}},
            name="backup_jobs_active_lock_singleflight",
        )
        # SPASIAL (Fase 1): indeks geospasial PERTAMA di repo ini. Koordinat aset
        # tersimpan sebagai STRING dan tidak dapat diindeks; field `geo` adalah
        # turunan GeoJSON Point dari pasangan string itu (lihat spasial_utils.py).
        # Tanpa indeks ini setiap kueri berbasis area ($geoWithin/$geoIntersects
        # per-bbox peta) adalah full collection scan.
        #
        # CATATAN: indeks 2dsphere SELALU sparse — aset TANPA koordinat sah tidak
        # masuk indeks sama sekali. Itu memang yang diinginkan: mayoritas aset
        # belum berkoordinat, dan memaksanya masuk indeks hanya memboroskan RAM.
        await _idx(db.assets, [("geo", "2dsphere")], name="assets_geo_2dsphere")

        # SPASIAL (Fase 2): hierarki level & pohon. Indeks geometri (2dsphere pada
        # spasial_node) menyusul di Fase 3 saat geometri masuk.
        await _idx(db.spasial_level, "id", unique=True, name="spasial_level_id")
        await _idx(db.spasial_level, "ordinal_level", name="spasial_level_ordinal")
        await _idx(db.spasial_node, "id", unique=True, name="spasial_node_id")
        await _idx(db.spasial_node, 
            [("kode_satker", 1), ("ordinal_level", 1), ("status", 1)],
            name="spasial_node_satker_level")
        await _idx(db.spasial_node, "parent_id", name="spasial_node_parent")
        await _idx(db.spasial_node, "ancestors", name="spasial_node_ancestors")  # subtree 1-hop
        await _idx(db.spasial_node, "jalur", name="spasial_node_jalur")           # breadcrumb & prefix
        # Indeks pencarian kode (mendukung cek keunikan di aplikasi). SENGAJA tidak
        # unik — keunikan ditegakkan PER SATKER PER TIPE di rute (konvensi REVIEW-9
        # R9): dua satker boleh punya "GD-A", dan indeks unik global akan menolak
        # satker kedua sekaligus membocorkan eksistensi kode milik satker lain.
        # Konsisten dengan pola koleksi `ruangan`. Partial: node tanpa kode diabaikan.
        await _idx(db.spasial_node, 
            [("kode_satker", 1), ("tipe", 1), ("kode", 1)],
            partialFilterExpression={"kode": {"$exists": True, "$gt": ""}},
            name="spasial_node_kode_per_satker_tipe")
        # SPASIAL Fase 3: indeks geometri — inti deteksi lokasi otomatis
        # (tancap titik -> rantai wilayah) & render peta per-viewport.
        # 2dsphere SELALU sparse: node tanpa geometri (mis. baru disusun
        # strukturnya) tak masuk indeks sama sekali — memang diinginkan.
        await _idx(db.spasial_node, [("geometry", "2dsphere")],
                                           name="spasial_node_geometry_2dsphere")
        # Ordinal lantai per gedung: level switcher basement -> rooftop.
        await _idx(db.spasial_node, [("parent_id", 1), ("lantai.ordinal", 1)],
                                           name="spasial_node_lantai_ordinal")
        # Custody berlokasi (Fase 9): "aset apa saja di ruangan ini" — tanpa
        # indeks ini, membuka isi satu ruangan memindai SELURUH koleksi aset.
        # Sparse: hanya aset yang sudah ditempatkan yang masuk indeks.
        await _idx(db.assets, "lokasi_spasial.node_id", sparse=True,
                                     name="asset_lokasi_spasial_node")
        # Riwayat perpindahan per aset, terbaru dulu.
        await _idx(db.riwayat_lokasi_aset, 
            [("asset_id", 1), ("pada", -1)], name="riwayat_lokasi_aset_waktu")

        # IoT (Fase 11) — ingest posisi perangkat.
        #
        # UNIK obs_id = penegak IDEMPOTENSI, bukan sekadar optimasi. Pengiriman
        # IoT bersifat at-least-once: perangkat yang kehilangan sinyal MENGIRIM
        # ULANG batch yang sebenarnya sudah tiba. Tanpa indeks ini setiap
        # pengiriman ulang menggandakan jejak posisi, dan rute ingest yang
        # mengandalkan galat 11000 untuk menghitung duplikat akan diam-diam
        # melaporkan semuanya "tersimpan".
        await _idx(db.iot_observasi, "obs_id", unique=True,
                                            name="iot_observasi_obs_id")
        # TTL: penghapusan retensi dijalankan MongoDB sendiri, bukan job yang
        # bisa mati tanpa disadari — kepatuhan retensi UU PDP tak boleh
        # bergantung pada proses yang perlu diawasi manusia. `kedaluwarsa_pada`
        # diisi rute ingest dari privasi_utils.batas_retensi(), jadi angka
        # retensi hanya hidup di SATU tempat.
        await _idx(db.iot_observasi, "kedaluwarsa_pada",
                                            expireAfterSeconds=0,
                                            name="iot_observasi_ttl")
        # Riwayat posisi per perangkat, terbaru dulu (dipakai daftar perangkat
        # untuk membaca observasi TERAKHIR tiap perangkat — tanpa ini, membuka
        # daftar berisi N perangkat memindai seluruh koleksi observasi N kali).
        await _idx(db.iot_observasi, [("device_id", 1), ("ts_server", -1)],
                                            name="iot_observasi_device_waktu")
        await _idx(db.iot_perangkat, "id", unique=True,
                                            name="iot_perangkat_id")
        # Autentikasi perangkat mencari lewat HASH token pada tiap batch masuk —
        # jalur terpanas di modul ini.
        await _idx(db.iot_perangkat, "token_hash",
                                            name="iot_perangkat_token_hash")
        await _idx(db.iot_perangkat, [("kode_satker", 1), ("created_at", -1)],
                                            name="iot_perangkat_satker_waktu")

        # Izin darurat (Fase 14) — dibaca pada SETIAP batch masuk untuk perangkat
        # yang sedang dibuka presisinya, dan dijadikan register jejak permanen.
        await _idx(db.iot_izin_darurat, "id", unique=True,
                                               name="iot_izin_darurat_id")
        await _idx(db.iot_izin_darurat, 
            [("device_id", 1), ("status", 1), ("berlaku_sampai", -1)],
            name="iot_izin_darurat_aktif")
        await _idx(db.iot_izin_darurat, 
            [("kode_satker", 1), ("diminta_pada", -1)],
            name="iot_izin_darurat_satker")

        # GEOFENCE (Fase 12). Aturan dibaca pada SETIAP batch masuk — jalur
        # terpanas kedua setelah autentikasi perangkat.
        await _idx(db.iot_geofence_aturan, "id", unique=True,
                                                  name="geofence_aturan_id")
        await _idx(db.iot_geofence_aturan, [("device_id", 1), ("aktif", 1)],
                                                  name="geofence_aturan_device")
        await _idx(db.iot_geofence_aturan, [("kode_satker", 1), ("created_at", -1)],
                                                  name="geofence_aturan_satker")
        # UNIK (aturan, perangkat): status histeresis harus TUNGGAL per pagar.
        # Dua baris untuk pasangan yang sama berarti dua mesin status berjalan
        # bergantian, saling menimpa, dan dwell tak pernah matang — geofence
        # yang tampak berjalan tetapi tak pernah memberi peringatan.
        await _idx(db.iot_geofence_state, [("aturan_id", 1), ("device_id", 1)],
                                                 unique=True,
                                                 name="geofence_state_kunci")
        await _idx(db.iot_geofence_event, "id", unique=True,
                                                 name="geofence_event_id")
        # Register peringatan: daftar per satker terbaru dulu + hitung yang
        # belum dibaca (badge). Partial pada `dibaca:false` menjaga indeks tetap
        # kecil — yang sudah dibaca tak pernah dikueri lewat jalur ini.
        await _idx(db.iot_geofence_event, 
            [("kode_satker", 1), ("dibuat_pada", -1)], name="geofence_event_satker")
        await _idx(db.iot_geofence_event, 
            [("kode_satker", 1), ("dibaca", 1)],
            partialFilterExpression={"dibaca": False},
            name="geofence_event_belum_dibaca")
        # Penjaga idempotensi sapuan `dwell_terlampaui`: satu peringatan per
        # KEPERGIAN, bukan satu per jam selama aset masih hilang. WAJIB unique —
        # loop pemeliharaan berjalan di SETIAP worker uvicorn, jadi cek-lalu-
        # tulis di aplikasi bisa dilewati dua sapuan yang nyaris serempak.
        # Partial: hanya event dwell yang punya `sejak`; jenis lain tak
        # tersentuh aturan keunikan ini.
        await _idx(db.iot_geofence_event, 
            [("aturan_id", 1), ("sejak", 1)], unique=True,
            partialFilterExpression={"jenis": "dwell_terlampaui"},
            name="geofence_event_dwell_unik")

        # OPNAME LEWAT SCAN STIKER (Fase 11).
        #
        # UNIK scan_id = penegak idempotensi antrean luring. Petugas memindai di
        # ruangan tanpa sinyal; antrean PWA mengirim ulang isi yang sama saat
        # sinyal berkedip. Tanpa indeks ini satu pemindaian melahirkan beberapa
        # baris, dan rekap opname melaporkan lebih banyak "terpindai" daripada
        # barang yang benar-benar dilihat petugas. Partial pada tipe string:
        # dokumen era-lama tanpa scan_id tak boleh saling bertabrakan sebagai
        # null kembar.
        await _idx(db.opname_scan, 
            "scan_id", unique=True, name="opname_scan_idem",
            partialFilterExpression={"scan_id": {"$type": "string"}})
        await _idx(db.opname_scan, "id", unique=True, name="opname_scan_id")
        # Rekonsiliasi membaca "scan di lingkup node ini sejak tanggal X" —
        # bentuk kueri tetap halaman itu.
        await _idx(db.opname_scan, [("node_id", 1), ("pada", -1)],
                                          name="opname_scan_node_waktu")
        # Riwayat pemindaian per aset (terbaru dulu) di panel detail aset.
        await _idx(db.opname_scan, [("asset_id", 1), ("pada", -1)],
                                          name="opname_scan_aset_waktu")
        await _idx(db.opname_scan, [("kode_satker", 1), ("pada", -1)],
                                          name="opname_scan_satker_waktu")
        # TAUTAN PENDEK (/s/{kode}).
        #
        # UNIK kode = penegak keunikan yang dipakai buat_tautan_pendek() untuk
        # mendeteksi tabrakan lalu mencoba kode lain. Tanpa indeks ini dua
        # tautan bisa memakai kode sama dan salah satunya mengalihkan ke
        # dokumen ORANG LAIN — bukan sekadar tautan mati.
        await _idx(db.tautan_pendek, "kode", unique=True,
                                            name="tautan_pendek_kode")
        # Pencabutan massal saat permintaan TTD dibatalkan / link diterbitkan
        # ulang: cari semua tautan satu dokumen sekaligus.
        await _idx(db.tautan_pendek, [("jenis", 1), ("ref", 1)],
                                            name="tautan_pendek_jenis_ref")
        if _KEGAGALAN_INDEKS:
            logger.error(
                "Pembuatan indeks selesai dengan %d KEGAGALAN — kueri terkait "
                "akan memindai koleksi penuh. Lihat /api/health/deep "
                "checks.indexes untuk daftarnya.", len(_KEGAGALAN_INDEKS))
        else:
            logger.info("Database indexes created successfully")
    except Exception as e:
        # Jaring terakhir untuk galat NON-indeks (koneksi putus di tengah,
        # dsb.) — kegagalan per-indeks sudah ditangani _idx dan TIDAK sampai
        # ke sini. Tetap dicatat sebagai kegagalan agar health check tahu.
        _KEGAGALAN_INDEKS.append({"koleksi": "-", "indeks": "-",
                                  "galat": f"pembuatan indeks terhenti: {e}"[:200]})
        logger.error(f"Error creating indexes: {e}")
