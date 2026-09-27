import { useState } from "react";
import { act, renderHook } from "@testing-library/react";
import axios from "axios";
import { useRekonsiliasiBaris } from "../useRekonsiliasiBaris";
import { usePenjagaPermintaan } from "../usePenjagaPermintaan";
import { upsertSnapshotAsset } from "../../lib/offlineSnapshot";

jest.mock("axios", () => ({ get: jest.fn() }));
jest.mock("../../lib/offlineSnapshot", () => ({ upsertSnapshotAsset: jest.fn() }));
const baris = (version, asset_name = `Versi ${version}`) => ({ id: "a", activity_id: "keg", version, asset_name });
function tertunda() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
function siapkan() {
  const refs = { pendingItemsRef: { current: () => [] }, editAssetRef: { current: null }, wsNeedsRefreshRef: { current: false } };
  const hook = renderHook(({ lingkup }) => {
    const [assets, setAssets] = useState([baris(5)]);
    const [mobileAssets, setMobileAssets] = useState([baris(5)]);
    const penjaga = usePenjagaPermintaan(lingkup);
    const aksi = useRekonsiliasiBaris({ activityId: "keg", lingkupPermintaan: lingkup, penjaga, setAssets, setMobileAssets, ...refs });
    return { ...aksi, assets, mobileAssets, penjaga };
  }, { initialProps: { lingkup: "awal" } });
  return { ...hook, ...refs };
}
test("dua respons WS terbalik tidak memundurkan kedua daftar maupun cache", async () => {
  const a = tertunda(), b = tertunda();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const p = siapkan(); let satu, dua;
  act(() => { satu = p.result.current.muatBaris("a"); dua = p.result.current.muatBaris("a"); });
  await act(async () => { b.resolve({ data: baris(7) }); await dua; });
  await act(async () => { a.resolve({ data: baris(6) }); await satu; });
  expect(p.result.current.assets).toEqual([baris(7)]);
  expect(p.result.current.mobileAssets).toEqual([baris(7)]);
  expect(upsertSnapshotAsset).toHaveBeenCalledTimes(1);
});
test("WS dimulai sebelum simpan: respons versi lama tidak menimpa hasil simpan", async () => {
  const a = tertunda(); axios.get.mockReturnValue(a.promise);
  const p = siapkan(); let request;
  act(() => { request = p.result.current.muatBaris("a"); p.result.current.terapkanBaris(baris(8)); });
  await act(async () => { a.resolve({ data: baris(6) }); await request; });
  expect(p.result.current.assets).toEqual([baris(8)]);
  expect(p.result.current.mobileAssets).toEqual([baris(8)]);
});
test.each(["lingkup", "unmount", "hapus"])("respons setelah %s diabaikan sebelum menulis cache", async sebab => {
  const a = tertunda(); axios.get.mockReturnValue(a.promise);
  const p = siapkan(); let request;
  act(() => { request = p.result.current.muatBaris("a"); });
  if (sebab === "lingkup") p.rerender({ lingkup: "baru" });
  if (sebab === "unmount") p.unmount();
  if (sebab === "hapus") p.result.current.penjaga.batalkan("baris:a");
  await act(async () => { a.resolve({ data: baris(6) }); await request; });
  expect(upsertSnapshotAsset).not.toHaveBeenCalled();
});
test("pengguna mulai mengedit ketika GET masih terbang", async () => {
  const a = tertunda(); axios.get.mockReturnValue(a.promise);
  const p = siapkan(); const request = p.result.current.muatBaris("a", true);
  p.editAssetRef.current = { id: "a" };
  await act(async () => { a.resolve({ data: baris(6) }); await request; });
  expect(p.result.current.assets).toEqual([baris(5)]);
  expect(p.wsNeedsRefreshRef.current).toBe(true);
  expect(upsertSnapshotAsset).not.toHaveBeenCalled();
});
test("respons simpan pertama tidak menimpa baris/cache dengan edit kedua pending", () => {
  const p = siapkan();
  p.pendingItemsRef.current = () => [{ isEdit: true, editId: "a" }];
  act(() => p.result.current.terapkanBaris(baris(6)));
  expect(p.result.current.assets).toEqual([baris(5)]);
  expect(p.result.current.mobileAssets).toEqual([baris(5)]);
  expect(upsertSnapshotAsset).not.toHaveBeenCalled();
  p.pendingItemsRef.current = () => [];
  act(() => p.result.current.terapkanBaris(baris(7)));
  expect(p.result.current.assets).toEqual([baris(7)]);
});
