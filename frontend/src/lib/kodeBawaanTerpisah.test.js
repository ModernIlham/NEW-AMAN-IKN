/**
 * Layar tak boleh lagi menyebut Kode Klasifikasi Bawaan sebagai pengisi Kode
 * Klasifikasi Arsip.
 *
 * Permintaan pemilik: *"tolong bedakan Kode Klasifikasi Bawaan (fallback)
 * berdiri sendiri dan Kode Klasifikasi Arsip berdiri sendiri, independent
 * masing masing"*.
 *
 * Perilakunya sudah dipisah di server, dan itu diuji di
 * `backend/tests/unit/test_klasifikasi_berdiri_sendiri.py`. Yang dijaga di
 * sini bagian yang tak tersentuh uji perilaku: KALIMAT di layar. Cacat
 * aslinya justru sebuah kalimat — "Klasifikasi: SATKER-D · kode bawaan
 * pengaturan" — yang memanggil dua hal berbeda dengan satu nama. Kalimat yang
 * salah bertahan bertahun-tahun karena tak ada yang menagihnya.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const HALAMAN = "pages/PersuratanPage.jsx";
const HELPER = "lib/klasifikasiNomor.js";

function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
}

describe("Pengaturan penomoran menyatakan pemisahannya", () => {
  const kode = tanpaKomentar(baca(HALAMAN));

  test("kolom kode bawaan menyebut dirinya berdiri sendiri", () => {
    expect(kode).toMatch(/Kode Klasifikasi Bawaan — berdiri sendiri/);
  });

  test("kolom itu menunjukkan slotnya sendiri, bukan slot klasifikasi", () => {
    // Tanpa kalimat ini, "berdiri sendiri" hanya label tanpa jalan keluar:
    // pengguna yang MEMANG ingin kode bawaannya ikut ke nomor tak diberi tahu
    // caranya, lalu menyimpulkan fiturnya hilang.
    const i = kode.indexOf("atur-kode-bawaan-catatan");
    expect(i).toBeGreaterThan(-1);
    const blok = kode.slice(i, i + 600);
    expect(blok).toMatch(/\{kode_bawaan\}/);
    expect(blok).toMatch(/tidak/);
  });

  test("katalog tak lagi menyebut kode bawaan sebagai pengubah klasifikasi", () => {
    const i = kode.indexOf("Daftar ini");
    expect(i).toBeGreaterThan(-1);
    const blok = kode.slice(i, i + 800);
    expect(blok).toMatch(/aturan otomatis/);
    expect(blok).toMatch(/isian manual/);
    expect(blok).toMatch(/berdiri sendiri dan tidak termasuk/);
  });
});

describe("Helper tak menyimpan kalimat lama", () => {
  const helper = baca(HELPER);

  test("frasa 'kode bawaan pengaturan' sudah tak ada sebagai label", () => {
    // Itulah teks persis pada tangkapan layar pemilik.
    const kalimatHidup = helper
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    expect(kalimatHidup).not.toMatch(/kode bawaan pengaturan/);
  });

  test("cabang sumber 'bawaan' tak dihidupkan kembali", () => {
    const kalimatHidup = helper
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    expect(kalimatHidup).not.toMatch(/sumber === "bawaan"/);
  });
});

describe("Daftar placeholder di layar tak diketik ulang", () => {
  const kode = baca(HALAMAN);

  test("kalimat pengantar mengambil daftarnya dari server", () => {
    // Sebelumnya kalimat itu MENYALIN daftar placeholder. Salinan tak ikut
    // bertambah: begitu `{kode_bawaan}` lahir, kalimat yang mengaku
    // menyebutkan "placeholder" justru menyembunyikan satu-satunya slot baru
    // yang perlu diketahui pengguna.
    const i = kode.indexOf("Susunan PerANRI 5/2021");
    expect(i).toBeGreaterThan(-1);
    const blok = kode.slice(i, i + 400);
    expect(blok).toMatch(/formAtur\?\.placeholder/);
    expect(blok).not.toMatch(/\{kode_keamanan\} \{urut\}/);
  });
});
