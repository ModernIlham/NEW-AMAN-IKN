/**
 * UJI RENDER PERTAMA di repo ini (backlog #320).
 *
 * Sampai sekarang seluruh 741 uji bersifat STATIS: ia membaca berkas `.jsx`
 * sebagai teks dan mencocokkan pola. Penjaga semacam itu berharga — ia
 * menangkap kelas cacat yang tak terlihat saat membaca kode — tetapi ia buta
 * pada satu hal yang paling sering menjatuhkan halaman: komponennya gagal
 * dirender sama sekali.
 *
 * Dua kejadian nyata di repo ini membuktikannya:
 *   - Peta Aset tayang sebagai layar kosong ("Cannot access before
 *     initialization"); lint bersih, build sukses.
 *   - `kirimGeserRef` di Peta Kolaborasi dipakai tanpa pernah dideklarasikan,
 *     mematikan fitur "tamu menggeser marker" tepat di langkah terakhir; 741
 *     uji hijau, semuanya diam.
 *
 * Berkas ini mulai menutup celah itu pada komponen yang dipakai TUJUH halaman
 * modul siklus, dan sekaligus menguji satu klaim yang sebelumnya hanya bisa
 * saya tulis sebagai "perlu dicoba di perangkat nyata": butir menu "Tanggal
 * acuan" benar-benar memanggil pemilih tanggal.
 */
import React, { useRef } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MenuKepala from "@/components/ui/MenuKepala";
import TanggalanButton from "@/components/ui/TanggalanButton";

// `downloadFileWithProgress` menembak jaringan & DOM download — di sini yang
// diuji adalah "butirnya ada dan memanggil unduhan yang BENAR", bukan
// unduhannya sendiri.
// Awalan `mock` wajib: jest melarang factory-nya menyentuh variabel luar
// kecuali yang bernama mock* — pengaman terhadap mock yang belum terinisialisasi.
const mockUnduh = jest.fn();
jest.mock("@/lib/downloadFile", () => ({
  downloadFileWithProgress: (...a) => mockUnduh(...a),
}));

// Radix membuka menunya lewat pointer event yang tak lengkap di jsdom.
beforeAll(() => {
  if (!window.HTMLElement.prototype.hasPointerCapture) {
    window.HTMLElement.prototype.hasPointerCapture = () => false;
    window.HTMLElement.prototype.setPointerCapture = () => {};
    window.HTMLElement.prototype.releasePointerCapture = () => {};
  }
  window.HTMLElement.prototype.scrollIntoView = () => {};
});

// CRA menyetel `resetMocks: true`. Implementasi yang dipasang saat jest.fn()
// dibuat DIBUANG sebelum tiap uji — mock-nya lalu mengembalikan `undefined`,
// dan `.catch()` di kode produksi meledak. Jadi implementasinya dipasang ulang
// di sini, bukan sekali di atas.
beforeEach(() => { mockUnduh.mockImplementation(() => Promise.resolve()); });

/** Buka menunya seperti pengguna: tekan pemicunya. */
async function bukaMenu(testid) {
  await userEvent.click(screen.getByTestId(testid));
  await waitFor(() => expect(screen.getByRole("menu")).toBeInTheDocument());
}

const EKSPOR_WASDAL = [
  { judul: "Periode berjalan (semesteran)", url: "/api/wasdal/laporan-pdf",
    nama: "Laporan_Wasdal.pdf", label: "Laporan Hasil Pemantauan Wasdal",
    testid: "wasdal-laporan" },
  { judul: "Tahunan (Lampiran PMK 207)", url: "/api/wasdal/laporan-tahunan-pdf",
    nama: "Laporan_Tahunan_Wasdal.pdf", label: "Laporan Tahunan Wasdal",
    testid: "wasdal-laporan-tahunan" },
];

