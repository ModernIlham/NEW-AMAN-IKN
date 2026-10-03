import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import PortalPemegangPanel from "../PortalPemegangPanel";

jest.mock("axios");
const staff = { id: "p1", nama: "Pegawai Uji", email: "pegawai@example.test", kode_satker: "A" };
const report = { id: "r1", version: 1, status: "diajukan", asset_name: "Laptop Uji", jenis: "kehilangan", pegawai_nama: "Pegawai Uji", kondisi: "Tidak diketahui", catatan: "Barang belum ditemukan", bukti: [] };

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  axios.get.mockImplementation(async (url, options) => {
    if (url.endsWith("/pegawai")) return { data: { items: [staff] } };
    if (url.endsWith("/admin/akses")) return { data: { ...staff, pegawai_id: "p1", version: 0, akses: { aktif: false, version: 0 } } };
    if (url.endsWith("/admin/penugasan")) return { data: { items: [{ id: "t1", version: 1, status: "menunggu_konfirmasi", asset_name: "Laptop Uji", dasar_penugasan: "BAST sah" }] } };
    if (url.endsWith("/admin/laporan")) return { data: { items: [{ ...report, id: options.params.page === 2 ? "r31" : "r1" }], total: 31, page: options.params.page, page_size: 30 } };
    return { data: { items: [] } };
  });
  axios.post.mockResolvedValue({ data: { ok: true } });
});

test("operator boleh memeriksa laporan, tidak memiliki tombol persetujuan atau pemetaan akses", async () => {
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  await screen.findByTestId("portal-admin-tinjau-r1");
  fireEvent.change(screen.getByTestId("portal-admin-pegawai"), { target: { value: "p1" } });
  expect(await screen.findByText(/Operator dapat memeriksa laporan/)).toBeInTheDocument();
  await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/penugasan$/), { params: { pegawai_id: "p1" } }));
  expect(screen.queryByTestId("portal-admin-tambah-toggle")).not.toBeInTheDocument();
  expect(screen.queryByTestId("portal-admin-cabut-t1")).not.toBeInTheDocument();
  expect(screen.queryByTestId("portal-admin-aktifkan")).not.toBeInTheDocument();
  expect(axios.get.mock.calls.some(([url]) => url.endsWith("/admin/akses"))).toBe(false);
});

test("seluruh halaman laporan bisa ditelusuri dan status/pegawai difilter server", async () => {
  render(<PortalPemegangPanel user={{ role: "admin" }} />);
  await screen.findByTestId("portal-admin-tinjau-r1");
  fireEvent.click(screen.getByTestId("portal-admin-berikutnya"));
  expect(await screen.findByTestId("portal-admin-tinjau-r31")).toBeInTheDocument();
  expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/laporan$/), { params: { page: 2, page_size: 30, status: "" } });
  fireEvent.change(screen.getByTestId("portal-admin-status"), { target: { value: "perlu_perbaikan" } });
  await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/laporan$/), { params: { page: 1, page_size: 30, status: "perlu_perbaikan" } }));
  fireEvent.change(screen.getByTestId("portal-admin-pegawai"), { target: { value: "p1" } });
  await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/laporan$/), { params: { page: 1, page_size: 30, status: "perlu_perbaikan", pegawai_id: "p1" } }));
});

test("persetujuan email memerlukan konfirmasi eksplisit dan versi akses", async () => {
  render(<PortalPemegangPanel user={{ role: "admin" }} />);
  await screen.findByTestId("portal-admin-tinjau-r1");
  fireEvent.change(screen.getByTestId("portal-admin-pegawai"), { target: { value: "p1" } });
  const approve = await screen.findByTestId("portal-admin-aktifkan");
  expect(approve).toBeDisabled();
  fireEvent.click(screen.getByTestId("portal-admin-email-benar"));
  fireEvent.change(screen.getByTestId("portal-admin-akses-catatan"), { target: { value: "Email milik pegawai telah diperiksa" } });
  fireEvent.click(approve);
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/akses$/), expect.objectContaining({ pegawai_id: "p1", email: staff.email, aktif: true, konfirmasi_email: true, version: 0 }), expect.objectContaining({ headers: { "If-Match": "0", "Idempotency-Key": expect.any(String) } })));
});

test("review mewajibkan alasan, versi dan gerbang bukan mutasi master", async () => {
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  fireEvent.click(await screen.findByTestId("portal-admin-tinjau-r1"));
  fireEvent.click(screen.getByTestId("portal-admin-tinjau-simpan"));
  expect(await screen.findByRole("alert")).toHaveTextContent("minimal 5 karakter");
  expect(axios.post).not.toHaveBeenCalled();
  fireEvent.change(screen.getByTestId("portal-admin-tinjauan-catatan"), { target: { value: "Lengkapi kronologi dan lokasi terakhir" } });
  fireEvent.click(screen.getByTestId("portal-admin-tinjau-simpan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/laporan\/r1\/tinjau$/), { version: 1, keputusan: "perlu_perbaikan", catatan: "Lengkapi kronologi dan lokasi terakhir" }, expect.objectContaining({ headers: { "If-Match": "1", "Idempotency-Key": expect.any(String) } })));
});
