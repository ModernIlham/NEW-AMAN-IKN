import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import DokumenAkhirBast from "../DokumenAkhirBast";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
const doc = { id: "d1", filename: "BAST-akhir.pdf", jenis: "e_meterai", status: "menunggu", catatan: "Meterai dilengkapi", oleh: "Operator", diunggah_pada: "2026-10-26" };
const bast = { id: "b1", dokumen_akhir_version: 2, dokumen_akhir: [doc], portal_otomasi: { ever_applied: true } };
let updated;
beforeEach(() => {
  jest.clearAllMocks();
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  URL.createObjectURL = jest.fn(() => "blob:uji");
  URL.revokeObjectURL = jest.fn();
  axios.post.mockResolvedValue({ data: { ok: true } });
  updated = jest.fn();
});

function openUpload(props = {}) {
  render(<DokumenAkhirBast bast={bast} editable onUpdated={updated} {...props} />);
  fireEvent.click(screen.getByTestId("bast-unggah-akhir-b1"));
}

test("BAST yang sudah diterapkan tetap dapat menambah arsip tanpa menimpa bukti", async () => {
  openUpload();
  const file = new File(["%PDF-1.7"], "Final.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByTestId("bast-akhir-file"), { target: { files: [file] } });
  fireEvent.change(screen.getByTestId("bast-akhir-jenis"), { target: { value: "e_meterai" } });
  fireEvent.change(screen.getByTestId("bast-akhir-catatan"), { target: { value: "Setelah e-meterai lengkap" } });
  expect(screen.getByTestId("bast-akhir-preview-lokal")).toHaveAttribute("href", "blob:uji");
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  await waitFor(() => expect(updated).toHaveBeenCalledTimes(1));
  const [path, fd, config] = axios.post.mock.calls[0];
  expect(path).toMatch(/\/bast\/b1\/dokumen-akhir$/);
  expect(fd.get("file")).toBe(file);
  expect(fd.get("jenis")).toBe("e_meterai");
  expect(fd.has("verifikasi_lengkap")).toBe(false);
  expect(config.headers).toEqual({ "If-Match": "2", "Idempotency-Key": expect.any(String) });
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:uji");
});

test.each([{ editable: false }, { bast: { ...bast, direvisi_oleh: "b2" } }, { bast: { ...bast, tt_dicabut: true } }])("arsip tetap dapat dibaca tetapi tulisan diblok sesuai izin/status %j", props => {
  render(<DokumenAkhirBast bast={bast} editable onUpdated={updated} {...props} />);
  expect(screen.queryByTestId("bast-unggah-akhir-b1")).not.toBeInTheDocument();
  expect(screen.queryByTestId("bast-akhir-periksa-d1")).not.toBeInTheDocument();
  expect(screen.getByTestId("bast-akhir-lihat-d1")).toBeInTheDocument();
});

test.each(["sesuai", "tidak_sesuai"])("pemeriksaan %s wajib pratinjau, catatan dan konfirmasi", async status => {
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  localStorage.setItem("media_token", "media-uji");
  try {
    render(<DokumenAkhirBast bast={bast} editable onUpdated={updated} />);
    fireEvent.click(screen.getByTestId("bast-akhir-periksa-d1"));
    expect(screen.getByTestId("bast-akhir-konfirmasi")).toBeDisabled();
    expect(screen.getByTestId("bast-akhir-simpan-periksa")).toBeDisabled();
    fireEvent.click(screen.getByTestId("bast-akhir-lihat-d1"));
    expect(open).toHaveBeenCalledWith(expect.stringContaining("/bast/b1/dokumen-akhir/d1?token=media-uji"), "_blank", "noopener,noreferrer");
    fireEvent.change(screen.getByTestId("bast-akhir-hasil"), { target: { value: status } });
    fireEvent.change(screen.getByTestId("bast-akhir-catatan-periksa"), { target: { value: "Telah diperiksa seluruh halaman" } });
    expect(screen.getByTestId("bast-akhir-simpan-periksa")).toBeDisabled();
    fireEvent.click(screen.getByTestId("bast-akhir-konfirmasi"));
    fireEvent.click(screen.getByTestId("bast-akhir-simpan-periksa"));
    await waitFor(() => expect(updated).toHaveBeenCalled());
    expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/dokumen-akhir\/d1\/periksa$/), {
      status, sudah_diperiksa: true, catatan: "Telah diperiksa seluruh halaman",
    }, expect.objectContaining({ headers: { "If-Match": "2", "Idempotency-Key": expect.any(String) } }));
  } finally { open.mockRestore(); localStorage.clear(); }
});

