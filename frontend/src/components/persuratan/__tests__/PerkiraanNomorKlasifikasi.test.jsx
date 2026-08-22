/**
 * Pemilih Kode Klasifikasi Arsip pada booking nomor OTOMATIS lintas modul.
 *
 * Keluhan pemilik: *"ketika buat BAST dan klik nomor otomatis dari registrasi
 * persuratan, bagian klasifikasi arsip tidak ada dan tidak ada pilihan memilih
 * klasifikasi arsip yang ada."*
 *
 * Dua hal yang perlu diuji dan tak terlihat dari membaca kode:
 *
 *   1. Kode yang dipilih benar-benar IKUT ke permintaan pratinjau. Kolom yang
 *      terlihat tapi tak menyetir apa pun adalah bentuk kegagalan yang paling
 *      menyesatkan — layarnya tampak sudah diperbaiki.
 *   2. Halaman yang TIDAK memakai pemilih tetap seperti sebelumnya. Komponen
 *      ini dipakai empat halaman; menyalakan kolom baru untuk semuanya
 *      sekaligus akan menambah kolom di tempat yang tak memintanya.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import PerkiraanNomor from "../PerkiraanNomor";

jest.mock("axios");

const PRATINJAU = {
  nomor: "B-001/PL.02/OIKN/VIII/2026",
  kode_klasifikasi: "PL.02",
  sumber_klasifikasi: "pemetaan",
};
const KATALOG = { items: [
  { id: "k1", kode: "PL.02", uraian: "Pengelolaan BMN" },
  { id: "k2", kode: "UM.01", uraian: "Ketatausahaan" },
] };

beforeEach(() => {
  axios.get.mockImplementation((url) => Promise.resolve({
    data: String(url).includes("/persuratan/klasifikasi") ? KATALOG : PRATINJAU,
  }));
});

const urlPratinjau = () => (axios.get.mock.calls
  .map((c) => String(c[0])).filter((u) => u.includes("pratinjau-nomor")).pop() || "");

describe("Tanpa onKlasifikasi — perilaku lama, tak berubah", () => {
  test("hanya perkiraan nomor, tanpa kolom klasifikasi", async () => {
    render(<PerkiraanNomor aktif modul="penggunaan" jenisNaskah="Berita Acara"
      tanggal="2026-08-19" testId="pra" />);
    expect(await screen.findByTestId("pra")).toHaveTextContent(PRATINJAU.nomor);
    expect(screen.queryByTestId("pra-klasifikasi")).not.toBeInTheDocument();
  });

  test("katalog kode TIDAK ikut diminta — halaman itu tak membutuhkannya", async () => {
    render(<PerkiraanNomor aktif modul="penggunaan" jenisNaskah="Berita Acara"
      testId="pra" />);
    await screen.findByTestId("pra");
    const katalog = axios.get.mock.calls
      .map((c) => String(c[0])).filter((u) => u.includes("/persuratan/klasifikasi"));
    expect(katalog).toEqual([]);
  });

  test("tidak aktif → tak merender apa pun", () => {
    const { container } = render(
      <PerkiraanNomor aktif={false} modul="penggunaan" testId="pra" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Dengan onKlasifikasi — kolomnya hadir dan menyetir", () => {
  const props = {
    aktif: true, modul: "penggunaan", jenisNaskah: "Berita Acara",
    tanggal: "2026-08-19", testId: "pra",
  };

  test("kolom, katalog, dan asal kodenya tampil", async () => {
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={() => {}} />);
    expect(await screen.findByTestId("pra-klasifikasi")).toBeInTheDocument();
    await waitFor(() => expect(
      screen.getByTestId("pra-sumber-klasifikasi")
    ).toHaveTextContent("PL.02 · otomatis dari aturan pemetaan"));
  });

  test("kode otomatis muncul sebagai placeholder, bukan sebagai isian", async () => {
    // Menuliskannya sebagai NILAI akan memakukan kode hasil aturan ke dalam
    // dokumen; begitu aturannya diubah, dokumen ini diam-diam tak ikut.
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={() => {}} />);
    const kolom = await screen.findByTestId("pra-klasifikasi");
    await waitFor(() => expect(kolom).toHaveAttribute("placeholder", "otomatis: PL.02"));
    expect(kolom).toHaveValue("");
  });

  test("mengetik kode meneruskannya ke pemanggil", async () => {
    const ubah = jest.fn();
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={ubah} />);
    await userEvent.type(await screen.findByTestId("pra-klasifikasi"), "U");
    expect(ubah).toHaveBeenCalledWith("U");
  });

  test("kode terpilih IKUT ke permintaan pratinjau", async () => {
    // Inilah bedanya kolom yang bekerja dengan kolom yang cuma terlihat.
    render(<PerkiraanNomor {...props} klasifikasi="UM.01" onKlasifikasi={() => {}} />);
    await screen.findByTestId("pra-klasifikasi");
    await waitFor(() => expect(urlPratinjau()).toMatch(/kode_klasifikasi=UM\.01/));
  });

  test("kosong tetap dikirim kosong — server yang memutuskan aturannya", async () => {
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={() => {}} />);
    await screen.findByTestId("pra-klasifikasi");
    await waitFor(() => expect(urlPratinjau()).toMatch(/kode_klasifikasi=(&|$)/));
  });

  test("katalog kode dimuat untuk daftar pilihannya", async () => {
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={() => {}} />);
    await screen.findByTestId("pra-klasifikasi");
    await waitFor(() => expect(screen.getByText("Pengelolaan BMN")).toBeInTheDocument());
  });

  test("katalog gagal dimuat tidak mematikan kolomnya", async () => {
    // Kolomnya tetap bisa diketik manual — daftar pilihan itu kemudahan,
    // bukan syarat.
    axios.get.mockImplementation((url) => (
      String(url).includes("/persuratan/klasifikasi")
        ? Promise.reject(new Error("gagal"))
        : Promise.resolve({ data: PRATINJAU })));
    render(<PerkiraanNomor {...props} klasifikasi="" onKlasifikasi={() => {}} />);
    expect(await screen.findByTestId("pra-klasifikasi")).toBeInTheDocument();
  });
});
