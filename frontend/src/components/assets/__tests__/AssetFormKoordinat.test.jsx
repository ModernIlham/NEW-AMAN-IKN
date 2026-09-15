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
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

test("denah memperbarui kolom baca-saja tanpa menimpa draft lokasi manual", async () => {
  const aset = { id: "a1", activity_id: "k1", asset_name: "Meja", asset_code: "123",
    NUP: "1", version: 3, location: "Lama", koordinat_latitude: "-1.4", koordinat_longitude: "116.7" };
  axios.get.mockImplementation(url => Promise.resolve({ data: url.includes("/assets/a1?") ? aset : { items: [] } }));
  const onOpenLokasiDenah = jest.fn();
  render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }} categories={[]}
    editAsset={aset} onSubmitSuccess={jest.fn()} onOpenLokasiDenah={onOpenLokasiDenah} />);
  await waitFor(() => expect(screen.getByTestId("asset-form-denah-btn")).toBeEnabled());
  fireEvent.change(kolom("koordinat_latitude"), { target: { value: "-1.5" } });
  fireEvent.change(kolom("asset_name"), { target: { value: "Meja belum disimpan" } });
  fireEvent.change(kolom("location"), { target: { value: "Lokasi manual belum disimpan" } });
  fireEvent.click(screen.getByTestId("asset-form-denah-btn"));
  const konteks = onOpenLokasiDenah.mock.calls[0][2];
  expect(konteks.koordinat_latitude).toBe("-1.5");
  expect(konteks.version).toBe(3);
  act(() => konteks.onSaved({ id: "a1", version: 4, location: "Lama", koordinat_latitude: "-1.6", koordinat_longitude: "116.9",
    lokasi_spasial: { node_id: "r2", jalur_nama: "Gedung B / Lantai 2 / Ruang Baru" } }));
  expect(kolom("asset_name")).toHaveValue("Meja belum disimpan");
  expect(kolom("location")).toHaveValue("Lokasi manual belum disimpan");
  expect(screen.getByTestId("asset-lokasi-denah")).toHaveValue("Gedung B / Lantai 2 / Ruang Baru");
  expect(screen.getByTestId("asset-lokasi-denah")).toHaveAttribute("readonly");
  expect(kolom("koordinat_latitude")).toHaveValue("-1.6");
  fireEvent.click(screen.getByTestId("asset-form-denah-btn"));
  expect(onOpenLokasiDenah.mock.calls[1][2].version).toBe(4);
});

test("lokasi denah dari cache tetap terbaca saat offline", async () => {
  const daring = Object.getOwnPropertyDescriptor(window.navigator, "onLine");
  Object.defineProperty(window.navigator, "onLine", { configurable: true, value: false });
  try {
    render(<AssetForm isOpen onClose={jest.fn()} activity={{ id: "k1" }} categories={[]}
      editAsset={{ id: "a1", version: 3, location: "Lokasi manual", di_denah: true,
        denah_jalur: "Gedung A / Ruang 1" }} onSubmitSuccess={jest.fn()} />);
    expect(await screen.findByTestId("asset-lokasi-denah")).toHaveValue("Gedung A / Ruang 1");
    expect(kolom("location")).toHaveValue("Lokasi manual");
  } finally {
    if (daring) Object.defineProperty(window.navigator, "onLine", daring);
    else delete window.navigator.onLine;
  }
});
