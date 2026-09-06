/**
 * Tingkat eselon satker pada Master Satker — puncak pohon unit kerjanya.
 *
 * Tidak semua satker berpuncak Eselon I: Kantor Wilayah adalah satker Eselon
 * II, sedangkan KPP Pratama, Lapas, Madrasah Negeri, dan Kantor Pertanahan
 * kabupaten/kota adalah satker Eselon III/IV — mandiri karena memegang DIPA
 * sendiri. Tingkatnya dinyatakan SEKALI di sini, lalu dibaca seluruh lapisan.
 *
 * Kegagalan yang dijaga berkas ini tak menampakkan gejala: bila dialog profil
 * tak ikut membaca-dan-mengirim `eselon_satker`, maka sekadar mengubah nomor
 * telepon akan MENGEMBALIKAN satker itu ke Eselon I — PUT satker menulis apa
 * yang dikirim — dan pengelolaan unit kerjanya mendadak menuntut dua tingkat
 * yang tak pernah dimiliki satkernya. Toast tetap berbunyi "tersimpan".
 * Cacat yang sama pernah menimpa `eselon1` dan `penandatangan` pada layar ini.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { SatkerPanel } from "../SatkerPage";

jest.mock("axios");

const LAPAS = {
  kode_satker: "333333", nama_satker: "Lapas Kelas IIA Nusantara",
  terdaftar: true, jumlah_kegiatan: 1, telepon: "0541-000",
  eselon_satker: "3",
};

function pasangApi(satker) {
  axios.get.mockImplementation((url) => {
    if (String(url).includes("/pejabat")) {
      return Promise.resolve({ data: { items: [], slot_tanda_tangan: [] } });
    }
    return Promise.resolve({ data: { items: [satker] } });
  });
  axios.put.mockResolvedValue({ data: { ok: true } });
}

async function bukaProfil(satker) {
  pasangApi(satker);
  render(<SatkerPanel user={{ role: "admin", kode_satker: satker.kode_satker }} />);
  await userEvent.click(
    await screen.findByTestId(`satker-edit-${satker.kode_satker}`));
  return screen.findByTestId("satker-form-eselon_satker");
}

beforeEach(() => jest.clearAllMocks());

test("tingkat yang tersimpan TERBACA di dialog profil", async () => {
  const pilih = await bukaProfil(LAPAS);
  expect(pilih).toHaveValue("3");
});

test("satker lama tanpa field itu tampil sebagai Eselon I bawaan", async () => {
  const { eselon_satker: _abaikan, ...tanpa } = LAPAS;
  const pilih = await bukaProfil(tanpa);
  expect(pilih).toHaveValue("");
});

test("menyimpan profil TANPA menyentuh tingkatnya tak mengembalikannya ke Eselon I", async () => {
  await bukaProfil(LAPAS);
  await userEvent.click(screen.getByTestId("satker-form-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalled());
  expect(axios.put.mock.calls[0][1].eselon_satker).toBe("3");
});

test("tingkat yang dipilih ikut terkirim", async () => {
  const pilih = await bukaProfil(LAPAS);
  await userEvent.selectOptions(pilih, "2");
  await userEvent.click(screen.getByTestId("satker-form-simpan"));
  await waitFor(() => expect(axios.put).toHaveBeenCalled());
  expect(axios.put.mock.calls[0][1].eselon_satker).toBe("2");
});

test("pilihannya menyebut contoh satker nyata, bukan angka telanjang", async () => {
  // "Eselon III" saja tak memberi tahu siapa pun bahwa Lapas termasuk di
  // dalamnya; yang mengisi layar ini adalah admin satker, bukan penyusun
  // peraturan organisasi.
  const pilih = await bukaProfil(LAPAS);
  const teks = [...pilih.options].map((o) => o.textContent).join(" | ");
  expect(teks).toMatch(/Lapas/);
  expect(teks).toMatch(/Kantor Wilayah/);
  expect(teks).toMatch(/bawaan/);
});
