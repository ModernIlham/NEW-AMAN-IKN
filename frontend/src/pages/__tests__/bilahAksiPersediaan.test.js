/**
 * Bilah aksi halaman Persediaan — dipindai dari sumber.
 *
 * Laporan pemilik: *"bagian permohonan jadi melewati batas."* Label
 * "Permohonan" tercetak MELUAR dari kotak tombolnya di layar sempit.
 *
 * Sebabnya berpasangan, dan yang pertama berlawanan dengan dugaan:
 *
 * 1. **Aturan tap-target global justru yang mengizinkan tombol diperas.**
 *    `index.css` memasang `button, a { min-width: 44px }` pada ≤1023px. Nilai
 *    EKSPLISIT itu menimpa `min-width: auto` milik flex item — justru nilai
 *    yang biasanya mencegah item menyusut di bawah lebar isinya. Tombol
 *    karenanya boleh menyusut sampai 44px sementara labelnya
 *    `whitespace-nowrap` meluber keluar kotak, dan barisnya tak pernah
 *    menggulir seperti yang dimaksudkan `overflow-x-auto`.
 *
 * 2. **Tombol Permohonan tak seragam dengan tetangganya.** Ia satu-satunya
 *    yang labelnya selalu tampil, sehingga di HP jauh lebih lebar daripada
 *    yang lain — dan yang paling lebar itulah yang paling banyak diperas.
 *
 * Dipindai dari sumber: jsdom tidak menata halaman, sehingga tak ada uji
 * perilaku yang dapat melihat luapan ini; merender PersediaanPage utuh pun
 * berarti menghidupkan belasan dependensi hanya untuk memeriksa dua kelas.
 * Pola yang sama dengan `lingkupUnitTataLetak.test.js`.
 */
import fs from "fs";
import path from "path";

const HALAMAN = fs.readFileSync(
  path.join(__dirname, "..", "PersediaanPage.jsx"), "utf8");
const PANEL = fs.readFileSync(
  path.join(__dirname, "..", "..", "components", "persediaan",
            "PermohonanPanel.jsx"), "utf8");

/** Baris pembungkus bilah aksi (yang ber-`flex-nowrap overflow-x-auto`). */
function barisAksi() {
  const baris = HALAMAN.split("\n").find(
    (l) => l.includes("flex-nowrap") && l.includes("overflow-x-auto"));
  expect(baris).toBeTruthy();
  return baris;
}

test("bilah aksi mencegah tombolnya diperas", () => {
  // Tanpa ini, aturan 44px membiarkan tombol menyusut dan labelnya meluber.
  expect(barisAksi()).toContain("[&>*]:shrink-0");
});

test("bilah aksi tetap menggulir menyamping, bukan membungkus", () => {
  const baris = barisAksi();
  expect(baris).toContain("flex-nowrap");
  expect(baris).toContain("overflow-x-auto");
});

test("tombol Permohonan setinggi tetangganya", () => {
  // Tetangganya memakai h-10; tanpa itu tingginya berbeda sendiri.
  expect(PANEL).toMatch(/<Button variant="outline" className="h-10 gap-1\.5"/);
});

test("label Permohonan menepi di layar sempit seperti tombol lain", () => {
  expect(PANEL).toContain('<span className="hidden sm:inline">Permohonan</span>');
});

test("lencana jumlah menunggu TETAP tampil di layar sempit", () => {
  // Menyembunyikannya bersama label akan menghapus satu-satunya tanda bahwa
  // ada permohonan yang menanti — justru alasan tombol ini perlu dilihat.
  const i = PANEL.indexOf("persediaan-permohonan");
  const blok = PANEL.slice(PANEL.indexOf("{menunggu > 0 && ("),
                           PANEL.indexOf("</Button>"));
  expect(i).toBeGreaterThan(-1);
  expect(blok).not.toContain("hidden sm:inline");
  expect(blok).toContain("bg-amber-500");
});

test("tombol Permohonan tetap punya nama yang terbaca pembaca layar", () => {
  // Ikon tanpa label butuh aria-label; tanpa itu tombolnya menjadi anonim
  // persis di layar tempat labelnya disembunyikan.
  expect(PANEL).toContain("aria-label={k.judul}");
});
