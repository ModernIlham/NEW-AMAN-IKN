import { act, renderHook, waitFor } from "@testing-library/react";
import { useLensaKamera } from "./useLensaKamera";

const kamera = id => ({ readyState: "live", getSettings: () => ({ deviceId: id }) });
const daftar = (...ids) => ids.map(deviceId => ({ kind: "videoinput", deviceId, label: deviceId }));
let media;
beforeEach(() => {
  localStorage.removeItem("aman_lensa_makro_perangkat_v1");
  media = { enumerateDevices: jest.fn(), addEventListener: jest.fn(), removeEventListener: jest.fn() };
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: media });
});
test("hasil enumerasi lama tidak menimpa perubahan perangkat terbaru", async () => {
  let lama; media.enumerateDevices.mockReturnValueOnce(new Promise(r => { lama = r; })).mockResolvedValue(daftar("utama", "baru"));
  const track = kamera("utama"); const { result } = renderHook(() => useLensaKamera(track, true));
  expect(result.current.memuat).toBe(true);
  const berubah = media.addEventListener.mock.calls[0][1];
  await act(async () => { await berubah(); });
  expect(result.current.daftar.map(d => d.id)).toEqual(["utama", "baru"]);
  await act(async () => { lama(daftar("utama", "usang")); });
  expect(result.current.daftar.map(d => d.id)).toEqual(["utama", "baru"]);
});
test("enumerasi gagal menghapus daftar usang dan memasang penjelasan", async () => {
  media.enumerateDevices.mockResolvedValue(daftar("utama", "macro"));
  const track = kamera("utama"); const { result } = renderHook(() => useLensaKamera(track, true));
  await waitFor(() => expect(result.current.memuat).toBe(false));
  media.enumerateDevices.mockRejectedValue(Error("Izin dibatasi"));
  await act(async () => { await media.addEventListener.mock.calls[0][1](); });
  expect(result.current.daftar).toEqual([]); expect(result.current.kandidat).toBeNull();
  expect(result.current.galat).toContain("Browser tidak menyediakan daftar kamera");
});
test("ID tersimpan yang hilang tidak dipakai dan kamera aktif tidak dipilih ulang", async () => {
  localStorage.setItem("aman_lensa_makro_perangkat_v1", "hilang");
  media.enumerateDevices.mockResolvedValue(daftar("utama", "Camera 2"));
  const track = kamera("utama"); const { result } = renderHook(() => useLensaKamera(track, true));
  await waitFor(() => expect(result.current.memuat).toBe(false));
  expect(result.current.kandidat).toBeNull();
  expect(result.current.pilih("hilang")).toBe(false); expect(result.current.pilih("utama")).toBe(false);
  expect(result.current.permintaan.deviceId).toBe("");
});
test("pergantian track melepas listener dan mengabaikan enumerasi track lama", async () => {
  let lama; media.enumerateDevices.mockReturnValueOnce(new Promise(r => { lama = r; })).mockResolvedValue(daftar("baru"));
  const { result, rerender, unmount } = renderHook(({ track }) => useLensaKamera(track, true), { initialProps: { track: kamera("utama") } });
  rerender({ track: kamera("baru") });
  await waitFor(() => expect(result.current.memuat).toBe(false));
  await act(async () => { lama(daftar("usang")); });
  expect(result.current.daftar.map(d => d.id)).toEqual(["baru"]);
  unmount(); expect(media.removeEventListener).toHaveBeenCalledTimes(2);
});
