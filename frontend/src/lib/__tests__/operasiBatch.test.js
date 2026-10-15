import axios from "axios";
import { buatKlienOperasiBatch, ringkasBatch } from "../operasiBatch";
jest.mock("axios");
const originalCrypto = globalThis.crypto;
beforeAll(() => { Object.defineProperty(globalThis, "crypto", { value: require("crypto").webcrypto, configurable: true }); });
afterAll(() => { Object.defineProperty(globalThis, "crypto", { value: originalCrypto, configurable: true }); });
const photo = "data:image/jpeg;base64,FOTO-RAHASIA";
const ids = n => Array.from({ length: n }, (_, i) => `aset-${i}`);
const clone = x => JSON.parse(JSON.stringify(x));
function server({ timeoutChild = -1, afterCommit = false } = {}) {
  const operations = new Map(), photos = new Map(), events = [];
  let timedOut = false;
  const response = (record, applied = false) => ({ protocol: "batch_v2", operation_id: record.operation_id,
    requested_unique: record.asset_ids.length, applied: applied ? record.asset_ids.length : 0,
    unchanged: 0, conflicts: 0, missing: 0, failed: 0, pending: applied ? 0 : record.asset_ids.length,
    state: applied ? "completed" : "running", results: record.asset_ids.map(id => ({ id, status: applied ? "applied" : "pending" })) });
  axios.post.mockImplementation(async (url, payload) => {
    if (url.endsWith("/preflight")) return { data: { protocol: "batch_v2", dataset_generation: "g", max_targets: 200,
      targets: payload.asset_ids.map(id => ({ id, version: 8, status: "ready" })) } };
    if (url.endsWith("/prepare")) {
      events.push("prepare");
      const record = clone(payload); operations.set(record.operation_id, { ...record, response: response(record) });
      return { data: clone(operations.get(record.operation_id).response) };
    }
    const op = operations.get(url.split("/").at(-2));
    events.push("resume");
    const index = [...operations.keys()].indexOf(op.operation_id);
    const timeout = index === timeoutChild && !timedOut;
    if (!timeout || afterCommit) {
      for (const id of op.asset_ids) photos.set(id, (photos.get(id) || 0) + 1);
      op.response = response(op, true);
    }
    if (timeout) { timedOut = true; throw Object.assign(new Error("timeout"), { code: "ECONNABORTED" }); }
    return { data: clone(op.response) };
  });
  axios.get.mockImplementation(async url => {
    const op = operations.get(url.split("/").at(-1));
    if (!op) throw { response: { status: 404 } };
    return { data: clone(op.response) };
  });
  return { operations, photos, events };
}
const client = extra => buatKlienOperasiBatch({ owner: "pemilik", satker: "A", activityId: "kegiatan-1", ...extra });
beforeEach(() => { localStorage.clear(); jest.resetAllMocks(); });

test.each([401, 501])("%s target: semua potongan disiapkan sebelum write, timeout lalu reload melanjutkan tanpa foto ganda", async count => {
  const api = server({ timeoutChild: 1 });
  const c = client();
  const draft = { notes: "Draf asli", batch_photos: [photo] };
  const plan = await c.plan(ids(count), draft, { "aset-0": 4 });
  draft.notes = "Draf berubah"; draft.batch_photos.push("lain");
  expect(plan.payloads[0].expected_versions["aset-0"]).toBe(4);
  expect(plan.payloads[0].updates.notes).toBe("Draf asli");
  expect(plan.payloads.map(p => p.asset_ids.length)).toEqual(count === 401 ? [200, 200, 1] : [200, 200, 101]);
  const result = await c.start(plan);
  expect(api.events.slice(0, 4)).toEqual(["prepare", "prepare", "prepare", "resume"]);
  expect(ringkasBatch(result).success).toBe(200);
  expect(ringkasBatch(result).pending).toBe(count - 200);
  expect(localStorage.getItem(c.key)).not.toContain(photo);
  expect(localStorage.getItem(c.key)).not.toContain("Draf asli");
  const operationIds = plan.payloads.map(p => p.operation_id);
  const afterReload = client();
  const final = await afterReload.resume(afterReload.read());
  expect(ringkasBatch(final)).toMatchObject({ total: count, applied: count, pending: 0, done: true });
  expect([...api.operations.keys()]).toEqual(operationIds);
  expect([...api.photos.values()]).toEqual(Array(count).fill(1));
  expect(axios.post.mock.calls.filter(([url]) => url.endsWith("/prepare"))).toHaveLength(3);
});

test("timeout setelah commit diperiksa lewat GET; reload hanya mengerjakan potongan yang belum selesai", async () => {
  const api = server({ timeoutChild: 1, afterCommit: true });
  const c = client(), plan = await c.plan(ids(501), { batch_photos: [photo] });
  const initial = await c.start(plan);
  expect(ringkasBatch(initial).success).toBe(400);
  const reload = client();
  const final = await reload.resume(reload.read());
  expect(ringkasBatch(final).success).toBe(501);
  expect([...api.photos.values()]).toEqual(Array(501).fill(1));
});

test("klik ganda tidak melahirkan operasi baru; akun lain tidak membaca checkpoint", async () => {
  server(); const c = client(), plan = await c.plan(ids(1), { notes: "A" });
  const one = c.start(plan);
  await expect(c.start(plan)).rejects.toMatchObject({ code: "operation_busy" });
  await one;
  expect(axios.post.mock.calls.filter(([u]) => u.endsWith("/prepare"))).toHaveLength(1);
  expect(client({ owner: "akun-lain" }).read()).toBeNull();
  await expect(client({ owner: "akun-lain" }).start(plan)).rejects.toMatchObject({ code: "owner_changed" });
});

test.each([401, 403, 409])("izin/masa replay ditolak %s: checkpoint tetap ada dan tidak ada write ulang", async status => {
  server(); const c = client(), plan = await c.plan(ids(1), { notes: "A" });
  const done = await c.start(plan);
  axios.post.mockClear();
  axios.get.mockRejectedValue({ response: { status, data: { detail: { code: "operation_expired", message: "Ditahan server" } } } });
  await expect(c.resume(done)).rejects.toMatchObject({ code: "incomplete_admission" });
  expect(axios.post).not.toHaveBeenCalled();
  expect(c.read().children[0].operation_id).toBe(plan.payloads[0].operation_id);
});

test("persiapan gagal sebelum seluruh admission tidak mengubah satu aset pun", async () => {
  const api = server(); const real = axios.post.getMockImplementation();
  axios.post.mockImplementation((u, p) => u.endsWith("/prepare") && p.asset_ids[0] === "aset-200"
    ? Promise.reject(new Error("koneksi putus")) : real(u, p));
  const c = client(), result = await c.start(await c.plan(ids(401), { notes: "A" }));
  expect(api.photos.size).toBe(0);
  expect(result.phase).toBe("attention");
  await expect(c.resume(result)).rejects.toMatchObject({ code: "incomplete_admission" });
  await c.abandonPreparation(result);
  expect(c.read()).toBeNull();
});

test("penyimpanan checkpoint gagal: tidak melakukan admission/mutasi tanpa metadata pemulihan", async () => {
  server(); const c = client({ storage: { getItem: () => null, setItem: () => { throw new Error("quota"); } } });
  const plan = await c.plan(ids(1), { notes: "A" }); axios.post.mockClear();
  await expect(c.start(plan)).rejects.toMatchObject({ code: "checkpoint_storage" }); expect(axios.post).not.toHaveBeenCalled();
});
