import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import AssetForm from "../AssetForm";
import axios from "axios";

// Kepala form edit harus RINGKAS di semua mode: identitas aset satu blok di
// kepala (tanpa kepala identitas kedua di mode inventarisasi cepat), dan
// semua pemberitahuan (draf, luring, SIMAN) dilipat jadi satu baris status.
jest.mock("axios", () => {
  const api = { get: jest.fn(), post: jest.fn(), patch: jest.fn(), interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } } };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => function Camera() { return null; });

const asset = { id: "a1", asset_code: "3050204016", asset_name: "AC Presisi", NUP: "3", version: 2, activity_id: "k1",
  photo_count: 1, inventory_status: "Belum Diinventarisasi",
  siman: { status: "selisih", selisih: [
    { field: "brand", label: "Merk", aman: "", siman: "Gree Air" },
    { field: "model", label: "Tipe", aman: "", siman: "Cooled Close Control" },
  ] } };
beforeAll(() => { HTMLElement.prototype.scrollIntoView = () => {}; });
beforeEach(() => {
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/") ? asset : { items: [] } }));
});

async function buka(props) {
  render(<AssetForm isOpen editAsset={asset} activity={{ id: "k1" }} categories={[]} onClose={() => {}}
    onOptimisticSubmit={() => {}} assetIndex={4} totalAssetsInView={20} {...props} />);
  await screen.findByTestId("strip-status-form");
}

test.each([["inventarisasi cepat", true], ["form lengkap", false]])("kepala ringkas pada %s", async (_, inventoryMode) => {
  await buka({ inventoryMode });
  const kepala = screen.getByTestId("asset-form-header");
  expect(within(kepala).getByText("3050204016")).toBeInTheDocument();
  expect(within(kepala).getByText("NUP 3")).toBeInTheDocument();
  expect(within(kepala).getByTestId("asset-form-header-nama")).toHaveTextContent("AC Presisi");
  // Kode aset hanya muncul sekali — tak ada kepala identitas kedua.
  expect(screen.getAllByText("3050204016")).toHaveLength(1);
  if (inventoryMode) expect(within(kepala).getByText("5/20")).toBeInTheDocument();
});

test("selisih SIMAN dilipat jadi pil; rincian dibuka satu ketuk", async () => {
  await buka({ inventoryMode: true });
  expect(screen.getByTestId("siman-form-banner")).toHaveTextContent("≠ SIMAN 2");
  expect(screen.queryByText(/Gree Air/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("strip-status-toggle"));
  expect(screen.getByTestId("strip-status-rinci")).toHaveTextContent("Gree Air");
  fireEvent.click(screen.getByTestId("strip-status-toggle"));
  expect(screen.queryByTestId("strip-status-rinci")).not.toBeInTheDocument();
});

test("tanpa pemberitahuan, baris status tidak dirender sama sekali", async () => {
  const bersih = { ...asset, siman: null };
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/") ? bersih : { items: [] } }));
  render(<AssetForm isOpen editAsset={bersih} activity={{ id: "k1" }} categories={[]} onClose={() => {}} onOptimisticSubmit={() => {}} inventoryMode />);
  await screen.findByTestId("sheet-photo-thumb-0");
  expect(screen.queryByTestId("strip-status-form")).not.toBeInTheDocument();
});
