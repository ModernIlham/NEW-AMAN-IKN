import { act, renderHook, waitFor } from "@testing-library/react";
import axios from "axios";
import useReferensiSatker from "../useReferensiSatker";
import { kabarkanPerubahanSatker, REFERENSI_SATKER_EVENT } from "@/lib/referensiSatker";
import { terapkanHeaderSatker } from "@/lib/satkerAktif";

jest.mock("axios");
jest.mock("@/lib/muatAndal", () => ({ TENGGAT_BAKA: 20000, muatAndal: (fn) => fn() }));

beforeEach(() => { jest.clearAllMocks(); localStorage.clear(); });
const respons = (nama) => ({ data: { items: [{ kode_satker: "A", nama_satker: nama, terdaftar: false }] } });

test("daftar legacy tetap ditawarkan dan perubahan langsung disegarkan", async () => {
  axios.get.mockResolvedValueOnce(respons("Lama")).mockResolvedValueOnce(respons("Baru"));
  const { result } = renderHook(() => useReferensiSatker());
  await waitFor(() => expect(result.current.daftar[0]?.nama_satker).toBe("Lama"));
  act(() => kabarkanPerubahanSatker());
  await waitFor(() => expect(result.current.daftar[0]?.nama_satker).toBe("Baru"));
});

test("respons lama yang terlambat tidak menimpa nama terbaru", async () => {
  let selesaiLama;
  axios.get.mockImplementationOnce(() => new Promise((resolve) => { selesaiLama = resolve; }))
    .mockResolvedValueOnce(respons("Baru"));
  const { result } = renderHook(() => useReferensiSatker());
  act(() => kabarkanPerubahanSatker());
  await waitFor(() => expect(result.current.daftar[0]?.nama_satker).toBe("Baru"));
  await act(async () => selesaiLama(respons("Lama")));
  expect(result.current.daftar[0].nama_satker).toBe("Baru");
});

test("antar tab/fokus memperbarui daftar, tutup dialog menghentikan penulisan hasil", async () => {
  axios.get.mockResolvedValue(respons("Lama"));
  const { result, rerender } = renderHook(({ open }) => useReferensiSatker(open), { initialProps: { open: true } });
  await waitFor(() => expect(result.current.daftar.length).toBe(1));
  axios.get.mockResolvedValue(respons("Tab lain"));
  act(() => window.dispatchEvent(new StorageEvent("storage", { key: REFERENSI_SATKER_EVENT })));
  await waitFor(() => expect(result.current.daftar[0]?.nama_satker).toBe("Tab lain"));
  rerender({ open: false });
  const n = axios.get.mock.calls.length;
  act(() => window.dispatchEvent(new Event("focus")));
  expect(axios.get).toHaveBeenCalledTimes(n);
});

test("header kosong eksplisit memulihkan pemilih ketika kode aktif basi", () => {
  localStorage.setItem("satker_aktif", "KODE-LAMA");
  expect(terapkanHeaderSatker({ headers: {} }).headers["X-Satker-Aktif"]).toBe("KODE-LAMA");
  expect(terapkanHeaderSatker({ headers: { "X-Satker-Aktif": "" } }).headers["X-Satker-Aktif"]).toBe("");
});
