import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import PortalPemegangPanel from "../PortalPemegangPanel";

jest.mock("axios");

// Fixture fiktif, deterministik dan lokal: tidak memakai data/email pemegang nyata.
const pegawai = [
  { id: "p1", nama: "Pemegang Sintetis Satu", nip: "198001012006011001", email: "satu@example.test", kode_satker: "SATKER-UJI" },
  { id: "p2", nama: "Pemegang Sintetis Dua", nip: "198002022006012002", email: "dua@example.test", kode_satker: "SATKER-UJI" },
];
const asset = (id, nup) => ({ id, asset_name: `Laptop Sintetis ${id}`, asset_code: "3100102001", NUP: nup,
  activity_id: "kegiatan-uji", activity_name: "Inventarisasi Sintetis 2026", location: "Ruang Uji",
  condition: "Baik", user: "Pemegang Sintetis", boleh_dipilih: true, alasan: "", kunci_fisik: [`fisik:${id}`] });
const a1 = asset("a1", "1"); const a2 = asset("a2", "2"); const b1 = asset("b1", "3");
const daftar = items => ({ data: { items, total: items.length, total_pages: 1, page: 1, page_size: 20 } });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { resolve, promise }; };
const dasar = "BAST 001/SATKER-UJI/2026 telah diperiksa";

async function pilihPegawai(id) {
  await waitFor(() => expect(screen.getByTestId("portal-admin-pegawai")).not.toBeDisabled());
  fireEvent.click(screen.getByTestId("portal-admin-pegawai"));
  const option = await screen.findByTestId(`portal-admin-pegawai-option-${id}`);
  await act(async () => { fireEvent.click(option); });
}
async function bukaLegacy(open = true) {
  const summary = await screen.findByTestId("portal-admin-tambah-toggle");
  const details = summary.closest("details");
  if (details.open !== open) fireEvent.click(summary);
  await waitFor(() => expect(details.open).toBe(open));
}
async function tungguTidakSibuk() {
  await waitFor(() => expect(screen.getByTestId("portal-admin-tambah")).not.toHaveTextContent("Mencatat per barang"));
  await waitFor(() => expect(screen.getByTestId("portal-admin-muat")).not.toBeDisabled());
}

beforeEach(() => {
  Object.defineProperty(globalThis, "crypto", { configurable: true, value: require("crypto").webcrypto });
  axios.get.mockImplementation(async (url, options) => {
    if (url.endsWith("/pegawai")) return daftar(pegawai);
    if (url.endsWith("/admin/monitoring")) return { data: { pemegang: 2, penugasan: { diterima: 0 }, laporan: { menunggu_tinjauan: 0, perlu_perbaikan: 0 } } };
    if (url.endsWith("/admin/akses")) return { data: { ...pegawai.find(p => p.id === options.params.pegawai_id), version: 0, akses: { aktif: true } } };
    if (url.endsWith("/admin/kandidat-aset")) return daftar(options.params.pegawai_id === "p1" ? [a1, a2] : [b1]);
    return daftar([]);
  });
  axios.post.mockResolvedValue({ data: { ok: true } });
});

