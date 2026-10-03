import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axios from "axios";
import PortalPemegangPanel from "../PortalPemegangPanel";

jest.mock("axios");
const staff = { id: "p1", nama: "Pegawai Uji", email: "pegawai@example.test", kode_satker: "A" };
const report = { id: "r1", version: 1, status: "diajukan", asset_name: "Laptop Uji", jenis: "kehilangan", pegawai_nama: "Pegawai Uji", kondisi: "Tidak diketahui", catatan: "Barang belum ditemukan", bukti: [] };
const summary = { pemegang: 8, penugasan: { total: 87, diterima: 82, dicabut: 5 }, laporan: { total: 120, menunggu_tinjauan: 34, perlu_perbaikan: 12, terverifikasi: 71, ditolak: 3 } };
const deferred = () => { let resolve; let reject; const promise = new Promise((res, rej) => { resolve = res; reject = rej; }); return { promise, resolve, reject }; };

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  URL.createObjectURL = jest.fn(() => "blob:laporan");
  URL.revokeObjectURL = jest.fn();
  axios.get.mockImplementation(async (url, options) => {
    if (url.endsWith("/pegawai")) return { data: { items: [staff] } };
    if (url.endsWith("/admin/akses")) return { data: { ...staff, pegawai_id: "p1", version: 0, akses: { aktif: false, version: 0 } } };
    if (url.endsWith("/admin/monitoring")) return { data: summary };
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
  expect(screen.getByTestId("portal-admin-akses-toggle").closest("details")).not.toHaveAttribute("open");
  fireEvent.click(screen.getByTestId("portal-admin-akses-toggle"));
  expect(approve).toBeDisabled();
  fireEvent.click(screen.getByTestId("portal-admin-email-benar"));
  fireEvent.change(screen.getByTestId("portal-admin-akses-catatan"), { target: { value: "Email milik pegawai telah diperiksa" } });
  fireEvent.click(approve);
  await waitFor(() => expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/akses$/), expect.objectContaining({ pegawai_id: "p1", email: staff.email, aktif: true, konfirmasi_email: true, version: 0 }), expect.objectContaining({ headers: { "If-Match": "0", "Idempotency-Key": expect.any(String) } })));
});

test("ringkasan server tidak berubah menjadi hitungan halaman atau saringan laporan", async () => {
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  expect(await screen.findByTestId("portal-monitor-menunggu")).toHaveTextContent("34");
  expect(screen.getByTestId("portal-monitor-diterima")).toHaveTextContent("82");
  expect(screen.getByTestId("portal-admin-total-laporan")).toHaveTextContent("31 laporan sesuai saringan");
  expect(screen.getByText(/Status penugasan tercatat bukan jaminan akses masih berlaku/)).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("portal-admin-berikutnya"));
  await screen.findByTestId("portal-admin-tinjau-r31");
  expect(screen.getByTestId("portal-monitor-menunggu")).toHaveTextContent("34");
  fireEvent.change(screen.getByTestId("portal-admin-status"), { target: { value: "perlu_perbaikan" } });
  await screen.findByTestId("portal-admin-tinjau-r1");
  expect(screen.getByTestId("portal-monitor-perbaikan")).toHaveTextContent("12");
  expect(axios.get.mock.calls.filter(([url]) => url.endsWith("/admin/monitoring")).every(([, options]) => Object.keys(options.params).length === 0)).toBe(true);
});

test("pencarian laporan diterapkan server sebelum paginasi tanpa menyaring ringkasan", async () => {
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  await screen.findByTestId("portal-admin-tinjau-r1");
  fireEvent.click(screen.getByTestId("portal-admin-berikutnya"));
  await screen.findByTestId("portal-admin-tinjau-r31");
  fireEvent.change(screen.getByTestId("portal-admin-cari-laporan"), { target: { value: "  Ruang A  " } });
  await waitFor(() => expect(axios.get).toHaveBeenCalledWith(expect.stringMatching(/\/admin\/laporan$/), { params: { page: 1, page_size: 30, status: "", search: "Ruang A" } }));
  expect(screen.getByTestId("portal-monitor-menunggu")).toHaveTextContent("34");
  expect(axios.get.mock.calls.filter(([url]) => url.endsWith("/admin/monitoring")).every(([, options]) => !options.params.search)).toBe(true);
});

