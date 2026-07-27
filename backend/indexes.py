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
        # Filter "Log Sistem"/per-aksi panel audit menyaring by action —
        # tanpa indeks ini tiap filter adalah COLLSCAN koleksi log terbesar.
        await db.audit_logs.create_index([("action", 1), ("timestamp", -1)])
        # Row locks TTL index - auto-expires after expires_at
        await db.row_locks.create_index("asset_id", unique=True)
        await db.row_locks.create_index("expires_at", expireAfterSeconds=0)
        # Polling lock per kegiatan membaca row_locks langsung via activity_id
        await db.row_locks.create_index("activity_id")
        # OTP store TTL index - auto-cleanup after 10min
        await db.otp_store.create_index("email", unique=True)
        await db.otp_store.create_index("created_at", expireAfterSeconds=660)
        # Pemantauan kuota email Resend: satu doc per (lingkup, periode) —
        # upsert $inc harian/bulanan andal & bebas duplikat.
        await db.email_usage.create_index(
            [("lingkup", 1), ("periode", 1)], unique=True, name="email_usage_key")
        # Peta kolaboratif: share per-kegiatan + kontribusi (titik/komentar).
        await db.peta_shares.create_index("id", unique=True, name="peta_share_id")
        await db.peta_shares.create_index([("activity_id", 1), ("created_at", -1)],
                                          name="peta_share_activity")
        await db.peta_kolaborasi.create_index("id", unique=True, name="peta_kontrib_id")
        await db.peta_kolaborasi.create_index([("share_id", 1), ("created_at", 1)],
                                              name="peta_kontrib_share")
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
        # DEDUP IDEMPOTENSI PERMANEN (temuan audit G3): dokumen aset menyimpan
        # idem_key sejak dibuat, dan indeks unik PARSIAL ini menjadikannya
        # penanda anti-kembar yang tak pernah kedaluwarsa — cache respons 24 jam
        # di atas hanyalah jalur cepat. Parsial (hanya dokumen ber-idem_key
        # string) agar jutaan aset lama tanpa field itu tidak dianggap kembar.
        await db.assets.create_index(
            "idem_key", unique=True, name="idem_key_unik",
            partialFilterExpression={"idem_key": {"$type": "string"}},
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
        # Persediaan: identitas (kode+NUP) unik PER SATKER (REVIEW-9 R3 —
        # selaras dup-check aplikasi di create_persediaan). Indeks unik GLOBAL
        # era lama dilepas dulu: tanpa ini insert satker lain yang lolos
        # dup-check per-satker meledak DuplicateKeyError 500.
        try:
            await db.persediaan.drop_index("kode_barang_1_nup_1")
        except Exception:
            pass
        await db.persediaan.create_index(
            [("kode_satker", 1), ("kode_barang", 1), ("nup", 1)], unique=True)
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
        # Periode pelaporan: identitas unik per tahun+semester PER SATKER
        # (REVIEW-9 R15). Tiap satker menutup bukunya sendiri, jadi 2026-S1
        # sah dimiliki banyak satker. Indeks unik GLOBAL era lama dilepas dulu
        # — tanpa itu satker kedua yang lolos dup-check per-satker meledak
        # DuplicateKeyError 500 (pola sama seperti persediaan di atas).
        try:
            await db.periode_pelaporan.drop_index("kunci_unik_1")
        except Exception:
            pass
        await db.periode_pelaporan.create_index(
            [("kode_satker", 1), ("kunci_unik", 1)], unique=True)
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
        # Job latar bersama (jobs.py): lookup per job_id + TTL auto-hapus dokumen
        # job > 7 hari (created_at BSON datetime) agar koleksi tak menumpuk.
        await db.background_jobs.create_index("job_id", unique=True)
        await db.background_jobs.create_index("created_at", expireAfterSeconds=7 * 86400)
        # ── Indeks kunci-sort/filter daftar aset yang belum tertutup (audit perf) ──
        # get_assets menawarkan sort price/condition/eselon1 (dengan tiebreak id)
        # dan filter condition/eselon/stiker_status/inventory_status. Tanpa indeks,
        # sort GLOBAL (tanpa activity_id) = in-memory sort → berisiko gagal pada
        # dataset besar (batas sort agregasi), dan filter = partial scan.
        # purchase_price PALING berisiko (satu-satunya sort tanpa indeks apa pun).
        await db.assets.create_index([("purchase_price", 1), ("id", 1)], name="sort_price_id")
        await db.assets.create_index([("condition", 1), ("id", 1)], name="sort_condition_id")
        await db.assets.create_index([("eselon1", 1), ("id", 1)], name="sort_eselon1_id")
        # Filter status lazim per-kegiatan (RHI/DBHI, cetak stiker).
        await db.assets.create_index([("activity_id", 1), ("inventory_status", 1)])
        await db.assets.create_index([("activity_id", 1), ("stiker_status", 1)])
        # GridFS: pembersih artifact-ekspor yatim (jobs.py) memindai fs.files pada
        # metadata.job_id tiap jam — tanpa indeks = COLLSCAN penuh, makin lambat
        # seiring bertambahnya foto. sparse: hanya dokumen ber-metadata.job_id.
        try:
            await db["fs.files"].create_index("metadata.job_id", sparse=True,
                                              name="gridfs_job_artifact")
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
        await db.backup_jobs.create_index(
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
        await db.assets.create_index([("geo", "2dsphere")], name="assets_geo_2dsphere")

        # SPASIAL (Fase 2): hierarki level & pohon. Indeks geometri (2dsphere pada
        # spasial_node) menyusul di Fase 3 saat geometri masuk.
        await db.spasial_level.create_index("id", unique=True, name="spasial_level_id")
        await db.spasial_level.create_index("ordinal_level", name="spasial_level_ordinal")
        await db.spasial_node.create_index("id", unique=True, name="spasial_node_id")
        await db.spasial_node.create_index(
            [("kode_satker", 1), ("ordinal_level", 1), ("status", 1)],
            name="spasial_node_satker_level")
        await db.spasial_node.create_index("parent_id", name="spasial_node_parent")
        await db.spasial_node.create_index("ancestors", name="spasial_node_ancestors")  # subtree 1-hop
        await db.spasial_node.create_index("jalur", name="spasial_node_jalur")           # breadcrumb & prefix
        # Indeks pencarian kode (mendukung cek keunikan di aplikasi). SENGAJA tidak
        # unik — keunikan ditegakkan PER SATKER PER TIPE di rute (konvensi REVIEW-9
        # R9): dua satker boleh punya "GD-A", dan indeks unik global akan menolak
        # satker kedua sekaligus membocorkan eksistensi kode milik satker lain.
        # Konsisten dengan pola koleksi `ruangan`. Partial: node tanpa kode diabaikan.
        await db.spasial_node.create_index(
            [("kode_satker", 1), ("tipe", 1), ("kode", 1)],
            partialFilterExpression={"kode": {"$exists": True, "$gt": ""}},
            name="spasial_node_kode_per_satker_tipe")
        # SPASIAL Fase 3: indeks geometri — inti deteksi lokasi otomatis
        # (tancap titik -> rantai wilayah) & render peta per-viewport.
        # 2dsphere SELALU sparse: node tanpa geometri (mis. baru disusun
        # strukturnya) tak masuk indeks sama sekali — memang diinginkan.
        await db.spasial_node.create_index([("geometry", "2dsphere")],
                                           name="spasial_node_geometry_2dsphere")
        # Ordinal lantai per gedung: level switcher basement -> rooftop.
        await db.spasial_node.create_index([("parent_id", 1), ("lantai.ordinal", 1)],
                                           name="spasial_node_lantai_ordinal")
        # Custody berlokasi (Fase 9): "aset apa saja di ruangan ini" — tanpa
        # indeks ini, membuka isi satu ruangan memindai SELURUH koleksi aset.
        # Sparse: hanya aset yang sudah ditempatkan yang masuk indeks.
        await db.assets.create_index("lokasi_spasial.node_id", sparse=True,
                                     name="asset_lokasi_spasial_node")
        # Riwayat perpindahan per aset, terbaru dulu.
        await db.riwayat_lokasi_aset.create_index(
            [("asset_id", 1), ("pada", -1)], name="riwayat_lokasi_aset_waktu")

        # IoT (Fase 11) — ingest posisi perangkat.
        #
        # UNIK obs_id = penegak IDEMPOTENSI, bukan sekadar optimasi. Pengiriman
        # IoT bersifat at-least-once: perangkat yang kehilangan sinyal MENGIRIM
        # ULANG batch yang sebenarnya sudah tiba. Tanpa indeks ini setiap
        # pengiriman ulang menggandakan jejak posisi, dan rute ingest yang
        # mengandalkan galat 11000 untuk menghitung duplikat akan diam-diam
        # melaporkan semuanya "tersimpan".
        await db.iot_observasi.create_index("obs_id", unique=True,
                                            name="iot_observasi_obs_id")
        # TTL: penghapusan retensi dijalankan MongoDB sendiri, bukan job yang
        # bisa mati tanpa disadari — kepatuhan retensi UU PDP tak boleh
        # bergantung pada proses yang perlu diawasi manusia. `kedaluwarsa_pada`
        # diisi rute ingest dari privasi_utils.batas_retensi(), jadi angka
        # retensi hanya hidup di SATU tempat.
        await db.iot_observasi.create_index("kedaluwarsa_pada",
                                            expireAfterSeconds=0,
                                            name="iot_observasi_ttl")
        # Riwayat posisi per perangkat, terbaru dulu (dipakai daftar perangkat
        # untuk membaca observasi TERAKHIR tiap perangkat — tanpa ini, membuka
        # daftar berisi N perangkat memindai seluruh koleksi observasi N kali).
        await db.iot_observasi.create_index([("device_id", 1), ("ts_server", -1)],
                                            name="iot_observasi_device_waktu")
        await db.iot_perangkat.create_index("id", unique=True,
                                            name="iot_perangkat_id")
        # Autentikasi perangkat mencari lewat HASH token pada tiap batch masuk —
        # jalur terpanas di modul ini.
        await db.iot_perangkat.create_index("token_hash",
                                            name="iot_perangkat_token_hash")
        await db.iot_perangkat.create_index([("kode_satker", 1), ("created_at", -1)],
                                            name="iot_perangkat_satker_waktu")

        # Izin darurat (Fase 14) — dibaca pada SETIAP batch masuk untuk perangkat
        # yang sedang dibuka presisinya, dan dijadikan register jejak permanen.
        await db.iot_izin_darurat.create_index("id", unique=True,
                                               name="iot_izin_darurat_id")
        await db.iot_izin_darurat.create_index(
            [("device_id", 1), ("status", 1), ("berlaku_sampai", -1)],
            name="iot_izin_darurat_aktif")
        await db.iot_izin_darurat.create_index(
            [("kode_satker", 1), ("diminta_pada", -1)],
            name="iot_izin_darurat_satker")

        # GEOFENCE (Fase 12). Aturan dibaca pada SETIAP batch masuk — jalur
        # terpanas kedua setelah autentikasi perangkat.
        await db.iot_geofence_aturan.create_index("id", unique=True,
                                                  name="geofence_aturan_id")
        await db.iot_geofence_aturan.create_index([("device_id", 1), ("aktif", 1)],
                                                  name="geofence_aturan_device")
        await db.iot_geofence_aturan.create_index([("kode_satker", 1), ("created_at", -1)],
                                                  name="geofence_aturan_satker")
        # UNIK (aturan, perangkat): status histeresis harus TUNGGAL per pagar.
        # Dua baris untuk pasangan yang sama berarti dua mesin status berjalan
        # bergantian, saling menimpa, dan dwell tak pernah matang — geofence
        # yang tampak berjalan tetapi tak pernah memberi peringatan.
        await db.iot_geofence_state.create_index([("aturan_id", 1), ("device_id", 1)],
                                                 unique=True,
                                                 name="geofence_state_kunci")
        await db.iot_geofence_event.create_index("id", unique=True,
                                                 name="geofence_event_id")
        # Register peringatan: daftar per satker terbaru dulu + hitung yang
        # belum dibaca (badge). Partial pada `dibaca:false` menjaga indeks tetap
        # kecil — yang sudah dibaca tak pernah dikueri lewat jalur ini.
        await db.iot_geofence_event.create_index(
            [("kode_satker", 1), ("dibuat_pada", -1)], name="geofence_event_satker")
        await db.iot_geofence_event.create_index(
            [("kode_satker", 1), ("dibaca", 1)],
            partialFilterExpression={"dibaca": False},
            name="geofence_event_belum_dibaca")
        # Penjaga idempotensi sapuan `dwell_terlampaui`: satu peringatan per
        # KEPERGIAN, bukan satu per jam selama aset masih hilang. WAJIB unique —
        # loop pemeliharaan berjalan di SETIAP worker uvicorn, jadi cek-lalu-
        # tulis di aplikasi bisa dilewati dua sapuan yang nyaris serempak.
        # Partial: hanya event dwell yang punya `sejak`; jenis lain tak
        # tersentuh aturan keunikan ini.
        await db.iot_geofence_event.create_index(
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
        await db.opname_scan.create_index(
            "scan_id", unique=True, name="opname_scan_idem",
            partialFilterExpression={"scan_id": {"$type": "string"}})
        await db.opname_scan.create_index("id", unique=True, name="opname_scan_id")
        # Rekonsiliasi membaca "scan di lingkup node ini sejak tanggal X" —
        # bentuk kueri tetap halaman itu.
        await db.opname_scan.create_index([("node_id", 1), ("pada", -1)],
                                          name="opname_scan_node_waktu")
        # Riwayat pemindaian per aset (terbaru dulu) di panel detail aset.
        await db.opname_scan.create_index([("asset_id", 1), ("pada", -1)],
                                          name="opname_scan_aset_waktu")
        await db.opname_scan.create_index([("kode_satker", 1), ("pada", -1)],
                                          name="opname_scan_satker_waktu")
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
