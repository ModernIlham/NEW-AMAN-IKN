import "../uji/indexedDB";
import { deleteDB, openDB } from "idb";
import { appendOperation, readOperations, claimOperation, acknowledgeOperation, failOperation,
  retryOperations, cancelOperations, renumberOperation, OUTBOX_LEASE_MS } from "./saveOutbox";

const row = (id, extra = {}) => ({ antreanId: id, statusKey: "asset", pemilik: "alice", satkerAktif: "s1",
  isEdit: true, editId: "asset", usePatch: true, baseVersion: 5, idempotencyKey: `key-${id}`,
  queuedAt: new Date().toISOString(), payload: { asset_name: id }, ...extra });
beforeEach(async () => { await deleteDB("aman_save_queue"); });

test("migration preserves legacy photo bytes and retry key, without claiming ownerless work", async () => {
  const legacy = await openDB("aman_save_queue", 1, { upgrade: db => db.createObjectStore("items", { keyPath: "statusKey" }) });
  const payload = { photo_ops: { add: ["data:image/jpeg;base64," + "x".repeat(32768)] } };
  await legacy.put("items", row("old", { payload }));
  await legacy.put("items", row("unknown", { statusKey: "unknown", pemilik: "" }));
  legacy.close();
  const loaded = await readOperations("alice");
  expect(loaded.items[0]).toMatchObject({ payload, idempotencyKey: "key-old" });
  const ticket = await claimOperation("alice", "tab1");
  expect(ticket.payload).toEqual(payload);
  expect(await claimOperation("bob", "tab2")).toBeNull();
  expect((await readOperations("")).items).toHaveLength(1);
});

test("two edits survive reload; concurrent tabs claim only the oldest on each resource", async () => {
  await appendOperation(row("first", { payload: { photo_ops: { add: ["photo"] } } }), "tab1");
  await appendOperation(row("second"), "tab1");
  const reopened = await readOperations("alice", new Map());
  expect(reopened.items.map(x => x.antreanId)).toEqual(["first", "second"]);
  const claims = await Promise.all([claimOperation("alice", "tab1"), claimOperation("alice", "tab2")]);
  expect(claims.filter(Boolean)).toHaveLength(1);
  await acknowledgeOperation(claims.find(Boolean), { id: "asset", version: 6 });
  const second = await claimOperation("alice", "tab2");
  expect(second.antreanId).toBe("second");
  expect(second.baseVersion).toBe(6);
  expect(second.payload).toEqual({ asset_name: "second" });
});

test("crashed lease replays identical body, key and version; stale worker cannot ack/fail the new lease", async () => {
  const payload = { photo_ops: { add: ["unaltered-photo"], remove: [1] } };
  await appendOperation(row("a", { payload }), "old");
  const now = Date.now();
  const old = await claimOperation("alice", "old", now);
  expect(await claimOperation("alice", "new", now + OUTBOX_LEASE_MS - 1)).toBeNull();
  const next = await claimOperation("alice", "new", now + OUTBOX_LEASE_MS + 1);
  expect(next).toMatchObject({ payload, baseVersion: 5, idempotencyKey: old.idempotencyKey });
  expect(await acknowledgeOperation(old, { version: 6 })).toBe(false);
  expect(await failOperation(old, "failed", "late timeout")).toBe(false);
  expect((await readOperations("alice")).items).toHaveLength(1);
  expect(await acknowledgeOperation(next, { id: "asset", version: 6 })).toBe(true);
  expect((await readOperations("alice")).items).toHaveLength(0);
});

test("network retry never mints another key and never overtakes failed predecessor", async () => {
  await appendOperation(row("a"), "tab"); await appendOperation(row("b"), "tab");
  const a = await claimOperation("alice", "tab");
  await failOperation(a, "failed", "response lost");
  expect(await claimOperation("alice", "tab")).toBeNull();
  await retryOperations("alice", { auto: true });
  const retry = await claimOperation("alice", "tab");
  expect(retry.antreanId).toBe("a"); expect(retry.idempotencyKey).toBe(a.idempotencyKey);
  expect(retry.payload).toEqual(a.payload);
});

