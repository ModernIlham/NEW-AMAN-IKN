/**
 * Penjaga: aset harus bisa ditempatkan di denah DARI LAYAR, bukan hanya lewat
 * pindai stiker QR di lapangan.
 *
 * `PUT /assets/{id}/lokasi-spasial` sudah ada sejak Spasial Fase 9 — lengkap
 * dengan pencatatan riwayat perpindahan — tetapi tak pernah punya satu pun
 * pemanggil di frontend. Akibatnya penempatan aset HANYA bisa lahir dari
 * `/opname/terapkan`, yang mensyaratkan seseorang berdiri di depan barangnya
 * dan memindai stikernya. Salah pindai pun tak bisa dikoreksi dari meja.
 *
 * Dialognya sendiri sudah ada dan sudah ber-parameter `submitUrl`
 * (`components/wasdal/LokasiTemuanDialog.jsx`) — hanya kata-katanya yang
 * terpaku pada wasdal. Uji ini menjaga dua hal:
 *
 *   1. Endpoint itu benar-benar dipanggil dari UI (kelas cacat yang diperbaiki).
 *   2. Dialognya DIPAKAI BERSAMA, bukan disalin — salinan kedua akan menyimpang
 *      diam-diam dari yang asli (Leaflet-di-dalam-modal, guard koordinat korup,
 *      anti-balapan deteksi titik semuanya harus tetap satu sumber).
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const DIALOG = "components/wasdal/LokasiTemuanDialog.jsx";
const DASBOR = "pages/DashboardPage.jsx";
const FORM = "components/assets/AssetForm.jsx";

/** Semua .jsx di bawah src/ (rekursif). */
function berkasJsx(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return berkasJsx(p);
    return e.isFile() && e.name.endsWith(".jsx") ? [p] : [];
  });
}

describe("endpoint penempatan denah punya pemanggil UI", () => {
  const dasbor = baca(DASBOR);

  test("submitUrl menunjuk PUT /assets/{id}/lokasi-spasial", () => {
    expect(dasbor).toMatch(/\/assets\/\$\{[\w.]+\}\/lokasi-spasial/);
  });

  test("tombolnya ada di form aset dan tersambung ke dasbor", () => {
    expect(baca(FORM)).toContain("onOpenLokasiDenah");
    expect(dasbor).toContain("handleOpenLokasiDenah");
    expect(dasbor).toContain("onOpenLokasiDenah=");
  });

  test("lokasi yang BERLAKU diambil dulu sebelum dialog dibuka", () => {
    // Tanpa ini peta terbuka di pusat kawasan (bukan di posisi aset) dan
    // tombol "Cabut Penempatan" tak pernah muncul — respons daftar aset tak
    // membawa `lokasi_spasial`.
    const potong = dasbor.split("handleOpenLokasiDenah = useCallback")[1] || "";
    expect(potong.slice(0, 700)).toContain("lokasi_spasial");
    expect(dasbor).toContain("lokasiAwal={lokasiDenahAset.lokasi}");
  });

  test("aksi tulis digerbangi izin — viewer tak melihat tombolnya", () => {
    // Server memang menolak lewat require_writer, tetapi tombol yang selalu
    // berakhir 403 adalah janji palsu.
    expect(dasbor).toMatch(/onOpenLokasiDenah=\{perms\.canEdit \?/);
  });
});

describe("dialog denah dipakai bersama, bukan disalin", () => {
  test("hanya ada SATU komponen dialog penanda denah", () => {
    // Penanda khas: peta Leaflet + deteksi titik Fase 3 + PUT ber-`submitUrl`.
    const salinan = berkasJsx(SRC).filter((f) => {
      const isi = fs.readFileSync(f, "utf8");
      return isi.includes("spasial/lokasi-di-titik") && isi.includes("axios.put(submitUrl");
    }).map((f) => path.relative(SRC, f));
    expect(salinan).toEqual([DIALOG]);
  });

  test("kedua pemanggil memakai komponen yang sama", () => {
    expect(baca("pages/WasdalPage.jsx")).toContain("LokasiTemuanDialog");
    expect(baca(DASBOR)).toContain("wasdal/LokasiTemuanDialog");
  });
});

describe("kata-kata dialog di-parameterkan tanpa mengubah pemakai lama", () => {
  const dialog = baca(DIALOG);

  test("default-nya tetap bunyi wasdal", () => {
    // WasdalPage tak dioper prop kata-kata apa pun; bila default-nya bergeser,
    // layar Wasdal ikut berubah tanpa ada yang memintanya.
    expect(dialog).toContain('judulDialog = "Lokasi Temuan"');
    expect(dialog).toContain('labelHapus = "Hapus Penanda"');
    expect(dialog).toContain('pesanSimpan = "Lokasi temuan tersimpan"');
    expect(dialog).toContain('pesanHapus = "Penanda lokasi dihapus"');
    expect(baca("pages/WasdalPage.jsx")).not.toContain("judulDialog=");
  });

  test("tak ada lagi teks wasdal yang terpaku di badan dialog", () => {
    // Kalimat-kalimat ini dulu ditulis langsung di JSX; menyisakannya membuat
    // layar aset berbunyi "temuan" untuk barang yang sehat-sehat saja.
    const badan = dialog.split("}) {", 2)[1] || "";
    expect(badan).not.toContain('"Lokasi temuan tersimpan"');
    expect(badan).not.toContain('"Penanda lokasi dihapus"');
    expect(badan).not.toContain("klik lokasi temuan di peta");
  });

  test("pemakai aset benar-benar mengganti kata-katanya", () => {
    const dasbor = baca(DASBOR);
    expect(dasbor).toContain('judulDialog="Lokasi Aset di Denah"');
    expect(dasbor).toContain('labelHapus="Cabut Penempatan"');
  });

  test("prop kata-kata ikut di deps useCallback", () => {
    // Toast yang membeku pada nilai render pertama akan menampilkan kalimat
    // milik pemakai lain setelah prop berubah.
    expect(dialog).toMatch(/onSaved, onClose, pesanSimpan\]/);
    expect(dialog).toMatch(/onSaved, onClose, pesanHapus\]/);
  });
});

