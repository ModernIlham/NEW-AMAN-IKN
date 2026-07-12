"""Database index creation — extracted from server.py to break the circular
import with routes/backup.py (which re-creates indexes after a restore).

Any module that needs to (re)build indexes should import from here, NOT from
`server`.
"""
import logging

from db import db

logger = logging.getLogger(__name__)


async def create_indexes() -> None:
    """Create database indexes for optimized query performance."""
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
        await db.assets.create_index(
            [("asset_code", 1), ("NUP", 1), ("activity_id", 1)],
            unique=True, name="unique_asset_code_nup_activity"
        )
        await db.assets.create_index([("kode_register", 1), ("activity_id", 1)], name="kode_register_activity")
        await db.assets.create_index("asset_name")
        await db.assets.create_index("category")
        await db.assets.create_index("created_at")
        await db.assets.create_index("location")
        await db.assets.create_index("serial_number")
        await db.assets.create_index("status")
        await db.assets.create_index("activity_id")
        await db.assets.create_index([("category", 1), ("created_at", -1)])
        await db.assets.create_index([("status", 1), ("category", 1)])
        await db.assets.create_index([("category", 1), ("asset_name", 1)])
        await db.assets.create_index([("activity_id", 1), ("created_at", -1)])
        await db.assets.create_index([("activity_id", 1), ("category", 1), ("created_at", -1)])
        # Offline snapshot delta sync: /assets/offline-snapshot filters by
        # activity_id + updated_at > since
        await db.assets.create_index([("activity_id", 1), ("updated_at", -1)])
        # Snapshot feed sort {created_at:-1, id:1} — tanpa tiebreak id di indeks,
        # Mongo melakukan in-memory sort seluruh aset kegiatan di tiap halaman.
        await db.assets.create_index([("activity_id", 1), ("created_at", -1), ("id", 1)])
        try:
            await db.assets.create_index([
                ("asset_name", "text"), ("asset_code", "text"),
                ("serial_number", "text"), ("location", "text"), ("brand", "text")
            ])
        except Exception:
            pass
        await db.categories.create_index("id", unique=True)
        await db.categories.create_index("label")
        await db.categories.create_index("kode_aset")
        await db.users.create_index("username", unique=True)
        await db.users.create_index("id", unique=True)
        await db.audit_logs.create_index([("activity_id", 1), ("timestamp", -1)])
        await db.audit_logs.create_index([("asset_id", 1), ("timestamp", -1)])
        await db.audit_logs.create_index("timestamp")
        # Row locks TTL index - auto-expires after expires_at
        await db.row_locks.create_index("asset_id", unique=True)
        await db.row_locks.create_index("expires_at", expireAfterSeconds=0)
        # Polling lock per kegiatan membaca row_locks langsung via activity_id
        await db.row_locks.create_index("activity_id")
        # OTP store TTL index - auto-cleanup after 10min
        await db.otp_store.create_index("email", unique=True)
        await db.otp_store.create_index("created_at", expireAfterSeconds=660)
        # Idempotency keys TTL index - auto-cleanup after 24h (offline queues can
        # replay far beyond 5 minutes; keys must stay reserved until then)
        await db.idempotency_keys.create_index("key", unique=True)
        try:
            # Older deployments created this TTL with 300s under the auto name —
            # drop it so the 24h TTL below can be created without option conflict
            await db.idempotency_keys.drop_index("created_at_1")
        except Exception:
            pass
        await db.idempotency_keys.create_index(
            "created_at", expireAfterSeconds=86400, name="idem_created_at_ttl_24h"
        )
        # Inventory activity indexes — required for fast list sort and satker filters
        # (without these the /inventory-activities and /satker-list calls do full COLLSCAN,
        # which is why the activity list page loaded slowly on deployed data).
        await db.inventory_activities.create_index([("created_at", -1)])
        await db.inventory_activities.create_index("kode_satker")
        await db.inventory_activities.create_index("nama_satker")
        await db.inventory_activities.create_index("nomor_surat")
        # Pengesahan lock guard: setiap mutasi aset melakukan satu lookup
        # {"id": ..., "status_pengesahan": "disahkan"} — id harus ber-indeks.
        await db.inventory_activities.create_index("id", unique=True)
        # Kartu inventarisasi: riwayat pengesahan dicari per identitas aset
        await db.inventory_history.create_index("kode_register")
        await db.inventory_history.create_index([("asset_code", 1), ("NUP", 1)])
        await db.inventory_history.create_index("activity_id")
        # Kodefikasi referensi barang: kode unik; list per level/induk
        await db.kodefikasi.create_index("kode", unique=True)
        await db.kodefikasi.create_index([("level", 1), ("kode", 1)])
        await db.kodefikasi.create_index("parent_kode")
        # Persediaan: identitas (kode+NUP) unik; jalur akses id; sort daftar
        await db.persediaan.create_index([("kode_barang", 1), ("nup", 1)], unique=True)
        await db.persediaan.create_index("id", unique=True)
        await db.persediaan.create_index([("nama_barang", 1), ("kode_barang", 1)])
        # Jurnal transaksi persediaan: riwayat per barang, terbaru dulu
        await db.transaksi_persediaan.create_index([("persediaan_id", 1), ("timestamp", -1)])
        await db.transaksi_persediaan.create_index("timestamp")
        # Pemeliharaan: riwayat per aset terbaru dulu; daftar global per tanggal
        await db.pemeliharaan.create_index([("asset_id", 1), ("tanggal", -1)])
        await db.pemeliharaan.create_index([("tanggal", -1), ("created_at", -1)])
        await db.pemeliharaan.create_index("id", unique=True)
        # Jadwal pemeliharaan berkala: akses per aset + jalur id
        await db.jadwal_pemeliharaan.create_index("asset_id")
        await db.jadwal_pemeliharaan.create_index("id", unique=True)
        # Usulan penghapusan: cek usulan aktif per aset + daftar per status
        await db.usulan_penghapusan.create_index([("asset_id", 1), ("status", 1)])
        await db.usulan_penghapusan.create_index("id", unique=True)
        # Referensi masa manfaat penyusutan: satu entri per kelompok
        await db.masa_manfaat.create_index("kode", unique=True)
        # Register pemanfaatan: urut jatuh tempo + jalur id
        await db.pemanfaatan.create_index("berakhir")
        await db.pemanfaatan.create_index("id", unique=True)
        # Register BA pemusnahan: urut tanggal + jalur id
        await db.pemusnahan.create_index("tanggal_ba")
        await db.pemusnahan.create_index("id", unique=True)
        # Register pemindahtanganan: daftar per status + jalur id
        await db.pemindahtanganan.create_index("status")
        await db.pemindahtanganan.create_index("id", unique=True)
        # Register penganggaran: daftar per status/tahun + jalur id
        await db.penganggaran.create_index([("status", 1), ("tahun_anggaran", 1)])
        await db.penganggaran.create_index("id", unique=True)
        # Register perolehan pengadaan: urut tanggal BAST + jalur id
        await db.pengadaan.create_index("tanggal_bast")
        await db.pengadaan.create_index("id", unique=True)
        # Tiket BMN idle: cek duplikat aktif per aset + jalur id
        await db.bmn_idle.create_index([("asset_id", 1), ("status", 1)])
        await db.bmn_idle.create_index("id", unique=True)
        # Register SK penetapan penggunaan: urut tanggal + jalur id
        await db.psp.create_index("tanggal_sk")
        await db.psp.create_index("id", unique=True)
        # Tiket penertiban wasdal: daftar per status/tenggat + jalur id
        await db.penertiban.create_index([("status", 1), ("tenggat", 1)])
        await db.penertiban.create_index("id", unique=True)
        # Pemantauan insidentil wasdal: daftar per status + jalur id
        await db.pemantauan_insidentil.create_index([("status", 1), ("tanggal_mulai", 1)])
        await db.pemantauan_insidentil.create_index("id", unique=True)
        # Periode pelaporan: identitas unik per tahun+jenis + jalur id
        await db.periode_pelaporan.create_index("kunci_unik", unique=True)
        await db.periode_pelaporan.create_index("id", unique=True)
        # Kalender penganggaran: urut tenggat + jalur id
        await db.penganggaran_kalender.create_index("tanggal")
        await db.penganggaran_kalender.create_index("id", unique=True)
        # Register kasus pengamanan: kasus aktif per aset + jalur id
        await db.pengamanan_kasus.create_index([("asset_id", 1), ("status", 1)])
        await db.pengamanan_kasus.create_index("id", unique=True)
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
