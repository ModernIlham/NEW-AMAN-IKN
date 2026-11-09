import { openDB } from "idb";

let database;
let persistenceRequested = false;
function dbDraf() {
  if (!database) database = openDB("aman_asset_drafts", 1, {
    upgrade(db) { db.createObjectStore("drafts", { keyPath: "key" }); },
    blocking() { database?.then(db => db.close()); database = null; },
    terminated() { database = null; },
  }).catch(error => { database = null; throw error; });
  return database;
}
export async function bacaDraf(key) { return (await dbDraf()).get("drafts", key); }
export async function tulisDraf(key, value, revision = 0) {
  const db = await dbDraf();
  if (!persistenceRequested) {
    persistenceRequested = true;
    navigator.storage?.persist?.().catch(() => {});
  }
  const tx = db.transaction("drafts", "readwrite");
  const old = await tx.store.get(key);
  if ((old?.revision || 0) !== revision) {
    await tx.done;
    throw new Error("Draf berubah di tab lain. Muat ulang untuk memulihkannya; isian tab ini tetap tersedia.");
  }
  const record = { key, value, revision: revision + 1, updatedAt: Date.now() };
  await Promise.all([tx.store.put(record), tx.done]);
  return record;
}
export async function hapusDraf(key, revision) {
  const db = await dbDraf();
  const tx = db.transaction("drafts", "readwrite");
  const old = await tx.store.get(key);
  if (old?.revision === revision) await tx.store.delete(key);
  await tx.done;
}
