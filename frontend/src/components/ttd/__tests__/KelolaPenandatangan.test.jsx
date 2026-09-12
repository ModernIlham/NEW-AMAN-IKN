import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import KelolaPenandatangan, { RiwayatPenandatangan } from "../KelolaPenandatangan";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
const data = { id: "sr", version: 4, status: "sebagian", dapat_kelola_penandatangan: true, dok_file_id: "pdf",
  signers: [{ signer_id: "s1", nama: "Pertama", status: "menunggu_validasi", signature_file_id: "f1" },
    { signer_id: "s2", nama: "Kedua", status: "aktif" }] };
beforeEach(() => { jest.clearAllMocks(); axios.post.mockResolvedValue({ data: { ok: true } }); });
const buka = () => fireEvent.click(screen.getByRole("button", { name: "Kelola penanda tangan" }));
const isi = () => {
  fireEvent.change(screen.getByLabelText("Nama"), { target: { value: "Tambahan" } });
  fireEvent.change(screen.getByLabelText("Alasan perubahan"), { target: { value: "Terlupa saat membuat permintaan" } });
};

test.each([false, true])("tambah peserta memakai versi dan idempotensi; tema gelap=%s", async gelap => {
  document.documentElement.classList.toggle("dark", gelap);
  const onBerubah = jest.fn();
  render(<KelolaPenandatangan data={data} onBerubah={onBerubah} />);
  buka(); isi();
  expect(screen.queryByRole("button", { name: "Hapus Pertama" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Simpan penanda tangan" }));
  await waitFor(() => expect(onBerubah).toHaveBeenCalled());
  const [url, body, config] = axios.post.mock.calls[0];
  expect(url).toMatch(/\/sr\/penandatangan$/);
  expect(body.signer.nama).toBe("Tambahan");
  expect(config.headers["If-Match"]).toBe("4");
  expect(config.headers["Idempotency-Key"]).toBeTruthy();
  document.documentElement.classList.remove("dark");
});

test("gangguan jaringan mengulang kunci yang sama, bukan peserta baru", async () => {
  axios.post.mockRejectedValueOnce(new Error("putus"));
  render(<KelolaPenandatangan data={data} />); buka(); isi();
  fireEvent.click(screen.getByRole("button", { name: "Simpan penanda tangan" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Simpan penanda tangan" }));
  await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(2));
  expect(axios.post.mock.calls[0][2].headers).toEqual(axios.post.mock.calls[1][2].headers);
});

test("konflik versi menahan simpan dan menyediakan muat ulang", async () => {
  axios.post.mockRejectedValue({ response: { status: 409, data: { detail: { message: "Permintaan berubah" } } } });
  const onBerubah = jest.fn();
  render(<KelolaPenandatangan data={data} onBerubah={onBerubah} />); buka(); isi();
  fireEvent.click(screen.getByRole("button", { name: "Simpan penanda tangan" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Permintaan berubah");
  expect(screen.queryByRole("button", { name: "Simpan penanda tangan" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Muat ulang permintaan" }));
  await waitFor(() => expect(onBerubah).toHaveBeenCalled());
});

test("hapus terakhir perlu buka PDF dan konfirmasi final eksplisit", async () => {
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  render(<KelolaPenandatangan data={{ ...data, signers: [{ ...data.signers[0], status: "terverifikasi" }, data.signers[1]] }} />);
  buka(); fireEvent.click(screen.getByRole("button", { name: "Hapus Kedua" }));
  fireEvent.change(screen.getByLabelText("Alasan perubahan"), { target: { value: "Peserta tambahan tidak diperlukan" } });
  const konfirmasi = screen.getByRole("checkbox");
  expect(konfirmasi).toBeDisabled();
  expect(screen.getByRole("button", { name: "Hapus dan finalisasi" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Periksa Dokumen" }));
  expect(open.mock.calls[0][0]).toMatch(/\/sr\/dokumen-ttd/);
  fireEvent.click(konfirmasi);
  fireEvent.click(screen.getByRole("button", { name: "Hapus dan finalisasi" }));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(axios.post.mock.calls[0][1]).toMatchObject({ aksi: "hapus", signer_id: "s2", konfirmasi_final: true });
  open.mockRestore();
});

test.each([{ ...data, dapat_kelola_penandatangan: false }, { ...data, status: "selesai" }, { ...data, status: "batal" }])(
  "pengguna tanpa hak atau permintaan final/batal tidak ditawari perubahan", detail => {
    render(<KelolaPenandatangan data={detail} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

test("riwayat dapat dipakai halaman TTD maupun BAST tanpa memuat kredensial", () => {
  render(<RiwayatPenandatangan data={{ riwayat_penandatangan: [{ aksi: "hapus", nama: "Kedua", alasan: "Duplikat peserta", oleh: "operator", pada: "2026-09-12T00:00:00Z" }] }} />);
  expect(screen.getByTestId("riwayat-penandatangan")).toHaveTextContent("Dihapus: Kedua");
});
