import { act, renderHook } from "@testing-library/react";
import { useMakroKamera } from "./useMakroKamera";
import { cariFokusMakro, terapkanFokus } from "../lib/makroKamera";
jest.mock("../lib/makroKamera", () => ({
  deteksiMakro: () => ({ jenis: "manual" }), bacaFokus: () => ({ focusMode: "continuous" }),
  pembacaKetajaman: () => () => 10, cariFokusMakro: jest.fn(), terapkanFokus: jest.fn(async () => {}),
}));
function janji() { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; }
test("menutup/mengganti kamera membatalkan hasil lambat dan hanya memulihkan track lama", async () => {
  const d = janji(); cariFokusMakro.mockReturnValue(d.promise); terapkanFokus.mockResolvedValue();
  const lama = { readyState: "live" }, baru = { readyState: "live" }, ref = { current: {} };
  const h = renderHook(({ track }) => useMakroKamera(track, ref, false), { initialProps: { track: lama } });
  await act(async () => { h.result.current.toggle(); });
  expect(h.result.current.status).toBe("mencari");
  h.rerender({ track: baru });
  await act(async () => { d.resolve("manual"); await d.promise; });
  expect(h.result.current.status).toBe("mati");
  expect(terapkanFokus).toHaveBeenCalledWith(lama, { focusMode: "continuous" });
  expect(terapkanFokus.mock.calls[0][0]).toBe(lama);
  expect(terapkanFokus.mock.calls[0][0]).not.toBe(baru);
});
test("makro aktif dapat dimatikan dan kegagalan memulihkan fokus sebelum membuka rana", async () => {
  cariFokusMakro.mockResolvedValueOnce("manual").mockRejectedValueOnce(Error("Ditolak kamera"));
  terapkanFokus.mockResolvedValue();
  const track = { readyState: "live" }, ref = { current: {} };
  const h = renderHook(() => useMakroKamera(track, ref, false));
  await act(async () => { await h.result.current.toggle(); });
  expect(h.result.current.status).toBe("aktif");
  await act(async () => { await h.result.current.toggle(); });
  expect(h.result.current.status).toBe("mati");
  await act(async () => { await h.result.current.toggle(); });
  expect(h.result.current.pesan).toBe("Ditolak kamera");
  expect(h.result.current.sibuk).toBe(false);
  expect(terapkanFokus).toHaveBeenCalledTimes(2);
});
test("kamera baru tidak menunggu operasi kamera lama yang belum selesai", async () => {
  const d = janji(); cariFokusMakro.mockReturnValueOnce(d.promise).mockResolvedValueOnce("manual");
  terapkanFokus.mockResolvedValue();
  const lama = { readyState: "live" }, baru = { readyState: "live" }, ref = { current: {} };
  const h = renderHook(({ track }) => useMakroKamera(track, ref, false), { initialProps: { track: lama } });
  await act(async () => { h.result.current.toggle(); });
  h.rerender({ track: baru });
  await act(async () => { await h.result.current.toggle(); });
  expect(h.result.current.status).toBe("aktif");
  await act(async () => { d.resolve("manual"); await d.promise; });
  expect(h.result.current.status).toBe("aktif");
  expect(terapkanFokus.mock.calls[0][0]).toBe(lama);
});
