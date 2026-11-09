import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssetForm from "../AssetForm";
import axios from "axios";

// Draf: perubahan belum disimpan (isian + foto) harus selamat dari tutup form
// / Back, dialog hanya muncul bila memang ada perubahan, dan draf dipulihkan
// saat aset yang sama dibuka lagi. IndexedDB diganti peta memori.
// (fungsi biasa, bukan jest.fn: CRA memakai resetMocks sehingga implementasi
// jest.fn dikosongkan sebelum tiap uji)
const mockToko = new Map();
const mockMuat = { n: 0 };
jest.mock("../../../lib/drafAset", () => {
  const asli = jest.requireActual("../../../lib/drafAset");
  return {
    ...asli,
    simpanDraf: async (rec) => { mockToko.set(rec.key, rec); },
    muatDraf: async (key) => { mockMuat.n += 1; return mockToko.get(key) || null; },
    hapusDraf: async (key) => { mockToko.delete(key); },
  };
});
jest.mock("axios", () => {
  const api = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } } };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => function Camera() { return null; });

const asset = { id: "a1", asset_code: "3050105007", asset_name: "Laptop uji", category: "Komputer", NUP: "1", version: 7,
  activity_id: "k1", photo_count: 1, thumbnail_index: 0, stiker_photo_index: null, inventory_status: "Belum Diinventarisasi",
  koordinat_latitude: "-1", koordinat_longitude: "116" };
const KUNCI = "u1|k1|a1";
beforeAll(() => { HTMLElement.prototype.scrollIntoView = () => {}; });
beforeEach(() => {
  mockToko.clear(); sessionStorage.clear(); mockMuat.n = 0;
  jest.clearAllMocks();
  localStorage.setItem("user", JSON.stringify({ id: "u1", name: "Uji" }));
  localStorage.setItem("aman_auto_inventarisasi", "off");
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/") ? asset : { items: [] } }));
});
async function buka(extra = {}) {
  const props = { isOpen: true, inventoryMode: true, editAsset: asset, activity: { id: "k1" }, categories: [],
    onClose: jest.fn(), onOptimisticSubmit: jest.fn(), ...extra };
  const view = render(<AssetForm {...props} />);
  await screen.findByTestId("sheet-photo-thumb-0");
  await waitFor(() => expect(mockMuat.n).toBeGreaterThan(0));
  await act(async () => {}); // biarkan pemeriksaan draf selesai
  return { ...view, props };
}
const ubahLokasi = (v) => fireEvent.change(document.querySelector('input[name="location"]'), { target: { value: v } });

test("form yang tidak disentuh langsung tertutup tanpa dialog", async () => {
  const { props } = await buka();
  expect(screen.queryByTestId("asset-form-dirty-badge")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("sheet-close"));
  expect(screen.queryByTestId("konfirmasi-keluar-form")).not.toBeInTheDocument();
  expect(props.onClose).toHaveBeenCalledTimes(1);
});

test("perubahan ditandai, dialog muncul, 'Lanjut Edit' bertahan, 'Keluar' menyimpan draf", async () => {
  const { props } = await buka();
  ubahLokasi("Ruang Rapat 2");
  expect(screen.getByTestId("asset-form-dirty-badge")).toBeInTheDocument();
  expect(screen.getByTestId("draf-banner")).toHaveTextContent("Lokasi");
  fireEvent.click(screen.getByTestId("sheet-close"));
  expect(screen.getByTestId("konfirmasi-keluar-form")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-lanjut"));
  expect(screen.queryByTestId("konfirmasi-keluar-form")).not.toBeInTheDocument();
  expect(props.onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("sheet-close"));
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-draf"));
  expect(props.onClose).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(mockToko.get(KUNCI)?.formData.location).toBe("Ruang Rapat 2"));
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
});

