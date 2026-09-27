import { act, renderHook } from "@testing-library/react";
import axios from "axios";
import { useOptimisticQueue } from "../useOptimisticQueue";

jest.mock("axios", () => {
  const upload = { patch: jest.fn(), put: jest.fn(), post: jest.fn(), interceptors: { request: { use: () => {} } } };
  return { create: () => upload, upload };
});
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../../lib/connectivity", () => ({ checkReachable: async () => false, REACHABILITY_RETRY_MS: 10000 }));
jest.mock("idb", () => ({ openDB: async () => ({ getAll: async () => [], get: async () => null, put: async () => {}, delete: async () => {} }) }));

function tertunda() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
const item = asset_name => ({ tempId: "a", isEdit: true, editId: "a", usePatch: true,
  baseVersion: 5, payload: { asset_name, activity_id: "keg" } });

beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

test("callback simpan pertama melihat edit kedua, callback terakhir melihat antrean kosong", async () => {
  const a = tertunda(), b = tertunda();
  axios.upload.patch.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const terlihat = [];
  const onItemSaved = jest.fn();
  const p = renderHook(() => useOptimisticQueue({ onItemSaved,
    onRowSynced: () => terlihat.push(p.result.current.getPendingItems().map(it => it.payload.asset_name)) }));
  let pertama, kedua;
  act(() => { pertama = p.result.current.enqueue(item("Pertama")); });
  act(() => { kedua = p.result.current.enqueue(item("Kedua")); });
  expect(axios.upload.patch).toHaveBeenCalledTimes(1);
  await act(async () => { a.resolve({ data: { id: "a", version: 6 } }); await pertama; });
  expect(terlihat).toEqual([["Kedua"]]);
  expect(onItemSaved).not.toHaveBeenCalled();
  expect(p.result.current.syncStatuses.a.status).toBe("saving");
  expect(axios.upload.patch.mock.calls[1][2].headers["If-Match"]).toBe("6");
  await act(async () => { b.resolve({ data: { id: "a", version: 7 } }); await kedua; });
  expect(terlihat).toEqual([["Kedua"], []]);
  expect(onItemSaved).toHaveBeenCalledTimes(1);
  expect(p.result.current.syncStatuses.a.status).toBe("saved");
});

test("versi rekan tidak diambil otomatis untuk melewati pemeriksaan konflik server", async () => {
  const p = renderHook(() => useOptimisticQueue({ getLatestVersion: () => 99 }));
  axios.upload.patch.mockResolvedValue({ data: { id: "a", version: 6 } });
  await act(async () => { await p.result.current.enqueue(item("Edit")); });
  expect(axios.upload.patch.mock.calls[0][2].headers["If-Match"]).toBe("5");
});
