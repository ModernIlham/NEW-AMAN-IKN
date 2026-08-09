/**
 * Uji render dialog pemilihan Nota Dinas stok kritis/habis.
 *
 * Sifat yang dijaga: PILIHAN operator benar-benar sampai ke URL unduhan —
 * barang yang tidak dicentang tidak ikut di `ids`, dan saat semua terpilih
 * URL kembali ke bentuk tanpa `ids` (perilaku lama "semua barang").
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotaDinasKritisDialog from "../NotaDinasKritisDialog";

const mockUnduh = jest.fn();
jest.mock("@/lib/downloadFile", () => ({
  downloadFileWithProgress: (...a) => mockUnduh(...a),
}));

const ITEMS = [
  { id: "hab-1", nama_barang: "Kertas HVS A4", kode_barang: "K001",
    stok: 0, batas_kritis: 5, satuan: "Rim" },
  { id: "kri-1", nama_barang: "Tinta Printer Hitam", kode_barang: "K002",
    stok: 2, batas_kritis: 5, satuan: "Botol" },
];

// resetMocks CRA menghapus implementasi tiap uji — pasang ulang di sini.
beforeEach(() => mockUnduh.mockImplementation(() => Promise.resolve()));

async function bukaDialog() {
  render(<NotaDinasKritisDialog items={ITEMS} />);
  await userEvent.click(screen.getByTestId("persediaan-nota-kritis"));
  await screen.findByTestId("nota-kritis-item-hab-1");
}

test("semua tercentang → unduh tanpa parameter ids (perilaku lama)", async () => {
  await bukaDialog();
  expect(screen.getByText(/Unduh Nota Dinas \(2 barang\)/)).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("nota-kritis-unduh"));
  await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
  const url = String(mockUnduh.mock.calls[0][0]);
  expect(url).toContain("jenis=kritis");
  expect(url).not.toContain("ids=");
});

test("barang yang tidak dicentang tidak ikut di ids", async () => {
  await bukaDialog();
  await userEvent.click(screen.getByTestId("nota-kritis-item-kri-1"));
  expect(screen.getByText(/Unduh Nota Dinas \(1 barang\)/)).toBeInTheDocument();
  await userEvent.click(screen.getByTestId("nota-kritis-unduh"));
  await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
  const url = String(mockUnduh.mock.calls[0][0]);
  expect(url).toContain("ids=hab-1");
  expect(url).not.toContain("kri-1");
});

test("tanpa satu pun pilihan tombol unduh mati", async () => {
  await bukaDialog();
  await userEvent.click(screen.getByTestId("nota-kritis-kosongkan"));
  expect(screen.getByTestId("nota-kritis-unduh")).toBeDisabled();
  expect(mockUnduh).not.toHaveBeenCalled();
});
