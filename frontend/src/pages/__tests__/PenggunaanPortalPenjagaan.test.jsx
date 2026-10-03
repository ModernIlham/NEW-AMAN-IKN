import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import PenggunaanPage from "../PenggunaanPage";

jest.mock("axios");
jest.mock("@/lib/downloadFile", () => ({ downloadFileWithProgress: async () => {} }));
const pegawai = { id: "p1", nama: "Pemegang Sintetis", nip: "198001012006011001", email: "pemegang@example.test", kode_satker: "SATKER-UJI" };
const asset = { id: "a1", asset_name: "Laptop Sintetis", asset_code: "3100102001", NUP: "1", activity_id: "uji", activity_name: "Inventarisasi Uji", boleh_dipilih: true, kunci_fisik: ["uji:a1"], alasan: "" };
const dasar = "BAST UJI 001/2026 telah diperiksa";
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { resolve, promise }; };

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  axios.get.mockImplementation(async url => {
    if (url.endsWith("/pegawai")) return { data: { items: [pegawai] } };
    if (url.endsWith("/admin/akses")) return { data: { ...pegawai, version: 0, akses: { aktif: true } } };
    if (url.endsWith("/admin/monitoring")) return { data: { pemegang: 1, penugasan: { diterima: 0 }, laporan: { menunggu_tinjauan: 0, perlu_perbaikan: 0 } } };
    if (url.endsWith("/admin/kandidat-aset")) return { data: { items: [asset], total: 1, total_pages: 1 } };
    return { data: { items: [] } };
  });
  axios.post.mockResolvedValue({ data: { ok: true } });
});

async function siapkan(onBack) {
  await act(async () => { render(<PenggunaanPage user={{ role: "admin" }} onBack={onBack} />); });
  expect(screen.queryByTestId("penggunaan-portal-panel")).not.toBeInTheDocument();
  await act(async () => { fireEvent.click(screen.getByTestId("penggunaan-portal-pemegang")); });
  fireEvent.click(await screen.findByTestId("portal-admin-pegawai"));
  const pilihan = await screen.findByTestId("portal-admin-pegawai-option-p1");
  await act(async () => { fireEvent.click(pilihan); });
  fireEvent.click(await screen.findByTestId("portal-admin-tambah-toggle"));
  fireEvent.click(await screen.findByTestId("portal-admin-aset-a1"));
  fireEvent.change(screen.getByTestId("portal-admin-dasar"), { target: { value: dasar } });
}

test("lipatan luar tidak melepas portal atau kunci retry; Back tombol dan browser meminta konfirmasi untuk hasil belum pasti", async () => {
  const onBack = jest.fn();
  axios.post.mockRejectedValueOnce({ response: { status: 503, data: { detail: "Hasil sementara belum diketahui" } } });
  await siapkan(onBack);
  const portalNode = screen.getByTestId("penggunaan-portal-panel");
  const wrapper = portalNode.closest("#portal-pemegang-panel");
  fireEvent.click(screen.getByTestId("penggunaan-portal-pemegang"));
  expect(wrapper).toHaveAttribute("hidden");
  expect(screen.getByTestId("penggunaan-portal-panel")).toBe(portalNode);
  fireEvent.click(screen.getByTestId("penggunaan-portal-pemegang"));
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue(dasar);
  expect(screen.getByTestId("portal-massal-lepas-a1")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-a1")).toHaveTextContent("Hasil belum pasti"));
  await waitFor(() => expect(screen.getByTestId("portal-admin-muat")).not.toBeDisabled());
  const first = axios.post.mock.calls[0];
  fireEvent.click(screen.getByTestId("penggunaan-portal-pemegang"));
  expect(wrapper).toHaveAttribute("hidden");
  fireEvent.click(screen.getByTestId("penggunaan-back"));
  expect(await screen.findByTestId("confirm-dialog")).toHaveTextContent("Permintaan yang sudah terkirim mungkin tetap diproses server");
  expect(screen.getByTestId("confirm-dialog")).toHaveTextContent("kunci percobaan ulang");
  expect(onBack).not.toHaveBeenCalled();
  await act(async () => { fireEvent.click(screen.getByTestId("confirm-dialog-cancel")); });
  fireEvent(window, new PopStateEvent("popstate"));
  await screen.findByTestId("confirm-dialog");
  expect(onBack).not.toHaveBeenCalled();
  await act(async () => { fireEvent.click(screen.getByTestId("confirm-dialog-cancel")); });
  fireEvent.click(screen.getByTestId("penggunaan-portal-pemegang"));
  expect(screen.getByTestId("penggunaan-portal-panel")).toBe(portalNode);
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue(dasar);
  expect(screen.getByTestId("portal-massal-hasil-a1")).toHaveTextContent("Hasil belum pasti");
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-a1")).toHaveTextContent("Berhasil"));
  await waitFor(() => expect(screen.getByTestId("portal-admin-pegawai")).not.toBeDisabled());
  expect(axios.post).toHaveBeenCalledTimes(2);
  expect(axios.post.mock.calls[1][1]).toEqual(first[1]);
  expect(axios.post.mock.calls[1][2].headers).toEqual(first[2].headers);
  fireEvent.click(screen.getByTestId("penggunaan-back"));
  expect(onBack).toHaveBeenCalledTimes(1);
  expect(screen.queryByTestId("confirm-dialog")).not.toBeInTheDocument();
});

test("penugasan yang masih dikirim tidak ditinggalkan diam-diam dan keputusan tinggalkan harus eksplisit", async () => {
  const onBack = jest.fn(); const pending = deferred();
  axios.post.mockReturnValueOnce(pending.promise);
  await siapkan(onBack);
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  expect(screen.getByTestId("portal-admin-pegawai")).toBeDisabled();
  fireEvent.click(screen.getByTestId("penggunaan-back"));
  const dialog = await screen.findByTestId("confirm-dialog");
  expect(dialog).toHaveTextContent("sedang dikirim atau hasilnya belum pasti");
  fireEvent(window, new PopStateEvent("popstate"));
  expect(screen.getAllByTestId("confirm-dialog")).toHaveLength(1);
  expect(onBack).not.toHaveBeenCalled();
  await act(async () => { fireEvent.click(screen.getByTestId("confirm-dialog-confirm")); });
  expect(onBack).toHaveBeenCalledTimes(1);
  await act(async () => { pending.resolve({ data: { ok: true } }); });
  expect(axios.post).toHaveBeenCalledTimes(1);
});