test("lipatan mempertahankan pilihan dan hasil 503; parent mengunci pemegang, replay mempertahankan body/kunci tanpa mengulang sukses", async () => {
  let gagalSekali = true;
  axios.post.mockImplementation(async (url, body) => {
    if (body.asset_id === "a2" && gagalSekali) {
      gagalSekali = false;
      throw { response: { status: 503, data: { detail: "Hasil server sementara belum tersedia" } } };
    }
    return { data: { ok: true } };
  });
  await act(async () => { render(<PortalPemegangPanel user={{ role: "admin" }} />); });
  await pilihPegawai("p1"); await bukaLegacy();
  fireEvent.click(await screen.findByTestId("portal-admin-aset-a1"));
  fireEvent.click(screen.getByTestId("portal-admin-aset-a2"));
  fireEvent.change(screen.getByTestId("portal-admin-dasar"), { target: { value: dasar } });
  fireEvent.change(screen.getByTestId("portal-admin-penugasan-catatan"), { target: { value: "Dua barang legacy sesuai dokumen uji" } });
  await bukaLegacy(false); await bukaLegacy();
  expect(screen.getByTestId("portal-massal-lepas-a1")).toBeInTheDocument();
  expect(screen.getByTestId("portal-massal-lepas-a2")).toBeInTheDocument();
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue(dasar);
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-a2")).toHaveTextContent("Hasil belum pasti"));
  await tungguTidakSibuk();
  expect(screen.getByTestId("portal-admin-pegawai")).toBeDisabled();
  expect(screen.getByTestId("portal-admin-pegawai-clear")).toBeDisabled();
  expect(screen.getByTestId("portal-massal-reset")).toBeDisabled();
  expect(screen.getByTestId("portal-massal-lepas-a2")).toBeDisabled();
  expect(screen.getByTestId("portal-admin-dasar")).toBeDisabled();
  expect(screen.queryByTestId("portal-massal-lepas-a1")).not.toBeInTheDocument();
  const firstUnknown = axios.post.mock.calls[1];
  await bukaLegacy(false); await bukaLegacy();
  expect(screen.getByTestId("portal-massal-hasil-a2")).toHaveTextContent("Hasil belum pasti");
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue(dasar);
  expect(screen.getByTestId("portal-admin-tambah")).not.toBeDisabled();
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-a2")).toHaveTextContent("Berhasil"));
  await tungguTidakSibuk();
  expect(axios.post.mock.calls.map(call => call[1].asset_id)).toEqual(["a1", "a2", "a2"]);
  expect(axios.post.mock.calls[2][1]).toEqual(firstUnknown[1]);
  expect(axios.post.mock.calls[2][2].headers).toEqual(firstUnknown[2].headers);
  expect(firstUnknown[2].headers["If-Match"]).toBe("0");
  expect(screen.getByTestId("portal-admin-pegawai")).not.toBeDisabled();
});

test("pilihan pegawai sama mempertahankan keranjang; ganti pegawai sesudah hasil pasti membersihkan state dan menolak respons kandidat lama", async () => {
  const baseGet = axios.get.getMockImplementation();
  const lambat = deferred();
  let tahanKandidatLama = false;
  axios.get.mockImplementation((url, options) => url.endsWith("/admin/kandidat-aset") && options.params.pegawai_id === "p1" && tahanKandidatLama
    ? lambat.promise : baseGet(url, options));
  await act(async () => { render(<PortalPemegangPanel user={{ role: "admin" }} />); });
  await pilihPegawai("p1"); await bukaLegacy();
  fireEvent.click(await screen.findByTestId("portal-admin-aset-a1"));
  fireEvent.change(screen.getByTestId("portal-admin-dasar"), { target: { value: dasar } });
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-a1")).toHaveTextContent("Berhasil"));
  await tungguTidakSibuk();
  fireEvent.click(screen.getByTestId("portal-admin-aset-a2"));
  await pilihPegawai("p1");
  expect(screen.getByTestId("portal-admin-tambah-toggle").closest("details")).toHaveAttribute("open");
  expect(screen.getByTestId("portal-massal-lepas-a2")).toBeInTheDocument();
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue(dasar);
  expect(screen.getByTestId("portal-massal-hasil-a1")).toHaveTextContent("Berhasil");
  tahanKandidatLama = true;
  fireEvent.click(screen.getByTestId("portal-massal-muat"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-muat")).toBeDisabled());
  await pilihPegawai("p2");
  expect(screen.queryByTestId("portal-massal")).not.toBeInTheDocument();
  await bukaLegacy();
  expect(await screen.findByTestId("portal-admin-aset-b1")).toBeInTheDocument();
  expect(screen.getByTestId("portal-admin-dasar")).toHaveValue("");
  expect(screen.queryByTestId("portal-massal-lepas-a2")).not.toBeInTheDocument();
  expect(screen.queryByTestId("portal-massal-hasil-a1")).not.toBeInTheDocument();
  await act(async () => lambat.resolve(daftar([asset("aset-usang", "99")])));
  expect(screen.queryByTestId("portal-admin-aset-aset-usang")).not.toBeInTheDocument();
  expect(screen.getByTestId("portal-admin-aset-b1")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("portal-admin-aset-b1"));
  fireEvent.change(screen.getByTestId("portal-admin-dasar"), { target: { value: "BAST 002/SATKER-UJI/2026 untuk pemegang kedua" } });
  fireEvent.click(screen.getByTestId("portal-admin-tambah"));
  await waitFor(() => expect(screen.getByTestId("portal-massal-hasil-b1")).toHaveTextContent("Berhasil"));
  await tungguTidakSibuk();
  expect(axios.post.mock.calls.map(call => [call[1].pegawai_id, call[1].asset_id])).toEqual([["p1", "a1"], ["p2", "b1"]]);
});
