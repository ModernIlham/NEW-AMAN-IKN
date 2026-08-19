/**
 * Uji render dialog pemilihan Nota Dinas — stok kritis/habis DAN kedaluwarsa.
 *
 * Sifat yang dijaga: PILIHAN operator benar-benar sampai ke URL unduhan —
 * barang yang tidak dicentang tidak ikut di `ids`, dan saat semua terpilih
 * URL kembali ke bentuk tanpa `ids` (perilaku lama "semua barang").
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NotaDinasDialog, { kelompokkanPerBarang } from "../NotaDinasDialog";

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
  render(<NotaDinasDialog items={ITEMS} />);
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

// ── Nota dinas KEDALUWARSA ───────────────────────────────────────────────────
// Permintaan pemilik: "setiap nota dinas dapat memilih barangnya sesuai
// seleksi" — bukan hanya yang kritis. Yang menentukan bentuk layarnya: satu
// barang bisa punya BEBERAPA layer bertanggal berbeda, sementara penyaring
// server bekerja per id BARANG. Pilihan karena itu disajikan per barang.

const LAYER = [
  { id: "b-1", nama_barang: "Masker Medis", kode_barang: "M001", satuan: "Box",
    qty: 5, expired: "2026-09-01", lewat: true },
  { id: "b-1", nama_barang: "Masker Medis", kode_barang: "M001", satuan: "Box",
    qty: 3, expired: "2026-08-20", lewat: true },
  { id: "b-2", nama_barang: "Hand Sanitizer", kode_barang: "M002", satuan: "Botol",
    qty: 7, expired: "2026-10-15" },
];

describe("kelompokkanPerBarang", () => {
  test("layer satu barang diringkas jadi satu baris", () => {
    const hasil = kelompokkanPerBarang(LAYER);
    expect(hasil).toHaveLength(2);
    const masker = hasil.find((x) => x.id === "b-1");
    expect(masker.n_layer).toBe(2);
    expect(masker.total_qty).toBe(8);
  });

  test("tanggal yang ditampilkan adalah yang TERDEKAT", () => {
    // Yang paling mendesak; menampilkan yang terjauh akan menenangkan
    // pembaca justru pada barang yang paling perlu ditindak.
    const masker = kelompokkanPerBarang(LAYER).find((x) => x.id === "b-1");
    expect(masker.expired_terdekat).toBe("2026-08-20");
  });

  test("baris tanpa id diabaikan, bukan meledak", () => {
    expect(kelompokkanPerBarang([{ qty: 1 }, null])).toEqual([]);
    expect(kelompokkanPerBarang(undefined)).toEqual([]);
  });
});

describe("dialog kedaluwarsa", () => {
  async function bukaKedaluwarsa() {
    render(<NotaDinasDialog items={LAYER} jenis="kedaluwarsa" />);
    await userEvent.click(screen.getByTestId("persediaan-nota-kedaluwarsa"));
    await screen.findByTestId("nota-kedaluwarsa-item-b-1");
  }

  test("menghitung BARANG, bukan layer", async () => {
    await bukaKedaluwarsa();
    expect(screen.getByText(/Unduh Nota Dinas \(2 barang\)/)).toBeInTheDocument();
  });

  test("semua tercentang → unduh tanpa ids, dan jenisnya benar", async () => {
    await bukaKedaluwarsa();
    await userEvent.click(screen.getByTestId("nota-kedaluwarsa-unduh"));
    await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
    const url = String(mockUnduh.mock.calls[0][0]);
    expect(url).toContain("jenis=kedaluwarsa");
    expect(url).not.toContain("ids=");
  });

  test("barang yang dilepas tidak ikut di ids", async () => {
    await bukaKedaluwarsa();
    await userEvent.click(screen.getByTestId("nota-kedaluwarsa-item-b-1"));
    expect(screen.getByText(/Unduh Nota Dinas \(1 barang\)/)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("nota-kedaluwarsa-unduh"));
    await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
    const url = String(mockUnduh.mock.calls[0][0]);
    expect(url).toContain("ids=b-2");
    expect(url).not.toContain("b-1");
  });

  test("melepas satu barang melepas SELURUH layer-nya", async () => {
    // Konsekuensi jujur dari penyaring server yang bekerja per id barang.
    // Kalau layar menjanjikan pilihan per layer, ia berbohong.
    await bukaKedaluwarsa();
    expect(screen.queryAllByTestId(/^nota-kedaluwarsa-item-b-1$/)).toHaveLength(1);
  });
});
