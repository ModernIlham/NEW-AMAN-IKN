/**
 * Uji render Panel Permohonan Persediaan — SEDIA-KPB (PR UI).
 *
 * Sifat terpenting yang dijaga di sisi UI: PEMISAHAN PERAN terlihat —
 * pengaju tidak DIBERI tombol Setujui/Tolak untuk permohonannya sendiri
 * (server tetap menegakkan 403; UI tak boleh mengajak pengguna menabraknya),
 * sementara admin lain melihat keduanya.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import PermohonanPanel from "../PermohonanPanel";

jest.mock("axios");
const mockUnduh = jest.fn();
jest.mock("@/lib/downloadFile", () => ({
  downloadFileWithProgress: (...a) => mockUnduh(...a),
}));

const ADMIN = { username: "adm1", role: "admin" };

const ROWS = [
  { id: "p-1", status: "diusulkan", ringkasan: "Transaksi Masuk Kertas HVS A4: 10 unit (pembelian)",
    diajukan_oleh: "op1", diajukan_pada: "2026-08-09T01:00:00" },
  { id: "p-2", status: "diusulkan", ringkasan: "Transaksi Keluar Tinta: 2 unit (habis_pakai)",
    diajukan_oleh: "adm1", diajukan_pada: "2026-08-09T01:05:00" },
  { id: "p-3", status: "disetujui", ringkasan: "Opname Fisik (P01) Map Folder: stok fisik 40",
    diajukan_oleh: "op1", diajukan_pada: "2026-08-08T09:00:00",
    nomor: "SP-007/UJI/2026" },
];

beforeEach(() => {
  axios.get.mockImplementation((url) => {
    if (String(url).includes("permohonan-pengaturan")) {
      return Promise.resolve({ data: { aktif: true } });
    }
    return Promise.resolve({ data: { items: ROWS, menunggu: 2 } });
  });
  axios.post.mockResolvedValue({ data: { nomor: "SP-008/UJI/2026" } });
  mockUnduh.mockImplementation(() => Promise.resolve());
});

async function bukaPanel(user = ADMIN) {
  render(<PermohonanPanel user={user} onSelesai={jest.fn()} />);
  expect(await screen.findByTestId("persediaan-permohonan-badge"))
    .toHaveTextContent("2");
  await userEvent.click(screen.getByTestId("persediaan-permohonan-buka"));
  await screen.findByTestId("permohonan-p-1");
}

test("lencana menunggu hidup tanpa membuka panel, daftar tampil saat dibuka", async () => {
  await bukaPanel();
  expect(screen.getByText(/Kertas HVS A4/)).toBeInTheDocument();
  expect(screen.getByText(/SP-007\/UJI\/2026/)).toBeInTheDocument();
});

test("pemisahan peran terlihat: Setujui hanya untuk permohonan ORANG LAIN", async () => {
  await bukaPanel();
  // p-1 diajukan op1 → admin adm1 boleh memutus.
  expect(screen.getByTestId("permohonan-setujui-p-1")).toBeInTheDocument();
  expect(screen.getByTestId("permohonan-tolak-p-1")).toBeInTheDocument();
  // p-2 diajukan adm1 SENDIRI → tombol putus tak ditawarkan, hanya Batalkan.
  expect(screen.queryByTestId("permohonan-setujui-p-2")).not.toBeInTheDocument();
  expect(screen.getByTestId("permohonan-batal-p-2")).toBeInTheDocument();
});

test("Setujui memanggil endpoint yang benar", async () => {
  await bukaPanel();
  await userEvent.click(screen.getByTestId("permohonan-setujui-p-1"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(String(axios.post.mock.calls[0][0]))
    .toMatch(/\/persediaan\/permohonan\/p-1\/setujui$/);
});

test("Tolak wajib beralasan sebelum terkirim", async () => {
  await bukaPanel();
  await userEvent.click(screen.getByTestId("permohonan-tolak-p-1"));
  const isian = await screen.findByTestId("permohonan-alasan-tolak");
  await userEvent.type(isian, "bukti belum lengkap");
  await userEvent.click(screen.getByText("Kirim"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(String(url)).toMatch(/\/permohonan\/p-1\/tolak$/);
  expect(body.alasan).toBe("bukti belum lengkap");
});

test("permohonan disetujui menyediakan unduhan Surat Persetujuan", async () => {
  await bukaPanel();
  await userEvent.click(screen.getByTestId("permohonan-surat-p-3"));
  await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
  expect(String(mockUnduh.mock.calls[0][0]))
    .toMatch(/\/persediaan\/permohonan\/p-3\/dokumen$/);
});