describe("titik yang sudah ada dideteksi otomatis saat dialog terbuka", () => {
  // Laporan pemilik: "belum terdeteksi informasi sama sekali" — PADAHAL node
  // denah sudah aktif dan geometrinya sah. Akarnya bukan di deteksi server:
  // dialog hanya memicu deteksi pada KLIK peta, jadi aset yang sudah punya
  // titik terbuka bisu (marker tampak, panel info kosong total — tak ada
  // rantai, tak ada pesan), dan aset ber-koordinat GPS yang belum pernah
  // ditempatkan malah terbuka kosong di pusat kawasan.
  const dialog = baca(DIALOG);
  const dasbor = baca(DASBOR);

  test("deteksi berjalan pada titik awal tanpa menunggu klik", () => {
    // Panggilannya harus di jalur init peta dan memakai mode pertahankan-node.
    expect(dialog).toMatch(/deteksiTitik\(seed\.lat, seed\.lon, true\)/);
  });

  test("deteksi otomatis TIDAK menimpa node tersimpan", () => {
    // Deteksi berhenti di gedung; menimpa nodeId membuat "buka lalu Simpan"
    // diam-diam menurunkan penempatan lantai/ruangan menjadi gedung.
    expect(dialog).toMatch(/adaTersimpan = pertahankanNode && nodeIdRef\.current/);
    expect(dialog).toMatch(/if \(!adaTersimpan\)/);
    // Kegagalan deteksi otomatis pun tak boleh menghapus node tersimpan.
    expect(dialog).toMatch(/if \(!pertahankanNode\) setNodeId\(""\)/);
  });

  test("penempatan tersimpan menang; koordinat GPS aset jadi cadangan", () => {
    expect(dialog).toMatch(
      /titikSah\(lokasiAwal\?\.titik\) \|\| titikSah\(titikAwal\)/);
  });

  test("dasbor mengumpankan koordinat GPS aset sebagai titikAwal", () => {
    const potong = dasbor.split("handleOpenLokasiDenah = useCallback")[1] || "";
    expect(potong.slice(0, 1400)).toContain("koordinat_latitude");
    expect(potong.slice(0, 1400)).toContain("koordinat_longitude");
    expect(dasbor).toContain("titikAwal={lokasiDenahAset.titik}");
  });
});

describe("informasi tampil tanpa bergantung satu panggilan jaringan", () => {
  // Laporan pemilik: "data informasi dari wilayah hingga ruangan masih tidak
  // muncul padahal sudah saya simpan" — dari layar yang petanya pun hitam
  // (ubin OSM tak termuat, jaringan lapangan buruk). Tiga penjaga di sini
  // memastikan dialog TETAP informatif dalam kondisi itu.
  const dialog = baca(DIALOG);

  test("penempatan tersimpan tampil dari snapshot server, bukan hasil deteksi", () => {
    // `jalur_nama` sudah ada di dokumen aset; menampilkannya tak butuh
    // jaringan. Bila hilang, "sudah saya simpan" kembali tak terlihat.
    expect(dialog).toContain('data-testid="lokasi-temuan-tersimpan"');
    expect(dialog).toContain("lokasiAwal.jalur_nama");
  });

  test("poligon denah digambar di peta dialog — dan TIDAK menelan klik", () => {
    expect(dialog).toContain("/spasial/geojson");
    // interactive: false wajib — poligon yang menangkap klik membuat
    // menancapkan titik DI DALAM denah (kegunaan inti dialog) mustahil.
    expect(dialog).toMatch(/interactive: false/);
  });

  test("deteksi gagal menyisakan tombol coba lagi, bukan jalan buntu", () => {
    expect(dialog).toContain('data-testid="lokasi-temuan-deteksi-ulang"');
  });
});

describe("rantai menyempit hingga RUANGAN dan tombol tertata", () => {
  const dialog = baca(DIALOG);

  test("persempit ke ruangan memakai deteksi ruangan-di-titik", () => {
    // Tanpa ini rantai berhenti di gedung/lantai — padahal permintaan
    // pemilik eksplisit: "dari wilayah hingga mengerucutnya (ruangan)".
    expect(dialog).toContain("/spasial/ruangan-di-titik");
    expect(dialog).toContain('data-testid="lokasi-temuan-ruangan"');
  });

  test("prapilih ruangan tak menggeser node tersimpan/lebih dalam", () => {
    expect(dialog).toMatch(/kini === lantaiAktif \? r\.data\.ruangan\.id : kini/);
  });

  test("tombol Batal dihapus; Simpan & Cabut dalam satu baris footer", () => {
    // Tiga tombol membuat footer pecah dua baris di HP (tangkapan layar
    // pemilik); menutup dialog cukup lewat ikon × / ketuk luar.
    expect(dialog).not.toContain("lokasi-temuan-batal");
    expect(dialog).toContain('data-testid="lokasi-temuan-hapus"');
    expect(dialog).toContain('data-testid="lokasi-temuan-simpan"');
  });

  test("header memberi ruang tombol tutup bawaan dialog", () => {
    // Tanpa pr-10 judul/deskripsi menabrak ikon × (laporan pemilik).
    expect(dialog).toMatch(/DialogHeader className="[^"]*pr-10/);
  });
});
