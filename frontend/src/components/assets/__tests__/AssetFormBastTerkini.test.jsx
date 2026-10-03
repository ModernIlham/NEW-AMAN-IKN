import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AssetForm from "../AssetForm";
import { toast } from "sonner";

jest.mock("axios", () => {
  const api = { interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);
jest.mock("sonner", () => ({ toast: { info: jest.fn(), error: jest.fn(), success: jest.fn() } }));
const axios = require("axios");
const base = { id: "a1", activity_id: "k1", version: 4, asset_code: "301", asset_name: "Barang Uji", category: "Uji", pengguna_melekat_ke: "Individual" };
const terkelola = { ...base, amanah_bast: { bast_id: "revisi-sah", aksi: "serah" }, bast_terakhir: { id: "revisi-sah", nomor: "BAST-REVISI-002" } };
let asset;
beforeEach(() => {
  jest.clearAllMocks();
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
  asset = { ...terkelola };
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/a1?") ? asset : { items: [] } }));
  window.HTMLElement.prototype.scrollIntoView = () => {};
});
afterEach(() => { Object.defineProperty(navigator, "onLine", { configurable: true, value: true }); localStorage.clear(); });

async function buka() {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }} categories={[]} editAsset={asset} onSubmitSuccess={jest.fn()} />);
  await screen.findByTestId("asset-code-picker");
  await waitFor(() => expect(screen.queryByTestId("form-loading-skeleton")).toBeNull());
}

test.each([false, true])("BAST terapan bisa dibuka tanpa bergantung scan lama (ada scan=%s)", async scan => {
  if (scan) asset = { ...asset, bast_file_id: "scan-lama", bast_filename: "LAMA.pdf" };
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  localStorage.setItem("media_token", "media-uji"); localStorage.setItem("satker_aktif", "SATKER-UJI");
  try {
    await buka();
    const button = screen.getByTestId("bast-preview-btn");
    expect(button).toHaveTextContent("lihat dokumen terkini");
    expect(button).toHaveAttribute("title", expect.stringContaining("BAST-REVISI-002"));
    expect(screen.getByTestId("bast-upload-btn")).toBeDisabled();
    fireEvent.click(button);
    const [url, target, features] = open.mock.calls[0];
    const parsed = new URL(url, "https://example.test");
    expect(parsed.pathname).toMatch(/\/assets\/a1\/bast$/);
    expect(parsed.searchParams.get("v")).toMatch(/^\d+$/);
    expect(url).not.toContain("scan-lama");
    expect(parsed.searchParams.get("token")).toBe("media-uji"); expect(parsed.searchParams.get("sa")).toBe("SATKER-UJI");
    expect(target).toBe("_blank"); expect(features).toBe("noopener,noreferrer");
    expect(axios.post).not.toHaveBeenCalled();
    if (process.env.AMAN_QA_FORM_DIR) {
      const fs = require("fs"), path = require("path");
      fs.mkdirSync(process.env.AMAN_QA_FORM_DIR, { recursive: true });
      fs.writeFileSync(path.join(process.env.AMAN_QA_FORM_DIR, "bast-terkini.html"), document.body.innerHTML);
    }
  } finally { open.mockRestore(); }
});

test("unggahan manual lama tetap tersedia dan nonce diperbarui pada setiap klik", async () => {
  asset = { ...base, bast_file_id: "scan-manual", bast_filename: "arsip.pdf" };
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  const now = jest.spyOn(Date, "now");
  try {
    await buka();
    expect(screen.getByTestId("bast-upload-btn")).not.toBeDisabled();
    now.mockReturnValue(1000); fireEvent.click(screen.getByTestId("bast-preview-btn"));
    now.mockReturnValue(2000); fireEvent.click(screen.getByTestId("bast-preview-btn"));
    expect(open.mock.calls[0][0]).toContain("?v=1000");
    expect(open.mock.calls[1][0]).toContain("?v=2000");
  } finally { now.mockRestore(); open.mockRestore(); }
});

test("form luring mempertahankan referensi tanpa membuka cache dokumen lama", async () => {
  Object.defineProperty(navigator, "onLine", { configurable: true, value: false });
  const open = jest.spyOn(window, "open").mockImplementation(() => null);
  try {
    await buka();
    fireEvent.click(screen.getByTestId("bast-preview-btn"));
    expect(open).not.toHaveBeenCalled();
    expect(toast.info).toHaveBeenCalledWith(expect.stringContaining("Hubungkan internet"));
    expect(axios.get.mock.calls.some(([url]) => String(url).includes("/assets/a1?"))).toBe(false);
  } finally { open.mockRestore(); }
});
