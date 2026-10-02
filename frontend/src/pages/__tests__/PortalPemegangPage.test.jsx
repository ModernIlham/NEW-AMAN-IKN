import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
