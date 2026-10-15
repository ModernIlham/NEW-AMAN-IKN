import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import BatchEditPanel from "../BatchEditPanel";
import BatchOperationStatus from "../BatchOperationStatus";
jest.mock("axios");
beforeEach(() => axios.get.mockResolvedValue({ data: { items: [] } }));
const selected = new Set(["a"]);
test("draf memakai versi saat dibuka, preflight mendahului konfirmasi, klik ganda hanya satu operasi", async () => {
  let resolve;
  const prepare = jest.fn(() => new Promise(r => { resolve = r; }));
  const apply = jest.fn();
  const props = { selectedCount: 1, categories: [], onPrepare: prepare, onApply: apply,
    selectedAssets: selected, assets: [{ id: "a", version: 4 }] };
  const { rerender } = render(<BatchEditPanel {...props} />);
  await userEvent.type(screen.getAllByRole("textbox")[0], "Gudang A");
  rerender(<BatchEditPanel {...props} assets={[{ id: "a", version: 8 }]} />);
  await act(async () => {
    fireEvent.click(screen.getByTestId("batch-apply-btn"));
    fireEvent.click(screen.getByTestId("batch-apply-btn"));
  });
  expect(prepare).toHaveBeenCalledTimes(1);
  expect(prepare).toHaveBeenCalledWith({ location: "Gudang A" }, ["a"], { a: 4 });
  expect(apply).not.toHaveBeenCalled();
  await act(async () => { resolve({ metadata: { total: 1 } }); });
  expect(screen.getByTestId("confirm-dialog")).toHaveTextContent("telah diperiksa sebelum konfirmasi");
  expect(apply).not.toHaveBeenCalled();
  await act(async () => { await userEvent.click(screen.getByTestId("confirm-dialog-confirm")); });
  expect(apply).toHaveBeenCalledTimes(1);
  expect(apply).toHaveBeenCalledWith({ location: "Gudang A" }, ["a"], { metadata: { total: 1 } });
});

test("hasil parsial memisahkan berhasil, konflik, gagal, menunggu dan daftar yang perlu tindakan", async () => {
  const resume = jest.fn();
  render(<BatchOperationStatus onResume={resume} onRefresh={jest.fn()} operation={{ total: 4,
    activityId: "kegiatan-a", children: [{ prepared: true, asset_ids: ["a", "b", "c", "d"], response: {
      applied: 1, unchanged: 0, conflicts: 1, failed: 1, pending: 1,
      results: [{ id: "a", status: "applied" }, { id: "b", status: "conflict" }, { id: "c", status: "failed" }, { id: "d", status: "pending" }],
    } }] }} />);
  expect(screen.getByRole("status")).toHaveTextContent("Berhasil 1 · Sudah sesuai 0 · Konflik 1 · Tidak ditemukan 0 · Gagal 1 · Menunggu 1");
  await userEvent.click(screen.getByRole("button", { name: "Rincian 3 aset" }));
  expect(screen.getByRole("list", { name: "Aset yang perlu tindakan" }).children).toHaveLength(3);
  await userEvent.click(screen.getByRole("button", { name: "Lanjutkan yang menunggu" }));
  expect(resume).toHaveBeenCalledTimes(1);
});
