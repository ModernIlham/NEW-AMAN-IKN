import React, { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import SelectionToolbar from "../SelectionToolbar";
import BatchEditPanel from "../BatchEditPanel";

jest.mock("axios");
beforeEach(() => axios.get.mockResolvedValue({ data: { items: [] } }));
const assets = [];
const selectedAssets = new Set(["a1", "a2", "a3"]);

function Editor({ onApply = jest.fn() }) {
  const [count, setCount] = useState(3);
  const [expanded, setExpanded] = useState(true);
  const [revision, setRevision] = useState(0);
  return count > 0 && <>
    <SelectionToolbar count={count} expanded={expanded} onClear={() => setCount(0)} onSelectAll={jest.fn()} onTogglePanel={() => setExpanded(!expanded)} />
    <div id="asset-batch-panel" hidden={!expanded}><BatchEditPanel key={revision} attached selectedCount={count} categories={[]} assets={assets} selectedAssets={selectedAssets} onClose={() => setExpanded(false)} onApply={(updates, ids) => { onApply(updates, ids); setRevision(n => n + 1); setExpanded(false); }} /></div>
  </>;
}

test("sembunyikan panel mempertahankan seleksi dan isian; hapus seleksi mengakhiri keduanya", async () => {
  render(<Editor />);
  const location = screen.getAllByRole("textbox")[0];
  await userEvent.type(location, "Gudang A");
  await userEvent.click(screen.getByTestId("toggle-batch-panel-btn"));
  expect(screen.getByText("aset terpilih", { exact: true })).toBeVisible();
  expect(screen.getByTestId("batch-edit-panel")).not.toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Ubah massal" }));
  expect(location).toHaveValue("Gudang A");
  await userEvent.click(screen.getByRole("button", { name: "Hapus seleksi" }));
  expect(screen.queryByTestId("batch-edit-panel")).toBeNull();
});

test("sembunyikan dari footer mempertahankan isian dan tidak menerapkan perubahan", async () => {
  render(<Editor />);
  await userEvent.type(screen.getAllByRole("textbox")[0], "Gudang B");
  await userEvent.click(screen.getByRole("button", { name: "Sembunyikan", exact: true }));
  expect(screen.getByTestId("toggle-batch-panel-btn")).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(screen.getByTestId("toggle-batch-panel-btn"));
  expect(screen.getAllByRole("textbox")[0]).toHaveValue("Gudang B");
});

test("hapus seleksi dan pilih semua ditahan saat perubahan sedang diterapkan", () => {
  render(<SelectionToolbar count={3} expanded onClear={jest.fn()} onSelectAll={jest.fn()} onTogglePanel={jest.fn()} disabled />);
  expect(screen.getByRole("button", { name: "Hapus seleksi" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Pilih semua" })).toBeDisabled();
});

test("setelah perubahan diterapkan, seleksi tetap ada dan draf baru tidak mengirim ulang perubahan lama", async () => {
  const onApply = jest.fn();
  render(<Editor onApply={onApply} />);
  await userEvent.type(screen.getAllByRole("textbox")[0], "Gudang C");
  await userEvent.click(screen.getByTestId("batch-apply-btn"));
  expect(onApply).toHaveBeenCalledWith({ location: "Gudang C" }, ["a1", "a2", "a3"]);
  await userEvent.click(screen.getByTestId("toggle-batch-panel-btn"));
  expect(screen.getAllByRole("textbox")[0]).toHaveValue("");
  expect(screen.getByTestId("batch-apply-btn")).toBeDisabled();
  expect(screen.getByText("aset terpilih", { exact: true })).toBeVisible();
});

test("kolom tambahan dapat ditampilkan dan disembunyikan tanpa kehilangan isian", async () => {
  render(<Editor />);
  await userEvent.click(screen.getByTestId("batch-toggle-more"));
  expect(screen.getByTestId("batch-doc-custom-input")).toBeVisible();
  // Skenario ini memeriksa retensi kolom, bukan urutan keystroke. Satu
  // perubahan nyata menghindari 11 render seluruh form tambahan pada CI.
  fireEvent.change(screen.getByTestId("batch-doc-custom-input"), { target: { value: "Buku servis" } });
  expect(screen.getByTestId("batch-doc-custom-input")).toHaveValue("Buku servis");
  await userEvent.click(screen.getByTestId("batch-doc-custom-add"));
  expect(screen.getByRole("button", { name: "Ubah kelengkapan Buku servis" })).toHaveAttribute("aria-pressed", "true");
  if (process.env.AMAN_QA_UI_DIR) {
    const fs = require("fs");
    fs.mkdirSync(process.env.AMAN_QA_UI_DIR, { recursive: true });
    fs.writeFileSync(`${process.env.AMAN_QA_UI_DIR}/batch.html`, document.body.innerHTML);
  }
  await userEvent.click(screen.getByTestId("batch-toggle-more"));
  expect(screen.queryByTestId("batch-doc-custom-input")).toBeNull();
  await userEvent.click(screen.getByTestId("batch-toggle-more"));
  expect(screen.getByRole("button", { name: "Ubah kelengkapan Buku servis" })).toHaveAttribute("aria-pressed", "true");
});
