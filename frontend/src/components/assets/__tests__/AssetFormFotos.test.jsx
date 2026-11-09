import "../../../uji/indexedDB";
import { deleteDB } from "idb";
import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import AssetForm from "../AssetForm";
import axios from "axios";

jest.mock("axios", () => {
  const api = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } } };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => function Camera({ photos, thumbnails, onClose }) {
  return <div><img alt="Sumber kamera" src={photos[0]} /><img alt="Thumbnail kamera" src={thumbnails[0]} /><button onClick={onClose}>Selesai kamera</button></div>;
});
const asset = { id: "a1", asset_code: "3050105007", asset_name: "Laptop uji", category: "Komputer", NUP: "1", version: 7,
  activity_id: "k1", photo_count: 3, thumbnail_index: 2, stiker_photo_index: 1, inventory_status: "Belum Diinventarisasi" };
beforeAll(() => { HTMLElement.prototype.scrollIntoView = () => {}; });
beforeEach(async () => {
  await deleteDB("aman_draf_aset");
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: jest.fn() } });
  jest.clearAllMocks(); localStorage.setItem("aman_auto_inventarisasi", "off");
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/") ? asset : { items: [] } }));
  Object.defineProperty(window, "BarcodeDetector", { configurable: true, value: function Detector() {} });
});
afterEach(() => { delete window.BarcodeDetector; localStorage.removeItem("aman_auto_inventarisasi"); });
async function open() {
  const props = { isOpen: true, inventoryMode: true, editAsset: asset, activity: { id: "k1" }, categories: [],
    onClose: jest.fn(), onOptimisticSubmit: jest.fn() };
  const view = render(<AssetForm {...props} />);
  await screen.findByTestId("sheet-photo-thumb-2");
  return { ...view, props };
}

test("thumbnail membuka foto penuh dan penghapusan baru dikirim saat simpan", async () => {
  const { props } = await open();
  fireEvent.click(screen.getByRole("button", { name: "Lihat foto 2" }));
  const viewer = screen.getByTestId("lightbox-fullscreen-view");
  expect(within(viewer).getByRole("img")).toHaveAttribute("src", expect.stringContaining("/assets/a1/photos/1?v=7"));
  expect(within(viewer).getByRole("img").getAttribute("src")).not.toContain("thumb=");
  fireEvent.click(screen.getByTestId("photo-preview-delete"));
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Batal" }));
  expect(screen.getByTestId("sheet-photo-thumb-2")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("photo-preview-delete"));
  fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("lightbox-fullscreen-close"));
  expect(screen.queryByTestId("sheet-photo-thumb-2")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("sheet-submit-next"));
  await waitFor(() => expect(props.onOptimisticSubmit).toHaveBeenCalledTimes(1));
  expect(props.onOptimisticSubmit.mock.calls[0][0]).toMatchObject({
    photo_ops: { keep: [0, 2], add: [], thumbnail_index: 1, base_version: 7 }, stiker_photo_index: null,
  });
  expect(axios.patch).not.toHaveBeenCalled();
});

test("silang foto membutuhkan konfirmasi; empat pemicu ada di deretan foto", async () => {
  await open();
  const strip = screen.getByTestId("sheet-photo-strip");
  for (const id of ["sheet-camera-btn", "sheet-gallery-btn", "sheet-full-camera-btn", "sheet-full-camera-scan-btn"]) {
    expect(within(strip).getByTestId(id)).toHaveClass("w-14", "h-14");
  }
  fireEvent.click(screen.getByTestId("sheet-photo-remove-0"));
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Batal" }));
  expect(screen.getByTestId("sheet-photo-thumb-2")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("sheet-full-camera-btn"));
  expect(screen.getByAltText("Sumber kamera").getAttribute("src")).not.toContain("thumb=");
  expect(screen.getByAltText("Thumbnail kamera").getAttribute("src")).toContain("thumb=1");
});

test("konfirmasi draf tidak ikut berpindah ke aset lain", async () => {
  const { props, rerender } = await open();
  fireEvent.click(screen.getByTestId("sheet-photo-remove-1"));
  rerender(<AssetForm {...props} editAsset={{ ...asset, id: "b1" }} />);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
});

test("Tutup berada di kanan Simpan dan menutup tanpa mengirim draf", async () => {
  const { props } = await open();
  const close = screen.getByTestId("sheet-close");
  expect(close).toHaveAttribute("type", "button");
  expect(close.previousElementSibling).toBe(screen.getByTestId("sheet-submit-next"));
  fireEvent.change(document.querySelector('input[name="location"]'), { target: { value: "Draf lokasi" } });
  fireEvent.click(close);
  // Ada perubahan → dialog dulu; keluar menyimpan draf di perangkat, bukan mengirim.
  expect(props.onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("konfirmasi-keluar-draf"));
  await waitFor(() => expect(props.onClose).toHaveBeenCalledTimes(1));
  expect(props.onOptimisticSubmit).not.toHaveBeenCalled();
  expect(axios.patch).not.toHaveBeenCalled();
});
