/**
 * Satu penanda tangan, BANYAK pembubuhan.
 *
 * Permintaan pemilik: *"pastikan TTD elektronik dapat melakukan penandatanganan
 * lebih sesuai jumlah yang harus dia tandatangani — sebagai contoh BAST
 * operasional ini, di mana terdapat tanda tangan lagi di lembar berikutnya di
 * surat pernyataan."*
 *
 * ALUR BARU (permintaan pemilik berikutnya): *"hilangkan bagian '+ tanda
 * tangan lagi', otomatiskan; jika sudah mengklik 'bubuhkan di posisi ini',
 * jika diklik lagi maka akan tertempel lagi. Dan pastikan ketika sudah selesai
 * bubuhkan bisa memencet tombol 'Selesai' agar tidak terjadi kesalahan
 * mis-konsepsi alur akibat bias makna kata dan fungsi tombol."*
 *
 * Yang paling mudah rusak tanpa terlihat: tempelan kedua dan seterusnya harus
 * benar-benar IKUT TERKIRIM. Tombol yang menempel tapi tak pernah
 * mengirimkannya membuat lembar kedua terbit kosong — dan layarnya tetap
 * tampak benar.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AturPosisiTtd from "../AturPosisiTtd";

const PNG = "data:image/png;base64,iVBORw0KGgo=";

/** "Selesai" pada dokumen banyak halaman membuka PEMERIKSAAN AKHIR lebih
 *  dulu — daftar halaman yang akan & tidak tertanda tangan. Lihat
 *  PeriksaSebelumBubuh.test.jsx; di sini ia sekadar dilewati. */
function selesai() {
  fireEvent.click(screen.getByTestId("posisi-kirim"));
  const lanjut = screen.queryByTestId("periksa-lanjut");
  if (lanjut) fireEvent.click(lanjut);
}

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

/** jsdom memberi ukuran 0 pada semua elemen; wadah dipalsukan 200×400. */
function ukurWadah() {
  const wadah = screen.getByTestId("posisi-wadah");
  wadah.getBoundingClientRect = () => ({
    left: 0, top: 0, width: 200, height: 400, right: 200, bottom: 400,
  });
  return wadah;
}

/** Arahkan kotak ke titik piksel tertentu, lalu tempelkan di sana. */
function bubuhDi(x, y) {
  fireEvent.click(ukurWadah(), { clientX: x, clientY: y });
  fireEvent.click(screen.getByTestId("posisi-bubuh"));
}

describe("Menempel berkali-kali", () => {
  test("tombol penempel hadir untuk peran ttd", () => {
    pasang();
    expect(screen.getByTestId("posisi-bubuh")).toHaveTextContent(
      "Bubuhkan di Posisi Ini");
  });

  test("'Tanda tangan lagi' SUDAH TIDAK ADA", () => {
    // Dua tombol untuk satu pekerjaan, dengan yang salah nama memegang
    // pekerjaan yang salah, adalah sumber mis-konsepsi alurnya.
    pasang();
    expect(screen.queryByTestId("posisi-tambah")).not.toBeInTheDocument();
    // Nama TEPAT, bukan /tanda tangan lagi/i — pola longgar itu juga cocok
    // dengan label "Kurang 1 tanda tangan lagi" pada tombol Selesai, dan
    // ujinya lulus/gagal karena kalimat yang salah.
    expect(screen.queryByRole("button", { name: "Tanda tangan lagi" }))
      .not.toBeInTheDocument();
  });

  test("peran QR tetap satu langkah — tak ada tombol penempel", () => {
    pasang({ jenis: "qr", banyak: false });
    expect(screen.queryByTestId("posisi-bubuh")).not.toBeInTheDocument();
  });

  test("satu tempelan lalu Selesai mengirim tepat satu", () => {
    const onKirim = pasang();
    bubuhDi(60, 120);
    selesai();
    expect(onKirim).toHaveBeenCalledTimes(1);
    const [utama, lain] = onKirim.mock.calls[0];
    expect(utama).toHaveProperty("halaman");
    // `undefined` lolos ke payload dan server menerimanya sebagai "tak ada
    // kolom", yang kebetulan benar hari ini — dan diam-diam salah begitu
    // servernya membedakan "kosong" dari "tak dikirim".
    expect(lain).toEqual([]);
  });

  test("menempel LAGI di titik lain membuat dua, dan KEDUANYA terkirim", () => {
    const onKirim = pasang();
    bubuhDi(60, 120);
    bubuhDi(140, 300);
    selesai();
    const [utama, lain] = onKirim.mock.calls[0];
    expect(utama).toHaveProperty("halaman");
    expect(lain).toHaveLength(1);
    expect(lain[0]).toHaveProperty("halaman");
    // Benar-benar dua TITIK berbeda, bukan objek yang sama dua kali.
    expect(lain[0].x).not.toBeCloseTo(utama.x, 5);
  });

  test("menempel dua kali TANPA memindahkan kotak ditolak dan dijelaskan", () => {
    // Dua tanda tangan bertumpuk persis pada dokumen resmi selalu salah
    // tekan, tak pernah maksud.
    const onKirim = pasang();
    bubuhDi(60, 120);
    expect(screen.queryByTestId("posisi-rangkap")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("posisi-bubuh"));
    expect(screen.getByTestId("posisi-rangkap")).toBeInTheDocument();
    selesai();
    expect(onKirim.mock.calls[0][1]).toEqual([]);
  });

  test("peringatan rangkap hilang begitu kotaknya dipindahkan", () => {
    pasang();
    bubuhDi(60, 120);
    fireEvent.click(screen.getByTestId("posisi-bubuh"));
    expect(screen.getByTestId("posisi-rangkap")).toBeInTheDocument();
    fireEvent.click(ukurWadah(), { clientX: 150, clientY: 320 });
    expect(screen.queryByTestId("posisi-rangkap")).not.toBeInTheDocument();
  });

  test("daftar menyebut jumlah yang akan dibubuhkan", () => {
    pasang();
    expect(screen.queryByTestId("posisi-daftar")).not.toBeInTheDocument();
    bubuhDi(60, 120);
    expect(screen.getByTestId("posisi-daftar")).toHaveTextContent(
      "1 tanda tangan akan dibubuhkan");
    bubuhDi(140, 300);
    expect(screen.getByTestId("posisi-daftar")).toHaveTextContent(
      "2 tanda tangan akan dibubuhkan");
  });

  test("tempelan bisa DIBATALKAN satu per satu", () => {
    const onKirim = pasang();
    bubuhDi(60, 120);
    bubuhDi(140, 300);
    fireEvent.click(screen.getByTestId("posisi-hapus-0"));
    selesai();
    expect(onKirim.mock.calls[0][1]).toEqual([]);
  });
});

