import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssetForm from "../AssetForm";
import { emptyAssetForm } from "../../../lib/assetFormData";
jest.mock("axios", () => {
  const api = { interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } }, get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);
const axios = require("axios");
let online;
beforeEach(() => {
  jest.clearAllMocks(); online = Object.getOwnPropertyDescriptor(navigator, "onLine");
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  HTMLElement.prototype.scrollIntoView = () => {};
});
afterEach(() => { if (online) Object.defineProperty(navigator, "onLine", online); else delete navigator.onLine; });
test("lazy metadata tetap menunjuk STNK server0 setelah rekomendasi, payload menjaga ID/sentinel tanpa metadata UI", async () => {
  const asset = { ...emptyAssetForm("k1"), id: "a1", asset_code: "3020105004", asset_name: "Mobil", NUP: "1", version: 7,
    document_checklist: [{ id: "item-stnk", name: "STNK", checked: true, photos: [], documents: [], photo_count: 1 }] };
  axios.get.mockImplementation(async url => ({ data: String(url).includes("/checklist-full") ? { document_checklist: [{ id: "item-stnk", name: "STNK", checked: true, photo_count: 1, documents: [{ id: "doc-stnk", name: "STNK.pdf", idx: 0 }] }] } : String(url).includes("/assets/a1?") ? asset : { items: [] } }));
  const apply = jest.fn(); render(<AssetForm isOpen activity={{ id: "k1" }} editAsset={asset} categories={[]} onClose={jest.fn()} onOptimisticSubmit={apply} />);
  await waitFor(() => expect(screen.queryByTestId("form-loading-skeleton")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: "Dokumen" }));
  const image = await screen.findByRole("img", { name: "STNK foto 1" });
  expect(image).toHaveAttribute("src", expect.stringContaining("/checklist/0/photos/0?v=7"));
  const names = screen.getAllByRole("button", { name: /^Kelengkapan / }).map(button => button.getAttribute("aria-label"));
  expect(names.indexOf("Kelengkapan STNK")).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Lihat foto 1 STNK" }));
  expect(screen.getByRole("img", { name: "Preview" })).toHaveAttribute("src", expect.stringContaining("/checklist/0/photos/0?v=7"));
  fireEvent.click(screen.getByRole("button", { name: "Tutup pratinjau foto" }));
  fireEvent.click(screen.getByRole("button", { name: "Kelengkapan STNK" })); fireEvent.click(screen.getByTestId("asset-form-submit"));
  await waitFor(() => expect(apply).toHaveBeenCalledTimes(1));
  const item = apply.mock.calls[0][0].document_checklist.find(entry => entry.name === "STNK");
  expect(item).toEqual({ id: "item-stnk", name: "STNK", checked: false, notes: "", photos: ["__existing__:0"], documents: [{ id: "doc-stnk", name: "STNK.pdf", data: "__existing__:0" }] });
});
