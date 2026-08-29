/**
 * Tombol "Bubuhkan" DITAHAN selama pembubuhan masih kurang.
 *
 * Laporan pemilik: *"ketika salah satu penanda tangan menandatangani hanya 1
 * lembar yang ia tanda tangani dan sudah memencet tombol bubuhkan, sehingga
 * lembaran yang ada tanda tangan dia lagi di lembar sebelum atau selanjutnya
 * tidak ditandatangani ... jika memiliki banyak penandatangan yang sudah
 * ditandatangani harus mengirim link baru dan meminta tanda tangan ulang."*
 *
 * Kenapa DITAHAN, bukan sekadar diperingatkan: sekali dibubuhkan, tautan
 * sekali-pakai tertutup dan lembar yang terlewat TIDAK bisa ditambahkan lagi.
 * Peringatan yang bisa dilewati akan dilewati — dan biayanya ditanggung
 * semua penanda tangan lain, bukan hanya orang yang melewatinya.
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
  const gambar = document.querySelector("img");
  if (gambar) fireEvent.load(gambar);
  return onKirim;
}

const kirim = () => screen.getByTestId("posisi-kirim");
/** Menekan "Selesai" membuka PEMERIKSAAN AKHIR lebih dulu (dokumen banyak
 *  halaman) — lihat PeriksaSebelumBubuh.test.jsx. Di sini dilewati. */
function bubuhkan() {
  fireEvent.click(kirim());
  const lanjut = screen.queryByTestId("periksa-lanjut");
  if (lanjut) fireEvent.click(lanjut);
}

/** jsdom memberi ukuran 0 pada semua elemen; wadah dipalsukan 200×400. */
function ukurWadah() {
  const wadah = screen.getByTestId("posisi-wadah");
  wadah.getBoundingClientRect = () => ({
    left: 0, top: 0, width: 200, height: 400, right: 200, bottom: 400,
  });
  return wadah;
}

/** Arahkan kotak ke titik piksel lalu TEMPELKAN di sana. Titiknya harus
 *  berbeda tiap kali: dua tempelan pada koordinat identik ditolak sebagai
 *  salah tekan (lihat AturPosisiBanyak.test.jsx). */
let n = 0;
function bubuhLagi() {
  n += 1;
  fireEvent.click(ukurWadah(), { clientX: 20 + n * 25, clientY: 40 + n * 45 });
  fireEvent.click(screen.getByTestId("posisi-bubuh"));
}
beforeEach(() => { n = 0; });

describe("wajib lebih dari satu", () => {
  test("tombol Bubuhkan TERKUNCI selama masih kurang", () => {
    pasang({ wajib: 3 });
    expect(kirim()).toBeDisabled();
  });

  test("menekannya saat terkunci tak mengirim apa pun", () => {
    // Kalau hanya tampilannya yang berubah, kiriman kurang tetap lolos.
    const onKirim = pasang({ wajib: 3 });
    fireEvent.click(kirim());
    expect(onKirim).not.toHaveBeenCalled();
  });

  test("label tombol menyebut BERAPA lagi yang kurang", () => {
    pasang({ wajib: 3 });
    expect(kirim()).toHaveTextContent("Kurang 3 tanda tangan lagi");
  });

  test("terbuka tepat setelah jumlahnya genap", () => {
    const onKirim = pasang({ wajib: 3 });
    bubuhLagi();
    expect(kirim()).toBeDisabled();       // 1 dari 3
    bubuhLagi();
    expect(kirim()).toBeDisabled();       // 2 dari 3
    bubuhLagi();
    expect(kirim()).not.toBeDisabled();   // 3 dari 3
    bubuhkan();
    expect(onKirim).toHaveBeenCalledTimes(1);
    expect(onKirim.mock.calls[0][1]).toHaveLength(2);
  });

  test("panel penjelas tampil SEJAK AWAL, sebelum satu pun ditempel", () => {
    // Justru orang yang TIDAK TAHU dirinya harus meneken beberapa kali yang
    // perlu diberi tahu; menunggu ia menekan tombolnya lebih dulu berarti
    // memberi tahu hanya orang yang sudah tahu.
    pasang({ wajib: 2 });
    expect(screen.getByTestId("posisi-daftar")).toBeInTheDocument();
    expect(screen.getByTestId("posisi-kurang")).toBeInTheDocument();
  });

  test("penjelasnya menerangkan bahwa tautan tertutup sesudah dibubuhkan", () => {
    pasang({ wajib: 2 });
    expect(screen.getByTestId("posisi-kurang")).toHaveTextContent(/tertutup/i);
  });

  test("menghapus satu letak MENGUNCI tombolnya kembali", () => {
    pasang({ wajib: 2 });
    bubuhLagi();
    bubuhLagi();
    expect(kirim()).not.toBeDisabled();
    fireEvent.click(screen.getByTestId("posisi-hapus-0"));
    expect(kirim()).toBeDisabled();
  });
});

describe("wajib satu (bawaan)", () => {
  test("satu tempelan sudah cukup membuka tombolnya", () => {
    // Perilaku LAMA (tombol terbuka sejak awal) sengaja tak dipertahankan:
    // dulu kotak yang sedang diatur ikut terhitung, sehingga menekan tombol
    // tanpa menempel apa pun tetap mengirim. Kini yang belum ditempel memang
    // belum terhitung.
    const onKirim = pasang();
    expect(kirim()).toBeDisabled();
    bubuhLagi();
    expect(kirim()).not.toBeDisabled();
    expect(kirim()).toHaveTextContent("Selesai");
    bubuhkan();
    expect(onKirim).toHaveBeenCalledTimes(1);
  });

  test("panel penjelas tak muncul tanpa sebab", () => {
    pasang();
    expect(screen.queryByTestId("posisi-daftar")).not.toBeInTheDocument();
  });

  test("nilai cacat diperlakukan sebagai satu, bukan mengunci selamanya", () => {
    for (const w of [0, -3, null, undefined, NaN, "abc"]) {
      const { unmount } = render(
        <AturPosisiTtd jenis="ttd" banyak jumlahHalaman={2} pngTtd={PNG}
          bangunUrlHalaman={(h) => `/uji/${h}.png?token=uji`} wajib={w}
          onKirim={() => {}} onBatal={() => {}} />);
      const img = document.querySelector("img");
      if (img) fireEvent.load(img);
      // Nilai cacat => diperlakukan sebagai wajib 1: SATU tempelan cukup,
      // bukan tombol yang terkunci selamanya.
      n = 0;
      bubuhLagi();
      expect(screen.getByTestId("posisi-kirim")).not.toBeDisabled();
      unmount();
    }
  });
});

describe("peran QR tak terpengaruh", () => {
  test("pemilik dokumen tetap bisa menyimpan letak QR", () => {
    const onKirim = jest.fn();
    render(
      <AturPosisiTtd jenis="qr" jumlahHalaman={2}
        bangunUrlHalaman={(h) => `/uji/${h}.png?token=uji`}
        onKirim={onKirim} onBatal={() => {}} />);
    const img = document.querySelector("img");
    if (img) fireEvent.load(img);
    expect(screen.getByTestId("posisi-kirim")).not.toBeDisabled();
  });
});
