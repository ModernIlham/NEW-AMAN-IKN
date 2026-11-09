import "../../uji/indexedDB";
import { deleteDB } from "idb";
import { appendOperation } from "../../lib/saveOutbox";
import { act, renderHook, waitFor } from "@testing-library/react";
import axios from "axios";
import { useOptimisticQueue } from "../useOptimisticQueue";
jest.mock("axios", () => {
  const upload = { post: jest.fn(), interceptors: { request: { use: () => {} } } };
  return { create: () => upload, upload };
});
jest.mock("../../lib/saveOutbox", () => ({ ...jest.requireActual("../../lib/saveOutbox"), appendOperation: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../../lib/connectivity", () => ({ checkReachable: async () => false, REACHABILITY_RETRY_MS: 10000 }));
beforeEach(async () => { await deleteDB("aman_save_queue"); localStorage.setItem("user", JSON.stringify({ id: "alice" })); });
const item = { tempId: "test-create", payload: { asset_name: "Kursi", photos: ["foto"] }, isEdit: false };
test("request server menunggu commit IDB; receipt lokal berbeda dari penyelesaian server", async () => {
  let commit;
  const committed = new Promise(resolve => { commit = resolve; });
  appendOperation.mockImplementation(async (...args) => { await committed; return jest.requireActual("../../lib/saveOutbox").appendOperation(...args); });
  axios.upload.post.mockImplementation(() => new Promise(() => {}));
  const p = renderHook(() => useOptimisticQueue({}));
  let saving;
  await act(async () => { saving = p.result.current.enqueue(item); });
  expect(axios.upload.post).not.toHaveBeenCalled();
  await act(async () => { commit(); await saving.persisted; });
  await waitFor(() => expect(axios.upload.post).toHaveBeenCalledTimes(1));
});
test("write gagal menolak receipt dan tidak mengirim ke server", async () => {
  appendOperation.mockRejectedValue(new Error("disk penuh"));
  const p = renderHook(() => useOptimisticQueue({}));
  let saving;
  await act(async () => {
    saving = p.result.current.enqueue(item);
    saving.catch(() => {});
    await expect(saving.persisted).rejects.toThrow("disk penuh");
  });
  expect(axios.upload.post).not.toHaveBeenCalled();
  expect(p.result.current.getPendingItems()[0].payload.photos).toEqual(["foto"]);
});

test("form yang menyimpan ulang sesudah disk gagal tidak meninggalkan percobaan RAM lama", async () => {
  const online = jest.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  appendOperation.mockRejectedValueOnce(new Error("disk penuh"))
    .mockImplementation(jest.requireActual("../../lib/saveOutbox").appendOperation);
  const p = renderHook(() => useOptimisticQueue({}));
  const edit = { ...item, isEdit: true, editId: "asset", usePatch: true };
  await act(async () => {
    const failed = p.result.current.enqueue(edit);
    await failed.persisted.catch(() => {});
    failed.discardUncommitted(); // caller keeps edit.payload in its form/draft
    await p.result.current.enqueue(edit).persisted;
  });
  expect(p.result.current.getPendingItems()).toHaveLength(1);
  expect(p.result.current.getPendingItems()[0].payload.photos).toEqual(["foto"]);
  online.mockRestore();
});
