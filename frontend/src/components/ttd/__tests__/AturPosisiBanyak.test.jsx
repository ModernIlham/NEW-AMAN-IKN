/**
 * Satu penanda tangan, BANYAK pembubuhan.
 *
 * Permintaan pemilik: *"pastikan TTD elektronik dapat melakukan penandatanganan
 * lebih sesuai jumlah yang harus dia tandatangani — sebagai contoh BAST
 * operasional ini, di mana terdapat tanda tangan lagi di lembar berikutnya di
 * surat pernyataan."*
 *
 * Bagian yang paling mudah rusak tanpa terlihat: tombol "Tanda tangan lagi"
 * MENYIMPAN letak yang sedang diatur, lalu letak berikutnya dikirim BERSAMA
 * yang tersimpan itu. Tombol yang menyimpan tapi tak pernah mengirimkannya
 * membuat lembar kedua terbit kosong — dan layarnya tetap tampak benar.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AturPosisiTtd from "../AturPosisiTtd";

const PNG = "data:image/png;base64,iVBORw0KGgo=";

function pasang(props = {}) {
  const onKirim = jest.fn();
  render(
    <AturPosisiTtd
      jenis="ttd" banyak jumlahHalaman={4} pngTtd={PNG}
      bangunUrlHalaman={(hal) => `/uji/${hal}.png?token=uji`}
      onKirim={onKirim} onBatal={() => {}} {...props} />);
  // Pratinjau halaman dimuat lewat <img>; tombol terkunci sampai ia siap.
  const gambar = document.querySelector("img");
  if (gambar) fireEvent.load(gambar);
  return onKirim;
}

describe("Pembubuhan tambahan", () => {
  test("tombol 'Tanda tangan lagi' hadir hanya pada mode banyak", () => {
    pasang();
    expect(screen.getByTestId("posisi-tambah")).toBeInTheDocument();
  });

  test("mode tunggal TIDAK menampilkannya", () => {
    pasang({ banyak: false });
    expect(screen.queryByTestId("posisi-tambah")).not.toBeInTheDocument();
  });

  test("tanpa menambah, kirim membawa daftar KOSONG — bukan undefined", () => {
    // `undefined` lolos ke payload dan server menerimanya sebagai "tak ada
    // kolom", yang kebetulan benar hari ini — dan diam-diam salah begitu
    // servernya membedakan "kosong" dari "tak dikirim".
    const onKirim = pasang();
    fireEvent.click(screen.getByTestId("posisi-kirim"));
    expect(onKirim).toHaveBeenCalledTimes(1);
    expect(onKirim.mock.calls[0][1]).toEqual([]);
  });

  test("menambah satu letak lalu kirim membawa KEDUANYA", () => {
    const onKirim = pasang();
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    fireEvent.click(screen.getByTestId("posisi-kirim"));
    const [utama, lain] = onKirim.mock.calls[0];
    expect(lain).toHaveLength(1);
    expect(utama).toHaveProperty("halaman");
    expect(lain[0]).toHaveProperty("halaman");
  });

  test("daftar tampil beserta jumlah total yang akan dibubuhkan", () => {
    pasang();
    expect(screen.queryByTestId("posisi-daftar")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    expect(screen.getByTestId("posisi-daftar")).toHaveTextContent(
      "2 tanda tangan akan dibubuhkan");
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    expect(screen.getByTestId("posisi-daftar")).toHaveTextContent(
      "3 tanda tangan akan dibubuhkan");
  });

  test("letak yang tersimpan bisa DIBATALKAN satu per satu", () => {
    const onKirim = pasang();
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    fireEvent.click(screen.getByTestId("posisi-hapus-0"));
    fireEvent.click(screen.getByTestId("posisi-kirim"));
    expect(onKirim.mock.calls[0][1]).toHaveLength(1);
  });

  test("tombol kirim menyebutkan berapa yang akan dibubuhkan", () => {
    pasang();
    expect(screen.getByTestId("posisi-kirim"))
      .toHaveTextContent("Bubuhkan di Posisi Ini");
    fireEvent.click(screen.getByTestId("posisi-tambah"));
    expect(screen.getByTestId("posisi-kirim"))
      .toHaveTextContent("Bubuhkan 2 Tanda Tangan");
  });
});
