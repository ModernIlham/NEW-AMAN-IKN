import axios from "axios";
import { toast } from "sonner";
import { getSnapshotAssets, snapshotMeta, isSnapshotExpired } from "../offlineSnapshot";
import { buatPemuatDaftarAset } from "../pemuatDaftarAset";
import { buatPenjagaPermintaan, HASIL_USANG } from "@/hooks/usePenjagaPermintaan";

jest.mock("axios", () => ({ get: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../offlineSnapshot", () => ({
  getSnapshotAssets: jest.fn(), snapshotMeta: jest.fn(), isSnapshotExpired: jest.fn(),
}));

function tertunda() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
const respons = (id, page = 1) => ({ data: { items: [{ id }], total: 20, total_pages: 10, page } });
const giliran = async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); };

function layar(tambahan = {}) {
  const penjaga = buatPenjagaPermintaan();
  penjaga.aktifkan("A");
  const state = { Assets: [], MobileAssets: [{ id: "awal" }], MobileLoading: false };
  const k = {
    activity: { id: "kegiatan-a" }, filters: {}, isOnlineRef: { current: true },
    getPendingItems: jest.fn(() => []), serverHasPendingRow: (a, b) => a.id === b.id,
    filterSnapshotRows: jest.fn(rows => rows), sortSnapshotRows: jest.fn(rows => rows),
    buildFilterParams: jest.fn(p => p.append("condition", "Baik")),
    mobileLoading: false, mobileCurrentPage: 2, mobileFirstPage: 2,
    totalPages: 10, pageSize: 2, debouncedSearch: "meja", filterCategory: [], sortBy: "newest",
    penjaga, lingkupPermintaan: "A", ...tambahan,
  };
  const nama = ["Assets", "TotalItems", "TotalPages", "CurrentPage", "Stats", "MobileAssets",
    "MobileCurrentPage", "MobileFirstPage", "MobileLoading", "OfflineLastSync", "OfflineServed", "LoadingMessage"];
  for (const n of nama) k[`set${n}`] = jest.fn(v => { state[n] = typeof v === "function" ? v(state[n]) : v; });
  return { k, state, ...buatPemuatDaftarAset(k) };
}
const muat = (p, page = 1, preserve = false) => p.doFetch(page, 2, "meja", [], "newest", false, preserve);

beforeEach(() => {
  jest.resetAllMocks();
  getSnapshotAssets.mockResolvedValue(null);
  snapshotMeta.mockResolvedValue({ lastSync: "waktu-cache" });
  isSnapshotExpired.mockReturnValue(false);
});

test.each([false, true])("daftar A tidak menimpa B yang selesai dahulu; gagal A=%s", async gagal => {
  const a = tertunda(), b = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const p = layar();
  const lama = muat(p), baru = muat(p, 2);
  b.resolve(respons("baru", 2));
  await baru;
  const stateBaru = { ...p.state };
  if (gagal) a.reject(new Error("lama")); else a.resolve(respons("lama"));
  expect(await lama).toBe(HASIL_USANG);
  expect(p.state).toEqual(stateBaru);
  expect(getSnapshotAssets).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
});

test.each(["lingkup", "unmount"])("respons ditolak setelah %s meski belum ada request pengganti", async sebab => {
  const a = tertunda(); axios.get.mockReturnValue(a.promise);
  const p = layar(); const lama = muat(p);
  if (sebab === "lingkup") p.k.penjaga.aktifkan("B"); else p.k.penjaga.tutup();
  a.resolve(respons("lama"));
  expect(await lama).toBe(HASIL_USANG);
  expect(p.k.setAssets).not.toHaveBeenCalled();
  expect(await muat(p)).toBe(HASIL_USANG); // closure A juga tidak boleh mulai lagi
  expect(axios.get).toHaveBeenCalledTimes(1);
});

test("statistik terakhir menang, perakit parameter daftar dan statistik sama", async () => {
  const a = tertunda(), b = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise).mockResolvedValueOnce(respons("aset"));
  const p = layar();
  const lama = p.doFetchStats("lama"), baru = p.doFetchStats("baru");
  b.resolve({ data: { total_assets: 2, total_value: 1000 } }); await baru;
  a.resolve({ data: { total_assets: 999 } }); expect(await lama).toBe(HASIL_USANG);
  expect(p.state.Stats.totalAssets).toBe(2);
  await muat(p);
  expect(p.k.buildFilterParams).toHaveBeenCalledTimes(3);
  for (const [url] of axios.get.mock.calls) {
    expect(url).toContain("condition=Baik");
    expect(url).toContain("activity_id=kegiatan-a");
  }
});

