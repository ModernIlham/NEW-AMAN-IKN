import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PortalPemegangPage from "../PortalPemegangPage";
import * as portal from "@/lib/portalPemegang";

jest.mock("@/lib/portalPemegang", () => ({
  ...jest.requireActual("@/lib/portalPemegang"),
  portalRequest: jest.fn(), bacaLuringPortal: jest.fn(), hapusLuringPortal: jest.fn(),
  simpanSnapshotPortal: jest.fn(), aktifkanLuringPortal: jest.fn(),
  simpanDrafPortal: jest.fn(), hapusDrafPortal: jest.fn(),
}));
const sesi = { session_id: "s1", pegawai: { id: "p1", nama: "Pegawai Uji", kode_satker: "SATKER-A" }, csrf_token: "csrf", expires_at: new Date(Date.now() + 3600000).toISOString(), idle_expires_at: new Date(Date.now() + 1800000).toISOString() };
const asset = { id: "t1", version: 2, status: "diterima", asset_id: "a1", asset_name: "Laptop BMN", asset_code: "301", NUP: "1", location: "Ruang 1", condition: "Baik", dasar_penugasan: "BAST-001 tanggal 1 Oktober 2026" };
const rejected = () => Object.assign(new Error("Sesi berakhir"), { status: 401 });

beforeEach(() => {
  localStorage.setItem("theme", "light");
  document.documentElement.classList.remove("dark");
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  window.history.replaceState(null, "", "/bmn-saya");
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  portal.bacaLuringPortal.mockResolvedValue({ aktif: false, aset: [], antrean: [] });
  portal.hapusLuringPortal.mockResolvedValue(); portal.simpanSnapshotPortal.mockResolvedValue();
  portal.aktifkanLuringPortal.mockResolvedValue(); portal.simpanDrafPortal.mockResolvedValue([]);
  portal.portalRequest.mockImplementation(async path => {
    if (path === "/sesi") return sesi;
    if (path === "/aset") return { items: [asset] };
    if (path === "/laporan") return { items: [] };
    return { ok: true };
  });
});
afterEach(() => jest.useRealTimers());

test("tautan fragment langsung dibersihkan dan tidak masuk otomatis", async () => {
  window.history.replaceState(null, "", "/bmn-saya#token=secret-link");
  portal.portalRequest.mockImplementation(async path => { if (path === "/sesi") throw rejected(); return {}; });
  render(<PortalPemegangPage />);
  const button = await screen.findByTestId("portal-masuk-token");
  expect(window.location.hash).toBe("");
  expect(portal.portalRequest).not.toHaveBeenCalledWith("/auth/masuk", expect.anything());
  fireEvent.click(button);
  await waitFor(() => expect(portal.portalRequest).toHaveBeenCalledWith("/auth/masuk", { method: "POST", body: { token: "secret-link" } }));
});

test("login meminta email saja dengan respons tidak membocorkan registrasi", async () => {
  portal.portalRequest.mockImplementation(async path => { if (path === "/sesi") throw rejected(); return { pesan: "Jika email memenuhi syarat, tautan dikirim." }; });
  render(<PortalPemegangPage />);
  const email = await screen.findByTestId("portal-email");
  fireEvent.change(email, { target: { value: "pegawai@example.test" } });
  fireEvent.click(screen.getByTestId("portal-minta-link"));
  await waitFor(() => expect(portal.portalRequest).toHaveBeenCalledWith("/auth/minta-link", { method: "POST", body: { email: "pegawai@example.test" } }));
  expect(await screen.findByText("Jika email memenuhi syarat, tautan dikirim.")).toBeInTheDocument();
  expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
});

test("laporan kehilangan bisa tanpa foto/GPS dan tidak mengubah data induk", async () => {
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-buat-laporan-t1"));
  fireEvent.change(screen.getByTestId("portal-jenis"), { target: { value: "kehilangan" } });
  fireEvent.change(screen.getByTestId("portal-catatan"), { target: { value: "Barang tidak ditemukan setelah pemeriksaan ruangan." } });
  expect(screen.getByTestId("portal-berkas-foto")).not.toHaveAttribute("capture");
  expect(screen.getByTestId("portal-berkas-kamera")).toHaveAttribute("capture", "environment");
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  await waitFor(() => expect(portal.portalRequest).toHaveBeenCalledWith("/laporan", expect.objectContaining({ method: "POST", version: 2, csrf: "csrf", body: expect.objectContaining({ jenis: "kehilangan", bukti: [], penugasan_id: "t1", penugasan_version: 2 }) })));
  expect(await screen.findByText(/Laporan diterima untuk pemeriksaan operator/)).toBeInTheDocument();
  expect(portal.portalRequest.mock.calls.some(([path]) => path.startsWith("/assets/"))).toBe(false);
});

