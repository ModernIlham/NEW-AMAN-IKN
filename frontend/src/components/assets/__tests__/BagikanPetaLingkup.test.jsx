/**
 * Bagikan Peta Kolaboratif — LINGKUP yang dibagikan.
 *
 * Permintaan pemilik: *"ketika filter dan seleksi aktif, pada saat dibuat
 * Bagikan Peta Kolaboratif, berarti hanya titik-titik itu saja yang dibagikan
 * dan tidak semua titik. tolong berikan informasi jumlahnya juga agar tahu
 * berapa aset titik yang ada di dalam peta-peta yang dibagikan."*
 *
 * Dua hal yang dijaga di sini, dan keduanya pernah tidak ada:
 *   1. daftar id benar-benar IKUT saat peta sedang disempitkan — tanpa itu
 *      tautan membagikan seluruh aset kegiatan;
 *   2. jumlahnya TERBACA sebelum tombol ditekan, sebab itulah keputusan yang
 *      sedang diambil operator.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";
import BagikanPetaDialog from "../BagikanPetaDialog";

jest.mock("axios");
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const KEGIATAN = { id: "keg-1", nama: "Inventarisasi Uji" };

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: { items: [], diarsipkan: 0 } });
  axios.post.mockResolvedValue({ data: { id: "s1", link: "https://x/p" } });
  Object.assign(navigator, { clipboard: { writeText: jest.fn().mockResolvedValue() } });
});

function buka(lingkup) {
  return render(
    <BagikanPetaDialog open onClose={() => {}} activity={KEGIATAN} lingkup={lingkup} />);
}

test("tanpa penyempit: dinyatakan seluruh titik, dan asset_ids TIDAK dikirim", async () => {
  buka({ ids: null, jumlah: 12, total: 12, disempitkan: false, sebab: "" });
  await waitFor(() => expect(screen.getByTestId("bagikan-lingkup")).toBeInTheDocument());
  expect(screen.getByTestId("bagikan-lingkup").textContent).toMatch(/seluruh titik/i);

  screen.getByTestId("bagikan-buat").click();
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  const body = axios.post.mock.calls[0][1];
  // Membekukan daftar tanpa diminta akan menghentikan aset baru ikut tampil.
  expect(body.asset_ids).toBeUndefined();
});

test("seleksi aktif: jumlahnya tampil dan asset_ids dikirim", async () => {
  buka({ ids: ["a1", "a2", "a3"], jumlah: 3, total: 40,
         disempitkan: true, sebab: "seleksi" });
  const kotak = await screen.findByTestId("bagikan-lingkup");
  expect(kotak.textContent).toMatch(/3/);
  expect(kotak.textContent).toMatch(/yang dipilih/i);
  // Totalnya disebut supaya terbaca berapa yang TIDAK ikut.
  expect(kotak.textContent).toMatch(/40/);

  screen.getByTestId("bagikan-buat").click();
  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(axios.post.mock.calls[0][1].asset_ids).toEqual(["a1", "a2", "a3"]);
});

test("hasil filter disebut sebabnya, bukan sekadar 'terpilih'", async () => {
  buka({ ids: ["a1"], jumlah: 1, total: 9, disempitkan: true, sebab: "filter" });
  const kotak = await screen.findByTestId("bagikan-lingkup");
  expect(kotak.textContent).toMatch(/hasil filter/i);
});

test("paging terpotong diberitahukan — yang belum termuat tidak ikut", async () => {
  buka({ ids: ["a1"], jumlah: 1, total: 9000, disempitkan: true,
         sebab: "filter", terpotong: true });
  expect(await screen.findByTestId("bagikan-lingkup-terpotong")).toBeInTheDocument();
});

test("nol titik: tombol dimatikan, bukan menerbitkan peta kosong", async () => {
  buka({ ids: [], jumlah: 0, total: 9, disempitkan: true, sebab: "filter" });
  expect(await screen.findByTestId("bagikan-lingkup-kosong")).toBeInTheDocument();
  expect(screen.getByTestId("bagikan-buat")).toBeDisabled();
});

test("daftar link menyebut jumlah titik tiap tautan", async () => {
  axios.get.mockResolvedValue({ data: { diarsipkan: 0, items: [
    { id: "s1", judul: "Terfilter", link: "https://x/1", status: "aktif",
      berlaku_sampai: new Date(Date.now() + 864e5).toISOString(),
      lingkup: "terpilih", jumlah_titik_dibagikan: 7, jumlah_kontribusi: 2 },
    { id: "s2", judul: "Semua", link: "https://x/2", status: "aktif",
      berlaku_sampai: new Date(Date.now() + 864e5).toISOString(),
      lingkup: "semua", jumlah_titik_dibagikan: null, jumlah_kontribusi: 0 },
  ] } });
  buka(null);
  // Dua tautan pada kegiatan yang sama tampak identik tanpa angka ini.
  const s1 = await screen.findByTestId("bagikan-item-s1");
  expect(s1.textContent).toMatch(/7\s*titik dibagikan/i);
  const s2 = screen.getByTestId("bagikan-item-s2");
  expect(s2.textContent).toMatch(/seluruh titik kegiatan/i);
});
