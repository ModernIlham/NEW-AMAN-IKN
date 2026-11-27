import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import CitraEksistingDialog from "../CitraEksistingDialog";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children, ...p }) => <div {...p}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <p>{children}</p>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

const CITRA = {
  id: "c1", version: 3, nama: "Citra KIPP", sumber: "Tim", tanggal_rekam: "2026-10-15",
  url_template: "/uploads/ubin/kipp/{z}/{x}/{y}.webp",
  batas: { barat: 116.69, selatan: -0.98, timur: 116.72, utara: -0.95 },
  zoom_min: 14, zoom_maks: 20, opasitas: 0.85, aktif: true, bisa_ubah: true, kode_satker: "A",
};

beforeEach(() => jest.clearAllMocks());

test("belum ada citra: panduan menyiapkan ubin tampil", async () => {
  axios.get.mockResolvedValue({ data: { items: [] } });
  render(<CitraEksistingDialog onClose={() => {}} />);
  expect(await screen.findByTestId("citra-daftar-kosong")).toHaveTextContent(/Generate XYZ tiles/);
});

test("mendaftarkan citra mengirim batas & zoom sebagai angka", async () => {
  axios.get.mockResolvedValue({ data: { items: [] } });
  axios.post.mockResolvedValue({ data: CITRA });
  render(<CitraEksistingDialog onClose={() => {}} />);
  await screen.findByTestId("citra-daftar-kosong");
  fireEvent.click(screen.getByTestId("citra-tambah"));
  const isi = (id, v) => fireEvent.change(screen.getByTestId(id), { target: { value: v } });
  isi("citra-f-nama", "Citra KIPP");
  isi("citra-f-tanggal", "2026-10-15");
  isi("citra-f-url", "/uploads/ubin/kipp/{z}/{x}/{y}.webp");
  isi("citra-f-barat", "116,69");
  isi("citra-f-selatan", "-0.98");
  isi("citra-f-timur", "116.72");
  isi("citra-f-utara", "-0.95");
  fireEvent.click(screen.getByTestId("citra-simpan"));
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const [url, body] = axios.post.mock.calls[0];
  expect(url).toMatch(/\/peta-lapisan$/);
  expect(body.batas).toEqual({ barat: 116.69, selatan: -0.98, timur: 116.72, utara: -0.95 });
  expect(body).toMatchObject({ zoom_min: 14, zoom_maks: 20, opasitas: 0.85, aktif: true });
});

test("mengubah citra mengirim versi (OCC)", async () => {
  axios.get.mockResolvedValue({ data: { items: [CITRA] } });
  axios.put.mockResolvedValue({ data: CITRA });
  render(<CitraEksistingDialog onClose={() => {}} />);
  fireEvent.click(await screen.findByTestId("citra-ubah-c1"));
  fireEvent.click(screen.getByTestId("citra-f-aktif"));
  fireEvent.click(screen.getByTestId("citra-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalled());
  const [url, body] = axios.put.mock.calls[0];
  expect(url).toMatch(/\/peta-lapisan\/c1$/);
  expect(body).toMatchObject({ version: 3, aktif: false });
});

test("citra satker lain tak bisa diubah dari sini", async () => {
  axios.get.mockResolvedValue({ data: { items: [{ ...CITRA, bisa_ubah: false, kode_satker: "B" }] } });
  render(<CitraEksistingDialog onClose={() => {}} />);
  expect(await screen.findByTestId("citra-item-c1")).toHaveTextContent("Dikelola satker B");
  expect(screen.queryByTestId("citra-ubah-c1")).not.toBeInTheDocument();
});