test("another tab's edit and positional media retain original OCC version", async () => {
  await appendOperation(row("a"), "tab1");
  await appendOperation(row("b", { payload: { photo_ops: { remove: [0] } } }), "tab1");
  await appendOperation(row("c"), "tab2");
  await acknowledgeOperation(await claimOperation("alice", "tab1"), { version: 6 });
  const media = await claimOperation("alice", "tab1");
  expect(media.baseVersion).toBe(5);
  await failOperation(media, "conflict", "review");
  await retryOperations("alice", { statusKey: "asset", version: 99 });
  expect(await claimOperation("alice", "tab2")).toBeNull();
  expect((await readOperations("alice")).items[0].payload.photo_ops.remove).toEqual([0]);
});

test("scalar conflict retries require manual review; cached bodies update on a new key", async () => {
  await appendOperation(row("a"), "tab1");
  const cache = new Map(); const original = (await readOperations("alice", cache)).items[0];
  const ticket = await claimOperation("alice", "tab1");
  await failOperation(ticket, "conflict", "review");
  await retryOperations("alice", { auto: true, version: 6 });
  expect(await claimOperation("alice", "tab1")).toBeNull();
  await retryOperations("alice", { statusKey: "asset", version: 6 });
  const changed = (await readOperations("alice", cache)).items[0];
  expect(changed.idempotencyKey).not.toBe(original.idempotencyKey);
  expect(changed.baseVersion).toBe(6);
  expect(changed.payload).toEqual(original.payload);
});

test("owners and satkers remain isolated; cancel invalidates a sending worker", async () => {
  await appendOperation(row("a"), "tab1");
  await appendOperation(row("b", { pemilik: "bob" }), "tab2");
  await appendOperation(row("c", { satkerAktif: "s2" }), "tab1");
  const sending = await claimOperation("alice", "tab1");
  expect((await claimOperation("alice", "tab2")).satkerAktif).toBe("s2");
  await cancelOperations("alice", "asset");
  expect(await acknowledgeOperation(sending, { version: 6 })).toBe(false);
  expect((await readOperations("alice")).items).toHaveLength(0);
  expect((await readOperations("bob")).items).toHaveLength(1);
});

test("dummy renumber commits new payload and key together, preserving photos", async () => {
  await appendOperation(row("a", { isEdit: false, payload: { NUP: "1", photos: ["photo"] } }), "tab");
  const ticket = await claimOperation("alice", "tab");
  await renumberOperation(ticket, "2");
  const next = await claimOperation("alice", "tab");
  expect(next.payload).toEqual({ NUP: "2", photos: ["photo"] });
  expect(next.idempotencyKey).not.toBe(ticket.idempotencyKey);
});

test("synchronous quota failure after body write rolls back the entire journal operation", async () => {
  const original = IDBObjectStore.prototype.add;
  const fail = jest.spyOn(IDBObjectStore.prototype, "add").mockImplementation(function (...args) {
    if (this.name === "operation_states") throw new DOMException("Full", "QuotaExceededError");
    return original.apply(this, args);
  });
  await expect(appendOperation(row("a"), "tab")).rejects.toMatchObject({ name: "QuotaExceededError" });
  fail.mockRestore();
  const db = await openDB("aman_save_queue", 2);
  expect(await db.count("operations")).toBe(0);
  expect(await db.count("operation_states")).toBe(0);
  expect(await db.get("outbox_meta", "sequence")).toBeUndefined();
  db.close();
});

test("retry otomatis menghormati Retry-After server", async () => {
  await appendOperation(row("rate-limited"), "tab");
  const ticket = await claimOperation("alice", "tab");
  const deadline = Date.now() + 300000;
  await failOperation(ticket, "failed", "429", deadline);
  await retryOperations("alice", { auto: true });
  expect(await claimOperation("alice", "tab", deadline - 1)).toBeNull();
  const next = await claimOperation("alice", "tab", deadline + 1);
  expect(next.idempotencyKey).toBe(ticket.idempotencyKey);
});
