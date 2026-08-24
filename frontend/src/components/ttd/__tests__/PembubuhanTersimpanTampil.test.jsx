/**
 * Pembubuhan yang SUDAH tersimpan tetap terlihat saat halamannya dibuka lagi.
 *
 * Laporan pemilik: *"apabila sudah menentukan posisi tanda tangan, saat
 * di-next halaman berikutnya dan kembali lagi ke halaman tanda tangan, lokasi
 * serta ukuran tanda tangan tidak terlihat lagi tampil — tolong buat agar
 * muncul dan pengguna dapat memastikan semua halaman sudah tervisualisasi
 * sesuai pengaturan."*
 *
 * Sebelum ini hanya kotak yang SEDANG diatur yang digambar; letak yang sudah
 * disimpan hanya tercatat sebagai label teks "Halaman 3". Orang yang hendak
 * memeriksa hasil pengaturannya tak punya cara melihatnya sama sekali.
 */
import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import AturPosisiTtd from "../AturPosisiTtd";

const PNG = "data:image/png;base64,iVBORw0KGgo=";

function pasang(props = {}) {
  const onKirim = jest.fn();
  render(
    <AturPosisiTtd
      jenis="ttd" banyak jumlahHalaman={4} pngTtd={PNG}
      bangunUrlHalaman={(hal) => `/uji/${hal}.png?token=uji`}
      onKirim={onKirim} onBatal={() => {}} {...props} />);
  muatHalaman();
  return onKirim;
}

/** Pratinjau halaman dimuat lewat <img>; kotak baru digambar setelah siap. */
function muatHalaman() {
  const gambar = document.querySelector("img");
  if (gambar) fireEvent.load(gambar);
}

const majuHalaman = () => {
  fireEvent.click(screen.getByLabelText("Halaman berikutnya"));
  muatHalaman();
};
const mundurHalaman = () => {
  fireEvent.click(screen.getByLabelText("Halaman sebelumnya"));
  muatHalaman();
};
const simpanLetak = () => fireEvent.click(screen.getByTestId("posisi-tambah"));

it("letak tersimpan MUNCUL kembali saat halamannya dibuka lagi", () => {
  pasang();                      // mulai di halaman 4 (terakhir)
  simpanLetak();                 // simpan letak di halaman 4
  mundurHalaman();               // ke halaman 3
  expect(screen.queryByTestId("posisi-tetap-0")).not.toBeInTheDocument();
  majuHalaman();                 // kembali ke halaman 4
  expect(screen.getByTestId("posisi-tetap-0")).toBeInTheDocument();
});

it("hanya digambar pada HALAMANNYA sendiri", () => {
  pasang();
  simpanLetak();
  mundurHalaman();
  const bayang = screen.queryByTestId("posisi-tetap-0");
  expect(bayang).not.toBeInTheDocument();
});

it("letak & ukurannya sama persis dengan yang disimpan", () => {
  // Bayangan yang digambar di tempat lain justru menyesatkan — orangnya akan
  // mengira tanda tangannya jatuh di posisi yang salah.
  pasang();
  const kotak = screen.getByTestId("posisi-kotak");
  const { left, top, width } = kotak.style;
  simpanLetak();
  const bayang = screen.getByTestId("posisi-tetap-0");
  expect(bayang.style.left).toBe(left);
  expect(bayang.style.top).toBe(top);
  expect(bayang.style.width).toBe(width);
});

it("bayangan TIDAK merampas geser kotak yang sedang diatur", () => {
  // Keduanya bertumpuk persis sesudah disimpan. Bayangan yang menangkap
  // sentuhan membuat tanda tangan aktif mendadak tak bisa dipindahkan, tanpa
  // satu pun tanda kenapa.
  pasang();
  simpanLetak();
  expect(screen.getByTestId("posisi-tetap-0")).toHaveClass("pointer-events-none");
});

it("bayangan diberi label supaya tak tertukar dengan yang sedang diatur", () => {
  pasang();
  simpanLetak();
  expect(within(screen.getByTestId("posisi-tetap-0")).getByText("Tersimpan"))
    .toBeInTheDocument();
});

it("label daftar MELONCAT ke halaman letaknya", () => {
  // "Memastikan semua halaman sudah tervisualisasi" menuntut orangnya bisa
  // melihat tiap letak; menyuruhnya menekan ◀ ▶ berkali-kali untuk itu adalah
  // pekerjaan yang komputer bisa lakukan sekali tekan.
  pasang();
  simpanLetak();                 // tersimpan di halaman 4
  mundurHalaman();
  mundurHalaman();               // sekarang di halaman 2
  expect(screen.getByTestId("posisi-halaman")).toHaveTextContent("Hal. 2/4");
  fireEvent.click(screen.getByTestId("posisi-lihat-0"));
  muatHalaman();
  expect(screen.getByTestId("posisi-halaman")).toHaveTextContent("Hal. 4/4");
  expect(screen.getByTestId("posisi-tetap-0")).toBeInTheDocument();
});

it("menghapus letak juga menghapus bayangannya", () => {
  pasang();
  simpanLetak();
  expect(screen.getByTestId("posisi-tetap-0")).toBeInTheDocument();
  fireEvent.click(screen.getByTestId("posisi-hapus-0"));
  expect(screen.queryByTestId("posisi-tetap-0")).not.toBeInTheDocument();
});

it("beberapa letak pada halaman yang sama digambar semuanya", () => {
  pasang();
  simpanLetak();
  simpanLetak();
  expect(screen.getByTestId("posisi-tetap-0")).toBeInTheDocument();
  expect(screen.getByTestId("posisi-tetap-1")).toBeInTheDocument();
});

it("peran QR tak menggambar bayangan apa pun", () => {
  render(
    <AturPosisiTtd jenis="qr" jumlahHalaman={2}
      bangunUrlHalaman={(h) => `/uji/${h}.png?token=uji`}
      onKirim={() => {}} onBatal={() => {}} />);
  muatHalaman();
  expect(screen.queryByTestId("posisi-tetap-0")).not.toBeInTheDocument();
});
