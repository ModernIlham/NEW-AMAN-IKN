import "../../uji/indexedDB";
import { deleteDB } from "idb";
import { act, renderHook, waitFor } from "@testing-library/react";
import axios from "axios";
import { useOptimisticQueue } from "../useOptimisticQueue";

jest.mock("axios", () => {
  const upload = { patch: jest.fn(), put: jest.fn(), post: jest.fn(), interceptors: { request: { use: () => {} } } };
  return { create: () => upload, upload };
});
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../../lib/connectivity", () => ({ checkReachable: async () => false, REACHABILITY_RETRY_MS: 10000 }));


function tertunda() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
const item = asset_name => ({ tempId: "a", isEdit: true, editId: "a", usePatch: true,
  baseVersion: 5, payload: { asset_name, activity_id: "keg" } });

beforeEach(async () => { await deleteDB("aman_save_queue"); localStorage.setItem("user", JSON.stringify({ id: "alice" })); });

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
  await act(async () => { await pertama.persisted; });
  await waitFor(() => expect(axios.upload.patch).toHaveBeenCalledTimes(1));
  await act(async () => { a.resolve({ data: { id: "a", version: 6 } }); await pertama; });
  expect(terlihat).toEqual([["Kedua"]]);
  expect(onItemSaved).not.toHaveBeenCalled();
  await waitFor(() => expect(p.result.current.syncStatuses.a.status).toBe("saving"));
  expect(axios.upload.patch.mock.calls[1][2].headers["If-Match"]).toBe("6");
  await act(async () => { b.resolve({ data: { id: "a", version: 7 } }); await kedua; });
  expect(terlihat).toEqual([["Kedua"], []]);
  expect(onItemSaved).toHaveBeenCalledTimes(1);
  expect(p.result.current.getPendingItems()).toEqual([]);
});

test("versi rekan tidak diambil otomatis untuk melewati pemeriksaan konflik server", async () => {
  const p = renderHook(() => useOptimisticQueue({ getLatestVersion: () => 99 }));
  axios.upload.patch.mockResolvedValue({ data: { id: "a", version: 6 } });
  await act(async () => { await p.result.current.enqueue(item("Edit")); });
  expect(axios.upload.patch.mock.calls[0][2].headers["If-Match"]).toBe("5");
});

test("409 idempotensi sedang diproses mengulang kunci identik tanpa konflik/rebase", async () => {
  const onConflict = jest.fn();
  axios.upload.patch.mockRejectedValueOnce({ response: { status: 409,
    data: { detail: "Permintaan dengan kunci idempotensi ini sedang diproses, coba lagi sebentar" } } });
  axios.upload.patch.mockResolvedValue({ data: { id: "a", version: 6 } });
  const p = renderHook(() => useOptimisticQueue({ onConflict, getLatestVersion: () => 99 }));
  let saving;
  await act(async () => { saving = p.result.current.enqueue(item("Photo retry")); await saving.persisted; });
  await act(async () => { await saving.catch(() => {}); });
  expect(onConflict).not.toHaveBeenCalled();
  act(() => p.result.current.flushPending());
  await waitFor(() => expect(axios.upload.patch).toHaveBeenCalledTimes(2));
  const first = axios.upload.patch.mock.calls[0], next = axios.upload.patch.mock.calls[1];
  expect(next[1]).toEqual(first[1]);
  expect(next[2].headers["Idempotency-Key"]).toBe(first[2].headers["Idempotency-Key"]);
  expect(next[2].headers["If-Match"]).toBe("5");
  await waitFor(() => expect(p.result.current.getPendingItems()).toHaveLength(0));
});

test("batal menghapus mempertahankan foto; konfirmasi menghapus seluruh operasi satu aset sekali", async () => {
  const confirm = jest.spyOn(window, "confirm").mockReturnValue(false);
  const online = jest.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  const onItemDismissed = jest.fn();
  const p = renderHook(() => useOptimisticQueue({ onItemDismissed }));
  await act(async () => {
    await p.result.current.enqueue({ ...item("first"), payload: { photo_ops: { add: ["foto"] } } }).persisted;
    await p.result.current.enqueue(item("second")).persisted;
  });
  act(() => p.result.current.dismiss("a"));
  expect(p.result.current.getPendingItems()).toHaveLength(2);
  expect(onItemDismissed).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  act(() => p.result.current.dismiss("a"));
  await waitFor(() => expect(p.result.current.getPendingItems()).toHaveLength(0));
  expect(onItemDismissed).toHaveBeenCalledTimes(1);
  online.mockRestore(); confirm.mockRestore();
});
