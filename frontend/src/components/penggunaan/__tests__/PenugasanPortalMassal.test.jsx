import React from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import axios from "axios";
import PenugasanPortalMassal from "../PenugasanPortalMassal";

jest.mock("axios");
const asset = (id, extra = {}) => ({ id, asset_name: `Barang ${id}`, asset_code: "3100102001", NUP: id, activity_name: "Kegiatan acuan", boleh_dipilih: true, kunci_fisik: [id], ...extra });
const a = asset("a"); const b = asset("b"); const c = asset("c");
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
const setup = props => render(<PenugasanPortalMassal pegawaiId="p1" {...props} />);
const dasar = () => fireEvent.change(screen.getByTestId("portal-admin-dasar"), { target: { value: "BAST 001/Satker tahun 2026" } });
const pick = async id => fireEvent.click(await screen.findByTestId(`portal-admin-aset-${id}`));

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  axios.get.mockImplementation(async () => ({ data: { items: [a, b], total: 2, total_pages: 1 } }));
  axios.post.mockResolvedValue({ data: { ok: true } });
});

test("pilihan bertahan lintas halaman/pencarian, hapus satu dan reset tanpa menulis", async () => {
  axios.get.mockImplementation(async (url, { params }) => ({ data: { items: params.search ? [c] : params.page === 1 ? [a] : [b], total: 2, total_pages: params.search ? 1 : 2 } }));
  setup(); await pick("a");
  fireEvent.click(screen.getByTestId("portal-massal-berikutnya")); await pick("b");
  expect(screen.getByTestId("portal-massal-lepas-a")).toBeInTheDocument();
  fireEvent.change(screen.getByTestId("portal-admin-cari-aset"), { target: { value: "Baru" } });
  expect(screen.getByTestId("portal-massal-pilih-tampak")).toBeDisabled();
  await pick("c");
  expect(screen.getByRole("region", { name: "Barang terpilih" })).toHaveTextContent("3 barang terpilih");
  fireEvent.click(screen.getByTestId("portal-massal-lepas-b"));
  expect(screen.queryByTestId("portal-massal-lepas-b")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("portal-massal-reset"));
  expect(screen.queryByRole("region", { name: "Barang terpilih" })).not.toBeInTheDocument();
  expect(axios.post).not.toHaveBeenCalled();
});

test("pilih halaman hanya kandidat tampak tanpa menebak kegiatan acuan barang duplikat", async () => {
  const sibling = asset("a2", { kunci_fisik: ["a"], activity_name: "Kegiatan berbeda" });
  axios.get.mockResolvedValue({ data: { items: [a, sibling, b, asset("terblokir", { boleh_dipilih: false, alasan: "Mengikuti BAST" })], total: 55, total_pages: 3 } });
  setup(); await screen.findByTestId("portal-admin-aset-a");
  fireEvent.click(screen.getByTestId("portal-massal-pilih-tampak"));
  expect(screen.getByTestId("portal-massal-lepas-b")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-massal-lepas-a")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-massal-seleksi-info")).toHaveTextContent("2 baris perlu dipilih kegiatan acuannya satu per satu");
  expect(screen.getByTestId("portal-massal-seleksi-info")).toHaveTextContent("1 baris tidak memenuhi syarat");
  await pick("a"); expect(screen.getByTestId("portal-admin-aset-a2")).toBeDisabled();
  expect(screen.getByTestId("portal-admin-aset-terblokir")).toBeDisabled();
});

test("hasil parsial mempertahankan gagal, retry memakai kunci yang sama dan tidak mengirim ulang sukses", async () => {
  let fail = true;
  axios.post.mockImplementation(async (url, body) => {
    if (body.asset_id === "b" && fail) throw { response: { status: 409, data: { detail: "Konflik penugasan" } } };
    return { data: { ok: true } };
  });
  const done = jest.fn(); const busy = jest.fn();
  setup({ onComplete: done, onBusyChange: busy }); await pick("a"); await pick("b"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(screen.getByTestId("portal-massal-hasil")).toHaveTextContent("1 berhasil · 1 belum berhasil");
  expect(screen.queryByTestId("portal-massal-lepas-a")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-massal-lepas-b")).toBeInTheDocument();
  expect(screen.getByTestId("portal-massal-hasil-b")).toHaveTextContent("Konflik penugasan");
  const firstFailed = axios.post.mock.calls[1]; fail = false;
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(2));
  expect(axios.post.mock.calls.map(call => call[1].asset_id)).toEqual(["a", "b", "b"]);
  expect(axios.post.mock.calls[2][2].headers).toEqual(firstFailed[2].headers);
  expect(firstFailed[2].headers["If-Match"]).toBe("0");
  expect(busy).toHaveBeenLastCalledWith(false);
});

test("hasil jaringan belum pasti menghentikan antrean dan mengunci payload/pilihan hingga replay pasti", async () => {
  axios.get.mockResolvedValue({ data: { items: [a, b, c], total: 3, total_pages: 1 } });
  axios.post.mockRejectedValueOnce(new Error("putus jaringan"));
  const unknown = jest.fn(); const done = jest.fn();
  setup({ onUncertainChange: unknown, onComplete: done });
  await pick("a"); await pick("b"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("portal-massal-hasil-a")).toHaveTextContent("Hasil belum pasti");
  expect(screen.getByTestId("portal-admin-dasar")).toBeDisabled();
  expect(screen.getByTestId("portal-admin-penugasan-catatan")).toBeDisabled();
  expect(screen.getByTestId("portal-massal-reset")).toBeDisabled();
  expect(screen.getByTestId("portal-massal-lepas-a")).toBeDisabled();
  expect(screen.getByTestId("portal-massal-lepas-b")).not.toBeDisabled();
  expect(unknown).toHaveBeenLastCalledWith(true);
  const first = axios.post.mock.calls[0];
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(2));
  expect(axios.post.mock.calls[1][1]).toEqual(first[1]);
  expect(axios.post.mock.calls[1][2].headers).toEqual(first[2].headers);
  expect(axios.post.mock.calls.map(call => call[1].asset_id)).toEqual(["a", "a", "b"]);
  expect(unknown).toHaveBeenLastCalledWith(false);
});

