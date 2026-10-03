import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PortalPemegangPage from "../PortalPemegangPage";
import * as portal from "@/lib/portalPemegang";
let mockCamera;
jest.mock("@/components/portal/KameraPemegang", () => props => {
  mockCamera = props;
  return <div data-testid="uji-kamera">{props.pesanPemegang}<button onClick={props.onClose}>Tutup kamera uji</button></div>;
});
jest.mock("@/lib/portalPemegang", () => ({ ...jest.requireActual("@/lib/portalPemegang"),
  portalRequest: jest.fn(), bacaLuringPortal: jest.fn(), hapusLuringPortal: jest.fn(),
  simpanSnapshotPortal: jest.fn(), simpanDrafPortal: jest.fn(),
}));
const session = () => ({ session_id: "s1", pegawai: { id: "p1", nama: "Pemegang Uji", kode_satker: "A" }, csrf_token: "csrf", expires_at: new Date(Date.now() + 3600000).toISOString(), idle_expires_at: new Date(Date.now() + 1800000).toISOString() });
const a = { id: "t1", asset_id: "a1", version: 2, status: "diterima", asset_code: "3050101001", asset_name: "Laptop", NUP: "1" };
const b = { ...a, id: "t2", asset_id: "a2", NUP: "2" };
const data = "data:image/jpeg;base64,YQ==";
const meta = { waktu: "2026-10-03T10:00:00Z", gps: { lat: -0.96, lng: 116.7, accuracy: 25 } };
beforeEach(() => {
  localStorage.setItem("theme", "light");
  mockCamera = null;
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  window.history.replaceState(null, "", "/bmn-saya");
  portal.bacaLuringPortal.mockResolvedValue({ aktif: true, aset: [a, b], antrean: [] });
  portal.simpanSnapshotPortal.mockResolvedValue(); portal.hapusLuringPortal.mockResolvedValue(); portal.simpanDrafPortal.mockResolvedValue([]);
  portal.portalRequest.mockImplementation(async path => path === "/sesi" ? session() : path === "/aset" ? { items: [a, b] } : { items: [] });
});
async function buka() {
  render(<PortalPemegangPage />);
  fireEvent.click(await screen.findByTestId("portal-buat-laporan-t1"));
  fireEvent.click(screen.getByTestId("portal-kamera"));
  await screen.findByTestId("uji-kamera");
}
test("foto GPS dan laporan memakai endpoint portal saja, kamera biasa tetap terpisah", async () => {
  await buka();
  act(() => mockCamera.onCapture(data, mockCamera.sesiAset, meta));
  expect(mockCamera.form.bukti[0].pengambilan).toEqual(meta);
  act(() => mockCamera.onField("catatan", "Barang telah diperiksa langsung"));
  act(() => mockCamera.onField("asset_name", "Tidak boleh mengganti induk"));
  expect(mockCamera.form.asset_name).toBeUndefined();
  fireEvent.click(screen.getByText("Tutup kamera uji"));
  expect(screen.getByTestId("portal-kamera-biasa")).toBeInTheDocument();
  expect(screen.getByTestId("portal-berkas-kamera")).toHaveAttribute("capture", "environment");
  expect(screen.getByTestId("portal-berkas-foto")).not.toHaveAttribute("capture");
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  await waitFor(() => expect(portal.portalRequest).toHaveBeenCalledWith("/laporan", expect.objectContaining({ method: "POST", version: 2, csrf: "csrf", body: expect.objectContaining({ bukti: [expect.objectContaining({ pengambilan: meta })] }) })));
  expect(portal.portalRequest.mock.calls.some(([path]) => path.startsWith("/assets") || path.startsWith("/auth/preferensi"))).toBe(false);
});
test("scan ambigu/asing tidak memilih; scan tepat berpindah tanpa mencampur callback foto lama", async () => {
  await buka(); const old = mockCamera;
  act(() => mockCamera.onScanAsset(a.asset_code));
  expect(screen.getByTestId("uji-kamera")).toHaveTextContent("beberapa barang");
  act(() => mockCamera.onScanAsset("orang-lain"));
  expect(mockCamera.assignment.id).toBe("t1");
  act(() => mockCamera.onScanAsset(a.asset_code, `#${b.asset_code}-2`));
  expect(mockCamera.assignment.id).toBe("t2");
  act(() => old.onCapture(data, old.sesiAset, meta));
  expect(mockCamera.form.bukti).toEqual([]);
  act(() => mockCamera.onCapture(data, mockCamera.sesiAset, meta));
  act(() => mockCamera.onScanAsset(a.asset_code, `#${a.asset_code}-1`));
  expect(mockCamera.assignment.id).toBe("t2");
  expect(screen.getByTestId("uji-kamera")).toHaveTextContent("belum selesai");
});
test("luring mempertahankan foto/koordinat dalam draf, tidak mengirim otomatis", async () => {
  await buka();
  act(() => mockCamera.onCapture(data, mockCamera.sesiAset, meta));
  act(() => mockCamera.onField("catatan", "Keadaan barang telah diperiksa"));
  fireEvent.click(screen.getByText("Tutup kamera uji"));
  Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
  act(() => window.dispatchEvent(new Event("offline")));
  fireEvent.click(screen.getByTestId("portal-kirim-laporan"));
  await waitFor(() => expect(portal.simpanDrafPortal).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ bukti: [expect.objectContaining({ pengambilan: meta })] }), expect.objectContaining({ siap: true })));
  expect(portal.portalRequest.mock.calls.some(([, o]) => o?.method === "POST")).toBe(false);
});
test("akhir sesi menutup kamera dan menolak hasil tertunda", async () => {
  await buka(); const old = mockCamera;
  portal.portalRequest.mockRejectedValue(Object.assign(Error("Sesi habis"), { status: 401 }));
  fireEvent.click(screen.getByTestId("portal-muat-ulang"));
  await screen.findByTestId("portal-email");
  expect(screen.queryByTestId("uji-kamera")).not.toBeInTheDocument();
  act(() => old.onCapture(data, old.sesiAset, meta));
  expect(screen.queryByTestId("portal-pengambilan-0")).not.toBeInTheDocument();
});
