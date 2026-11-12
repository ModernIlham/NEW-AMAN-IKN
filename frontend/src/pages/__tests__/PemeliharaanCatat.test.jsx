import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import PemeliharaanPage from "../PemeliharaanPage";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn(), warning: jest.fn() } }));

const ASET = { id: "a1", asset_code: "3100102001", NUP: "1", asset_name: "AC Split" };
const PT = { id: "pt1", nama: "PT Servis Andal", kelompok: "pihak_ketiga", tataran: "" };

beforeEach(() => {
  jest.useFakeTimers(); jest.clearAllMocks(); localStorage.clear();
  axios.get.mockImplementation((url, config) => {
    if (url.endsWith("/assets")) return Promise.resolve({ data: { items: [ASET], total: 1, total_pages: 1 } });
    if (url.endsWith("/pemeliharaan")) return Promise.resolve({ data: { items: [], total: 0, total_pages: 1 } });
    if (url.endsWith("/luar/instansi")) {
      return Promise.resolve({ data: { items: config.params.kelompok === "pihak_ketiga" ? [PT] : [] } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
  axios.post.mockResolvedValue({ data: { id: "c1", peringatan_kebijakan: ["Instansi pelaksana ini berstatus nonaktif di direktori"] } });
});
afterEach(() => jest.useRealTimers());
async function tick() { await act(async () => { jest.advanceTimersByTime(350); }); }

test("tombol + membuka pemilih aset (bukan event klik sebagai aset) dan menyimpan tautan pelaksana", async () => {
  render(<PemeliharaanPage user={{ role: "admin", id: "u", kode_satker: "A" }} />);
  await act(async () => {});
  fireEvent.click(screen.getByTestId("pemeliharaan-tambah"));
  // Regresi: dulu `onClick={bukaForm}` menjadikan event klik sebagai aset.
  fireEvent.change(screen.getByTestId("pemeliharaan-cari-aset"), { target: { value: "AC Split" } }); await tick();
  fireEvent.click(screen.getByTestId("pemeliharaan-pilih-aset-a1"));
  fireEvent.change(screen.getByTestId("pemeliharaan-uraian"), { target: { value: "Ganti kompresor" } });
  fireEvent.change(screen.getByTestId("pemeliharaan-pelaksana"), { target: { value: "PT Servis" } }); await tick();
  fireEvent.change(screen.getByTestId("pemeliharaan-pelaksana"), { target: { value: PT.nama } });
  expect(screen.getByTestId("pemeliharaan-pelaksana-status")).toHaveTextContent("Tertaut");
  fireEvent.click(screen.getByTestId("pemeliharaan-simpan"));
  await act(async () => {});
  expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/pemeliharaan$/), expect.objectContaining({
    asset_id: "a1", pelaksana: PT.nama, pelaksana_instansi_id: "pt1" }));
  expect(toast.warning).toHaveBeenCalledWith("Instansi pelaksana ini berstatus nonaktif di direktori");
});