test("draf dipulihkan saat aset dibuka lagi dan bisa dibuang", async () => {
  mockToko.set(KUNCI, { key: KUNCI, userId: "u1", activityId: "k1", assetId: "a1", baseVersion: 7, updatedAt: Date.now(),
    formData: { ...asset, location: "Gudang" }, original: { ...asset, location: "" }, fotoBaru: [], fotoTetap: [0], fotoDiubah: false });
  await buka();
  await waitFor(() => expect(document.querySelector('input[name="location"]').value).toBe("Gudang"));
  expect(screen.getByTestId("draf-banner")).toHaveTextContent("draf dipulihkan");
  fireEvent.click(screen.getByTestId("draf-banner-buang"));
  fireEvent.click(screen.getByTestId("draf-banner-buang"));
  await waitFor(() => expect(document.querySelector('input[name="location"]').value).toBe(""));
  expect(mockToko.has(KUNCI)).toBe(false);
});

test("foto baru dari draf kembali ke strip dengan tanda 'Baru'", async () => {
  mockToko.set(KUNCI, { key: KUNCI, userId: "u1", activityId: "k1", assetId: "a1", baseVersion: 7, updatedAt: Date.now(),
    formData: { ...asset }, original: { ...asset }, fotoBaru: [{ newData: "data:image/jpeg;base64,AAA", thumbnail: "data:image/jpeg;base64,AAA" }],
    fotoTetap: [0], fotoDiubah: true });
  await buka();
  expect(await screen.findByTestId("sheet-photo-new-1")).toBeInTheDocument();
  expect(screen.getByTestId("draf-banner")).toHaveTextContent("1 foto baru");
});

test("'Jangan tanya lagi' membuat keluar berikutnya tanpa dialog", async () => {
  const { props, unmount } = await buka();
  ubahLokasi("Lantai 3");
  fireEvent.click(screen.getByTestId("sheet-close"));
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-jangan-tanya"));
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-draf"));
  expect(props.onClose).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(mockToko.get(KUNCI)?.formData.location).toBe("Lantai 3"));
  unmount();
  expect(mockToko.get(KUNCI)?.formData.location).toBe("Lantai 3");
  const kedua = await buka();
  await waitFor(() => expect(document.querySelector('input[name="location"]').value).toBe("Lantai 3"));
  fireEvent.click(screen.getByTestId("sheet-close"));
  expect(screen.queryByTestId("konfirmasi-keluar-form")).not.toBeInTheDocument();
  expect(kedua.props.onClose).toHaveBeenCalledTimes(1);
});

test("menyimpan menyerahkan perubahan ke antrean lalu menghapus draf", async () => {
  const { props } = await buka();
  ubahLokasi("Lantai 4");
  await waitFor(() => expect(mockToko.get(KUNCI)?.formData.location).toBe("Lantai 4"), { timeout: 2000 });
  fireEvent.click(screen.getByTestId("sheet-submit-next"));
  await waitFor(() => expect(props.onOptimisticSubmit).toHaveBeenCalledTimes(1));
  expect(props.onOptimisticSubmit.mock.calls[0][0]).toMatchObject({ location: "Lantai 4" });
  await waitFor(() => expect(mockToko.has(KUNCI)).toBe(false));
});

test("draf yang dipulihkan bisa langsung disimpan", async () => {
  mockToko.set(KUNCI, { key: KUNCI, userId: "u1", activityId: "k1", assetId: "a1", baseVersion: 7, updatedAt: Date.now(),
    formData: { ...asset, location: "Gudang" }, original: { ...asset, location: "" }, fotoBaru: [], fotoTetap: [0], fotoDiubah: false });
  const { props } = await buka();
  await waitFor(() => expect(document.querySelector('input[name="location"]').value).toBe("Gudang"));
  fireEvent.click(screen.getByTestId("sheet-submit-next"));
  await waitFor(() => expect(props.onOptimisticSubmit).toHaveBeenCalledTimes(1));
  expect(props.onOptimisticSubmit.mock.calls[0][0]).toMatchObject({ location: "Gudang" });
});

test("gerbang keluar terekspos ke induk (tombol Back HP)", async () => {
  const closeGuardRef = { current: null };
  const { props } = await buka({ closeGuardRef });
  const aksi = jest.fn();
  act(() => closeGuardRef.current(aksi));
  expect(aksi).toHaveBeenCalledTimes(1); // bersih → langsung
  ubahLokasi("X");
  act(() => closeGuardRef.current(aksi));
  expect(aksi).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("konfirmasi-keluar-form")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-buang"));
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-buang"));
  expect(aksi).toHaveBeenCalledTimes(2);
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
});
