/**
 * Mengubah kategori hanya boleh menghasilkan SATU permintaan.
 *
 * Kontrol kategori dulu memanggil `refreshData(1)` langsung di handler-nya,
 * padahal perubahan filter sudah punya efek pemuat ulang sendiri. Dua
 * permintaan untuk satu klik — dan yang langsung itu membaca `fetchParamsRef`
 * yang MASIH memuat kategori lama, sehingga hasilnya bisa mendarat belakangan
 * dan menimpa hasil yang benar.
 *
 * Selama kategori bernilai tunggal, gejalanya cuma boros. Dengan multi-pilih,
 * mencentang lima kategori menjadi sepuluh permintaan dan peluang salah-urutan
 * naik di tiap centang.
 *
 * Dipindai dari sumber: merender DashboardToolbar utuh berarti menghidupkan
 * belasan dependensi hanya untuk memeriksa satu baris pemanggilan.
 */
import fs from "fs";
import path from "path";

const TOOLBAR = fs.readFileSync(
  path.join(__dirname, "..", "DashboardToolbar.jsx"), "utf8");
const HALAMAN = fs.readFileSync(
  path.join(__dirname, "..", "..", "..", "pages", "DashboardPage.jsx"), "utf8");

test("kontrol kategori tidak memanggil refreshData sendiri", () => {
  expect(TOOLBAR).not.toMatch(/setFilterCategory\([^)]*\);\s*refreshData\(/);
});

test("reset kategori juga tidak memanggil refreshData sendiri", () => {
  expect(HALAMAN).not.toMatch(/handleCategoryReset\(\);\s*refreshData\(/);
});

test("efek pemuat ulang memang menyertakan kategori di deps", () => {
  // Penjaga anti-hampa: menghapus `refreshData(1)` hanya aman selama efeknya
  // benar-benar memantau `filterCategory`. Tanpa uji ini, dua perubahan yang
  // masing-masing masuk akal bisa bergabung jadi filter yang tak pernah
  // memuat ulang apa pun.
  const efek = HALAMAN.slice(HALAMAN.indexOf("// Re-fetch on filter/search/sort change"));
  const deps = efek.slice(efek.indexOf("}, ["), efek.indexOf("]);") + 3);
  expect(deps).toContain("filterCategory");
});
