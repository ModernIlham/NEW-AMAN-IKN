import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AssetForm from "../AssetForm";
import InventoryFieldSheet from "../InventoryFieldSheet";
import BatchEditPanel from "../BatchEditPanel";

jest.mock("axios", () => {
  const api = { interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn() };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);
const axios = require("axios");
const lama = { id: "a1", version: 2, asset_name: "Kursi", asset_code: "3050105007", NUP: "1",
  category: "Perabot", pengguna_melekat_ke: "Operasional", operasional_jenis: "Kegiatan/Acara/Kebutuhan" };

beforeEach(() => {
  jest.clearAllMocks();
  window.HTMLElement.prototype.scrollIntoView = () => {};
  axios.get.mockImplementation(url => Promise.resolve({ data: String(url).includes("/assets/a1?") ? lama : { items: [] } }));
});

test.each([true, false])("aset lama tetap terpilih di form (online=%s) tanpa tulis otomatis", async online => {
  const prop = Object.getOwnPropertyDescriptor(window.navigator, "onLine");
  Object.defineProperty(window.navigator, "onLine", { configurable: true, value: online });
  try {
    render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }} categories={[]}
      editAsset={lama} onSubmitSuccess={jest.fn()} />);
    const opsi = await screen.findByRole("button", { name: "Unit/Tempat/Tugas" });
    expect(opsi).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: "Kegiatan/Acara/Kebutuhan" })).toBeNull();
    expect(axios.patch).not.toHaveBeenCalled();
    expect(axios.put).not.toHaveBeenCalled();
    if (online && process.env.AMAN_QA_JENIS_DIR) {
      const fs = require("fs"), path = require("path");
      fs.mkdirSync(process.env.AMAN_QA_JENIS_DIR, { recursive: true });
      fs.writeFileSync(path.join(process.env.AMAN_QA_JENIS_DIR, "form.html"), document.body.innerHTML);
    }
    await userEvent.click(opsi);
    expect(opsi).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(screen.getByRole("button", { name: "Ruangan" }));
    expect(screen.getByRole("button", { name: "Ruangan" })).toHaveAttribute("aria-pressed", "true");
  } finally {
    if (prop) Object.defineProperty(window.navigator, "onLine", prop);
    else delete window.navigator.onLine;
  }
});

test("form tambah menawarkan jenis baru", async () => {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }} categories={[]}
    editAsset={null} onSubmitSuccess={jest.fn()} />);
  await userEvent.click(await screen.findByRole("button", { name: "Operasional", exact: true }));
  await userEvent.click(screen.getByRole("button", { name: "Unit/Tempat/Tugas" }));
  expect(screen.getByRole("button", { name: "Unit/Tempat/Tugas" })).toHaveAttribute("aria-pressed", "true");
});

test("lembar cepat menerima alias lama dan mengirim nilai baru", async () => {
  const onChange = jest.fn();
  render(<InventoryFieldSheet formData={lama} photoItems={[]} photoCount={0}
    onInputChange={jest.fn()} onOperasionalJenisChange={onChange} />);
  const opsi = screen.getByTestId("sheet-operasional-Unit/Tempat/Tugas");
  expect(opsi).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(opsi);
  expect(onChange).toHaveBeenCalledWith("Unit/Tempat/Tugas");
});

test("ubah massal mengirim jenis baru lewat jalur simpan yang sama", async () => {
  const onApply = jest.fn();
  render(<BatchEditPanel selectedCount={1} categories={[]} onApply={onApply}
    onClose={jest.fn()} updating={false} activity={{ id: "k1" }} assets={[]}
    selectedAssets={new Set(["a1"])} />);
  await userEvent.click(screen.getByTestId("batch-toggle-more"));
  await userEvent.click(await screen.findByRole("button", { name: "Operasional", exact: true }));
  await userEvent.click(screen.getByRole("button", { name: "Unit/Tempat/Tugas" }));
  await userEvent.click(screen.getByRole("button", { name: /Terapkan/i }));
  expect(onApply).toHaveBeenCalled();
  expect(onApply.mock.calls[0][0]).toMatchObject({ pengguna_melekat_ke: "Operasional", operasional_jenis: "Unit/Tempat/Tugas" });
});

test("kamera menampilkan alias lama dengan referensi baru dan pilihan tetap terpilih", async () => {
  const context = jest.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({});
  try {
    const Camera = jest.requireActual("../FullCameraSheet").default;
    const onSetField = jest.fn();
    render(<Camera formData={lama} isEditing onScanAsset={jest.fn()}
      onSetField={onSetField} onClose={jest.fn()} />);
    expect(await screen.findByText(/Operasional — Unit\/Tempat\/Tugas/)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("full-camera-edit-btn"));
    const opsi = screen.getByTestId("cam-opjenis-Unit/Tempat/Tugas");
    expect(opsi).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(opsi);
    expect(onSetField).toHaveBeenCalledWith("operasional_jenis", "Unit/Tempat/Tugas");
  } finally {
    context.mockRestore();
  }
});
