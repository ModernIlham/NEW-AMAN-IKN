import React from "react";
import { render, screen } from "@testing-library/react";
import axios from "axios";
import TtdPublikPage from "@/pages/TtdPublikPage";

jest.mock("axios");
jest.mock("../SignatureCapture", () => () => null);
jest.mock("../AturPosisiTtd", () => () => null);

afterEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, "", "/");
});

test("verifikasi publik menampilkan NIK tersamar, bukan NIP", async () => {
  window.history.replaceState({}, "", "/ttd/verifikasi/sr-uji");
  axios.get.mockResolvedValue({ data: { judul: "Dokumen Uji", status: "terkirim",
    penanda_tangan: [{ nama: "Pegawai Uji", jabatan: "Konsultan Individu",
      nip: "•••••••••••••001", label_identitas: "NIK", status: "aktif" }] } });
  render(<TtdPublikPage />);
  expect(await screen.findByText("Konsultan Individu · NIK •••••••••••••001"))
    .toBeInTheDocument();
  expect(screen.queryByText(/NIP/)).not.toBeInTheDocument();
});

test("halaman penanda tangan dan tooltip memakai label yang sama", async () => {
  window.history.replaceState({}, "", "/ttd/sr-uji?token=token-uji");
  axios.get.mockResolvedValue({ data: { judul: "Dokumen Uji", status_dokumen: "terkirim",
    penanda_tangan: { nama: "Pegawai Uji", jabatan: "Konsultan Individu",
      nip: "3506042503900001", label_identitas: "NIK", status: "aktif" } } });
  render(<TtdPublikPage />);
  expect(await screen.findByText("Konsultan Individu · NIK 3506042503900001"))
    .toHaveAttribute("title", "Konsultan Individu · NIK 3506042503900001");
  expect(screen.queryByText(/NIP/)).not.toBeInTheDocument();
});
