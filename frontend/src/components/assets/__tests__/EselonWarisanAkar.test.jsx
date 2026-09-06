/**
 * Dua select eselon WARISAN — pada form aset dan pada ubah massal — menulis ke
 * kolom yang benar menurut tingkat satkernya.
 *
 * Keduanya hanya muncul saat master unit belum terisi, dan pilihannya diambil
 * dari struktur ringkas kegiatan. Dipatok ke `eselon1`/`eselon2`, unit sebuah
 * Lapas tercatat sebagai Eselon I miliknya: laporan lalu mengelompokkan
 * barangnya di tingkat yang tak pernah dimiliki satker itu, dan pada ubah
 * massal kekeliruan itu ditulis ke seluruh aset terpilih sekaligus.
 *
 * Tak ada pesan galat pada kedua kasus — nilainya tersimpan, hanya di laci
 * yang salah.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import BatchEditPanel from "../BatchEditPanel";
import AssetForm from "../AssetForm";

// `axios` dipalsukan UTUH: form aset membuat instans sendiri untuk unggahan
// besar dan memasang interceptor padanya saat modulnya dimuat.
jest.mock("axios", () => {
  const instans = {
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(), post: jest.fn(), put: jest.fn(), patch: jest.fn(),
    delete: jest.fn(),
  };
  return { ...instans, create: jest.fn(() => instans), isAxiosError: () => false };
});
// `date-fns/locale` terbit sebagai ESM dan tak dilewatkan transform Jest; ia
// hanya dipakai pemilih tanggal, yang tak disentuh uji ini.
jest.mock("date-fns/locale", () => ({ id: {} }));
// Lembar kamera menyentuh canvas saat MODULNYA dimuat, yang tak ada di jsdom.
// Ia tak dipakai uji ini sama sekali.
jest.mock("../FullCameraSheet", () => () => null);

const KEGIATAN = {
  id: "k1",
  eselon1: [{ nama: "Lapas Kelas IIA Nusantara",
              eselon2: ["Subbagian Tata Usaha"] }],
  lingkup_unit: [],
};

function pasangApi(akar) {
  axios.get.mockImplementation((url) => {
    if (String(url).endsWith("/unit-kerja")) {
      // Master unit KOSONG — justru keadaan yang memunculkan jalur warisan.
      return Promise.resolve({ data: { items: [],
        ...(akar == null ? {} : { level_akar: akar }) } });
    }
    return Promise.resolve({ data: { items: [] } });
  });
}

function bukaUbahMassal(akar) {
  pasangApi(akar);
  return render(<BatchEditPanel selectedCount={3} categories={[]}
    onApply={jest.fn()} onClose={jest.fn()} updating={false}
    activity={KEGIATAN} assets={[]} selectedAssets={[]} />);
}

// Radix Select memakai Pointer Events API yang tak ada di jsdom; tanpa
// tambalan ini daftar opsinya tak pernah terbuka.
beforeAll(() => {
  window.HTMLElement.prototype.hasPointerCapture = () => false;
  window.HTMLElement.prototype.releasePointerCapture = () => {};
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => jest.clearAllMocks());

test("ubah massal satker Eselon III berlabel Eselon III & IV", async () => {
  bukaUbahMassal(3);
  await waitFor(() => expect(screen.getByText("Eselon III")).toBeInTheDocument());
  expect(screen.getByText("Eselon IV")).toBeInTheDocument();
  expect(screen.queryByText("Eselon I")).toBeNull();
  expect(screen.queryByText("Eselon II")).toBeNull();
});

test("satker Eselon I tetap berlabel Eselon I & II — perilaku lama", async () => {
  bukaUbahMassal(1);
  await waitFor(() => expect(screen.getByText("Eselon I")).toBeInTheDocument());
  expect(screen.getByText("Eselon II")).toBeInTheDocument();
});

test("server lama yang belum menyebut level_akar tetap Eselon I & II", async () => {
  bukaUbahMassal(null);
  await waitFor(() => expect(screen.getByText("Eselon I")).toBeInTheDocument());
  expect(screen.getByText("Eselon II")).toBeInTheDocument();
});

test("satker Eselon V tak punya select kedua — Eselon VI tak dikarang", async () => {
  bukaUbahMassal(5);
  await waitFor(() => expect(screen.getByText("Eselon V")).toBeInTheDocument());
  expect(screen.queryByText(/Eselon VI/)).toBeNull();
});

test("pilihan yang diterapkan masuk ke kolom eselon3, bukan eselon1", async () => {
  // Inti perbaikannya: bukan sekadar labelnya yang berganti.
  const onApply = jest.fn();
  pasangApi(3);
  render(<BatchEditPanel selectedCount={3} categories={[]} onApply={onApply}
    onClose={jest.fn()} updating={false} activity={KEGIATAN} assets={[]}
    selectedAssets={[]} />);
  const pengguna = userEvent.setup({ pointerEventsCheck: 0 });
  await waitFor(() => expect(screen.getByText("Eselon III")).toBeInTheDocument());
  await pengguna.click(screen.getByText("Eselon III").closest("div")
    .querySelector("[role='combobox']"));
  await pengguna.click(await screen.findByText("Lapas Kelas IIA Nusantara"));
  await pengguna.click(screen.getByRole("button", { name: /Terapkan/i }));
  await waitFor(() => expect(onApply).toHaveBeenCalled());
  const kirim = onApply.mock.calls[0][0];
  expect(kirim.eselon3).toBe("Lapas Kelas IIA Nusantara");
  expect(kirim.eselon1).toBeUndefined();
});

// ── Form aset: dua select yang sama, salinan wiring yang berbeda ────────

function bukaFormAset(akar) {
  pasangApi(akar);
  return render(<AssetForm isOpen onClose={jest.fn()} activity={KEGIATAN}
    categories={[]} editAsset={null} onSubmitSuccess={jest.fn()} />);
}

/** Tunggu sampai akar dari server terpasang — sebelum itu selectnya masih
 *  memakai bawaan Eselon I. */
const namaSelect = (testid, nama) => waitFor(
  () => expect(screen.getByTestId(testid)).toHaveAttribute("name", nama));

test("form aset satker Eselon III menulis ke kolom eselon3", async () => {
  bukaFormAset(3);
  // Namanya BUKAN hiasan: `handleInputChange` memakai `name` sebagai kolom
  // tujuan, jadi inilah yang menentukan aset tercatat di tingkat mana.
  await namaSelect("asset-eselon1-select", "eselon3");
  expect(screen.getByTestId("asset-eselon2-select"))
    .toHaveAttribute("name", "eselon4");
});

test("form aset satker Eselon I tetap menulis ke eselon1/eselon2", async () => {
  bukaFormAset(1);
  await namaSelect("asset-eselon1-select", "eselon1");
  expect(screen.getByTestId("asset-eselon2-select"))
    .toHaveAttribute("name", "eselon2");
});

test("form aset satker Eselon V hanya punya satu select", async () => {
  bukaFormAset(5);
  await namaSelect("asset-eselon1-select", "eselon5");
  expect(screen.queryByTestId("asset-eselon2-select")).toBeNull();
});
