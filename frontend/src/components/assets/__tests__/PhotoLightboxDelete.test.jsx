import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import Lightbox from "../PhotoLightbox";
import { toast } from "sonner";

jest.mock("axios", () => ({ get: jest.fn(), patch: jest.fn(), post: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../../hooks/useBackGuard", () => ({ useBackGuard: jest.fn() }));
const asset = { id: "a1", asset_name: "Barang uji", photo_count: 3, version: 5, thumbnail_index: 2, stiker_photo_index: 1 };
const updated = { ...asset, photo_count: 2, version: 6, thumbnail_index: 1, stiker_photo_index: null };
beforeEach(() => {
  jest.clearAllMocks(); localStorage.removeItem("satker_aktif");
  axios.get.mockResolvedValue({ data: asset });
  axios.patch.mockResolvedValue({ data: updated });
});
async function open(props = {}) {
  const onClose = jest.fn(), onAssetUpdated = jest.fn();
  const view = render(<Lightbox asset={asset} onClose={onClose} onEdit={jest.fn()} onAssetUpdated={onAssetUpdated} {...props} />);
  await waitFor(() => expect(screen.getByTestId("lightbox-delete")).not.toBeDisabled());
  return { ...view, onClose, onAssetUpdated };
}

test("minta konfirmasi, batal/escape tidak menghapus atau menutup penampil", async () => {
  const { onClose } = await open();
  fireEvent.click(screen.getByTestId("lightbox-delete"));
  expect(screen.getByRole("alertdialog")).toHaveTextContent("Hapus foto ini?");
  fireEvent.click(screen.getByRole("button", { name: "Batal" }));
  expect(axios.patch).not.toHaveBeenCalled(); expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("lightbox-delete"));
  fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
  expect(onClose).not.toHaveBeenCalled(); expect(axios.patch).not.toHaveBeenCalled();
});

test("hapus foto tengah memakai versi dan keep yang tepat, klik ganda tidak mengirim dua kali", async () => {
  let finish;
  axios.patch.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const { onAssetUpdated } = await open();
  fireEvent.keyDown(window, { key: "ArrowRight" });
  fireEvent.click(screen.getByTestId("lightbox-delete"));
  const confirm = screen.getByTestId("photo-delete-confirm");
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(axios.patch).toHaveBeenCalledTimes(1);
  expect(axios.patch).toHaveBeenCalledWith(expect.stringContaining("/assets/a1"), {
    photo_ops: { keep: [0, 2], add: [], thumbnail_index: 1, base_version: 5 }, stiker_photo_index: null,
  }, { headers: { "If-Match": "5", "Idempotency-Key": expect.any(String), "X-Satker-Aktif": "" } });
  await act(async () => finish({ data: updated }));
  expect(onAssetUpdated).toHaveBeenCalledWith(updated);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(screen.getByAltText("Barang uji")).toHaveAttribute("src", expect.stringContaining("/photos/1?v=6&w=1280"));
});

test("konflik versi tidak menghapus ulang secara otomatis atau menampilkan sukses", async () => {
  axios.patch.mockRejectedValue({ response: { status: 409 } });
  await open(); fireEvent.click(screen.getByTestId("lightbox-delete")); fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  await waitFor(() => expect(toast.error).toHaveBeenCalled());
  expect(axios.patch).toHaveBeenCalledTimes(1); expect(toast.success).not.toHaveBeenCalled();
  expect(screen.getByTestId("lightbox-delete")).toBeDisabled();
});

test("perubahan satker sesudah konfirmasi dibuka tidak mengirim penghapusan", async () => {
  await open(); fireEvent.click(screen.getByTestId("lightbox-delete"));
  localStorage.setItem("satker_aktif", "lain");
  fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  expect(axios.patch).not.toHaveBeenCalled();
});

test("pengguna baca saja tidak diberi tombol hapus", async () => {
  render(<Lightbox asset={asset} onClose={jest.fn()} />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  expect(screen.queryByTestId("lightbox-delete")).not.toBeInTheDocument();
});

test("hapus foto terakhir membersihkan penampil tanpa memakai sampul lama", async () => {
  const one = { ...asset, photo_count: 1 };
  axios.get.mockResolvedValue({ data: one });
  axios.patch.mockResolvedValue({ data: { ...one, photo_count: 0, version: 6, thumbnail: null } });
  await open({ asset: one });
  fireEvent.click(screen.getByTestId("lightbox-delete")); fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  await waitFor(() => expect(toast.success).toHaveBeenCalled());
  expect(screen.queryByTestId("lightbox-delete")).not.toBeInTheDocument();
  expect(screen.queryByAltText("Barang uji")).not.toBeInTheDocument();
});

test("gangguan koneksi mempertahankan konfirmasi dan kunci idempoten saat dicoba lagi", async () => {
  axios.patch.mockRejectedValueOnce(new Error("network")).mockResolvedValueOnce({ data: updated });
  await open(); fireEvent.click(screen.getByTestId("lightbox-delete")); fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  await waitFor(() => expect(toast.error).toHaveBeenCalled());
  expect(screen.getByRole("alertdialog")).toBeInTheDocument(); expect(toast.success).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("photo-delete-confirm"));
  await waitFor(() => expect(toast.success).toHaveBeenCalled());
  expect(axios.patch.mock.calls[0]).toEqual(axios.patch.mock.calls[1]);
});

test("satker berubah sebelum dialog diminta tidak memakai metadata satker sebelumnya", async () => {
  await open(); localStorage.setItem("satker_aktif", "lain");
  fireEvent.click(screen.getByTestId("lightbox-delete"));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(); expect(axios.patch).not.toHaveBeenCalled();
});

test("layar penuh menyediakan hapus dengan konfirmasi dan kembali ke penampil", async () => {
  await open(); fireEvent.click(screen.getByTestId("lightbox-fullscreen"));
  expect(screen.getByTestId("lightbox-fullscreen-view")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("lightbox-fullscreen-delete"));
  expect(screen.queryByTestId("lightbox-fullscreen-view")).not.toBeInTheDocument();
  expect(screen.getByRole("alertdialog")).toBeInTheDocument(); expect(axios.patch).not.toHaveBeenCalled();
});
