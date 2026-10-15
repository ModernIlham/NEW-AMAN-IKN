"""Installation-local dataset generation; never archived/restored/reset."""
from datetime import datetime, timezone
import uuid


async def get_generation(database):
    await database.dataset_state.update_one(
        {"_id": "batch_generation"},
        {"$setOnInsert": {"generation": str(uuid.uuid4()),
                           "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return (await database.dataset_state.find_one({"_id": "batch_generation"}))["generation"]


async def rotate_generation(database, reason="restore"):
    generation = str(uuid.uuid4())
    await database.dataset_state.update_one(
        {"_id": "batch_generation"},
        {"$set": {"generation": generation,
                  "changed_at": datetime.now(timezone.utc).isoformat(),
                  "reason": str(reason)[:100]}}, upsert=True)
    return generation