test.each([401, 403, 429])("galat sistematis %s menghentikan pengiriman barang berikutnya", async status => {
  axios.post.mockRejectedValue({ response: { status, data: { detail: "Tunda dan periksa akses" } } });
  const done = jest.fn(); setup({ onComplete: done }); await pick("a"); await pick("b"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(screen.getByTestId("portal-massal-hasil")).toHaveTextContent("Proses dijeda");
});

test.each([401, 403, 409, 429])("retry hasil belum pasti tidak dianggap pasti hanya karena galat %s", async status => {
  axios.post.mockRejectedValueOnce(new Error("respons pertama terputus"))
    .mockRejectedValueOnce({ response: { status, data: { detail: "Percobaan ulang belum bisa diperiksa" } } });
  const done = jest.fn(); setup({ onComplete: done }); await pick("a"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(2));
  expect(screen.getByTestId("portal-massal-hasil-a")).toHaveTextContent("Hasil belum pasti");
  expect(screen.getByTestId("portal-massal-reset")).toBeDisabled();
  expect(screen.getByTestId("portal-admin-dasar")).toBeDisabled();
  expect(axios.post.mock.calls[1][1]).toEqual(axios.post.mock.calls[0][1]);
  expect(axios.post.mock.calls[1][2].headers).toEqual(axios.post.mock.calls[0][2].headers);
});

test("antrean berhenti pada unmount, tidak meneruskan tulis ke barang berikutnya", async () => {
  const pending = deferred(); axios.post.mockReturnValue(pending.promise);
  const { unmount } = setup(); await pick("a"); await pick("b"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  expect(screen.getByTestId("portal-admin-cari-aset")).toBeDisabled();
  unmount(); await act(async () => pending.resolve({ data: {} }));
  expect(axios.post).toHaveBeenCalledTimes(1);
});

test("batas 100 seleksi diterapkan dan respons kandidat lama diabaikan", async () => {
  const pending = deferred();
  axios.get.mockImplementation((url, { params }) => !params.search ? pending.promise : Promise.resolve({ data: { items: Array.from({ length: 101 }, (_, i) => asset(String(i))), total: 101, total_pages: 1 } }));
  setup(); fireEvent.change(screen.getByTestId("portal-admin-cari-aset"), { target: { value: "baru" } });
  await screen.findByTestId("portal-admin-aset-100");
  fireEvent.click(screen.getByTestId("portal-massal-pilih-tampak"));
  expect(within(screen.getByRole("region", { name: "Barang terpilih" })).getByText("100 barang terpilih")).toBeInTheDocument();
  expect(screen.queryByTestId("portal-massal-lepas-100")).not.toBeInTheDocument();
  await act(async () => pending.resolve({ data: { items: [a], total: 1, total_pages: 1 } }));
  expect(screen.queryByTestId("portal-admin-aset-a")).not.toBeInTheDocument();
});

test("gagal baca kandidat tidak menghapus keranjang dan hasil sukses tetap tak bisa dipilih ulang", async () => {
  const done = jest.fn(); setup({ onComplete: done }); await pick("a"); dasar();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(screen.getByTestId("portal-admin-aset-a")).toBeDisabled();
  await pick("b"); axios.get.mockRejectedValue(new Error("offline"));
  fireEvent.click(screen.getByTestId("portal-massal-muat"));
  await screen.findByText(/Daftar barang gagal dimuat/);
  expect(screen.getByTestId("portal-massal-lepas-b")).toBeInTheDocument();
});