describe("MenuKepala benar-benar dirender, bukan hanya lolos regex", () => {
  test("terpasang tanpa melempar — pemicunya ada di DOM", () => {
    render(<MenuKepala modul="wasdal" ekspor={EKSPOR_WASDAL}
      booking={{ jenisNaskah: "Laporan", referensi: "Laporan Wasdal" }} />);
    expect(screen.getByTestId("wasdal-menu")).toBeInTheDocument();
  });

  test("DUA unduhan muncul — larik `ekspor` benar-benar dipetakan", async () => {
    // Uji statis hanya bisa melihat ada `.map(`; ini melihat hasilnya.
    render(<MenuKepala modul="wasdal" ekspor={EKSPOR_WASDAL} />);
    await bukaMenu("wasdal-menu");
    expect(screen.getByTestId("wasdal-laporan")).toBeInTheDocument();
    expect(screen.getByTestId("wasdal-laporan-tahunan")).toBeInTheDocument();
    expect(screen.getByText("Tahunan (Lampiran PMK 207)")).toBeInTheDocument();
  });

  test("satu objek `ekspor` (bukan larik) tetap bekerja — lima halaman lama", async () => {
    render(<MenuKepala modul="penganggaran"
      ekspor={{ url: "/api/penganggaran/export", nama: "register.csv",
        label: "Register", judul: "Unduh Register (CSV)" }} />);
    await bukaMenu("penganggaran-menu");
    expect(screen.getByTestId("penganggaran-export")).toBeInTheDocument();
  });

  test("menekan butir ekspor memanggil unduhan yang BENAR", async () => {
    render(<MenuKepala modul="wasdal" ekspor={EKSPOR_WASDAL} />);
    await bukaMenu("wasdal-menu");
    await userEvent.click(screen.getByTestId("wasdal-laporan-tahunan"));
    await waitFor(() => expect(mockUnduh).toHaveBeenCalledTimes(1));
    expect(mockUnduh).toHaveBeenCalledWith(
      "/api/wasdal/laporan-tahunan-pdf", "Laporan_Tahunan_Wasdal.pdf",
      { label: "Laporan Tahunan Wasdal" });
  });

  test("kategori kosong tak menyisakan label menggantung", async () => {
    // Hanya ekspor, tanpa booking & tanpa aksi → "Dokumen & Nomor" dan
    // "Tindakan" tak boleh muncul sebagai judul tanpa isi.
    render(<MenuKepala modul="wasdal" ekspor={EKSPOR_WASDAL} />);
    await bukaMenu("wasdal-menu");
    expect(screen.queryByText(/Dokumen & Nomor/)).not.toBeInTheDocument();
    expect(screen.queryByText("Tindakan")).not.toBeInTheDocument();
    expect(screen.getByText("Ekspor")).toBeInTheDocument();
  });

  test("butir `aksi` benar-benar memanggil handler-nya", async () => {
    const tekan = jest.fn();
    render(<MenuKepala modul="wasdal"
      aksi={[{ id: "reload", label: "Muat ulang", onSelect: tekan }]} />);
    await bukaMenu("wasdal-menu");
    expect(screen.getByText("Tindakan")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("wasdal-menu-reload"));
    await waitFor(() => expect(tekan).toHaveBeenCalledTimes(1));
  });
});

describe("TanggalanButton — klaim yang dulu hanya bisa ditulis, kini diuji", () => {
  function Bungkus({ kelasTombol = "" }) {
    const ref = useRef(null);
    return (
      <>
        <button type="button" data-testid="pemicu"
          onClick={() => ref.current?.buka()}>Tanggal acuan</button>
        <TanggalanButton ref={ref} kelasTombol={kelasTombol}
          value="2026-08-08" onChange={() => {}} testid="tgl" />
      </>
    );
  }

  test("input tanggal TETAP terpasang meski tombolnya disembunyikan", () => {
    // Inilah inti perbaikannya: `hidden sm:flex` hanya boleh mengenai TOMBOL.
    // Bila seluruh komponen yang disembunyikan, pemilih tanggalnya ikut lenyap
    // dan butir menu di HP jadi tombol mati.
    render(<Bungkus kelasTombol="hidden sm:flex" />);
    expect(screen.getByTestId("tgl")).toHaveClass("hidden");
    expect(screen.getByTestId("tgl-input")).toBeInTheDocument();
    expect(screen.getByTestId("tgl-input")).not.toHaveClass("hidden");
  });

  test("buka() lewat ref memanggil pemilih tanggal native", () => {
    const input = jest.fn();
    window.HTMLInputElement.prototype.showPicker = input;
    render(<Bungkus kelasTombol="hidden sm:flex" />);
    fireEvent.click(screen.getByTestId("pemicu"));
    expect(input).toHaveBeenCalledTimes(1);
    delete window.HTMLInputElement.prototype.showPicker;
  });

  test("jatuh ke click() bila showPicker melempar", () => {
    window.HTMLInputElement.prototype.showPicker = () => {
      throw new Error("NotAllowedError");
    };
    render(<Bungkus />);
    const el = screen.getByTestId("tgl-input");
    const klik = jest.spyOn(el, "click");
    fireEvent.click(screen.getByTestId("pemicu"));
    expect(klik).toHaveBeenCalledTimes(1);
    delete window.HTMLInputElement.prototype.showPicker;
  });

  test("jatuh ke click() bila showPicker tak ada sama sekali", () => {
    render(<Bungkus />);
    const el = screen.getByTestId("tgl-input");
    const klik = jest.spyOn(el, "click");
    fireEvent.click(screen.getByTestId("pemicu"));
    expect(klik).toHaveBeenCalledTimes(1);
  });

  test("menampilkan bulan, tanggal, dan tahun dari nilainya", () => {
    render(<Bungkus />);
    const tombol = screen.getByTestId("tgl");
    expect(tombol).toHaveTextContent("08");
    expect(tombol).toHaveTextContent("2026");
  });
});