describe("Tombol Selesai", () => {
  test("berbunyi Selesai, bukan 'bubuhkan' — kata itu milik penempel", () => {
    pasang();
    bubuhDi(60, 120);
    const kirim = screen.getByTestId("posisi-kirim");
    expect(kirim).toHaveTextContent(/Selesai/);
    expect(kirim).not.toHaveTextContent(/Bubuhkan di Posisi Ini/);
  });

  test("menyebut jumlah yang akan dikirim", () => {
    pasang();
    bubuhDi(60, 120);
    expect(screen.getByTestId("posisi-kirim"))
      .toHaveTextContent("Selesai — kirim 1 tanda tangan");
    bubuhDi(140, 300);
    expect(screen.getByTestId("posisi-kirim"))
      .toHaveTextContent("Selesai — kirim 2 tanda tangan");
  });

  test("TERKUNCI selama belum ada satu pun yang ditempel", () => {
    // Dulu tombol ini mengirim kotak yang sedang diatur meski belum
    // ditempel; kini yang belum ditempel memang belum terhitung, jadi
    // menekannya saat kosong akan mengirim dokumen TANPA tanda tangan.
    const onKirim = pasang();
    const kirim = screen.getByTestId("posisi-kirim");
    expect(kirim).toBeDisabled();
    expect(kirim).toHaveTextContent("Kurang 1 tanda tangan lagi");
    fireEvent.click(kirim);
    expect(onKirim).not.toHaveBeenCalled();
  });
});

describe("Jalur kirim LANGSUNG (dokumen satu halaman)", () => {
  /**
   * CELAH UJI YANG NYARIS LOLOS.
   *
   * Semua uji lain memakai dokumen 4 halaman, sehingga "Selesai" membuka
   * PEMERIKSAAN AKHIR dan pengiriman sebenarnya terjadi di tombol
   * `periksa-lanjut`. Jalur kirim LANGSUNG — dipakai dokumen satu halaman,
   * yang tak diperiksa — karena itu tak pernah tersentuh dengan lebih dari
   * satu tempelan.
   *
   * Mutasi `onKirim(akanDikirim[0], [])` pada jalur itu LOLOS dari 117 uji:
   * tanda tangan kedua dan seterusnya hilang diam-diam, dan dokumen resmi
   * terbit dengan blok tanda tangan kosong. Satu halaman pun bisa memuat dua
   * blok tanda tangan — Berita Acara dan pengesahan di bawahnya.
   */
  test("dua tempelan di SATU halaman terkirim keduanya, tanpa layar periksa", () => {
    const onKirim = pasang({ jumlahHalaman: 1 });
    bubuhDi(60, 120);
    bubuhDi(140, 300);
    fireEvent.click(screen.getByTestId("posisi-kirim"));
    // Dokumen satu halaman sengaja TIDAK diperiksa: tak ada halaman lain
    // untuk terlewat, dan konfirmasi di sana hanya melatih orang menekan
    // "Ya" tanpa membaca.
    expect(screen.queryByTestId("periksa-akhir")).not.toBeInTheDocument();
    expect(onKirim).toHaveBeenCalledTimes(1);
    const [utama, lain] = onKirim.mock.calls[0];
    expect(utama).toHaveProperty("halaman", 1);
    expect(lain).toHaveLength(1);
    expect(lain[0]).toHaveProperty("halaman", 1);
  });
});
