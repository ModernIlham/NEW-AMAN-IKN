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
