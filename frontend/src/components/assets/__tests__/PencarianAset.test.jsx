import React, { useState } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import axios from "axios";
import PencarianAset from "../PencarianAset";
import { SATKER_AKTIF_EVENT } from "@/lib/satkerAktif";

jest.mock("axios");
const assets = Array.from({ length: 55 }, (_, n) => ({
  id: `asset-${n + 1}`, asset_code: "3100102001", NUP: String(n + 1), asset_name: `Laptop ${n + 1}`,
}));
function api() {
  axios.get.mockImplementation((_url, config) => {
    const { page, page_size: size, nup } = config.params;
    const all = nup ? assets.filter(a => a.NUP === String(Number(nup))) : assets;
    return Promise.resolve({ data: { items: all.slice((page - 1) * size, page * size),
      total: all.length, total_pages: Math.ceil(all.length / size) } });
  });
}
function Harness({ user = { id: "admin" }, ...props }) {
  const [value, onChange] = useState("");
  const [chosen, setChosen] = useState([]);
  return <>
    <PencarianAset {...props} user={user} value={value} onChange={onChange}
      selectedIds={chosen.map(a => a.id)} onPilih={asset => setChosen(rows => [...rows, asset])} />
    <output data-testid="chosen">{chosen.map(a => a.id).join(",")}</output>
  </>;
}
async function settle() { await act(async () => { jest.advanceTimersByTime(350); }); }
beforeEach(() => { jest.useFakeTimers(); jest.clearAllMocks(); localStorage.clear(); api(); });
afterEach(() => jest.useRealTimers());

test("55 NUP reachable across pages; choices survive navigation and duplicate rows stay disabled", async () => {
  render(<Harness />);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "3100102001" } });
  await settle();
  expect(screen.getByText("1–20 dari 55 aset")).toBeInTheDocument();
  expect(axios.get.mock.calls.at(-1)[1].params).toMatchObject({ page: 1, page_size: 20, pencarian_lengkap: true });
  fireEvent.click(screen.getByTestId("cari-aset-pilih-asset-1"));
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset berikutnya" })); await settle();
  expect(screen.getByText("21–40 dari 55 aset")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset berikutnya" })); await settle();
  fireEvent.click(screen.getByTestId("cari-aset-pilih-asset-55"));
  expect(screen.getByTestId("chosen")).toHaveTextContent("asset-1,asset-55");
  expect(screen.getByRole("button", { name: "Halaman aset berikutnya" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset sebelumnya" })); await settle();
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset sebelumnya" })); await settle();
  expect(screen.getByTestId("cari-aset-pilih-asset-1")).toBeDisabled();
});

test("exact one-digit NUP narrows at server and resets the page, including returning to an old query", async () => {
  render(<Harness />);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "Laptop" } }); await settle();
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset berikutnya" })); await settle();
  fireEvent.change(screen.getByLabelText("NUP persis"), { target: { value: "1" } }); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params).toMatchObject({ search: "Laptop", nup: "1", page: 1 });
  expect(screen.getByTestId("cari-aset-pilih-asset-1")).toBeInTheDocument();
  expect(screen.queryByTestId("cari-aset-pilih-asset-11")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("NUP persis"), { target: { value: "" } }); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params.page).toBe(1);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "Kode lain" } }); await settle();
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "Laptop" } }); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params.page).toBe(1);
});

test("NUP alone can search; malformed NUP makes no broad unfiltered request", async () => {
  render(<Harness />);
  expect(axios.get).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("NUP persis"), { target: { value: "9" } }); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params).toMatchObject({ search: "", nup: "9" });
  axios.get.mockClear();
  fireEvent.change(screen.getByLabelText("NUP persis"), { target: { value: "9x" } }); await settle();
  expect(screen.getByRole("alert")).toHaveTextContent("NUP harus");
  expect(axios.get).not.toHaveBeenCalled();
  expect(screen.queryByTestId("cari-aset-pilih-asset-9")).not.toBeInTheDocument();
});

test("condition constraint and empty candidate search survive page changes", async () => {
  render(<Harness allowEmpty filters={{ condition: "Rusak Berat" }} />); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params).toMatchObject({ condition: "Rusak Berat", search: "", page: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Halaman aset berikutnya" })); await settle();
  expect(axios.get.mock.calls.at(-1)[1].params).toMatchObject({ condition: "Rusak Berat", page: 2 });
});

test("query change hides old rows immediately; late response, clear and unmount cannot restore them", async () => {
  const calls = [];
  axios.get.mockImplementation((_url, config) => new Promise(resolve => calls.push({ config, resolve })));
  const { unmount } = render(<Harness />);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "lama" } }); await settle();
  const old = calls[0];
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "baru" } });
  expect(old.config.signal.aborted).toBe(true);
  await settle();
  await act(async () => calls[1].resolve({ data: { items: [assets[1]], total: 1, total_pages: 1 } }));
  expect(screen.getByTestId("cari-aset-pilih-asset-2")).toBeInTheDocument();
  await act(async () => old.resolve({ data: { items: [assets[0]], total: 1, total_pages: 1 } }));
  expect(screen.queryByTestId("cari-aset-pilih-asset-1")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "" } });
  expect(screen.queryByTestId("cari-aset-pilih-asset-2")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "pending" } }); await settle();
  unmount(); expect(calls.at(-1).config.signal.aborted).toBe(true);
});

test("satker switch pins new requests and refuses clicks before its change event", async () => {
  localStorage.setItem("satker_aktif", "A");
  render(<Harness />);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "Laptop" } }); await settle();
  expect(axios.get.mock.calls.at(-1)[1].headers["X-Satker-Aktif"]).toBe("A");
  localStorage.setItem("satker_aktif", "B");
  fireEvent.click(screen.getByTestId("cari-aset-pilih-asset-1"));
  expect(screen.getByTestId("chosen")).toBeEmptyDOMElement();
  act(() => window.dispatchEvent(new Event(SATKER_AKTIF_EVENT))); await settle();
  expect(axios.get.mock.calls.at(-1)[1].headers["X-Satker-Aktif"]).toBe("B");
});

test("failure stays distinct from no matches and can be retried", async () => {
  axios.get.mockRejectedValueOnce(new Error("offline"));
  render(<Harness />);
  fireEvent.change(screen.getByTestId("cari-aset"), { target: { value: "Laptop" } }); await settle();
  expect(screen.getByRole("alert")).toHaveTextContent("Gagal memuat aset");
  fireEvent.click(screen.getByRole("button", { name: "Coba lagi" })); await settle();
  expect(screen.getByText("1–20 dari 55 aset")).toBeInTheDocument();
});
