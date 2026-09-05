/**
 * Riwayat SPPB — bukti pengeluaran barang persediaan.
 *
 * Sisi masuk sudah punya Riwayat LPB sejak lama; sisi keluar tak punya apa-apa.
 * Tanpa layar ini, SPPB yang terbit otomatis dari transaksi keluar tak pernah
 * bisa ditemukan lagi.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import RiwayatSppb from "../RiwayatSppb";

const mockUnduh = jest.fn();
jest.mock("@/lib/downloadFile", () => ({
  downloadFileWithProgress: (...a) => mockUnduh(...a),
}));
jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("@/components/ttd/TautanTtdDialog", () => function Palsu({ srId }) {
  return <div data-testid="tautan-ttd-dialog">{srId}</div>;
});

const SPPB = {
  id: "s1", nomor: "B-9/PL.01/2026", jenis: "habis_pakai",
  jenis_label: "Pemakaian Habis Pakai", jumlah_barang: 3,
  tanggal: "2026-09-05", penerima_nama: "Budi Santoso",
  unit_penerima: "Bagian Umum",
};

beforeEach(() => {
  mockUnduh.mockImplementation(() => Promise.resolve());
  axios.post.mockResolvedValue({ data: { id: "sr-1" } });
});

async function buka(items, user = { role: "operator" }) {
  axios.get.mockResolvedValue({ data: { total: items.length, items } });
  render(<RiwayatSppb user={user} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await userEvent.click(screen.getByTestId("persediaan-riwayat-sppb"));
  if (items.length) await screen.findByTestId(`persediaan-riwayat-sppb-${items[0].id}`);
}

test("menyebut penerima dan unitnya, bukan hanya nomornya", async () => {
  // Inti dokumen ini adalah SIAPA yang menerima; daftar yang hanya menyebut
  // nomor mengembalikan masalah yang justru hendak diselesaikan.
  await buka([{ ...SPPB, ttd: null }]);
  expect(screen.getByText("B-9/PL.01/2026")).toBeInTheDocument();
  expect(screen.getByText(/Budi Santoso/)).toBeInTheDocument();
  expect(screen.getByText(/Bagian Umum/)).toBeInTheDocument();
  expect(screen.getByText(/5 September 2026/)).toBeInTheDocument();
});

test("SPPB tanpa nomor tetap tampil, bukan disembunyikan", async () => {
  await buka([{ ...SPPB, nomor: "", ttd: null }]);
  expect(screen.getByText("Belum bernomor")).toBeInTheDocument();
  expect(screen.getByTestId("persediaan-riwayat-sppb-unduh-s1")).toBeInTheDocument();
});

test("yang belum dikirim menawarkan Kirim TTD", async () => {
  await buka([{ ...SPPB, ttd: null }]);
  await userEvent.click(screen.getByTestId("persediaan-riwayat-sppb-kirim-ttd-s1"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(String(axios.post.mock.calls[0][0]))
    .toContain("/persediaan/sppb/s1/kirim-ttd");
});

test("yang sudah dikirim menampilkan status dan jalan kembali ke tautannya", async () => {
  await buka([{
    ...SPPB, signature_request_id: "sr-1",
    ttd: { id: "sr-1", judul: "SPPB B-9", status: "terkirim",
           jumlah: 2, selesai_jumlah: 0, membubuhkan_jumlah: 0 },
  }]);
  expect(screen.getByTestId("persediaan-riwayat-sppb-ttd-s1")).toBeInTheDocument();
  expect(screen.queryByTestId("persediaan-riwayat-sppb-kirim-ttd-s1")).toBeNull();
  await userEvent.click(screen.getByTestId("persediaan-riwayat-sppb-tautan-s1"));
  expect(await screen.findByTestId("tautan-ttd-dialog")).toHaveTextContent("sr-1");
});

test("viewer tidak ditawari mengirim tanda tangan, tetap boleh mengunduh", async () => {
  await buka([{ ...SPPB, ttd: null }], { role: "viewer" });
  expect(screen.queryByTestId("persediaan-riwayat-sppb-kirim-ttd-s1")).toBeNull();
  expect(screen.getByTestId("persediaan-riwayat-sppb-unduh-s1")).toBeInTheDocument();
});

test("daftar kosong menyebutkan dari mana SPPB berasal", async () => {
  // "Belum ada data" saja membuat orang mencari tombol yang tak pernah ada.
  await buka([]);
  expect(await screen.findByTestId("persediaan-riwayat-sppb-kosong"))
    .toHaveTextContent(/transaksi keluar massal/);
});
