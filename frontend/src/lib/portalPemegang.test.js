const mockStore = new Map();
jest.mock("idb", () => ({ openDB: async () => ({
  clear: async () => mockStore.clear(),
  transaction: () => ({ store: {
    get: async key => mockStore.get(key),
    put: async (value, key) => mockStore.set(key, value),
    clear: async () => mockStore.clear(),
  }, done: Promise.resolve() }),
}) }));

import {
  aktifkanLuringPortal, bacaLuringPortal, hapusDrafPortal, hapusLuringPortal, pemilikPortal,
  periksaAntreanPortal, portalRequest, simpanDrafPortal, simpanSnapshotPortal,
  tenggatPortal, PORTAL_TTL, bacaBuktiPortal,
} from "./portalPemegang";

const session = () => ({ session_id: "session-1", csrf_token: "csrf-private", expires_at: new Date(Date.now() + PORTAL_TTL).toISOString(), idle_expires_at: new Date(Date.now() + 30 * 60000).toISOString(), pegawai: { id: "p1", nama: "Pegawai", kode_satker: "A" } });
const assignment = { id: "t1", version: 2, status: "diterima", asset_id: "a1", asset_name: "Kursi", asset_code: "301", NUP: "1", condition: "Baik", location: "Gedung" };
const payload = { penugasan_id: "t1", penugasan_version: 2, jenis: "kehilangan", catatan: "Dicari sejak kemarin", bukti: [] };

beforeEach(() => {
  mockStore.clear(); global.fetch = jest.fn();
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
});
afterEach(() => jest.useRealTimers());

test("snapshot register dan metadata foto tetap tersedia pada draf luring pemilik yang sama", async () => {
  const s = session(); await aktifkanLuringPortal(s);
  await simpanSnapshotPortal(s, [{ ...assignment, kode_register: "REGISTER-01" }]);
  const pengambilan = { waktu: "2026-10-03T10:00:00Z", gps: { lat: -0.96, lng: 116.7, accuracy: 15 } };
  await simpanDrafPortal(s, { ...payload, bukti: [{ nama: "uji.jpg", mime: "image/jpeg", data_base64: "YQ==", pengambilan }] });
  const result = await bacaLuringPortal(s);
  expect(result.aset[0].kode_register).toBe("REGISTER-01");
  expect(result.antrean[0].payload.bukti[0].pengambilan).toEqual(pengambilan);
});

test("API publik hanya memakai cookie portal tanpa token staf, cache, atau redirect", async () => {
  localStorage.setItem("token", "secret-staff-token");
  global.fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) });
  await portalRequest("/laporan", { method: "POST", body: payload, csrf: "csrf", version: 2, key: "tetap" });
  const [url, options] = global.fetch.mock.calls[0];
  expect(url).toMatch(/\/api\/portal-pemegang\/laporan$/);
  expect(options).toMatchObject({ credentials: "include", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer" });
  expect(options.headers).toMatchObject({ "X-Portal-CSRF": "csrf", "If-Match": "2", "Idempotency-Key": "tetap" });
  expect(options.headers.Authorization).toBeUndefined();
  expect(JSON.stringify(options)).not.toContain("secret-staff-token");
  localStorage.clear();
});

test("penolakan sesi dipertahankan sebagai 401 untuk membersihkan UI/cache", async () => {
  global.fetch.mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "Sesi berakhir" }) });
  await expect(portalRequest("/sesi")).rejects.toMatchObject({ status: 401, message: "Sesi berakhir" });
});

test("permintaan macet dibatalkan tanpa mengganti idempotency key", async () => {
  jest.useFakeTimers();
  global.fetch.mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(Object.assign(new Error("abort"), { name: "AbortError" })));
  }));
  const pending = expect(portalRequest("/laporan", { method: "POST", body: payload, key: "same" })).rejects.toThrow("batas waktu");
  jest.advanceTimersByTime(30001);
  await pending;
  expect(global.fetch.mock.calls[0][1].headers["Idempotency-Key"]).toBe("same");
});

test("IDB menolak simpan sebelum persetujuan dan tidak menyimpan csrf/token", async () => {
  const s = session();
  await expect(simpanDrafPortal(s, payload)).rejects.toThrow("tidak aktif");
  await aktifkanLuringPortal(s);
  await simpanSnapshotPortal(s, [{ ...assignment, purchase_price: 900, photo: "private", arbitrary: "secret" }]);
  await simpanDrafPortal(s, payload, { id: "d1", key: "k1" });
  const data = await bacaLuringPortal(s);
  expect(data.aktif).toBe(true); expect(data.antrean).toHaveLength(1);
  expect(data.aset[0]).not.toHaveProperty("photo"); expect(data.aset[0]).not.toHaveProperty("purchase_price");
  expect(JSON.stringify([...mockStore.values()])).not.toContain("csrf-private");
});

test.each([
  s => ({ ...s, session_id: "new-session" }),
  s => ({ ...s, pegawai: { ...s.pegawai, id: "p2" } }),
  s => ({ ...s, pegawai: { ...s.pegawai, kode_satker: "B" } }),
])("identitas, satker, atau sesi berbeda menghapus antrean lama", async change => {
  const s = session(); await aktifkanLuringPortal(s); await simpanDrafPortal(s, payload);
  const restored = await bacaLuringPortal(change(s));
  expect(restored).toEqual({ aktif: false, aset: [], antrean: [] });
  expect(mockStore.size).toBe(0);
});

