/**
 * Pemilih pengguna aset tiga kelompok + peringatan "belum terdaftar" dari
 * penjawab kelompok (PGW-08).
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AssetForm from "../AssetForm";
import { _setelUlangPenampung } from "../../../hooks/useKelompokOrang";

jest.mock("axios", () => {
  const api = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(), delete: jest.fn(),
  };
  return { ...api, create: jest.fn(() => api), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);

const axios = require("axios");
const ORANG_P3 = { id: "o1", nama: "Sari", nip: "3201010101010001", kelompok: "pihak_ketiga",
  tataran: "", kunci_ikon: "pihak_ketiga", ranah: "luar", jabatan: "Direktur",
  instansi_nama: "PT Maju", satker_luar_nama: "Kantor Pusat" };

beforeAll(() => { window.HTMLElement.prototype.scrollIntoView = () => {}; });
beforeEach(() => {
  jest.clearAllMocks();
  window.localStorage.clear();
  _setelUlangPenampung();
  axios.get.mockImplementation((url, cfg = {}) => {
    if (String(url).endsWith("/direktori-pegawai") && cfg.params?.kelompok === "pihak_ketiga") {
      return Promise.resolve({ data: { items: [ORANG_P3], total: 1 } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
});

async function buka() {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }}
    categories={[]} editAsset={null} onSubmitSuccess={jest.fn()} />);
  await screen.findByTestId("asset-code-picker");
}

test("pihak ketiga dicari di direktori dan terisi ke pengguna beserta ikonnya", async () => {
  axios.post.mockResolvedValue({ data: { nomor: { [ORANG_P3.nip]: "pihak_ketiga" } } });
  await buka();
  await userEvent.click(screen.getByTestId("pengguna-pegawai-picker"));
  await userEvent.click(await screen.findByTestId("pengguna-pegawai-kelompok-pihak_ketiga"));
  await userEvent.click(await screen.findByTestId("pengguna-pegawai-luar-opt-o1"));
  expect(screen.getByTestId("input-pengguna-nama")).toHaveValue("Sari");
  expect(screen.getByTestId("input-pengguna-nip")).toHaveValue(ORANG_P3.nip);
  expect(await screen.findByRole("img", { name: "Pihak ketiga" })).toBeInTheDocument();
  expect(screen.queryByTestId("pengguna-nip-warning")).toBeNull();
  const cari = axios.get.mock.calls.find(([u]) => String(u).endsWith("/direktori-pegawai"));
  expect(cari[1].params).toMatchObject({ kelompok: "pihak_ketiga" });
});

test("NIP yang tak dikenal penjawab kelompok memunculkan peringatan; luring tidak", async () => {
  axios.post.mockResolvedValue({ data: { nomor: {} } });
  await buka();
  await userEvent.type(screen.getByTestId("input-pengguna-nip"), "199001012020011001");
  expect(await screen.findByTestId("pengguna-nip-warning", {}, { timeout: 2000 })).toBeInTheDocument();
  await waitFor(() => expect(axios.post).toHaveBeenCalledTimes(1));
  expect(axios.post.mock.calls[0][1]).toEqual({ nomor: ["199001012020011001"] });
});

test("penjawab kelompok gagal (luring) → tanpa peringatan, form tetap jalan", async () => {
  axios.post.mockRejectedValue(new Error("luring"));
  await buka();
  await userEvent.type(screen.getByTestId("input-pengguna-nip"), "199001012020011002");
  await waitFor(() => expect(axios.post).toHaveBeenCalled(), { timeout: 2000 });
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByTestId("pengguna-nip-warning")).toBeNull();
  expect(screen.getByTestId("input-pengguna-nip")).toHaveValue("199001012020011002");
});
