import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AssetForm from "../AssetForm";

jest.mock("axios", () => {
  const api = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn(),
  };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);
jest.mock("../../ui/calendar", () => ({
  Calendar: ({ onSelect }) => <button type="button" onClick={() => onSelect(new Date(2026, 8, 21))}>Pilih tanggal uji</button>,
}));

const axios = require("axios");
const aset = { id: "a1", activity_id: "k1", version: 1, asset_code: "3050105007",
  asset_name: "Laptop", category: "Komputer", NUP: "1", pengguna_melekat_ke: "Individual",
  purchase_date: "2026-08-19", purchase_price: "26484600" };

beforeAll(() => { window.HTMLElement.prototype.scrollIntoView = () => {}; });
beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/a1?") ? aset : { items: [] } }));
});

async function buka(edit) {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }}
    categories={[]} editAsset={edit ? aset : null} onSubmitSuccess={jest.fn()} />);
  await screen.findByTestId("asset-code-picker");
  await waitFor(() => expect(screen.queryByTestId("form-loading-skeleton")).toBeNull());
}

test.each([false, true])("kontrol sejajar input tanpa mengecilkan tombol simpan (edit=%s)", async edit => {
  await buka(edit);
  const ids = ["asset-code-picker", "asset-purchase-date", "asset-garansi", "pengguna-pegawai-picker", "pengguna-tap-kartu"];
  if (edit) ids.push("bast-upload-btn");
  for (const id of ids) {
    expect(screen.getByTestId(id)).toHaveClass("h-8", "min-h-0", "min-w-0");
    expect(screen.getByTestId(id)).toHaveAttribute("type", "button");
  }
  expect(screen.getByTestId("asset-form-submit")).not.toHaveClass("min-h-0");
  if (!edit) expect(screen.queryByTestId("bast-upload-btn")).toBeNull();
  // Opsional untuk QA layout Chromium memakai DOM React + CSS produksi asli.
  if (process.env.AMAN_QA_FORM_DIR) {
    const fs = require("fs");
    const path = require("path");
    fs.mkdirSync(process.env.AMAN_QA_FORM_DIR, { recursive: true });
    fs.writeFileSync(path.join(process.env.AMAN_QA_FORM_DIR, edit ? "edit.html" : "tambah.html"), document.body.innerHTML);
  }
});

test("pemicu pencarian kode dan pegawai tetap membuka pilihan", async () => {
  await buka(false);
  await userEvent.click(screen.getByTestId("asset-code-picker"));
  expect(await screen.findByTestId("asset-code-picker-search")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(screen.getByTestId("pengguna-pegawai-picker"));
  expect(await screen.findByTestId("pengguna-pegawai-search")).toBeInTheDocument();
  expect(axios.post).not.toHaveBeenCalled();
});

test("tanggal tetap bisa diubah dan unggah BAST membuka input file", async () => {
  await buka(true);
  expect(screen.getByTestId("asset-purchase-date")).toHaveTextContent("19/08/2026");
  await userEvent.click(screen.getByTestId("asset-purchase-date"));
  await userEvent.click(await screen.findByText("Pilih tanggal uji"));
  expect(screen.getByTestId("asset-purchase-date")).toHaveTextContent("21/09/2026");
  await userEvent.click(screen.getByTestId("asset-garansi"));
  await userEvent.click(await screen.findByText("Pilih tanggal uji"));
  expect(screen.getByTestId("asset-garansi")).toHaveTextContent("21/09/2026");
  const click = jest.spyOn(screen.getByTestId("bast-file-input"), "click");
  await userEvent.click(screen.getByTestId("bast-upload-btn"));
  expect(click).toHaveBeenCalledTimes(1);
  click.mockRestore();
});
