import { act, renderHook, waitFor } from "@testing-library/react";
import axios from "axios";
import { useOperasiBatch } from "../useOperasiBatch";
import { kunciCheckpointBatch } from "@/lib/operasiBatch";
jest.mock("axios");

test("hasil yang ditutup tidak muncul lagi saat online atau muat ulang", async () => {
  const response = { applied: 1, pending: 0, results: [{ id: "a", status: "applied" }] };
  localStorage.setItem(kunciCheckpointBatch("user", "satker"), JSON.stringify({ schema: 1, total: 1,
    children: [{ operation_id: "op", asset_ids: ["a"], prepared: true, response }] }));
  axios.get.mockResolvedValue({ data: response });
  const options = { owner: "user", satker: "satker", sessionId: "test" };
  const { result, unmount } = renderHook(() => useOperasiBatch(options));
  await waitFor(() => expect(result.current.busy).toBe(false));
  act(() => { result.current.clear(); });
  expect(result.current.operation).toBeNull();
  axios.get.mockClear();
  act(() => window.dispatchEvent(new Event("online")));
  expect(axios.get).not.toHaveBeenCalled();
  expect(result.current.operation).toBeNull();
  unmount();
  const reload = renderHook(() => useOperasiBatch(options));
  expect(reload.result.current.operation).toBeNull();
  expect(axios.get).not.toHaveBeenCalled();
});
