import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import PenggunaanPage from "../PenggunaanPage";

jest.mock("axios");
jest.mock("@/lib/downloadFile", () => ({ downloadFileWithProgress: async () => {} }));
const pegawai = [{ id: "p1", nama: "Budi", nip: "111", email: "satu@example.test" }, { id: "p2", nama: "Budi", nip: "", email: "dua@example.test" }];
const bast = { id: "b1", jenis: "penggunaan_melekat", nomor: "BAST-01", tanggal: "2026-10-01", asset_ids: ["aset-lama"], aset: [{ id: "aset-lama", asset_name: "Barang sebelum mutasi", asset_code: "305", NUP: "7" }], pihak_kedua: { nama: "Budi" }, portal_otomasi: { version: 4, status: "menunggu_keabsahan", alasan: "Tanda tangan belum lengkap", hasil: [] } };

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  axios.get.mockImplementation(async url => {
    if (url.endsWith("/penggunaan/pemegang")) return { data: { items: [{ nama: "Pemegang", nip: "111", jumlah_aset: 1 }], total_pemegang: 1 } };
    if (url.endsWith("/penggunaan/pemegang/aset")) return { data: { items: [{ id: "a1", asset_name: "Laptop", asset_code: "301", NUP: "1" }] } };
    if (url.endsWith("/pegawai")) return { data: { items: pegawai } };
    if (url.endsWith("/bast/referensi")) return { data: { jenis: [{ kode: "penggunaan_melekat", uraian: "Penggunaan" }, { kode: "mutasi_pengguna", uraian: "Mutasi" }, { kode: "operasional_unit", uraian: "Operasional Unit" }] } };
    if (url.endsWith("/bast")) return { data: { items: [bast] } };
    return { data: { items: [] } };
  });
  axios.post.mockResolvedValue({ data: { id: "b2", ok: true } });
});

async function buka() {
  render(<PenggunaanPage user={{ role: "admin" }} />);
  fireEvent.click(await screen.findByTestId("penggunaan-row-Pemegang"));
  await screen.findByTestId("penggunaan-aset-a1");
}