test("perubahan penugasan saat reconnect menghentikan pengiriman", async () => {
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-buat-laporan-t1"));
  fireEvent.change(screen.getByTestId("portal-catatan"), { target: { value: "Barang baik dan masih digunakan" } });
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? sesi : path === "/aset" ? { items: [{ ...asset, version: 3 }] } : { items: [] });
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Penugasan berubah");
  expect(portal.portalRequest.mock.calls.some(([path, options]) => path === "/laporan" && options?.method === "POST")).toBe(false);
});

test("401 pada muat ulang membersihkan data dan kembali ke login", async () => {
  render(<PortalPemegangPage />); await screen.findByTestId("portal-aset-t1");
  portal.portalRequest.mockRejectedValue(rejected());
  fireEvent.click(screen.getByTestId("portal-muat-ulang"));
  expect(await screen.findByTestId("portal-email")).toBeInTheDocument();
  expect(screen.queryByText("Laptop BMN")).not.toBeInTheDocument();
  expect(portal.hapusLuringPortal).toHaveBeenCalled();
});

test("sanggahan tersedia dan penugasan belum diterima tidak boleh dilaporkan", async () => {
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? sesi : path === "/aset" ? { items: [{ ...asset, status: "menunggu_konfirmasi" }] } : { items: [] });
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-konfirmasi-t1"));
  expect(screen.queryByTestId("portal-buat-laporan-t1")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-konfirmasi-keputusan"), { target: { value: "sanggah" } });
  fireEvent.change(screen.getByTestId("portal-konfirmasi-catatan"), { target: { value: "Barang belum pernah diterima" } });
  fireEvent.click(screen.getByTestId("portal-konfirmasi-simpan"));
  await waitFor(() => expect(portal.portalRequest).toHaveBeenCalledWith("/penugasan/t1/konfirmasi", expect.objectContaining({ method: "POST", version: 2, body: expect.objectContaining({ keputusan: "sanggah", version: 2 }) })));
});

test("BAST sah membuka laporan tanpa konfirmasi penerimaan berulang", async () => {
  const otomatis = { ...asset, penerimaan_otomatis: true, sumber_bast: { id: "b1", nomor: "BAST-001", tanggal: "2026-10-01", jenis: "penggunaan_sementara", jangka_sampai: "2026-10-31" } };
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? sesi : path === "/aset" ? { items: [otomatis] } : { items: [] });
  render(<PortalPemegangPage />);
  expect(await screen.findByTestId("portal-buat-laporan-t1")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-konfirmasi-t1")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-aset-bast-t1")).toHaveTextContent("Penerimaan tercatat melalui BAST sah");
  expect(screen.getByTestId("portal-aset-bast-t1")).toHaveTextContent("Lewat jangka waktu tidak berarti barang sudah dikembalikan");
});

test("retry setelah gangguan memakai kunci dan isi sama, bukan laporan duplikat", async () => {
  let writes = 0;
  portal.portalRequest.mockImplementation(async (path, options) => {
    if (path === "/sesi") return sesi;
    if (path === "/aset") return { items: [asset] };
    if (path === "/laporan" && options?.method === "POST") {
      writes += 1; if (writes === 1) throw new Error("Koneksi terputus saat menunggu hasil");
    }
    return { items: [] };
  });
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-buat-laporan-t1"));
  fireEvent.change(screen.getByTestId("portal-catatan"), { target: { value: "Barang digunakan dalam keadaan baik" } });
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Koneksi terputus");
  expect(screen.getByTestId("portal-catatan")).toBeDisabled();
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  await screen.findByText(/Laporan diterima untuk pemeriksaan operator/);
  const calls = portal.portalRequest.mock.calls.filter(([path, options]) => path === "/laporan" && options?.method === "POST");
  expect(calls).toHaveLength(2); expect(calls[1][1].key).toBe(calls[0][1].key); expect(calls[1][1].body).toEqual(calls[0][1].body);
});

