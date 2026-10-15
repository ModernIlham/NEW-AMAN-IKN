import { act, renderHook } from "@testing-library/react";
import { usePencarianBaca } from "../usePencarianBaca";
function deferred() {
  let resolve, reject; const promise = new Promise((a,b) => { resolve = a; reject = b; });
  return { resolve, reject, promise };
}
beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());
test("query lama/scope dan error lama tidak mengganti hasil atau mematikan loading baru", async () => {
  const a = deferred(), b = deferred();
  const hasil = jest.fn(), gagal = jest.fn(), selesai = jest.fn(), kosong = jest.fn();
  const run = jest.fn().mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  const { rerender, unmount } = renderHook(p => usePencarianBaca({ ...p, delay: 10,
    jalankan: run, padaHasil: hasil, padaGagal: gagal, padaSelesai: selesai, padaKosong: kosong }),
  { initialProps: { lingkup: "satkerA", kunci: "lama", aktif: true } });
  await act(async () => jest.advanceTimersByTime(10));
  const signalA = run.mock.calls[0][0];
  rerender({ lingkup: "satkerA", kunci: "baru", aktif: true });
  expect(signalA.aborted).toBe(true);
  await act(async () => jest.advanceTimersByTime(10));
  await act(async () => { a.reject(new Error("usang")); });
  expect(gagal).not.toHaveBeenCalled(); expect(selesai).not.toHaveBeenCalled();
  await act(async () => { b.resolve("baru"); });
  expect(hasil).toHaveBeenCalledWith("baru"); expect(selesai).toHaveBeenCalledTimes(1);
  rerender({ lingkup: "satkerA", kunci: "menunggu", aktif: true });
  rerender({ lingkup: "satkerA", kunci: "", aktif: false });
  expect(kosong).toHaveBeenCalledTimes(1);
  await act(async () => jest.advanceTimersByTime(20)); expect(run).toHaveBeenCalledTimes(2);
  unmount();
});