test("dokumen yang sudah diperiksa tetap diarsip, tidak dapat ditimpa atau diperiksa ulang", () => {
  render(<DokumenAkhirBast bast={{ ...bast, dokumen_akhir: [{ ...doc, status: "sesuai", pemeriksaan: { oleh: "Admin", catatan: "Sesuai lengkap", pada: "2026-10-26" } }] }} editable onUpdated={updated} />);
  expect(screen.queryByTestId("bast-akhir-periksa-d1")).not.toBeInTheDocument();
  expect(screen.getByText(/Diperiksa Admin/)).toBeInTheDocument();
});

test("berkas terlalu besar/kosong/asing ditolak tanpa unggahan", () => {
  openUpload();
  for (const file of [new File([], "kosong.pdf"), new File(["a"], "asing.svg"), { name: "besar.pdf", size: 10 * 1024 * 1024 + 1 }]) {
    fireEvent.change(screen.getByTestId("bast-akhir-file"), { target: { files: [file] } });
    expect(screen.getByTestId("bast-akhir-simpan")).toBeDisabled();
  }
  expect(toast.error).toHaveBeenCalledTimes(3);
  expect(axios.post).not.toHaveBeenCalled();
});

test("gagal jaringan dapat diulang dengan kunci yang sama; klik ganda tidak membuat dua request", async () => {
  openUpload();
  fireEvent.change(screen.getByTestId("bast-akhir-file"), { target: { files: [new File(["pdf"], "a.pdf")] } });
  fireEvent.change(screen.getByTestId("bast-akhir-catatan"), { target: { value: "Dokumen setelah meterai" } });
  let reject;
  axios.post.mockImplementationOnce(() => new Promise((_, r) => { reject = r; }));
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  expect(axios.post).toHaveBeenCalledTimes(1);
  reject(new Error("putus jaringan"));
  await waitFor(() => expect(screen.getByTestId("bast-akhir-simpan")).not.toBeDisabled());
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  await waitFor(() => expect(updated).toHaveBeenCalledTimes(1));
  expect(axios.post.mock.calls[1][2].headers).toEqual(axios.post.mock.calls[0][2].headers);
});

test("konflik versi meminta pembaruan arsip, tidak menampilkan sukses", async () => {
  openUpload();
  fireEvent.change(screen.getByTestId("bast-akhir-file"), { target: { files: [new File(["pdf"], "a.pdf")] } });
  fireEvent.change(screen.getByTestId("bast-akhir-catatan"), { target: { value: "Dokumen lengkap" } });
  axios.post.mockRejectedValue({ response: { status: 409, data: { detail: "BAST berubah" } } });
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  await waitFor(() => expect(updated).toHaveBeenCalled());
  expect(toast.error).toHaveBeenCalledWith("BAST berubah");
  expect(toast.success).not.toHaveBeenCalled();
});

test.each([false, true])("menutup riwayat saat proses tidak dibuka paksa oleh respons terlambat (konflik=%s)", async konflik => {
  const view = render(<DokumenAkhirBast bast={bast} editable onUpdated={updated} />);
  fireEvent.click(screen.getByTestId("bast-unggah-akhir-b1"));
  fireEvent.change(screen.getByTestId("bast-akhir-file"), { target: { files: [new File(["pdf"], "a.pdf")] } });
  fireEvent.change(screen.getByTestId("bast-akhir-catatan"), { target: { value: "Dokumen lengkap" } });
  let resolve, reject;
  axios.post.mockImplementationOnce(() => new Promise((a, b) => { resolve = a; reject = b; }));
  fireEvent.click(screen.getByTestId("bast-akhir-simpan"));
  view.unmount();
  await act(async () => {
    if (konflik) reject({ response: { status: 409, data: { detail: "BAST berubah" } } });
    else resolve({ data: { ok: true } });
  });
  expect(updated).not.toHaveBeenCalled();
});
