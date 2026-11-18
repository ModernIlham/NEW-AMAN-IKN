/**
 * "Hapus Semua Aset Kegiatan" — tinjauan mutu Nov 2026 (F8).
 *
 * Bug yang direproduksi di Chromium: dengan pencarian aktif, dialog lama
 * berkata "Total: 248 aset akan dihapus" (jumlah TERFILTER), padahal endpoint
 * menghapus SELURUH kegiatan — 600 aset beserta fotonya lenyap permanen.
 * Uji ini menjaga: jumlah dari server tanpa filter, peringatan filter,
 * konfirmasi ketik-nama, dan jumlah_konfirmasi terkirim ke server.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import { toast } from "sonner";
import BulkDeleteDialog from "../BulkDeleteDialog";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: { total: 600, items: [] } });
  axios.delete.mockResolvedValue({ data: { message: "Berhasil menghapus 600 aset", deleted: 600 } });
});

function buka(props = {}) {
  const onClose = jest.fn(); const onSuccess = jest.fn();
  render(<BulkDeleteDialog open onClose={onClose} onSuccess={onSuccess} activityId="keg-1"
    activityName="Uji sintetis 3" totalItems={248} {...props} />);
  return { onClose, onSuccess };
}
const tombol = () => screen.getByTestId("bulk-delete-konfirmasi-btn");
const ketik = (t) => fireEvent.change(screen.getByTestId("bulk-delete-konfirmasi"), { target: { value: t } });

test("jumlah diambil dari server TANPA filter, bukan dari daftar terfilter", async () => {
  buka({ filterAktif: true });
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  expect(screen.getByTestId("bulk-delete-jumlah").textContent).not.toMatch(/248/);
  const [url, opsi] = axios.get.mock.calls[0];
  expect(url).toMatch(/\/assets$/);
  expect(opsi.params).toEqual({ activity_id: "keg-1", page: 1, page_size: 1 });
});

test("filter aktif → peringatan eksplisit bahwa filter tidak membatasi penghapusan", async () => {
  buka({ filterAktif: true });
  const peringatan = await screen.findByTestId("bulk-delete-peringatan-filter");
  expect(peringatan.textContent).toMatch(/248/);
  expect(peringatan.textContent).toMatch(/seluruh 600 aset/);
});

test("tanpa filter tidak ada peringatan filter", async () => {
  buka({ filterAktif: false, totalItems: 600 });
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  expect(screen.queryByTestId("bulk-delete-peringatan-filter")).toBeNull();
});

test("tombol hapus terkunci sampai nama kegiatan diketik dengan benar", async () => {
  buka();
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  expect(tombol()).toBeDisabled();
  ketik("Uji sintetis");
  expect(tombol()).toBeDisabled();
  ketik("  uji   SINTETIS 3 ");
  expect(tombol()).toBeEnabled();
  expect(tombol().textContent).toMatch(/Hapus 600 aset/);
});

test("konfirmasi mengirim jumlah_konfirmasi = jumlah yang dilihat operator", async () => {
  const { onClose, onSuccess } = buka();
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  ketik("Uji sintetis 3");
  fireEvent.click(tombol());
  await waitFor(() => expect(axios.delete).toHaveBeenCalled());
  const [url, opsi] = axios.delete.mock.calls[0];
  expect(url).toMatch(/\/assets\/bulk-delete\/keg-1$/);
  expect(opsi.params).toEqual({ jumlah_konfirmasi: 600 });
  await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  expect(onClose).toHaveBeenCalledWith(false);
});

test("409 (jumlah berubah) → konfirmasi direset dan jumlah terbaru dimuat ulang", async () => {
  buka();
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  axios.delete.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Jumlah aset kegiatan ini sekarang 601" } } });
  axios.get.mockResolvedValueOnce({ data: { total: 601 } });
  ketik("Uji sintetis 3");
  fireEvent.click(tombol());
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/601/));
  expect(toast.error).toHaveBeenCalled();
  expect(screen.getByTestId("bulk-delete-konfirmasi").value).toBe("");
  expect(tombol()).toBeDisabled();
});

test("gagal memuat jumlah (offline) → tidak ada tombol hapus, hanya Coba lagi", async () => {
  axios.get.mockRejectedValueOnce(new Error("Network Error"));
  buka();
  expect(await screen.findByTestId("bulk-delete-muat-ulang")).toBeInTheDocument();
  expect(screen.queryByTestId("bulk-delete-konfirmasi-btn")).toBeNull();
  expect(axios.delete).not.toHaveBeenCalled();
});

test("nama kegiatan kosong → frasa konfirmasi HAPUS", async () => {
  buka({ activityName: "" });
  await waitFor(() => expect(screen.getByTestId("bulk-delete-jumlah").textContent).toMatch(/600/));
  ketik("hapus");
  expect(tombol()).toBeEnabled();
});