test("BAST membawa UUID pilihan pegawai dan tidak lagi meminta mutasi dini", async () => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-buat-bast"));
  fireEvent.click(await screen.findByTestId("bast-penerima-pegawai"));
  fireEvent.click(await screen.findByTestId("bast-penerima-pegawai-option-p2"));
  expect(screen.getByTestId("bast-penerima-nip")).toHaveValue("");
  expect(screen.queryByTestId("bast-penerima")).not.toBeInTheDocument();
  expect(screen.getByTestId("bast-penerima-pegawai")).toHaveTextContent("Budi");
  expect(screen.queryByTestId("bast-penerima-pegawai-search")).not.toBeInTheDocument();
  expect(screen.queryByTestId("bast-terapkan")).not.toBeInTheDocument();
  expect(screen.getByTestId("bast-penerapan-final")).toHaveTextContent("setelah dokumen sah");
  fireEvent.click(screen.getByTestId("bast-simpan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/bast$/), expect.objectContaining({ pihak_kedua: expect.objectContaining({ pegawai_id: "p2", nama: "Budi", nip: "" }) }), expect.anything()));
  const body = axios.post.mock.calls.find(([url]) => url.endsWith("/bast"))[1];
  expect(body).not.toHaveProperty("terapkan_ke_aset");
});

test("ganti ke pihak luar mengosongkan FK dan identitas lama, tetap boleh menyusun BAST", async () => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-buat-bast"));
  fireEvent.click(await screen.findByTestId("bast-penerima-pegawai"));
  fireEvent.click(await screen.findByTestId("bast-penerima-pegawai-option-p1"));
  expect(screen.getByTestId("bast-penerima-nip")).toHaveValue("111");
  fireEvent.click(screen.getByTestId("bast-penerima-pegawai-clear"));
  expect(screen.getByTestId("bast-penerima")).toHaveValue("");
  expect(screen.getByTestId("bast-penerima-nip")).toHaveValue("");
  fireEvent.change(screen.getByTestId("bast-penerima"), { target: { value: "Penerima Eksternal" } });
  fireEvent.change(screen.getByTestId("bast-penerima-nip"), { target: { value: "123456" } });
  fireEvent.click(screen.getByTestId("bast-simpan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/bast$/), expect.objectContaining({ pihak_kedua: expect.objectContaining({ pegawai_id: "", nama: "Penerima Eksternal", nip: "123456", jabatan: "", alamat: "" }) }), expect.anything()));
});

test("PJ memilih identitas otomatis dan tidak dapat melekatkan barang sama dua kali", async () => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-buat-bast"));
  await screen.findByTestId("bast-jenis");
  await screen.findByRole("option", { name: "Operasional Unit" });
  fireEvent.change(screen.getByTestId("bast-jenis"), { target: { value: "operasional_unit" } });
  fireEvent.click(screen.getByTestId("bast-pj-tambah"));
  fireEvent.click(screen.getByTestId("bast-pj-pegawai-0"));
  fireEvent.click(await screen.findByTestId("bast-pj-pegawai-0-option-p1"));
  expect(screen.queryByTestId("bast-pj-nama-0")).not.toBeInTheDocument();
  expect(screen.getByTestId("bast-pj-nip-0")).toHaveValue("111");
  fireEvent.click(screen.getByTestId("bast-pj-pilih-aset-0"));
  fireEvent.click(await screen.findByTestId("bast-pj-pilih-aset-0-option-a1"));
  expect(screen.getByTestId("bast-pj-0-aset-a1")).toBeInTheDocument();
  expect(screen.queryByTestId("bast-pj-pilih-aset-0")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Lepas Laptop" }));
  expect(screen.getByTestId("bast-pj-pilih-aset-0")).toBeInTheDocument();
});

test("pemeriksaan ulang otomasi mengirim OCC versi ringkasan dan idempotensi", async () => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-riwayat-bast"));
  fireEvent.click(await screen.findByTestId("bast-portal-sinkron-b1"));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/bast\/b1\/sinkronkan-bmn$/), {}, expect.objectContaining({ headers: { "If-Match": "4", "Idempotency-Key": expect.any(String) } })));
});

test("revisi mempertahankan daftar barang sumber yang sudah berpindah pemegang", async () => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-riwayat-bast"));
  fireEvent.click(await screen.findByTestId("bast-revisi-b1"));
  expect(await screen.findByText("Barang sebelum mutasi")).toBeInTheDocument();
  expect(screen.getByTestId("bast-revisi-banner")).toBeInTheDocument();
});

test.each([false, true])("unggah bukti tidak mengesahkan tanpa centang eksplisit (lengkap=%s)", async lengkap => {
  await buka(); fireEvent.click(screen.getByTestId("penggunaan-riwayat-bast"));
  fireEvent.click(await screen.findByTestId("bast-unggah-bukti-b1"));
  expect(screen.getByTestId("bast-bukti-lengkap")).not.toBeChecked();
  fireEvent.change(screen.getByTestId("bast-bukti-input"), { target: { files: [new File(["pdf"], "bukti.pdf", { type: "application/pdf" })] } });
  if (lengkap) fireEvent.click(screen.getByTestId("bast-bukti-lengkap"));
  fireEvent.click(screen.getByTestId("bast-bukti-simpan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/bast\/b1\/bukti$/), expect.any(FormData), expect.objectContaining({ headers: expect.objectContaining({ "If-Match": "4", "Idempotency-Key": expect.any(String) }) })));
  const fd = axios.post.mock.calls.find(([url]) => url.endsWith("/b1/bukti"))[1];
  expect(fd.get("verifikasi_lengkap")).toBe(String(lengkap));
});
