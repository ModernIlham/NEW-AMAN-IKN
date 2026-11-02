import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AssetForm from "../AssetForm";
import { emptyAssetForm } from "../../../lib/assetFormData";
import { ASSET_FIELD_REGISTRY } from "../../../lib/assetFields";

jest.mock("axios", () => {
  const instance = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn(),
  };
  return { ...instance, create: jest.fn(() => instance), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);

const axios = require("axios");
let onlineDescriptor;

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: { items: [] } });
  onlineDescriptor = Object.getOwnPropertyDescriptor(window.navigator, "onLine");
  Object.defineProperty(window.navigator, "onLine", { configurable: true, value: false });
});

afterEach(() => {
  if (onlineDescriptor) Object.defineProperty(window.navigator, "onLine", onlineDescriptor);
  else delete window.navigator.onLine;
});

function props(value = "") {
  return {
    isOpen: true, onClose: jest.fn(), activity: { id: "k1" }, categories: [],
    onOptimisticSubmit: jest.fn(),
    editAsset: { ...emptyAssetForm("k1"), id: "a1", version: 4,
      asset_code: "301", asset_name: "Benda sejarah", NUP: "1",
      barang_bersejarah: value, photo_count: 3 },
  };
}

test.each([["", "Ya"], ["Ya", ""]])(
  "registered checkbox maps %p to explicit partial patch %p without touching unloaded media",
  async (before, after) => {
    const initial = props(before);
    render(<AssetForm {...initial} />);
    const checkbox = await screen.findByTestId("asset-barang-bersejarah");
    expect(checkbox.closest("label")).toHaveTextContent(ASSET_FIELD_REGISTRY.barang_bersejarah.label);
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByTestId("asset-form-submit"));
    await waitFor(() => expect(initial.onOptimisticSubmit).toHaveBeenCalledTimes(1));
    expect(initial.onOptimisticSubmit).toHaveBeenCalledWith(
      { barang_bersejarah: after }, true, "a1", true,
    );
  },
);

test("tambah aset menyediakan jenis dokumen tanpa menebak nilai bawaan", async () => {
  render(<AssetForm {...props()} editAsset={null} />);
  await screen.findByTestId("asset-barang-bersejarah");
  fireEvent.click(screen.getByRole("button", { name: "Pengadaan" }));
  expect(screen.getByLabelText("Jenis Dokumen Pengadaan")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Jenis Dokumen Pengadaan"), { target: { value: "Non Kontrak BLU" } });
  expect(screen.getByLabelText("Nomor Kontrak")).toBeDisabled();
  expect(screen.getByTestId("asset-bukti-perolehan")).not.toBeDisabled();
});

test.each(["Non Kontrak/Penerimaan Barang", "Non Kontrak BLU"])("jenis %s tersimpan sebagai PATCH luring, bukti perolehan tetap aktif", async jenis => {
  const initial = props();
  initial.editAsset.nomor_kontrak = "K-1";
  initial.editAsset.cara_bayar_kontrak = "Sekaligus";
  render(<AssetForm {...initial} />);
  await screen.findByTestId("asset-barang-bersejarah");
  fireEvent.click(screen.getByRole("button", { name: "Pengadaan" }));
  fireEvent.change(screen.getByLabelText("Jenis Dokumen Pengadaan"), { target: { value: jenis } });
  expect(screen.getByLabelText("Nomor Kontrak")).toBeDisabled();
  expect(screen.getByLabelText("Cara Bayar Kontrak")).toBeDisabled();
  expect(screen.getByTestId("asset-bukti-perolehan")).not.toBeDisabled();
  fireEvent.change(screen.getByTestId("asset-bukti-perolehan"), { target: { value: "KW-1" } });
  fireEvent.click(screen.getByTestId("asset-form-submit"));
  await waitFor(() => expect(initial.onOptimisticSubmit).toHaveBeenCalledWith(
    { jenis_dokumen_pengadaan: jenis, nomor_bukti_perolehan: "KW-1" }, true, "a1", true,
  ));
});

test("resize and panel hide keep input identity/focus; tabs and reopening keep the draft", async () => {
  const initial = props();
  const view = render(<AssetForm {...initial} />);
  await screen.findByTestId("asset-barang-bersejarah");
  const name = document.querySelector('input[name="asset_name"]');
  fireEvent.change(name, { target: { value: "Draft belum disimpan" } });
  name.focus();
  act(() => window.dispatchEvent(new Event("resize")));
  expect(document.querySelector('input[name="asset_name"]')).toBe(name);
  expect(name).toHaveFocus();
  view.rerender(<AssetForm {...initial} isOpen={false} />);
  expect(name).toHaveFocus();
  view.rerender(<AssetForm {...initial} isOpen />);
  expect(document.querySelector('input[name="asset_name"]')).toBe(name);
  expect(name).toHaveValue("Draft belum disimpan");
  fireEvent.click(screen.getByRole("button", { name: "Pengadaan" }));
  fireEvent.click(screen.getByRole("button", { name: "Info Dasar" }));
  expect(document.querySelector('input[name="asset_name"]')).toHaveValue("Draft belum disimpan");
  fireEvent.click(screen.getByTestId("asset-form-submit"));
  await waitFor(() => expect(initial.onOptimisticSubmit).toHaveBeenCalledWith(
    { asset_name: "Draft belum disimpan" }, true, "a1", true,
  ));
});
