import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axios from "axios";
import PanduanTipografiStiker from "../PanduanTipografiStiker";

jest.mock("axios", () => ({ get: jest.fn() }));
const spec = (kertas = "A4", size = 9) => ({ kertas, font_tebal: "Helvetica-Bold", font_biasa: "Helvetica",
  peran: [{ kode: "nama", nama: "Nama barang", tebal: true }, { kode: "sub", nama: "Baris kedua header", tebal: false }],
  ukuran: ["besar", "sedang", "kecil"].map((kode, i) => ({ kode, nama: kode, lebar_mm: 98.25 - i * 20,
    tinggi_mm: 46.25 - i * 10, font_pt: { nama: size - i, sub: size - i - 1 } })) });
const buka = () => {
  const d = screen.getByTestId("stiker-tipografi");
  d.open = true;
  fireEvent(d, new Event("toggle"));
};

beforeEach(() => { jest.clearAllMocks(); axios.get.mockResolvedValue({ data: spec() }); });

test("panduan dilipat dan tidak meminta jaringan sebelum dibuka", async () => {
  render(<PanduanTipografiStiker aktif kertas="A4" ukuran="sedang" />);
  expect(axios.get).not.toHaveBeenCalled();
  buka();
  await screen.findByTestId("stiker-tipografi-tabel");
  expect(axios.get).toHaveBeenCalledWith(expect.stringContaining("/stiker/tipografi"), { params: { kertas: "A4" } });
  expect(screen.getByText("Helvetica-Bold")).toBeInTheDocument();
  expect(within(screen.getByTestId("stiker-tipografi-tabel")).getByText("8")).toBeInTheDocument();
  expect(screen.getByText(/sebelum penyesuaian teks panjang/)).toHaveTextContent("Cetak 100%");
});

test("mode per aset menampilkan semua ukuran tanpa menyalin angka lokal", async () => {
  render(<PanduanTipografiStiker aktif kertas="A4" ukuran="per_aset" />); buka();
  const table = await screen.findByTestId("stiker-tipografi-tabel");
  ["besar", "sedang", "kecil"].forEach(n => expect(within(table).getByRole("columnheader", { name: n })).toBeInTheDocument());
});

test("hasil A4 terlambat tidak menimpa ukuran A3", async () => {
  let resolve;
  axios.get.mockReturnValueOnce(new Promise(r => { resolve = r; })).mockResolvedValue({ data: spec("A3", 11) });
  const { rerender } = render(<PanduanTipografiStiker aktif kertas="A4" ukuran="besar" />); buka();
  await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
  rerender(<PanduanTipografiStiker aktif kertas="A3" ukuran="besar" />);
  await screen.findByTestId("stiker-tipografi-tabel");
  await act(async () => resolve({ data: spec("A4", 9) }));
  expect(screen.getByTestId("stiker-tipografi-tabel")).toHaveTextContent("kertas A3");
  expect(within(screen.getByTestId("stiker-tipografi-tabel")).getByText("11")).toBeInTheDocument();
});

test("kegagalan dapat dicoba lagi dan tidak mengunci cetak", async () => {
  axios.get.mockRejectedValueOnce(new Error("offline"));
  render(<PanduanTipografiStiker aktif kertas="A4" ukuran="besar" />); buka();
  expect(await screen.findByRole("alert")).toHaveTextContent("Pembuatan PDF tetap dapat dicoba");
  fireEvent.click(screen.getByTestId("stiker-tipografi-coba-lagi"));
  await screen.findByTestId("stiker-tipografi-tabel");
});

test("respons rusak menampilkan pesan, bukan merusak dialog", async () => {
  axios.get.mockResolvedValue({ data: {} });
  render(<PanduanTipografiStiker aktif kertas="A4" ukuran="besar" />); buka();
  await screen.findByRole("alert");
});
