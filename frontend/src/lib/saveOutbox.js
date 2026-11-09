import { openDB } from "idb";
import { abortOnFailure } from "./idbTransaction";

const BODY = "operations", STATE = "operation_states", META = "outbox_meta";
export const OUTBOX_LEASE_MS = 150000;
let database;
let persistenceRequested = false;
function notify() {
  // Notifications carry no payload/owner data. Polling is the fallback.
  try {
    const channel = new BroadcastChannel("aman-outbox-v2");
    channel.postMessage("changed");
    channel.close();
  } catch { /* older browsers */ }
}
export const operationId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const resource = r => JSON.stringify([r.pemilik, r.satkerAktif || "", r.statusKey]);
const pending = s => !["ack", "cancelled"].includes(s.status);
export const hasMediaMutation = payload => ["photo_ops", "photos", "photo", "document_checklist", "thumbnail_index", "stiker_photo_index"]
  .some(key => Object.prototype.hasOwnProperty.call(payload || {}, key));

function initial(record, order, producer = "migration") {
  return { antreanId: record.antreanId, owner: record.pemilik || "", resource: resource(record),
    statusKey: record.statusKey, order, producer, baseVersion: record.baseVersion ?? null,
    status: record.hadConflict ? "conflict" : record.locked ? "locked" : "ready",
    attempts: 0, nextAt: 0, attempted: producer === "migration", queuedAt: record.queuedAt };
}
function db() {
  if (!database) database = openDB("aman_save_queue", 2, {
    upgrade(database, oldVersion, _version, tx) {
      tx.done.catch(() => {});
      const bodies = database.createObjectStore(BODY, { keyPath: "antreanId" });
      const states = database.createObjectStore(STATE, { keyPath: "antreanId" });
      states.createIndex("owner", "owner");
      database.createObjectStore(META);
      // Copy before clearing, in the SAME upgrade transaction. An aborted
      // upgrade leaves every legacy item intact. No destructive DB reset.
      if (oldVersion && database.objectStoreNames.contains("items")) {
        const copy = async () => {
          let cursor = await tx.objectStore("items").openCursor();
          let order = 0;
          while (cursor) {
            const old = cursor.value;
            const record = { ...old, antreanId: old.antreanId || `legacy:${old.statusKey}`,
              idempotencyKey: old.idempotencyKey || operationId() };
            await bodies.put(record);
            await states.put(initial(record, ++order));
            cursor = await cursor.continue();
          }
          await tx.objectStore(META).put(order, "sequence");
          await tx.objectStore("items").clear();
        };
        copy().catch(() => { try { tx.abort(); } catch { /* already aborted */ } });
      }
    },
    blocked() {
      globalThis.dispatchEvent?.(new Event("aman:outbox-upgrade-blocked"));
    },
    blocking() { database?.then(connection => connection.close()); database = null; },
    terminated() { database = null; },
  }).catch(error => { database = null; throw error; });
  return database;
}
export async function appendOperation(record, producer) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE, META], "readwrite");
  return abortOnFailure(tx, async () => {
    const sequence = (await tx.objectStore(META).get("sequence") || 0) + 1;
    const existing = await tx.objectStore(STATE).index("owner").getAll(record.pemilik || "");
    const state = initial(record, sequence, producer);
    const prior = existing.filter(s => s.resource === state.resource && pending(s))
      .sort((a,b) => b.order - a.order)[0];
    if (prior?.producer === producer) state.dependsOn = prior.antreanId;
    await tx.objectStore(BODY).add(record);
    await tx.objectStore(STATE).add(state);
    await tx.objectStore(META).put(sequence, "sequence");
    await tx.done;
    if (!persistenceRequested) {
      persistenceRequested = true;
      try { globalThis.navigator?.storage?.persist?.().catch(() => {}); } catch { /* best effort */ }
    }
    notify();
    return state;
  });
}
export async function readOperations(owner, cache = new Map()) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE], "readonly");
  return abortOnFailure(tx, async () => {
    const states = (await tx.objectStore(STATE).index("owner").getAll(owner)).sort((a,b) => a.order-b.order);
    const alive = new Set(states.filter(pending).map(s => s.antreanId));
    for (const id of cache.keys()) if (!alive.has(id)) cache.delete(id);
    const items = await Promise.all(states.filter(pending).map(async state => {
      let entry = cache.get(state.antreanId);
      if (!entry || entry.revision !== state.bodyRevision) {
        entry = { body: await tx.objectStore(BODY).get(state.antreanId), revision: state.bodyRevision };
        cache.set(state.antreanId, entry);
      }
      return { ...entry.body, baseVersion: state.baseVersion, state };
    }));
    await tx.done;
    return { states, items: items.filter(item => item.payload) };
  });
}
export async function claimOperation(owner, worker, now = Date.now()) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE], "readwrite");
  return abortOnFailure(tx, async () => {
    const states = (await tx.objectStore(STATE).index("owner").getAll(owner)).sort((a,b) => a.order-b.order);
    const resources = new Set();
    let claimed = null;
    for (const state of states) {
      if (!pending(state) && state.completedAt < now - 7 * 86400000) {
        await tx.objectStore(STATE).delete(state.antreanId);
      }
      if (!pending(state) || resources.has(state.resource)) continue;
      resources.add(state.resource); // a failed/conflicted predecessor blocks its successors
      if (["conflict", "locked", "rejected"].includes(state.status) || state.nextAt > now) continue;
      if (state.status === "sending" && state.leaseUntil > now) continue;
      const body = await tx.objectStore(BODY).get(state.antreanId);
      if (!body?.payload) continue;
      Object.assign(state, { status: "sending", attempted: true, worker,
        token: operationId(), leaseUntil: now + OUTBOX_LEASE_MS, attempts: state.attempts + 1 });
      await tx.objectStore(STATE).put(state);
      claimed = { ...body, baseVersion: state.baseVersion, state };
      break;
    }
    await tx.done;
    return claimed;
  });
}
async function transition(ticket, change, announce = true) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE], "readwrite");
  return abortOnFailure(tx, async () => {
    const store = tx.objectStore(STATE);
    const state = await store.get(ticket.antreanId);
    if (!state || state.status !== "sending" || state.token !== ticket.state.token) {
      await tx.done; return false;
    }
    await change(tx, state);
    await tx.done;
    if (announce) notify();
    return true;
  });
}
export const renewOperation = ticket => transition(ticket, async (tx, state) => {
  state.leaseUntil = Date.now() + OUTBOX_LEASE_MS;
  await tx.objectStore(STATE).put(state);
}, false);
export const acknowledgeOperation = (ticket, result) => transition(ticket, async (tx, state) => {
  const { photos, photo, document_checklist, ...light } = result || {};
  Object.assign(state, { status: "ack", result: light, completedAt: Date.now(), token: null });
  await tx.objectStore(STATE).put(state);
  await tx.objectStore(BODY).delete(ticket.antreanId);
  const siblings = await tx.objectStore(STATE).index("owner").getAll(state.owner);
  for (const next of siblings) {
    if (next.dependsOn !== state.antreanId || next.attempted || !pending(next)) continue;
    const body = await tx.objectStore(BODY).get(next.antreanId);
    // Never rebase positional media indices automatically. Leave OCC to
    // demand human review if the prior save changed the server version.
    if (light.version != null && !hasMediaMutation(body?.payload)) {
      next.baseVersion = light.version;
      await tx.objectStore(STATE).put(next);
    }
  }
});
export const failOperation = (ticket, status, error, retryAfter = 0) => transition(ticket, async (tx, state) => {
  Object.assign(state, { status, error, token: null, retryAfter: Number.isFinite(retryAfter) ? retryAfter : 0,
    nextAt: Math.max(Number.isFinite(retryAfter) ? retryAfter : 0,
      Date.now() + Math.min(60000, 2000 * 2 ** Math.min(state.attempts - 1, 5))) });
  await tx.objectStore(STATE).put(state);
});
// Only for a definitive validation rejection (e.g. auto-numbered dummy NUP).
// Commit the changed body AND fresh idempotency key before a new HTTP attempt.
export const renumberOperation = (ticket, nextNup) => transition(ticket, async (tx, state) => {
  await tx.objectStore(BODY).put({ ...ticket, state: undefined,
    payload: { ...ticket.payload, NUP: String(nextNup) },
    idempotencyKey: operationId(), nupRetries: (ticket.nupRetries || 0) + 1 });
  Object.assign(state, { status: "ready", nextAt: 0, token: null, bodyRevision: (state.bodyRevision || 0) + 1 });
  await tx.objectStore(STATE).put(state);
});
export async function retryOperations(owner, { statusKey, auto = false, version } = {}) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE], "readwrite");
  return abortOnFailure(tx, async () => {
    for (const state of await tx.objectStore(STATE).index("owner").getAll(owner)) {
      if (!pending(state) || state.status === "sending" || (statusKey && state.statusKey !== statusKey)) continue;
      if (auto && ["conflict", "locked", "rejected"].includes(state.status)) continue;
      if (state.status === "conflict") {
        const body = await tx.objectStore(BODY).get(state.antreanId);
        if (hasMediaMutation(body.payload) || version == null) continue;
        body.idempotencyKey = operationId(); // definitive 409: reviewed retry is a new attempt
        await tx.objectStore(BODY).put(body);
        state.baseVersion = version;
        state.bodyRevision = (state.bodyRevision || 0) + 1;
      }
      Object.assign(state, { status: "ready", nextAt: state.retryAfter || 0, error: null });
      await tx.objectStore(STATE).put(state);
    }
    await tx.done;
    notify();
  });
}
export async function cancelOperations(owner, statusKey) {
  const connection = await db();
  const tx = connection.transaction([BODY, STATE], "readwrite");
  return abortOnFailure(tx, async () => {
    for (const state of await tx.objectStore(STATE).index("owner").getAll(owner)) {
      if (state.statusKey !== statusKey || !pending(state)) continue;
      Object.assign(state, { status: "cancelled", token: null, completedAt: Date.now() });
      await tx.objectStore(STATE).put(state);
      await tx.objectStore(BODY).delete(state.antreanId);
    }
    await tx.done;
    notify();
  });
}
