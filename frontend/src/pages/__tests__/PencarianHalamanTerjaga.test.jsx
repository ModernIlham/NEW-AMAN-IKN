import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import KodefikasiPage from "../KodefikasiPage";
import PersediaanPage from "../PersediaanPage";
import PenggunaanPage from "../PenggunaanPage";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
const cases = [
  ["kodefikasi", KodefikasiPage, "/kodefikasi", id => ({ kode: id, uraian: id, level: 5 })],
  ["persediaan", PersediaanPage, "/persediaan", id => ({ id, kode_barang: id, nama_barang: id, nup: 1 })],
  ["penggunaan", PenggunaanPage, "/penggunaan/pemegang", id => ({ nama: id, nip: id, jumlah_aset: 1 })],
];
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
beforeEach(() => { jest.useFakeTimers(); jest.clearAllMocks(); });
afterEach(() => { jest.useRealTimers(); });

test.each(cases)("%s: respons A/B terbalik, clear, satker, dan unmount tidak menulis hasil lama", async (name, Page, endpoint, row) => {
  const requests = [];
  axios.get.mockImplementation((url, config) => {
    if (url.endsWith(endpoint)) {
      const d = deferred(); requests.push({ ...d, config }); return d.promise;
    }
    if (url.endsWith("/persediaan/peringatan")) return Promise.resolve({ data: { kedaluwarsa: [], segera_kedaluwarsa: [] } });
    return Promise.resolve({ data: { items: [] } });
  });
  const { rerender, unmount } = render(<Page user={{ id: "u", kode_satker: "A", role: "admin" }} />);
  const input = screen.getByTestId(`${name}-search`);
  fireEvent.change(input, { target: { value: "lama" } });
  expect(requests[0].config.signal.aborted).toBe(true);
  await act(async () => { jest.advanceTimersByTime(350); });
  const a = requests.at(-1);
  fireEvent.change(input, { target: { value: "baru" } });
  expect(a.config.signal.aborted).toBe(true);
  await act(async () => { jest.advanceTimersByTime(350); });
  const b = requests.at(-1);
  await act(async () => { b.resolve({ data: { items: [row("HASIL-BARU")], total_pages: 2 } }); });
  expect(screen.getAllByText("HASIL-BARU").length).toBeGreaterThan(0);
  await act(async () => { a.resolve({ data: { items: [row("HASIL-LAMA")] } }); });
  expect(screen.queryByText("HASIL-LAMA")).not.toBeInTheDocument();
  // Empty query invalidates immediately, before its replacement debounce runs.
  fireEvent.change(input, { target: { value: "menunggu" } });
  await act(async () => { jest.advanceTimersByTime(350); });
  const clear = requests.at(-1);
  fireEvent.change(input, { target: { value: "" } });
  expect(clear.config.signal.aborted).toBe(true);
  await act(async () => { clear.reject(new Error("putus usang")); });
  expect(toast.error).not.toHaveBeenCalled();
  await act(async () => { jest.advanceTimersByTime(350); });
  const oldScope = requests.at(-1);
  rerender(<Page user={{ id: "u", kode_satker: "B", role: "admin" }} />);
  expect(oldScope.config.signal.aborted).toBe(true);
  const current = requests.at(-1);
  unmount();
  expect(current.config.signal.aborted).toBe(true);
  await act(async () => { oldScope.reject(new Error("scope lama")); current.reject(new Error("dilepas")); });
  expect(toast.error).not.toHaveBeenCalled();
});
