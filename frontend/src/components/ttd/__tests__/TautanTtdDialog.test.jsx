/**
 * Jalan KEMBALI ke tautan tanda tangan sebuah dokumen.
 *
 * Laporan pemilik: dialog tautan yang lama hanya hidup di layar; begitu
 * ditutup, tautannya tak bisa ditemukan lagi dari dokumennya. Satu-satunya
 * jalan kembali adalah modul TTD elektronik — dan ketika orang akhirnya ke
 * sana, jendela 14 harinya kerap sudah lewat.
 *
 * Yang paling mudah rusak tanpa terlihat: menerbitkan tautan OTOMATIS saat
 * dialog dibuka. Itu terasa membantu, tetapi menerbitkan ulang MEMATIKAN
 * tautan lama — sekadar melihat-lihat akan membatalkan tautan yang sudah
 * telanjur dikirim ke orang yang belum sempat meneken.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import TautanTtdDialog from "../TautanTtdDialog";

jest.mock("axios");

const DETAIL = {
  id: "sr-1", judul: "BAST 1/2026", status: "terkirim",
  signers: [
    { signer_id: "s1", nama: "Budi", jabatan: "Pengurus Barang",
      status: "aktif", kedaluwarsa_info: { sisa_detik: 0, perkiraan: false } },
    { signer_id: "s2", nama: "Sari", jabatan: "Pemegang",
      status: "ditandatangani", kedaluwarsa_info: { sisa_detik: 0 } },
  ],
};

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: DETAIL });
  axios.post.mockResolvedValue({ data: { nama: "Budi", link: "https://x/s/AbCdEf1234" } });
});

function pasang(props = {}) {
  render(<TautanTtdDialog srId="sr-1" judul="BAST 1/2026"
    onTutup={() => {}} {...props} />);
}

test("memuat detail permintaan, bukan membuat permintaan baru", async () => {
  pasang();
  await screen.findByTestId("ttd-signer-s1");
  expect(String(axios.get.mock.calls[0][0])).toMatch(/\/ttd\/permintaan\/sr-1$/);
  expect(axios.post).not.toHaveBeenCalled();
});

test("TIDAK menerbitkan tautan otomatis saat dibuka", async () => {
  pasang();
  await screen.findByTestId("ttd-signer-s1");
  // Menerbitkan ulang mematikan tautan lama — tak boleh terjadi tanpa diminta.
  expect(axios.post).not.toHaveBeenCalled();
});

test("tautan mati tetap menawarkan terbitkan ulang", async () => {
  pasang();
  expect(await screen.findByTestId("ttd-terbit-ulang-s1")).toBeInTheDocument();
  expect(screen.getByText("Tautan mati")).toBeInTheDocument();
});

test("yang sudah menandatangani tidak ditawari tautan lagi", async () => {
  pasang();
  await screen.findByTestId("ttd-signer-s2");
  expect(screen.queryByTestId("ttd-terbit-ulang-s2")).toBeNull();
  expect(screen.getByText("Sudah menandatangani")).toBeInTheDocument();
});

test("terbitkan ulang menembak endpoint penanda tangan itu saja", async () => {
  pasang();
  await userEvent.click(await screen.findByTestId("ttd-terbit-ulang-s1"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(String(axios.post.mock.calls[0][0]))
    .toMatch(/\/ttd\/permintaan\/sr-1\/link\/s1$/);
});

test("tautan baru ditampilkan agar bisa disalin", async () => {
  pasang();
  await userEvent.click(await screen.findByTestId("ttd-terbit-ulang-s1"));
  expect(await screen.findByTestId("ttd-link-baru-s1"))
    .toHaveTextContent("https://x/s/AbCdEf1234");
});

test("induk diberi tahu agar status dokumennya ikut diperbarui", async () => {
  const onBerubah = jest.fn();
  pasang({ onBerubah });
  await userEvent.click(await screen.findByTestId("ttd-terbit-ulang-s1"));
  await waitFor(() => expect(onBerubah).toHaveBeenCalled());
});

test("gagal memuat tidak membuat dialog kosong tanpa keterangan", async () => {
  axios.get.mockRejectedValue({ response: { data: { detail: "Tidak ditemukan" } } });
  pasang();
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  expect(await screen.findByText(/Tidak ada penanda tangan/i)).toBeInTheDocument();
});
