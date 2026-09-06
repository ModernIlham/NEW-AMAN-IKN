/**
 * Form aset MEMAKAI pilihan dari pemilih unit — bukan sekadar menampilkannya.
 *
 * Uji pemilihnya sendiri (`PemilihUnitOrganisasi.test.jsx`) membuktikan ia
 * mengembalikan id yang benar. Yang belum dijaga: bahwa form aset benar-benar
 * mengubah `eselon1..eselon5` dari id itu. Sambungan yang putus di sini tak
 * memunculkan galat apa pun — pemilihnya menutup, tombolnya tampak terisi,
 * dan asetnya tersimpan tanpa unit organisasi.
 *
 * Ditemukan oleh uji mutasi: membuang argumen `id` pada `onPilih` lolos dari
 * seluruh berkas uji yang ada.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AssetForm from "../AssetForm";

jest.mock("axios", () => {
  const instans = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(),
    delete: jest.fn(),
  };
  return { ...instans, create: jest.fn(() => instans), isAxiosError: () => false };
});
jest.mock("date-fns/locale", () => ({ id: {} }));
jest.mock("../FullCameraSheet", () => () => null);

const axios = require("axios");

const MASTER = [
  { id: "k2", nama_unit: "Kedeputian Bidang Transformasi Hijau dan Digital",
    eselon: "1", parent_id: null },
  { id: "d22", nama_unit: "Direktorat Pengembangan Ekosistem Digital",
    eselon: "2", parent_id: "k2" },
];

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation((url) => {
    if (String(url).endsWith("/unit-kerja")) {
      return Promise.resolve({ data: { items: MASTER, level_akar: 1 } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
});

function bukaForm() {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }}
    categories={[]} editAsset={null} onSubmitSuccess={jest.fn()} />);
}

test("memilih unit MENGISI jalur eselon aset, bukan hanya menutup dialog", async () => {
  bukaForm();
  await userEvent.click(await screen.findByTestId("asset-unit-pemicu"));
  await userEvent.click(await screen.findByTestId("asset-unit-opsi-d22"));
  // "Tercatat" adalah baris yang memberi tahu pengguna apa yang tersimpan;
  // ia hanya muncul bila kolom eselon aset benar-benar terisi.
  await waitFor(() => expect(screen.getByTestId("asset-unit-tercatat"))
    .toHaveTextContent(
      "Kedeputian Bidang Transformasi Hijau dan Digital / "
      + "Direktorat Pengembangan Ekosistem Digital"));
});

test("pemicunya ikut menyebut yang baru dipilih", async () => {
  bukaForm();
  await userEvent.click(await screen.findByTestId("asset-unit-pemicu"));
  await userEvent.click(await screen.findByTestId("asset-unit-opsi-k2"));
  await waitFor(() => expect(screen.getByTestId("asset-unit-pemicu"))
    .toHaveTextContent("Kedeputian Bidang Transformasi Hijau dan Digital"));
});

test("mengosongkan pilihan MENGHAPUS jalur eselonnya", async () => {
  // Sisa unit sebelumnya yang tertinggal terbaca sebagai unit yang tak pernah
  // ada di sana — persis alasan `fieldEselon` mengosongkan tingkat tak terpakai.
  bukaForm();
  await userEvent.click(await screen.findByTestId("asset-unit-pemicu"));
  await userEvent.click(await screen.findByTestId("asset-unit-opsi-d22"));
  await waitFor(() => expect(screen.getByTestId("asset-unit-tercatat"))
    .toBeInTheDocument());
  await userEvent.click(screen.getByTestId("asset-unit-pemicu"));
  await userEvent.click(await screen.findByTestId("asset-unit-kosongkan"));
  await waitFor(() => expect(screen.queryByTestId("asset-unit-tercatat"))
    .toBeNull());
});