test("batas idle yang tampil berlaku juga untuk pembersihan UI dan draf", async () => {
  jest.useFakeTimers(); jest.setSystemTime(new Date(Date.parse(sesi.idle_expires_at) - 10000));
  await act(async () => { render(<PortalPemegangPage />); });
  expect(screen.getByTestId("portal-aset-t1")).toBeInTheDocument();
  expect(screen.getByText(/Kirim draf sebelum/)).toBeInTheDocument();
  expect(screen.getByText(/Draf\/foto lokal dihapus/)).toHaveTextContent("30 menit");
  await act(async () => { jest.advanceTimersByTime(15001); });
  expect(screen.queryByTestId("portal-aset-t1")).not.toBeInTheDocument();
  expect(portal.hapusLuringPortal).toHaveBeenCalled();
});

test("mode terang/gelap tersedia sebelum login dan preferensi bertahan ketika portal dibuka ulang", async () => {
  portal.portalRequest.mockImplementation(async () => { throw rejected(); });
  const view = render(<PortalPemegangPage />);
  await screen.findByTestId("portal-email");
  fireEvent.click(screen.getByRole("button", { name: "Aktifkan mode gelap" }));
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem("theme")).toBe("dark");
  view.unmount();
  render(<PortalPemegangPage />);
  await screen.findByTestId("portal-email");
  fireEvent.click(screen.getByRole("button", { name: "Aktifkan mode terang" }));
  expect(document.documentElement).not.toHaveClass("dark");
  expect(localStorage.getItem("theme")).toBe("light");
  expect(screen.getByTestId("portal-tema")).toHaveClass("min-h-[44px]");
});

const report = { id: "r1", penugasan_id: "t1", asset_name: "Laptop BMN", jenis: "berkala", status: "diajukan", kondisi: "Rusak Ringan", status_operasional: "diperbaiki", lokasi_laporan: "Bengkel", created_at: "2026-10-03T10:00:00Z", catatan: "Layar diperiksa oleh teknisi", tinjauan: [] };
const asset2 = { ...asset, id: "t2", asset_id: "a2", asset_name: "Meja BMN", NUP: "2", sumber_bast: { nomor: "BAST-MEJA" } };
function isiMonitoring(assets, reports) {
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? sesi : path === "/aset" ? { items: assets } : path === "/laporan" ? { items: reports } : {});
}

test("ringkasan berasal dari laporan terbaru per penugasan dan filter tidak mencampurkan kondisi induk", async () => {
  isiMonitoring([asset, asset2, { ...asset, id: "t3", asset_name: "Lemari", status: "menunggu_konfirmasi" }], [
    { ...report, id: "r-lama", status: "perlu_perbaikan", created_at: "2026-10-01T10:00:00Z" },
    report, { ...report, id: "r-asing", penugasan_id: "penugasan-lama", created_at: "2026-10-04T10:00:00Z" },
  ]);
  render(<PortalPemegangPage />);
  await screen.findByTestId("portal-aset-t1");
  expect(screen.getByTestId("portal-ringkasan-semua")).toHaveTextContent("3Barang dipantau");
  expect(screen.getByTestId("portal-ringkasan-belum")).toHaveTextContent("1Belum dilaporkan");
  expect(screen.getByTestId("portal-ringkasan-menunggu")).toHaveTextContent("1Menunggu pemeriksaan");
  expect(screen.getByTestId("portal-ringkasan-perhatian")).toHaveTextContent("2Perlu perhatian");
  expect(within(screen.getByTestId("portal-aset-t1")).getByText("Baik")).toBeInTheDocument();
  expect(screen.getByTestId("portal-terakhir-t1")).toHaveTextContent("Rusak Ringan · Sedang diperbaiki");
  expect(screen.getByTestId("portal-terakhir-t1")).toHaveTextContent("Menunggu pemeriksaan");
  expect(screen.getByTestId("portal-terakhir-t1")).not.toHaveTextContent("Perlu perbaikan");
  fireEvent.click(screen.getByTestId("portal-ringkasan-belum"));
  expect(screen.queryByTestId("portal-aset-t1")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-aset-t2")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-aset-t3")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-filter"), { target: { value: "semua" } });
  fireEvent.change(screen.getByTestId("portal-cari"), { target: { value: " bast-meja " } });
  expect(screen.getByTestId("portal-aset-t2")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-aset-t1")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-cari"), { target: { value: "tidak ditemukan" } });
  fireEvent.click(screen.getByTestId("portal-reset-filter"));
  expect(screen.getByTestId("portal-aset-t1")).toBeInTheDocument();
});

