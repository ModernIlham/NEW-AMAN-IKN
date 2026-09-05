/**
 * Menerbitkan Nota Dinas — dua tindakan yang sengaja dibedakan.
 *
 * Pratinjau tak memesan nomor dan tak meninggalkan jejak; menerbitkan memesan
 * nomor surat yang tak pernah dipakai ulang lalu membekukan daftar barangnya.
 * Satu tombol untuk keduanya akan membuat orang memesan nomor hanya karena
 * ingin melihat dokumennya.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import NotaDinasDialog from "../NotaDinasDialog";
import RiwayatNotaDinas, { tanggalId } from "../RiwayatNotaDinas";

const mockUnduh = jest.fn();
jest.mock("@/lib/downloadFile", () => ({
  downloadFileWithProgress: (...a) => mockUnduh(...a),
}));
jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const ITEMS = [
  { id: "hab-1", nama_barang: "Kertas HVS A4", kode_barang: "K001",
    stok: 0, batas_kritis: 5, satuan: "Rim" },
  { id: "kri-1", nama_barang: "Tinta Printer Hitam", kode_barang: "K002",
    stok: 2, batas_kritis: 5, satuan: "Botol" },
];

beforeEach(() => {
  mockUnduh.mockImplementation(() => Promise.resolve());
  axios.post.mockResolvedValue({
    data: { id: "nota-1", nomor: "B-7/PL.01/2026", jumlah_barang: 2,
            message: "Nota dinas terbit dengan nomor B-7/PL.01/2026" },
  });
  axios.get.mockResolvedValue({ data: { items: [], total: 0 } });
});

async function buka() {
  await userEvent.click(screen.getByTestId("persediaan-nota-kritis"));
  await screen.findByTestId("nota-kritis-item-hab-1");
}

test("pratinjau TIDAK memesan nomor", async () => {
  render(<NotaDinasDialog items={ITEMS} />);
  await buka();
  await userEvent.click(screen.getByTestId("nota-kritis-unduh"));
  await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
  expect(axios.post).not.toHaveBeenCalled();
  expect(String(mockUnduh.mock.calls[0][0])).toContain("/persediaan/nota-dinas?");
});

test("menerbitkan memanggil terbitkan lalu mengunduh naskah bernomor", async () => {
  const onTerbit = jest.fn();
  render(<NotaDinasDialog items={ITEMS} onTerbit={onTerbit} />);
  await buka();
  await userEvent.click(screen.getByTestId("nota-kritis-terbitkan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(url).toContain("/persediaan/nota-dinas/terbitkan");
  expect(body.jenis).toBe("kritis");
  // Unduhannya menunjuk register — BUKAN jalur pratinjau, yang akan
  // menghitung ulang daftarnya dan menghasilkan naskah tanpa nomor.
  await waitFor(() => expect(mockUnduh).toHaveBeenCalled());
  expect(String(mockUnduh.mock.calls[0][0])).toContain("/persediaan/nota-dinas/nota-1/pdf");
  expect(onTerbit).toHaveBeenCalled();
});

test("daftar LENGKAP diterbitkan tanpa ids", async () => {
  // Mengirim ids saat semua terpilih membuat server memperlakukan nota utuh
  // sebagai nota tersaring — dan naskahnya lalu memuat kalimat "sengaja
  // tidak disertakan" pada daftar yang sebenarnya lengkap.
  render(<NotaDinasDialog items={ITEMS} />);
  await buka();
  await userEvent.click(screen.getByTestId("nota-kritis-terbitkan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(axios.post.mock.calls[0][1].ids).toEqual([]);
});

test("melepas satu centang mengirim ids yang tersisa", async () => {
  render(<NotaDinasDialog items={ITEMS} />);
  await buka();
  await userEvent.click(screen.getByTestId("nota-kritis-item-hab-1"));
  await userEvent.click(screen.getByTestId("nota-kritis-terbitkan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(axios.post.mock.calls[0][1].ids).toEqual(["kri-1"]);
});

test("penerbitan gagal tidak mengunduh apa pun", async () => {
  axios.post.mockRejectedValue({ response: { data: { detail: "Tidak ada barang" } } });
  render(<NotaDinasDialog items={ITEMS} />);
  await buka();
  await userEvent.click(screen.getByTestId("nota-kritis-terbitkan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(mockUnduh).not.toHaveBeenCalled();
  // Dialognya tetap terbuka supaya pilihan yang sudah dibuat tak hilang.
  expect(screen.getByTestId("nota-kritis-terbitkan")).toBeInTheDocument();
});

// ── Riwayat ────────────────────────────────────────────────────────────

test("nota yang belum bernomor tetap tampil, bukan disembunyikan", async () => {
  axios.get.mockResolvedValue({
    data: {
      total: 2,
      items: [
        { id: "n1", nomor: "B-7/PL.01/2026", jenis: "kritis",
          jumlah_barang: 3, tanggal: "2026-09-05", seleksi: false },
        { id: "n2", nomor: "", jenis: "kedaluwarsa",
          jumlah_barang: 1, tanggal: "2026-09-04", seleksi: true },
      ],
    },
  });
  render(<RiwayatNotaDinas />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await userEvent.click(screen.getByTestId("persediaan-riwayat-nota"));
  expect(await screen.findByText("B-7/PL.01/2026")).toBeInTheDocument();
  expect(screen.getByText("Belum bernomor")).toBeInTheDocument();
  expect(screen.getByText(/sebagian dipilih/)).toBeInTheDocument();
});

test("riwayat memuat ulang saat versi berubah", async () => {
  const { rerender } = render(<RiwayatNotaDinas versi={0} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
  rerender(<RiwayatNotaDinas versi={1} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(2));
});

test("tanggal ditulis gaya Indonesia; yang cacat apa adanya", () => {
  expect(tanggalId("2026-09-05")).toBe("5 September 2026");
  expect(tanggalId("2026-01-31T10:00:00Z")).toBe("31 Januari 2026");
  expect(tanggalId("")).toBe("");
  expect(tanggalId("entah")).toBe("entah");
});

// ── Tanda tangan elektronik ────────────────────────────────────────────

jest.mock("@/components/ttd/TautanTtdDialog", () => function Palsu({ srId }) {
  return <div data-testid="tautan-ttd-dialog">{srId}</div>;
});

const NOTA = {
  id: "n1", nomor: "B-7/PL.01/2026", jenis: "kritis",
  jumlah_barang: 3, tanggal: "2026-09-05", seleksi: false,
};

async function bukaRiwayat(items) {
  axios.get.mockResolvedValue({ data: { total: items.length, items } });
  render(<RiwayatNotaDinas user={{ role: "operator" }} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await userEvent.click(screen.getByTestId("persediaan-riwayat-nota"));
  await screen.findByTestId("persediaan-riwayat-nota-n1");
}

test("nota yang belum dikirim menawarkan Kirim TTD", async () => {
  await bukaRiwayat([{ ...NOTA, ttd: null }]);
  expect(screen.getByTestId("persediaan-riwayat-nota-kirim-ttd-n1")).toBeInTheDocument();
  expect(screen.queryByTestId("persediaan-riwayat-nota-tautan-n1")).toBeNull();
  await userEvent.click(screen.getByTestId("persediaan-riwayat-nota-kirim-ttd-n1"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(String(axios.post.mock.calls[0][0]))
    .toContain("/persediaan/nota-dinas/n1/kirim-ttd");
});

test("nota yang sudah dikirim menampilkan status dan jalan kembali ke tautannya", async () => {
  // Tanpa jalan kembali, tautannya hilang bersama dialog dan yang tersisa
  // berminggu-minggu kemudian hanya "tautan mati".
  await bukaRiwayat([{
    ...NOTA, signature_request_id: "sr-1",
    ttd: { id: "sr-1", judul: "Nota Dinas B-7", status: "terkirim",
           jumlah: 1, selesai_jumlah: 0, membubuhkan_jumlah: 0 },
  }]);
  expect(screen.getByTestId("persediaan-riwayat-nota-ttd-n1")).toBeInTheDocument();
  expect(screen.queryByTestId("persediaan-riwayat-nota-kirim-ttd-n1")).toBeNull();
  await userEvent.click(screen.getByTestId("persediaan-riwayat-nota-tautan-n1"));
  expect(await screen.findByTestId("tautan-ttd-dialog")).toHaveTextContent("sr-1");
});

test("viewer tidak ditawari mengirim tanda tangan", async () => {
  axios.get.mockResolvedValue({ data: { total: 1, items: [{ ...NOTA, ttd: null }] } });
  render(<RiwayatNotaDinas user={{ role: "viewer" }} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  await userEvent.click(screen.getByTestId("persediaan-riwayat-nota"));
  await screen.findByTestId("persediaan-riwayat-nota-n1");
  expect(screen.queryByTestId("persediaan-riwayat-nota-kirim-ttd-n1")).toBeNull();
  // Unduh tetap tersedia — membaca dokumen bukan menandatanganinya.
  expect(screen.getByTestId("persediaan-riwayat-nota-unduh-n1")).toBeInTheDocument();
});
