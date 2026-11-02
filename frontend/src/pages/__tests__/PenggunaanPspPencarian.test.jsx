import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import axios from "axios";
import PenggunaanPage from "../PenggunaanPage";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
const rows = Array.from({ length: 35 }, (_, n) => ({ id: `psp-${n + 1}`,
  asset_code: "3999901777", NUP: String(n + 1), asset_name: `Laptop NUP ${n + 1}` }));
beforeEach(() => {
  jest.useFakeTimers(); jest.clearAllMocks(); localStorage.clear();
  axios.get.mockImplementation((url, config) => {
    if (url.endsWith("/assets")) {
      const { page, page_size: size, nup } = config.params;
      const all = nup ? rows.filter(a => a.NUP === String(Number(nup))) : rows;
      return Promise.resolve({ data: { items: all.slice((page - 1) * size, page * size), total: all.length, total_pages: Math.ceil(all.length / size) } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
  axios.post.mockResolvedValue({ data: { id: "new-sk" } });
});
afterEach(() => jest.useRealTimers());
async function tick() { await act(async () => { jest.advanceTimersByTime(350); }); }

test("Catat SK preserves choices from page 1 and NUP 35 on page 2, then saves the right asset IDs", async () => {
  render(<PenggunaanPage user={{ role: "admin", id: "user", kode_satker: "A" }} />);
  await act(async () => {});
  fireEvent.click(screen.getByTestId("penggunaan-psp-tambah"));
  fireEvent.change(screen.getByTestId("penggunaan-psp-cari"), { target: { value: "3999901777" } }); await tick();
  fireEvent.click(screen.getByTestId("penggunaan-psp-cari-pilih-psp-1"));
  expect(screen.getByTestId("penggunaan-psp-cari")).toHaveValue("3999901777");
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset berikutnya" })); await tick();
  fireEvent.click(screen.getByTestId("penggunaan-psp-cari-pilih-psp-35"));
  fireEvent.change(screen.getByTestId("penggunaan-psp-cari-nup"), { target: { value: "1" } }); await tick();
  expect(screen.getByTestId("penggunaan-psp-cari-pilih-psp-1")).toBeDisabled();
  expect(screen.queryByTestId("penggunaan-psp-cari-pilih-psp-11")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("penggunaan-psp-nomor"), { target: { value: "SK-1" } });
  fireEvent.click(screen.getByTestId("penggunaan-psp-simpan"));
  await act(async () => {});
  expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/penggunaan\/psp$/), expect.objectContaining({
    nomor_sk: "SK-1", asset_ids: ["psp-1", "psp-35"],
  }));
});