test.each(["baris", "metadata"])("snapshot %s yang tertunda tidak mengubah state sesudah lingkup berganti", async tahap => {
  const d = tertunda();
  if (tahap === "baris") getSnapshotAssets.mockReturnValue(d.promise);
  else { getSnapshotAssets.mockResolvedValue([{ id: "cache" }]); snapshotMeta.mockReturnValue(d.promise); }
  const p = layar({ isOnlineRef: { current: false } });
  const lama = muat(p); await giliran();
  expect(p.k.setAssets).not.toHaveBeenCalled(); // metadata harus siap sebelum commit
  p.k.penjaga.aktifkan("B");
  d.resolve(tahap === "baris" ? [{ id: "cache" }] : { lastSync: "lama" });
  expect(await lama).toBe(HASIL_USANG);
  expect(p.k.setAssets).not.toHaveBeenCalled();
  expect(p.k.setOfflineServed).not.toHaveBeenCalled();
  expect(axios.get).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
});

test("metadata fallback kedua yang usang tidak memunculkan toast kegagalan", async () => {
  const d = tertunda();
  axios.get.mockRejectedValue(new Error("jaringan"));
  snapshotMeta.mockResolvedValueOnce(null).mockReturnValueOnce(d.promise);
  const p = layar(); const lama = muat(p);
  for (let i = 0; i < 5; i++) await giliran();
  expect(snapshotMeta).toHaveBeenCalledTimes(2);
  p.k.penjaga.aktifkan("B"); d.resolve(null);
  expect(await lama).toBe(HASIL_USANG);
  expect(toast.error).not.toHaveBeenCalled();
});

test("snapshot mengembalikan baris Simpan Lanjut dan membatalkan statistik daring tertunda", async () => {
  const stat = tertunda(); axios.get.mockReturnValue(stat.promise);
  const p = layar(); const statistik = p.doFetchStats("");
  p.k.isOnlineRef.current = false;
  getSnapshotAssets.mockResolvedValue([{ id: "cache", purchase_price: 50 }]);
  expect(await muat(p)).toEqual([{ id: "cache", purchase_price: 50 }]);
  expect(p.state.Stats.totalAssets).toBe(1);
  stat.resolve({ data: { total_assets: 999 } });
  expect(await statistik).toBe(HASIL_USANG);
  expect(p.state.Stats.totalAssets).toBe(1);
  expect(p.state.OfflineLastSync).toBe("waktu-cache");
});

test.each([false, true])("preserveMobile berlaku juga setelah clamp; offline=%s", async offline => {
  const p = layar({ isOnlineRef: { current: !offline } });
  if (offline) getSnapshotAssets.mockResolvedValue([{ id: "cache" }]);
  else axios.get.mockResolvedValueOnce({ data: { items: [], total: 1, total_pages: 1 } }).mockResolvedValueOnce(respons("server"));
  await muat(p, 9, true);
  expect(p.state.CurrentPage).toBe(1);
  expect(p.state.MobileAssets).toEqual([{ id: "awal" }]);
  expect(p.k.setMobileCurrentPage).not.toHaveBeenCalled();
  expect(p.k.setMobileFirstPage).not.toHaveBeenCalled();
  if (!offline) expect(axios.get.mock.calls[1][0]).toContain("page=1&");
});

test("clamp lama tidak merebut prioritas request baru", async () => {
  const clamp = tertunda(), baru = tertunda();
  axios.get.mockResolvedValueOnce({ data: { items: [], total: 1, total_pages: 1 } })
    .mockReturnValueOnce(clamp.promise).mockReturnValueOnce(baru.promise);
  const p = layar(); const lama = muat(p, 9); await giliran();
  expect(axios.get).toHaveBeenCalledTimes(2);
  const terkini = muat(p, 3); baru.resolve(respons("baru", 3)); await terkini;
  clamp.resolve(respons("clamp")); expect(await lama).toBe(HASIL_USANG);
  expect(p.state.Assets).toEqual([{ id: "baru" }]);
});

