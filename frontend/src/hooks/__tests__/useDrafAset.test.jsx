import { act, renderHook } from "@testing-library/react";
import { useBackGuard } from "../useBackGuard";
import { useDrafAset } from "../useDrafAset";
import { bacaDraf, tulisDraf, hapusDraf } from "../../lib/drafAset";
jest.mock("../../lib/drafAset", () => ({ bacaDraf: jest.fn(), tulisDraf: jest.fn(), hapusDraf: jest.fn() }));
let records;
const value = { formData: { asset_name: "Kursi", photos: ["data:image/jpeg;base64,FOTO"] }, photoItems: [] };
const defaults = { scope: "akun-A:kegiatan-1:baru", value, enabled: true, dirty: true, onRestore: jest.fn() };
beforeEach(() => {
  jest.useFakeTimers(); records = new Map();
  bacaDraf.mockImplementation(async key => records.get(key));
  tulisDraf.mockImplementation(async (key, value, revision) => {
    const record = { key, value, revision: revision + 1 }; records.set(key, record); return record;
  });
  hapusDraf.mockImplementation(async (key, revision) => { if (records.get(key)?.revision === revision) records.delete(key); });
});
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });
async function settle() { await act(async () => {}); }

test("draf dan foto pulih sesudah unmount mendadak sebelum debounce, tanpa menimpa isian baru otomatis", async () => {
  const p = renderHook(props => useDrafAset(props), { initialProps: defaults });
  await settle();
  const newer = { ...value, formData: { ...value.formData, asset_name: "Kursi terbaru" } };
  p.rerender({ ...defaults, value: newer });
  p.unmount(); await settle();
  const restore = jest.fn();
  const next = renderHook(() => useDrafAset({ ...defaults, value: {}, onRestore: restore }));
  await settle();
  expect(next.result.current.candidate.value).toEqual(newer);
  expect(restore).not.toHaveBeenCalled();
  act(() => next.result.current.restore());
  expect(restore).toHaveBeenCalledWith(newer);
});

test("penyelesaian simpan aset lama tidak menghapus draf aset yang baru dibuka", async () => {
  const p = renderHook(props => useDrafAset(props), { initialProps: defaults }); await settle();
  const clearOld = p.result.current.clearCurrent();
  p.rerender({ ...defaults, scope: "akun-A:kegiatan-1:aset-B" }); await settle();
  await act(async () => { await clearOld(); });
  expect(records.has(defaults.scope)).toBe(false);
  expect(records.get("akun-A:kegiatan-1:aset-B").value).toEqual(value);
});

test("galat penyimpanan tidak menghilangkan isian dan retry menulis foto yang sama", async () => {
  tulisDraf.mockRejectedValueOnce(new Error("QuotaExceededError"));
  const p = renderHook(() => useDrafAset(defaults)); await settle();
  expect(p.result.current.status).toBe("error");
  await act(async () => { await p.result.current.flush(); });
  expect(p.result.current.status).toBe("saved");
  expect(records.get(defaults.scope).value.formData.photos).toEqual(value.formData.photos);
});

test("scope akun berbeda tidak memulihkan draf akun sebelumnya", async () => {
  records.set(defaults.scope, { revision: 2, value });
  const p = renderHook(() => useDrafAset({ ...defaults, scope: "akun-B:kegiatan-1:baru", dirty: false }));
  await settle(); expect(p.result.current.candidate).toBeNull();
  expect(records.get(defaults.scope).value).toEqual(value);
});

test("restore yang ditolak karena versi server berbeda tetap mempertahankan cadangan", async () => {
  records.set(defaults.scope, { revision: 1, value });
  const p = renderHook(() => useDrafAset({ ...defaults, onRestore: () => false })); await settle();
  act(() => p.result.current.restore());
  expect(p.result.current.candidate.value).toEqual(value);
});

test("Back menunggu commit lokal; kegagalan write menahan navigasi dan isian", async () => {
  const p = renderHook(props => useDrafAset(props), { initialProps: defaults }); await settle();
  p.rerender({ ...defaults, value: { ...value, note: "baru" } });
  tulisDraf.mockRejectedValue(new Error("disk penuh"));
  const proceed = jest.fn();
  const back = new CustomEvent("aman:before-back", { cancelable: true, detail: { proceed } });
  await act(async () => { window.dispatchEvent(back); });
  expect(back.defaultPrevented).toBe(true);
  expect(proceed).not.toHaveBeenCalled();
  expect(p.result.current.status).toBe("error");
});


test("popstate menutup form hanya setelah commit draf selesai", async () => {
  const onBack = jest.fn();
  const p = renderHook(props => { useBackGuard(onBack); return useDrafAset(props); }, { initialProps: defaults });
  await settle();
  let commit;
  tulisDraf.mockImplementation(() => new Promise(resolve => { commit = () => resolve({ revision: 2 }); }));
  p.rerender({ ...defaults, value: { ...value, note: "foto terbaru" } });
  await act(async () => { window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(onBack).not.toHaveBeenCalled();
  await act(async () => { commit(); });
  expect(onBack).toHaveBeenCalledTimes(1);
});
