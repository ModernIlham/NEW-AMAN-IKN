/**
 * Uji render dialog Referensi Kode Mutasi Aset Tetap — memastikan daftar
 * dari GET /pembukuan/jenis-transaksi benar-benar dirender terbelah per
 * arah (bertambah/berkurang) plus bagian kode warisan, bukan sekadar
 * tombol yang membuka dialog kosong.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import ReferensiKodeMutasiDialog from "../ReferensiKodeMutasiDialog";

jest.mock("axios");

const DATA = {
  referensi: [
    { kode: "100", uraian: "Saldo Awal", arah: "bertambah",
      kelompok: "perolehan", label_kelompok: "Perolehan" },
    { kode: "502", uraian: "Perolehan/Penambahan KDP", arah: "bertambah",
      kelompok: "kdp", label_kelompok: "Konstruksi Dalam Pengerjaan (KDP)" },
    { kode: "931", uraian: "Penyusutan Aset Tetap", arah: "berkurang",
      kelompok: "penyusutan", label_kelompok: "Penyusutan & Koreksinya" },
  ],
  warisan: [
    { kode: "205", uraian: "Koreksi Nilai Berkurang", arah: "berkurang",
      kelompok: "koreksi", label_kelompok: "Koreksi Pencatatan & Nilai" },
  ],
  label_kelompok: {},
};

beforeEach(() => {
  axios.get.mockImplementation(() => Promise.resolve({ data: DATA }));
});

test("dialog memuat referensi lalu merender kedua arah + warisan", async () => {
  render(<ReferensiKodeMutasiDialog />);
  await userEvent.click(screen.getByTestId("jurnal-referensi-kode"));
  expect(await screen.findByTestId("ref-mutasi-bertambah"))
    .toHaveTextContent("Mutasi Bertambah (2 kode)");
  expect(screen.getByTestId("ref-mutasi-berkurang"))
    .toHaveTextContent("Mutasi Berkurang (1 kode)");
  expect(screen.getByText("Perolehan/Penambahan KDP")).toBeInTheDocument();
  expect(screen.getByText("Penyusutan Aset Tetap")).toBeInTheDocument();
  expect(screen.getByText("Kode warisan AMAN")).toBeInTheDocument();
  expect(screen.getByText("Koreksi Nilai Berkurang")).toBeInTheDocument();
  expect(String(axios.get.mock.calls[0][0]))
    .toMatch(/\/pembukuan\/jenis-transaksi$/);
});