test.each(["loadMoreMobile", "loadPrevMobile"])("%s terserial secara sinkron, bukan menunggu setState", async metode => {
  const d = tertunda(); axios.get.mockReturnValue(d.promise);
  const p = layar(); const pertama = p[metode]();
  expect(await p.loadMoreMobile()).toBe(HASIL_USANG);
  expect(await p.loadPrevMobile()).toBe(HASIL_USANG);
  expect(axios.get).toHaveBeenCalledTimes(1);
  d.resolve(respons("tambahan")); await pertama;
  expect(p.state.MobileAssets.map(a => a.id)).toEqual(metode === "loadMoreMobile" ? ["awal", "tambahan"] : ["tambahan", "awal"]);
  expect(p.state.MobileLoading).toBe(false);
});

test.each([false, true])("penggantian daftar membatalkan append/prepend lama termasuk finally; gagal=%s", async gagal => {
  const a = tertunda(), b = tertunda(), c = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise).mockReturnValueOnce(c.promise);
  const p = layar(); const lama = p.loadMoreMobile(); const daftar = muat(p);
  expect(await p.loadPrevMobile()).toBe(HASIL_USANG); // jendela sedang diganti
  b.resolve(respons("baru")); await daftar;
  const mobileBaru = p.loadPrevMobile();
  expect(p.state.MobileLoading).toBe(true);
  if (gagal) a.reject(new Error("lama")); else a.resolve(respons("lama"));
  expect(await lama).toBe(HASIL_USANG);
  expect(p.state.MobileLoading).toBe(true);
  expect(p.state.MobileAssets).toEqual([{ id: "baru" }]);
  expect(toast.error).not.toHaveBeenCalled();
  c.resolve(respons("sebelumnya")); await mobileBaru;
  expect(p.state.MobileAssets.map(a => a.id)).toEqual(["sebelumnya", "baru"]);
  expect(p.state.MobileLoading).toBe(false);
});

test("refresh preserveMobile tidak membatalkan append yang sedang berjalan", async () => {
  const a = tertunda(); axios.get.mockReturnValueOnce(a.promise).mockResolvedValueOnce(respons("tabel"));
  const p = layar(); const mobile = p.loadMoreMobile(); await muat(p, 2, true);
  a.resolve(respons("tambahan")); await mobile;
  expect(p.state.Assets).toEqual([{ id: "tabel" }]);
  expect(p.state.MobileAssets.map(a => a.id)).toEqual(["awal", "tambahan"]);
});

test.each([false, true])("pending CREATE tetap terlihat dan hanya kegiatan aktif; offline=%s", async offline => {
  const p = layar({ isOnlineRef: { current: !offline } });
  p.k.getPendingItems.mockReturnValue([
    { tempId: "temp", payload: { activity_id: "kegiatan-a" } },
    { tempId: "lain", payload: { activity_id: "kegiatan-b" } },
  ]);
  if (offline) getSnapshotAssets.mockResolvedValue([{ id: "cache" }]);
  else axios.get.mockResolvedValue(respons("server"));
  const rows = await muat(p);
  expect(rows.map(a => a.id)).toEqual(["temp", offline ? "cache" : "server"]);
});

test("snapshot kedaluwarsa tetap memberi pesan yang dapat ditindaklanjuti", async () => {
  const p = layar(); axios.get.mockRejectedValue(new Error("jaringan"));
  isSnapshotExpired.mockReturnValue(true);
  await muat(p);
  expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("kedaluwarsa"), expect.any(Object));
  expect(p.state.LoadingMessage).toContain("kedaluwarsa");
});

test.each(["loadMoreMobile", "loadPrevMobile"])("%s membedakan batas halaman sah dari callback lingkup usang", async metode => {
  const p = layar({ mobileCurrentPage: 10, mobileFirstPage: 1 });
  expect(await p[metode]()).toBeNull();
  expect(p.k.penjaga.sibuk("mobile")).toBe(false);
  p.k.penjaga.aktifkan("B");
  expect(await p[metode]()).toBe(HASIL_USANG);
  expect(axios.get).not.toHaveBeenCalled();
  expect(p.k.setMobileLoading).not.toHaveBeenCalled();
});
