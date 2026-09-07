/**
 * Kolom koordinat form aset memakai pemisah desimal TITIK.
 *
 * Permintaan pemilik: *"ketika lat lng ditulis menggunakan koma ketika
 * disimpan, tolong sesuaikan langsung menggunakan titik saja."*
 *
 * Sisi server sudah merapikannya di seluruh jalur tulis, jadi yang tersimpan
 * pasti bertitik. Yang belum: apa yang TAMPAK di layar. Petugas yang mengetik
 * "-1,4001" lalu melihat komanya bertahan di kolom akan mengira itulah yang
 * tersimpan — dan pada laporan yang mereka cetak nanti angkanya berbeda bentuk
 * dari yang mereka ingat mengetiknya.
 *
 * Ditemukan uji mutasi: membuang perapian di `handleInputChange` lolos dari
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

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: { items: [] } });
});

function bukaForm() {
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }}
    categories={[]} editAsset={null} onSubmitSuccess={jest.fn()} />);
}

/** Kolom lintang/bujur — dicari lewat name, seperti markup formnya. */
function kolom(nama) {
  return document.querySelector(`input[name="${nama}"]`);
}

test("koma yang diketik SEGERA menjadi titik di kolom lintang", async () => {
  bukaForm();
  await waitFor(() => expect(kolom("koordinat_latitude")).toBeInTheDocument());
  await userEvent.type(kolom("koordinat_latitude"), "-1,4001");
  await waitFor(() => expect(kolom("koordinat_latitude")).toHaveValue("-1.4001"));
});

test("kolom bujur diperlakukan sama", async () => {
  bukaForm();
  await waitFor(() => expect(kolom("koordinat_longitude")).toBeInTheDocument());
  await userEvent.type(kolom("koordinat_longitude"), "116,7001");
  await waitFor(() => expect(kolom("koordinat_longitude")).toHaveValue("116.7001"));
});

test("yang sudah bertitik tak terusik saat diketik", async () => {
  bukaForm();
  await waitFor(() => expect(kolom("koordinat_latitude")).toBeInTheDocument());
  await userEvent.type(kolom("koordinat_latitude"), "-1.4001");
  await waitFor(() => expect(kolom("koordinat_latitude")).toHaveValue("-1.4001"));
});

test("kolom LAIN tak ikut dirapikan", async () => {
  // Perapian ini khusus koordinat. Nama barang yang berisi koma — "Meja, Kayu"
  // — tak boleh ikut berubah menjadi "Meja. Kayu".
  bukaForm();
  const nama = document.querySelector('input[name="asset_name"]');
  await waitFor(() => expect(nama).toBeInTheDocument());
  await userEvent.type(nama, "Meja, Kayu");
  await waitFor(() => expect(nama).toHaveValue("Meja, Kayu"));
});
