/**
 * Pemeriksaan akhir sebelum membubuhkan tanda tangan.
 *
 * Laporan pemilik: *"ketika link bubuhkan tanda tangan diterima penanda
 * tangan, sering kali penandatangan tidak melihat semua halaman terkait
 * padahal ada lebih dari 1 kali tanda tangan yang seharusnya dia
 * tandatangani, tapi dia tidak memperhatikan dan langsung mengklik
 * membubuhkan tanpa mengecek ulang."*
 *
 * Penahanan jumlah yang sudah ada hanya bekerja bila pemilik dokumen
 * MENDEKLARASIKAN jumlahnya. Bila ia lupa — dan bawaannya 1 — tak ada apa pun
 * yang menahan. Pemeriksaan akhir ini menutup celah itu tanpa menuntut
 * deklarasi apa pun: pada detik tombol ditekan, layar BERGANTI menjadi daftar
 * halaman — mana yang akan tertanda tangan, mana yang tidak, dan mana yang
 * belum pernah dibuka.
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
  muat();
  return onKirim;
}

const muat = () => {
  const g = document.querySelector("img");
  if (g) fireEvent.load(g);
};
const bubuh = () => fireEvent.click(screen.getByTestId("posisi-kirim"));
const mundur = () => {
  fireEvent.click(screen.getByLabelText("Halaman sebelumnya"));
  muat();
};

it("menekan Bubuhkan TIDAK langsung mengirim — layar berganti dulu", () => {
  const onKirim = pasang();
  bubuh();
  expect(onKirim).not.toHaveBeenCalled();
  expect(screen.getByTestId("periksa-akhir")).toBeInTheDocument();
});

it("menyebut halaman yang TIDAK akan tertanda tangan", () => {
  pasang();                       // mulai di halaman 4 (terakhir)
  bubuh();
  expect(screen.getByTestId("periksa-tanpa-ttd")).toHaveTextContent("1, 2, 3");
});

it("menyebut halaman yang BELUM PERNAH dibuka", () => {
  // Inilah yang mengubah "saya kira sudah semua" jadi "saya belum lihat".
  pasang();
  bubuh();
  expect(screen.getByTestId("periksa-belum-dibuka")).toHaveTextContent("1, 2, 3");
});

it("halaman yang DILEWATI tanpa ttd tetap terhitung sudah dibuka", () => {
  // Uji ini sempat ditulis dengan berhenti di halaman 3 — dan LOLOS meski
  // pencatatan "sudah dibuka" dicabut, karena halaman yang sedang diatur
  // selalu punya kotak dan otomatis terhitung ber-ttd. Yang benar-benar
  // membedakan adalah halaman yang DILEWATI: dibuka, lalu ditinggalkan.
  pasang();                       // mulai di halaman 4
  mundur();                       // lewati halaman 3
  mundur();                       // berhenti di halaman 2 (di sinilah ttd-nya)
  bubuh();
  const teks = screen.getByTestId("periksa-belum-dibuka").textContent;
  expect(teks).toContain("1");
  expect(teks).not.toContain("3");   // dibuka sekilas, tetap terhitung
});

it("semua halaman terbuka → peringatan itu hilang sama sekali", () => {
  pasang();
  mundur(); mundur(); mundur();   // 3, 2, 1
  bubuh();
  expect(screen.queryByTestId("periksa-belum-dibuka")).not.toBeInTheDocument();
});

it("'Periksa lagi' mengembalikan ke pengaturan tanpa mengirim", () => {
  const onKirim = pasang();
  bubuh();
  fireEvent.click(screen.getByTestId("periksa-kembali"));
  expect(onKirim).not.toHaveBeenCalled();
  expect(screen.getByTestId("atur-posisi-ttd")).toBeInTheDocument();
});

it("'Ya, bubuhkan sekarang' barulah mengirim — beserta letak tersimpan", () => {
  const onKirim = pasang();
  fireEvent.click(screen.getByTestId("posisi-tambah"));   // simpan hal. 4
  mundur();                                              // ke hal. 3
  bubuh();
  fireEvent.click(screen.getByTestId("periksa-lanjut"));
  expect(onKirim).toHaveBeenCalledTimes(1);
  expect(onKirim.mock.calls[0][0].halaman).toBe(3);
  expect(onKirim.mock.calls[0][1]).toHaveLength(1);
});

it("halaman ber-ttd ikut terhitung sudah dilihat", () => {
  const onKirim = pasang();
  fireEvent.click(screen.getByTestId("posisi-tambah"));   // ttd di hal. 4
  mundur();                                              // atur di hal. 3
  bubuh();
  const teks = screen.getByTestId("periksa-belum-dibuka").textContent;
  expect(teks).not.toContain("4");
  expect(onKirim).not.toHaveBeenCalled();
});

it("dokumen SATU halaman tak diperiksa — langsung terkirim", () => {
  // Tak ada halaman lain untuk terlewat. Konfirmasi di sana hanya melatih
  // orang menekan "Ya" tanpa membaca.
  const onKirim = pasang({ jumlahHalaman: 1 });
  bubuh();
  expect(onKirim).toHaveBeenCalledTimes(1);
  expect(screen.queryByTestId("periksa-akhir")).not.toBeInTheDocument();
});

it("peran QR tak pernah diperiksa — ia bukan tanda tangan", () => {
  const onKirim = jest.fn();
  render(
    <AturPosisiTtd jenis="qr" jumlahHalaman={4}
      bangunUrlHalaman={(h) => `/uji/${h}.png?token=uji`}
      onKirim={onKirim} onBatal={() => {}} />);
  muat();
  bubuh();
  expect(onKirim).toHaveBeenCalledTimes(1);
});