test("tab sesi lama tidak boleh menimpa simpanan sesi baru", async () => {
  const old = session(); const fresh = { ...old, session_id: "new" };
  await aktifkanLuringPortal(fresh); await simpanDrafPortal(fresh, payload);
  await expect(simpanDrafPortal(old, payload)).rejects.toThrow("tidak aktif");
  expect((await bacaLuringPortal(fresh)).antrean).toHaveLength(1);
});

test("TTL maksimum delapan jam dan expiry membersihkan draf", async () => {
  const s = session();
  expect(tenggatPortal({ ...s, expires_at: new Date(Date.now() + PORTAL_TTL * 2).toISOString() })).toBeLessThanOrEqual(Date.now() + PORTAL_TTL);
  expect(tenggatPortal({})).toBe(0);
  expect(tenggatPortal(s)).toBe(Date.parse(s.idle_expires_at));
  await aktifkanLuringPortal(s); await simpanDrafPortal(s, payload);
  mockStore.set("meta", { ...mockStore.get("meta"), expires: Date.now() - 1 });
  expect((await bacaLuringPortal(s)).aktif).toBe(false); expect(mockStore.size).toBe(0);
});

test("draf bisa diperbaiki sebelum antrean, antrean beku dan kunci tetap untuk retry", async () => {
  const s = session(); await aktifkanLuringPortal(s);
  await simpanDrafPortal(s, payload, { id: "d1", key: "k1" });
  const next = await simpanDrafPortal(s, { ...payload, catatan: "Sudah dicari" }, { id: "d1", key: "k1", siap: true });
  expect(next).toHaveLength(1); expect(next[0]).toMatchObject({ key: "k1", siap: true });
  await expect(simpanDrafPortal(s, payload, { id: "d1" })).rejects.toThrow("tidak boleh diubah");
  expect(await hapusDrafPortal(s, "d1")).toEqual([]);
});

test("refresh sesi yang masih berlaku menyelaraskan idle deadline cache dan draf", async () => {
  jest.useFakeTimers(); jest.setSystemTime(new Date("2026-10-03T01:00:00Z"));
  const s = session(); await aktifkanLuringPortal(s); await simpanDrafPortal(s, payload, { id: "d1", key: "k1" });
  jest.setSystemTime(new Date("2026-10-03T01:20:00Z"));
  const refreshed = { ...s, idle_expires_at: "2026-10-03T01:50:00Z" };
  const restored = await bacaLuringPortal(refreshed);
  expect(restored.antrean[0].expires).toBe(Date.parse(refreshed.idle_expires_at));
  expect(mockStore.get("meta").expires).toBe(Date.parse(refreshed.idle_expires_at));
  jest.setSystemTime(new Date("2026-10-03T01:31:00Z"));
  expect((await bacaLuringPortal(refreshed)).antrean).toHaveLength(1);
});

test("antrean dibatasi sepuluh draf dan logout membersihkan", async () => {
  const s = session(); await aktifkanLuringPortal(s);
  for (let i = 0; i < 10; i += 1) await simpanDrafPortal(s, payload, { id: `d${i}` });
  await expect(simpanDrafPortal(s, payload)).rejects.toThrow("Maksimal 10");
  await hapusLuringPortal(); expect(mockStore.size).toBe(0);
});

test("otorisasi antrean selalu menguji pemilik, masa berlaku, status dan versi", () => {
  const s = session(); const d = { owner: pemilikPortal(s), expires: Date.now() + 10000, payload };
  expect(periksaAntreanPortal(d, s, [assignment])).toBe("");
  expect(periksaAntreanPortal(d, s, [{ ...assignment, version: 3 }])).toMatch(/berubah/);
  expect(periksaAntreanPortal(d, s, [{ ...assignment, status: "menunggu_konfirmasi" }])).toMatch(/belum diterima/);
  expect(periksaAntreanPortal(d, s, [{ ...assignment, status: "dicabut" }])).toMatch(/tidak lagi/);
  expect(periksaAntreanPortal(d, s, [])).not.toBe("");
  expect(periksaAntreanPortal({ ...d, owner: "other" }, s, [assignment])).toMatch(/Identitas/);
  expect(periksaAntreanPortal({ ...d, expires: 0 }, s, [assignment])).toMatch(/kedaluwarsa/);
});

test("foto asli dibatasi jumlah, tipe dan ukuran; tidak ada kompresi diam-diam", async () => {
  await expect(bacaBuktiPortal([{ type: "image/jpeg", size: 4 * 1024 * 1024 }])).rejects.toThrow("3 MB");
  await expect(bacaBuktiPortal([{ type: "image/svg+xml", size: 12 }])).rejects.toThrow("JPEG");
  await expect(bacaBuktiPortal(Array(4).fill({ type: "image/jpeg", size: 1 }))).rejects.toThrow("tiga");
  const file = new File(["original"], "uji.jpg", { type: "image/jpeg" });
  expect(await bacaBuktiPortal([file])).toEqual([{ nama: "uji.jpg", mime: "image/jpeg", data_base64: btoa("original") }]);
});