test("riwayat dari kartu terfokus ke penugasan dan dapat disaring menurut keputusan", async () => {
  isiMonitoring([asset, asset2], [report, { ...report, id: "r2", penugasan_id: "t2", asset_name: "Meja BMN", status: "terverifikasi" }, { ...report, id: "r3", status: "terverifikasi", created_at: "2026-10-02T10:00:00Z" }]);
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-riwayat-t1"));
  expect(screen.getByTestId("portal-riwayat-aset")).toHaveValue("t1");
  expect(screen.getByTestId("portal-laporan-r1")).toBeInTheDocument();
  expect(screen.getByTestId("portal-laporan-r3")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-laporan-r2")).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-riwayat-status"), { target: { value: "terverifikasi" } });
  expect(screen.queryByTestId("portal-laporan-r1")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-laporan-r3")).toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-riwayat-aset"), { target: { value: "" } });
  expect(screen.getByTestId("portal-laporan-r2")).toBeInTheDocument();
});

test("pergantian principal membersihkan pencarian, filter, riwayat dan ringkasan identitas lama", async () => {
  isiMonitoring([asset], [report]);
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-riwayat-t1"));
  fireEvent.change(screen.getByTestId("portal-riwayat-status"), { target: { value: "diajukan" } });
  fireEvent.click(screen.getByTestId("portal-tab-aset"));
  fireEvent.change(screen.getByTestId("portal-cari"), { target: { value: "Laptop BMN" } });
  fireEvent.change(screen.getByTestId("portal-filter"), { target: { value: "menunggu" } });
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? { ...sesi, session_id: "s2", pegawai: { ...sesi.pegawai, id: "p2", nama: "Pegawai Baru" } } : path === "/aset" ? { items: [asset2] } : { items: [] });
  fireEvent.click(screen.getByTestId("portal-muat-ulang"));
  await screen.findByTestId("portal-aset-t2");
  expect(screen.getByTestId("portal-cari")).toHaveValue("");
  expect(screen.getByTestId("portal-filter")).toHaveValue("semua");
  expect(screen.queryByText("Laptop BMN")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-ringkasan-semua")).toHaveTextContent("1Barang dipantau");
  fireEvent.click(screen.getByTestId("portal-tab-laporan"));
  expect(screen.getByTestId("portal-riwayat-aset")).toHaveValue("");
  expect(screen.getByTestId("portal-riwayat-status")).toHaveValue("");
  expect(screen.queryByTestId("portal-laporan-r1")).not.toBeInTheDocument();
});

test("keluar menghapus ringkasan dan riwayat pribadi tanpa menghapus preferensi tema", async () => {
  isiMonitoring([asset], [report]);
  render(<PortalPemegangPage />);
  await screen.findByTestId("portal-aset-t1");
  fireEvent.click(screen.getByTestId("portal-tema"));
  fireEvent.click(screen.getByTestId("portal-keluar"));
  await screen.findByTestId("portal-email");
  expect(screen.queryByTestId("portal-ringkasan-semua")).not.toBeInTheDocument();
  expect(screen.queryByTestId("portal-aset-t1")).not.toBeInTheDocument();
  expect(screen.queryByText("Layar diperiksa oleh teknisi")).not.toBeInTheDocument();
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem("theme")).toBe("dark");
  expect(portal.hapusLuringPortal).toHaveBeenCalled();
});

test("tanpa barang menuntun pemegang ke BAST sah, bukan pemetaan ulang mandiri", async () => {
  isiMonitoring([], []);
  render(<PortalPemegangPage />);
  expect(await screen.findByText("Belum ada barang yang dapat dipantau")).toBeInTheDocument();
  expect(screen.getByText(/Barang muncul setelah BAST lengkap dan sah/)).toBeInTheDocument();
  expect(screen.getByTestId("portal-ringkasan-belum")).toHaveTextContent("0Belum dilaporkan");
});
