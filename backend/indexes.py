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
        # Filter rentang TANGGAL BELI (purchase_date) di daftar aset & ekspor
        # geo — tanpa indeks, range filter = full collection scan.
        await db.assets.create_index("purchase_date")
        await db.assets.create_index([("activity_id", 1), ("purchase_date", 1)])
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
        # Offline snapshot KEYSET (PR-OPT-G): paginasi cursor {id > c} sort {id:1}
        # difilter activity_id → seek O(log n), ganti $skip O(skip). Indeks ini
        # melayani prefix activity_id + range/sort id tanpa in-memory sort.
        await db.assets.create_index([("activity_id", 1), ("id", 1)], name="snapshot_keyset_activity_id")
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
        # Arsip dokumen kepemilikan: daftar per aset + jalur id
        await db.pengamanan_dokumen.create_index("asset_id")
        await db.pengamanan_dokumen.create_index("id", unique=True)
        # Checklist pengamanan: satu per aset + jalur id
        await db.pengamanan_checklist.create_index("asset_id", unique=True)
        await db.pengamanan_checklist.create_index("id", unique=True)
        # Register polis asuransi BMN: daftar per aset/berakhir + jalur id
        await db.pengamanan_polis.create_index([("asset_id", 1), ("berakhir", 1)])
        await db.pengamanan_polis.create_index("id", unique=True)
        # Register usulan RKBMN per unit: daftar per tahun/status + jalur id
        await db.perencanaan_usulan.create_index([("tahun_rkbmn", 1), ("status", 1)])
        await db.perencanaan_usulan.create_index("id", unique=True)
        # Tiket proses alih status/penggunaan sementara: per status + jalur id
        await db.penggunaan_proses.create_index([("jenis_proses", 1), ("status", 1)])
        await db.penggunaan_proses.create_index("id", unique=True)
        # Register koreksi nilai penilaian: per aset/tanggal + jalur id
        await db.penilaian_koreksi.create_index([("asset_id", 1), ("tanggal_dokumen", -1)])
        await db.penilaian_koreksi.create_index("id", unique=True)
        # ── Indeks tambahan hasil audit performa (#409) ──
        # SIMAN: panel ringkasan menghitung 4x count per status; daftar selisih.
        await db.assets.create_index("siman.status")
        await db.assets.create_index([("activity_id", 1), ("siman.status", 1)])
        # Pemegang aset: rekap per NIP (Master Pegawai) & daftar aset per
        # pegawai; filter pengguna pada daftar aset (kolom "user").
        await db.assets.create_index("pengguna_nip")
        await db.assets.create_index("user")
        # Persuratan: buku agenda (filter jenis/status, urut tahun+no_agenda)
        # + jalur id pada setiap operasi surat/BAST/LPB (dulu COLLSCAN penuh).
        await db.surat.create_index("id", unique=True)
        await db.surat.create_index([("jenis", 1), ("status", 1)])
        await db.surat.create_index([("jenis", 1), ("tahun", -1), ("no_agenda", -1)])
        # Master Pegawai: cek bentrok NIP saat impor massal + daftar per satker.
        await db.pegawai.create_index("id", unique=True)
        await db.pegawai.create_index("nip")
        await db.pegawai.create_index([("kode_satker", 1), ("nama", 1)])
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
        await db.pejabat.create_index("id", unique=True)
        await db.ruangan.create_index("id", unique=True)
        await db.unit_kerja.create_index("id", unique=True)
        # Register impor SIMAN: riwayat terbaru dulu.
        await db.siman_imports.create_index("waktu")
        # Register e-sign: daftar per pembuat, terbaru dulu.
        await db.signature_requests.create_index("id", unique=True)
        await db.signature_requests.create_index([("created_by", 1), ("created_at", -1)])

        # ── Indeks paginasi daftar yang belum tertutup (audit perf lanjutan) ──
        # Koleksi tumbuh yang DULU tanpa indeks kunci-sort → Mongo sort di memori
        # tiap halaman (COLLSCAN + in-memory sort), makin lambat seiring data.
        # Buku Barang (mutasi_bmn): daftar global urut tanggal buku; riwayat per
        # aset (KIB/timeline/LBP) urut tanggal buku.
        await db.mutasi_bmn.create_index([("tanggal_buku", -1), ("created_at", -1)])
        await db.mutasi_bmn.create_index([("asset_id", 1), ("tanggal_buku", -1)])
        # Riwayat LPB (db.lpb): daftar urut created_at + unduh ulang per id.
        try:
            await db.lpb.create_index("id", unique=True, name="unique_lpb_id")
        except Exception:
            await db.lpb.create_index("id", name="lpb_id_lookup")
        await db.lpb.create_index([("created_at", -1)])
        # BAST serah terima: daftar urut created_at, lihat/unduh per id, badge
        # riwayat per aset (asset_ids multikey).
        try:
            await db.bast_serah_terima.create_index("id", unique=True, name="unique_bast_id")
        except Exception:
            await db.bast_serah_terima.create_index("id", name="bast_id_lookup")
        await db.bast_serah_terima.create_index([("created_at", -1)])
        await db.bast_serah_terima.create_index("asset_ids")
        # Buku agenda surat: sort {tahun,no_agenda} saat filter `jenis` TIDAK
        # dipakai — indeks (jenis,tahun,no_agenda) yang ada tak melayani sort ini.
        await db.surat.create_index([("tahun", -1), ("no_agenda", -1)])
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