test("gagal atau lambat memuat ringkasan tidak menghalangi pemeriksaan laporan", async () => {
  const baseGet = axios.get.getMockImplementation();
  const pending = deferred();
  axios.get.mockImplementation((url, options) => url.endsWith("/admin/monitoring") ? pending.promise : baseGet(url, options));
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  expect(await screen.findByTestId("portal-admin-tinjau-r1")).not.toBeDisabled();
  expect(screen.getByTestId("portal-monitor-menunggu")).toHaveTextContent("—");
  await act(async () => pending.reject(new Error("Koneksi ringkasan gagal")));
  expect(await screen.findByText(/Ringkasan belum tersedia/)).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("portal-admin-tinjau-r1"));
  expect(screen.getByTestId("portal-admin-tinjau-simpan")).toBeInTheDocument();
});

test("hasil ringkasan dan laporan lama tidak menimpa lingkup pemegang baru", async () => {
  const baseGet = axios.get.getMockImplementation();
  const pendingSummary = deferred(); const pendingReports = deferred();
  axios.get.mockImplementation((url, options) => {
    if (url.endsWith("/admin/monitoring")) return options.params.pegawai_id ? Promise.resolve({ data: { ...summary, pemegang: 1 } }) : pendingSummary.promise;
    if (url.endsWith("/admin/laporan") && !options.params.pegawai_id) return pendingReports.promise;
    return baseGet(url, options);
  });
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  await screen.findByRole("option", { name: "Pegawai Uji · A" });
  fireEvent.change(screen.getByTestId("portal-admin-pegawai"), { target: { value: "p1" } });
  await screen.findByTestId("portal-admin-tinjau-r1");
  expect(within(screen.getByTestId("portal-monitor-pemegang")).getByText("1")).toBeInTheDocument();
  await act(async () => { pendingSummary.resolve({ data: summary }); pendingReports.resolve({ data: { items: [{ ...report, id: "usang" }], total: 99 } }); });
  expect(within(screen.getByTestId("portal-monitor-pemegang")).getByText("1")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-admin-tinjau-usang")).not.toBeInTheDocument();
});

test("kartu amanah membedakan data induk, BAST, laporan dan riwayat dicabut", async () => {
  const baseGet = axios.get.getMockImplementation();
  axios.get.mockImplementation((url, options) => url.endsWith("/admin/penugasan") ? Promise.resolve({ data: { items: [
    { id: "bast1", status: "diterima", asset_name: "Laptop BAST", asset_code: "301", NUP: "8", condition: "Baik", location: "Kantor A", akses_valid: true, sumber_bast: { nomor: "007/SATKER/2026", tanggal: "2026-10-03" }, penerimaan_otomatis: true, laporan_terakhir: { status: "diajukan", kondisi: "Rusak Ringan", lokasi_laporan: "Bengkel", created_at: "2026-10-03T01:00:00Z" } },
    { id: "lama", status: "dicabut", asset_name: "Printer Lama", condition: "Baik", location: "Kantor Lama", akses_valid: false, alasan_akses: "Pemegang telah berganti", dasar_penugasan: "Surat lama yang diverifikasi" },
  ] } }) : baseGet(url, options));
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  await screen.findByTestId("portal-admin-tinjau-r1");
  fireEvent.change(screen.getByTestId("portal-admin-pegawai"), { target: { value: "p1" } });
  const card = await screen.findByTestId("portal-admin-amanah-bast1");
  expect(card).toHaveTextContent("Kondisi data indukBaik");
  expect(card).toHaveTextContent("BAST 007/SATKER/2026");
  expect(card).toHaveTextContent("Diterima melalui BAST, tanpa konfirmasi ulang");
  expect(card).toHaveTextContent("Rusak Ringan");
  expect(card).toHaveTextContent("Lokasi dilaporkan: Bengkel");
  const oldCard = screen.getByTestId("portal-admin-amanah-lama");
  expect(oldCard).toHaveTextContent("Kondisi tercatat saat penugasan");
  expect(oldCard).toHaveTextContent("Penugasan lama / manual");
  expect(oldCard).toHaveTextContent("Pemegang telah berganti");
  fireEvent.change(screen.getByTestId("portal-admin-status-amanah"), { target: { value: "diterima" } });
  expect(screen.queryByTestId("portal-admin-amanah-lama")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-admin-cari-amanah"), { target: { value: "tidak cocok" } });
  expect(screen.getByText(/Tidak ada amanah sesuai pencarian/)).toBeInTheDocument();
});

test("keadaan kosong dibedakan dari laporan yang gagal dimuat", async () => {
  const baseGet = axios.get.getMockImplementation();
  axios.get.mockImplementation((url, options) => url.endsWith("/admin/laporan") ? Promise.resolve({ data: { items: [], total: 0 } }) : baseGet(url, options));
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  expect(await screen.findByText("Tidak ada laporan sesuai pilihan.")).toBeInTheDocument();
  axios.get.mockImplementation((url, options) => url.endsWith("/admin/laporan") ? Promise.reject(new Error("Tidak tersedia")) : baseGet(url, options));
  fireEvent.click(screen.getByTestId("portal-admin-muat"));
  expect(await screen.findByText("Laporan gagal dimuat. Coba muat ulang.")).toBeInTheDocument();
  expect(screen.queryByText("Tidak ada laporan sesuai pilihan.")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-admin-total-laporan")).toHaveTextContent("Jumlah laporan belum tersedia");
});

test("foto yang selesai dimuat setelah lingkup berubah tidak membuka pratinjau lama", async () => {
  const baseGet = axios.get.getMockImplementation();
  const photo = deferred();
  axios.get.mockImplementation((url, options) => {
    if (url.includes("/bukti/")) return photo.promise;
    if (url.endsWith("/admin/laporan")) return Promise.resolve({ data: { items: [{ ...report, bukti: [{ nama: "foto-laporan.jpg" }] }], total: 1 } });
    return baseGet(url, options);
  });
  const { rerender } = render(<PortalPemegangPanel user={{ role: "admin" }} />);
  fireEvent.click(await screen.findByTestId("portal-admin-bukti-r1-0"));
  // Perubahan kewenangan memuat ulang lingkup dan menutup pratinjau yang lama.
  rerender(<PortalPemegangPanel user={{ role: "operator" }} />);
  await act(async () => photo.resolve({ data: new Blob(["foto"]) }));
  expect(URL.createObjectURL).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog", { name: "Bukti laporan pemegang" })).not.toBeInTheDocument();
});

test("URL bukti dilepas saat pratinjau ditutup", async () => {
  const baseGet = axios.get.getMockImplementation();
  axios.get.mockImplementation((url, options) => {
    if (url.includes("/bukti/")) return Promise.resolve({ data: new Blob(["foto"]) });
    if (url.endsWith("/admin/laporan")) return Promise.resolve({ data: { items: [{ ...report, bukti: [{ nama: "foto-laporan.jpg" }] }], total: 1 } });
    return baseGet(url, options);
  });
  render(<PortalPemegangPanel user={{ role: "operator" }} />);
  fireEvent.click(await screen.findByTestId("portal-admin-bukti-r1-0"));
  fireEvent.click(await screen.findByTestId("portal-admin-tutup-bukti"));
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:laporan");
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
