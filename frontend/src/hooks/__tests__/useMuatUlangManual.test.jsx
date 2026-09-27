import { act, renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { useMuatUlangManual } from "../useMuatUlangManual";

jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
beforeEach(() => jest.clearAllMocks());

test("hanya tindakan eksplisit memuat ulang dan klik ganda tidak menggandakan permintaan", async () => {
  let selesai;
  const refresh = jest.fn(() => new Promise(r => { selesai = r; }));
  const { result } = renderHook(() => useMuatUlangManual(refresh));
  expect(refresh).not.toHaveBeenCalled();
  let tugas;
  act(() => { tugas = result.current.onRefreshData(); result.current.onRefreshData(); });
  expect(result.current.refreshing).toBe(true);
  expect(refresh).toHaveBeenCalledTimes(1);
  expect(refresh).toHaveBeenCalledWith(undefined);
  await act(async () => { selesai([]); await tugas; });
  expect(result.current.refreshing).toBe(false);
});

test("gagal dapat dicoba lagi tanpa rejection tak tertangani", async () => {
  const refresh = jest.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue([]);
  const { result } = renderHook(() => useMuatUlangManual(refresh));
  await act(async () => { await result.current.onRefreshData(); });
  expect(toast.error).toHaveBeenCalledTimes(1);
  expect(result.current.refreshing).toBe(false);
  await act(async () => { await result.current.onRefreshData(); });
  expect(refresh).toHaveBeenCalledTimes(2);
});

test("lepas halaman tidak menampilkan notifikasi terlambat atau menerima klik lama", async () => {
  let gagal;
  const refresh = jest.fn(() => new Promise((_, reject) => { gagal = reject; }));
  const { result, unmount } = renderHook(() => useMuatUlangManual(refresh));
  const callback = result.current.onRefreshData;
  let tugas;
  act(() => { tugas = callback(); });
  unmount();
  await act(async () => { gagal(new Error("terlambat")); await tugas; await callback(); });
  expect(toast.error).not.toHaveBeenCalled();
  expect(refresh).toHaveBeenCalledTimes(1);
});
