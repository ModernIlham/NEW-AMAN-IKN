import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import LapisanEksistingDialog from "../LapisanEksistingDialog";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));
jest.mock("../EditorGambarPeta", () => function EditorPalsu({ lapisan }) {
  return <div data-testid="editor-palsu">{lapisan.nama}</div>;
});
jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children, ...p }) => <div {...p}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <p>{children}</p>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

const C1 = { id: "c1", jenis: "citra", nama: "Citra Okt", tanggal_rekam: "2026-10-15", status: "siap",
  aktif: true, urutan: 2, version: 3, opasitas: 1, ukuran_byte: 5 * 1024 * 1024, bisa_ubah: true };
const C2 = { ...C1, id: "c2", nama: "Citra Mei", urutan: 1, version: 1 };
const G1 = { id: "g1", jenis: "gambar", nama: "Jalan", fitur: [{ id: "f" }], aktif: true, urutan: 1, version: 2,
  label_zoom_min: 15, bisa_ubah: false, kode_satker: "B" };

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: { items: [C2, C1, G1] } });
  axios.put.mockResolvedValue({ data: {} });
});

test("daftar ringkas per jenis, citra teratas = urutan tertinggi", async () => {
  render(<LapisanEksistingDialog onClose={() => {}} />);
  await screen.findByTestId("lapisan-c1");
  const urutanTampil = screen.getAllByTestId(/^lapisan-c\d$/).map((el) => el.dataset.testid);
  expect(urutanTampil).toEqual(["lapisan-c1", "lapisan-c2"]);
  expect(screen.getByTestId("lapisan-g1")).toHaveTextContent("1 objek");
  // Milik satker lain: tak bisa diubah/dihapus, tapi urutan tetap bisa.
  expect(screen.queryByTestId("lapisan-hapus-g1")).not.toBeInTheDocument();
});

test("turunkan citra teratas → kirim urutan bawah-ke-atas", async () => {
  render(<LapisanEksistingDialog onClose={() => {}} />);
  fireEvent.click(await screen.findByTestId("lapisan-turun-c1"));
  await waitFor(() => expect(axios.put).toHaveBeenCalledWith(expect.stringMatching(/peta-lapisan-urutan$/), { ids: ["c1", "c2"] }));
});

test("sembunyikan citra mengirim versi (OCC)", async () => {
  render(<LapisanEksistingDialog onClose={() => {}} />);
  fireEvent.click(await screen.findByTestId("lapisan-aktif-c1"));
  await waitFor(() => expect(axios.put).toHaveBeenCalled());
  const [url, body] = axios.put.mock.calls[0];
  expect(url).toMatch(/\/peta-lapisan\/c1$/);
  expect(body).toMatchObject({ jenis: "citra", aktif: false, version: 3 });
});

test("gambar baru → buat lapisan lalu buka editor", async () => {
  axios.post.mockResolvedValue({ data: { id: "g9", jenis: "gambar", nama: "Jalan 2026", fitur: [], version: 1 } });
  render(<LapisanEksistingDialog onClose={() => {}} />);
  fireEvent.click(await screen.findByTestId("lapisan-gambar-baru"));
  fireEvent.change(screen.getByTestId("gambar-nama"), { target: { value: "Jalan 2026" } });
  fireEvent.click(screen.getByTestId("gambar-buat"));
  expect(await screen.findByTestId("editor-palsu")).toHaveTextContent("Jalan 2026");
  expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/peta-lapisan$/), { jenis: "gambar", nama: "Jalan 2026", fitur: [] });
  // Dialog disembunyikan selama editor terbuka (dialog modal menahan klik di luarnya).
  expect(screen.queryByTestId("lapisan-eksisting-dialog")).not.toBeInTheDocument();
});

test("berkas bukan GeoTIFF memberi pesan jelas", async () => {
  jest.doMock("@/lib/ubinCitra", () => ({ bukaGeoTiff: jest.fn().mockRejectedValue(new Error("Berkas ini tidak memuat informasi lokasi (bukan GeoTIFF).")) }));
  const { toast } = require("sonner");
  render(<LapisanEksistingDialog onClose={() => {}} />);
  await screen.findByTestId("lapisan-c1");
  const berkas = new File(["x"], "foto.tif", { type: "image/tiff" });
  fireEvent.change(screen.getByTestId("lapisan-berkas"), { target: { files: [berkas] } });
  await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringMatching(/bukan GeoTIFF/)));
});
