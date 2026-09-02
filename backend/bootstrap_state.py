"""Status keamanan bootstrap administrator pertama.

Status dipisahkan dari koleksi ``users`` agar menghapus seluruh akun secara
manual tidak membuka kembali proses bootstrap. Koleksi ini merupakan kontrol
lokal instalasi dan sengaja tidak ikut backup/restore data aplikasi.
"""
from datetime import datetime, timezone


COLLECTION_NAME = "admin_bootstrap_state"
STATE_ID = "aman-admin-bootstrap-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def tutup_bila_pengguna_sudah_ada(database) -> None:
    """Tutup bootstrap secara idempoten untuk instalasi lama yang sudah berisi."""
    if not await database.users.find_one({}, {"_id": 1}):
        return
    await database[COLLECTION_NAME].update_one(
        {"_id": STATE_ID},
        {"$setOnInsert": {
            "status": "closed",
            "reason": "existing_users",
            "closed_at": _now(),
        }},
        upsert=True,
    )
