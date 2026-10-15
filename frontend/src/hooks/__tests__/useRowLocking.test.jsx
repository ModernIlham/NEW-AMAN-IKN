import { act, renderHook } from "@testing-library/react";
import axios from "axios";
import { useRowLocking } from "../useRowLocking";
jest.mock("axios");
function deferred() { let resolve; const promise = new Promise(r => { resolve = r; }); return { resolve, promise }; }
beforeEach(() => jest.clearAllMocks());
test("refresh setelah resync membatalkan polling lama dan respons kegiatan lama tidak mengganti lock", async () => {
  const a = deferred(), b = deferred(), c = deferred();
  axios.get.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise).mockReturnValueOnce(c.promise);
  const props = { activityId: "A", user: { id: "u", kode_satker: "s" }, wsSend: jest.fn() };
  const { result, rerender, unmount } = renderHook(useRowLocking, { initialProps: props });
  let refresh;
  act(() => { refresh = result.current.refreshLocks(); });
  expect(axios.get.mock.calls[0][1].signal.aborted).toBe(true);
  await act(async () => { b.resolve({ data: { locks: { fresh: { user_name: "Baru" } } } }); await refresh; });
  await act(async () => { a.resolve({ data: { locks: { stale: {} } } }); });
  expect(result.current.rowLocks).toEqual({ fresh: { user_name: "Baru" } });
  rerender({ ...props, activityId: "B" });
  unmount(); expect(axios.get.mock.calls[2][1].signal.aborted).toBe(true);
  await act(async () => { c.resolve({ data: { locks: { wrong: {} } } }); });
});
