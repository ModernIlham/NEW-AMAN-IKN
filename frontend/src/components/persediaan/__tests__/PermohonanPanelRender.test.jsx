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

test("chip status menampilkan LABEL terbaca, bukan kode mentah", async () => {
  await bukaPanel();
  // Kode status huruf kecil tak lagi tampil apa adanya — pembaca melihat
  // label berkapital dari LABEL_STATUS.
  expect(screen.getAllByText("Diusulkan").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Disetujui").length).toBeGreaterThan(0);
  expect(screen.queryByText("diusulkan")).not.toBeInTheDocument();
  expect(screen.queryByText("disetujui")).not.toBeInTheDocument();
});

// ── Status & tautan TTD elektronik ────────────────────────────────────────
// Pola yang sama dengan Riwayat BAST & Riwayat LPB: tautan permintaan yang
// sudah dikirim harus bisa dibuka LAGI. Tanpa itu ia hilang bersama dialog
// pembuatan, dan yang tersisa berminggu-minggu kemudian hanya "tautan mati".

const ROWS_TTD = [
  { ...ROWS[2],
    ttd: { id: "sr-9", judul: "Surat Persetujuan SP-007", jumlah: 2,
           selesai_jumlah: 1, kedaluwarsa_terdekat: { sisa_detik: 9 * 86400 } },
    signature_request_id: "sr-9" },
];

function pakaiRowsTtd() {
  axios.get.mockImplementation((url) => {
    if (String(url).includes("permohonan-pengaturan")) {
      return Promise.resolve({ data: { aktif: true } });
    }
    if (String(url).includes("/ttd/permintaan/")) {
      return Promise.resolve({ data: {
        id: "sr-9", judul: "Surat Persetujuan SP-007",
        signers: [{ signer_id: "s1", nama: "Sari", status: "aktif",
                    kedaluwarsa_info: { sisa_detik: 0 } }] } });
    }
    return Promise.resolve({ data: { items: ROWS_TTD, menunggu: 0 } });
  });
}

test("status TTD tampil di barisnya, bukan hanya 'sudah dikirim'", async () => {
  pakaiRowsTtd();
  render(<PermohonanPanel user={ADMIN} onSelesai={jest.fn()} />);
  await userEvent.click(await screen.findByTestId("persediaan-permohonan-buka"));
  const badge = await screen.findByTestId("permohonan-status-ttd-p-3");
  expect(badge).toHaveTextContent("1/2");
  expect(badge).toHaveTextContent(/9 hari lagi/);
});

test("tombol Tautan TTD membuka permintaan yang SUDAH ada", async () => {
  pakaiRowsTtd();
  render(<PermohonanPanel user={ADMIN} onSelesai={jest.fn()} />);
  await userEvent.click(await screen.findByTestId("persediaan-permohonan-buka"));
  await userEvent.click(await screen.findByTestId("permohonan-tautan-ttd-p-3"));
  // Dialog memuat DETAIL permintaan — bukan membuat permintaan baru.
  await waitFor(() => expect(
    axios.get.mock.calls.some(([u]) => String(u).includes("/ttd/permintaan/sr-9"))
  ).toBe(true));
  expect(await screen.findByTestId("ttd-signer-s1")).toBeInTheDocument();
});

test("permohonan yang belum pernah dikirim tidak menawarkan Tautan TTD", async () => {
  await bukaPanel();
  expect(screen.queryByTestId("permohonan-tautan-ttd-p-3")).not.toBeInTheDocument();
  expect(screen.queryByTestId("permohonan-status-ttd-p-3")).not.toBeInTheDocument();
});
