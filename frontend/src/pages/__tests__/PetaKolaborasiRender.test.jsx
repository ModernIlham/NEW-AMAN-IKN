/**
 * Uji render Peta Kolaborasi — backlog #346 (mock Leaflet + WS + IDB).
 *
 * Halaman ini pernah mati DUA KALI tanpa satu pun uji memerah:
 *   - `kirimGeserRef` dipakai tanpa pernah dideklarasikan (fitur "tamu
 *     menggeser marker" mati di langkah terakhir);
 *   - tombol "Muat ulang" melepas wadah peta dan menyisakan kotak putih.
 * Keduanya kelas cacat "komponen gagal berdiri / cabang mati saat dijalankan"
 * yang tak terlihat oleh uji statis pembaca teks. Berkas ini me-MOUNT
 * halamannya sungguhan di jsdom: Leaflet ditukar tiruan berantai
 * (lefletPalsu), jaringan ditukar mock axios, dan API peramban yang tak ada
 * di jsdom (WebSocket, IndexedDB) dipasang lewat lingkunganPeta.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import {
  pasangIndexedDbPalsu,
  pasangWebSocketPalsu,
} from "../../uji/lingkunganPeta";
import PetaKolaborasiPage from "../PetaKolaborasiPage";

jest.mock("leaflet", () => require("../../uji/lefletPalsu"));
jest.mock("leaflet.markercluster", () => ({}));
jest.mock("axios");

const DATA_PETA = {
  nama_kegiatan: "Inventarisasi Gedung Sekretariat",
  aset: [
    { id: "aset-1", asset_name: "Kursi Rapat", lat: -1.4001, lng: 116.7001,
      status: "Aktif", condition: "Baik", category: "Peralatan dan Mesin" },
  ],
  titik_kolaborasi: [
    { id: "titik-1", nama_titik: "Usulan titik baru", lat: -1.4002,
      lng: 116.7002 },
  ],
  komentar: [],
  boleh_moderasi: false,
  tamu: true,
};

beforeAll(() => {
  pasangWebSocketPalsu();
  pasangIndexedDbPalsu();
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

beforeEach(() => {
  // CRA menyetel resetMocks: true — implementasi mock DIBUANG sebelum tiap
  // uji, jadi wajib dipasang ulang di sini, bukan sekali di atas berkas.
  window.history.pushState({}, "", "/peta/kolaborasi/peta-uji-1?token=tok-1");
  axios.get.mockImplementation((url) => {
    const u = String(url);
    if (/\/peta\/kolaborasi\/[^/]+$/.test(u)) {
      return Promise.resolve({ data: DATA_PETA });
    }
    if (u.includes("/usulan")) {
      return Promise.resolve({ data: { items: [] } });
    }
    return Promise.resolve({ data: {} });
  });
  axios.post.mockResolvedValue({ data: {} });
});

test("halaman berdiri dari URL publik: memuat data lalu menampilkan kegiatan", async () => {
  render(<PetaKolaborasiPage />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  // Data termuat → nama kegiatan tampil di kepala halaman.
  expect(await screen.findByText("Inventarisasi Gedung Sekretariat"))
    .toBeInTheDocument();
  // Toolbar peta ikut berdiri — bukan sekadar layar pemuat yang bertahan.
  expect(screen.getByTestId("peta-kolab-filter")).toBeInTheDocument();
  expect(screen.getByTestId("peta-kolab-cluster")).toBeInTheDocument();
});

test("id memanggil endpoint yang benar dengan token dari query string", async () => {
  render(<PetaKolaborasiPage />);
  await waitFor(() => expect(axios.get).toHaveBeenCalled());
  const [url, cfg] = axios.get.mock.calls[0];
  expect(url).toMatch(/\/peta\/kolaborasi\/peta-uji-1$/);
  expect(cfg.params).toEqual(expect.objectContaining({ token: "tok-1" }));
});

test("galat server tampil sebagai pesan, bukan layar putih", async () => {
  axios.get.mockRejectedValue({
    response: { data: { detail: "Masa tayang peta telah berakhir" } },
  });
  render(<PetaKolaborasiPage />);
  expect(await screen.findByText("Masa tayang peta telah berakhir"))
    .toBeInTheDocument();
});

test("tanpa id di URL: berhenti dengan pesan, tanpa satu pun permintaan jaringan", async () => {
  window.history.pushState({}, "", "/halaman-lain");
  render(<PetaKolaborasiPage />);
  expect(await screen.findByText(/Link peta tidak lengkap/)).toBeInTheDocument();
  expect(axios.get).not.toHaveBeenCalled();
});
