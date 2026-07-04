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
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
