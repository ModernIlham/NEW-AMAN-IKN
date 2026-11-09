import "../uji/indexedDB";
import { deleteDB, openDB } from "idb";
import { getSnapshotPage, upsertSnapshotAsset, removeSnapshotAsset, clearAllSnapshots } from "./offlineSnapshot";
jest.mock("axios", () => ({ get: jest.fn() }));
beforeEach(async () => { await deleteDB("aman_offline_snapshot"); });

async function seedLegacy(count = 600) {
  const db = await openDB("aman_offline_snapshot", 2, { upgrade(db) {
    db.createObjectStore("assets", { keyPath: "id" }).createIndex("by-activity", "activity_id");
    db.createObjectStore("meta", { keyPath: "activityId" });
  } });
  const tx = db.transaction(["assets", "meta"], "readwrite");
  for (let i = 0; i < count; i++) tx.objectStore("assets").put({ id: String(i).padStart(4, "0"), activity_id: "act",
    asset_name: `Meja ${i}`, purchase_price: i, thumbnail: "media".repeat(1000) });
  tx.objectStore("meta").put({ activityId: "act", userId: "u", lastSync: new Date().toISOString(), count });
  await tx.done; db.close();
}

test("v2 migration retains all assets and builds a media-free projection; updates and deletes stay consistent", async () => {
  await seedLegacy();
  const first = await getSnapshotPage("act", { ownerId: "u", sort: "price_desc" });
  expect(first.total).toBe(600); expect(first.items[0].id).toBe("0599");
  const db = await openDB("aman_offline_snapshot", 3);
  expect(await db.count("assets")).toBe(600);
  expect(await db.count("query_rows")).toBe(600);
  expect((await db.get("query_rows", "0599")).thumbnail).toBeUndefined();
  expect((await db.get("meta", "act")).queryReady).toBe(true);
  await upsertSnapshotAsset("act", { id: "0001", purchase_price: 9999 });
  expect((await getSnapshotPage("act", { ownerId: "u", sort: "price_desc" })).items[0].id).toBe("0001");
  await removeSnapshotAsset("act", "0001");
  expect(await db.get("query_rows", "0001")).toBeUndefined();
  expect((await getSnapshotPage("act", { ownerId: "u" })).total).toBe(599);
  expect(await getSnapshotPage("act", { ownerId: "other" })).toBeNull();
  await clearAllSnapshots(); expect(await db.count("query_rows")).toBe(0);
  db.close();
});

test("interrupted backfill resumes at its committed cursor without deleting original media", async () => {
  await seedLegacy(5);
  const db = await openDB("aman_offline_snapshot", 3, { upgrade(db) {
    db.createObjectStore("query_rows", { keyPath: "id" }).createIndex("by-activity-id", ["activity_id", "id"]);
  } });
  const tx = db.transaction(["assets", "query_rows", "meta"], "readwrite");
  const original = await tx.objectStore("assets").get("0000");
  const { thumbnail, ...thin } = original;
  await tx.objectStore("query_rows").put(thin);
  const meta = await tx.objectStore("meta").get("act");
  await tx.objectStore("meta").put({ ...meta, queryCursor: "0000" });
  await tx.done;
  expect((await getSnapshotPage("act", { ownerId: "u" })).total).toBe(5);
  expect(await db.count("query_rows")).toBe(5);
  expect((await db.get("assets", "0000")).thumbnail).toBe(thumbnail);
  db.close();
});

test("quota failure preserves old snapshot, falls back to full rows, and rolls back partial upserts", async () => {
  await seedLegacy(5);
  const original = IDBObjectStore.prototype.put;
  const fail = jest.spyOn(IDBObjectStore.prototype, "put").mockImplementation(function (...args) {
    if (this.name === "query_rows") throw new DOMException("Full", "QuotaExceededError");
    return original.apply(this, args);
  });
  const fallback = await getSnapshotPage("act", { ownerId: "u" });
  expect(fallback.total).toBe(5); expect(fallback.items[0].thumbnail).toBe("media".repeat(1000));
  const db = await openDB("aman_offline_snapshot", 3);
  expect((await db.get("meta", "act")).queryReady).toBeUndefined();
  await upsertSnapshotAsset("act", { id: "0000", asset_name: "Uncommitted" });
  expect((await db.get("assets", "0000")).asset_name).toBe("Meja 0");
  fail.mockRestore();
  expect((await getSnapshotPage("act", { ownerId: "u" })).total).toBe(5);
  expect((await db.get("meta", "act")).queryReady).toBe(true);
  db.close();
});
