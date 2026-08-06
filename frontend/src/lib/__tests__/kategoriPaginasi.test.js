/**
 * Paginasi "Kelola Kategori Aset": tombol Sebelumnya/Berikutnya harus hidup.
 *
 * Cacat aslinya BUKAN pada tombolnya. `filteredCategories` memotong keras
 * `cats.slice(0, 50)` setiap kali kotak pencarian kosong (atau berisi < 2
 * huruf) — penjaga performa dari sebelum paginasi dipasang. Akibatnya
 * panjangnya SELALU 50, total halaman selalu 1, dan kedua tombol dinonaktifkan
 * permanen. Dari 12.488 kategori hanya 50 pertama yang bisa dilihat, dan
 * layarnya bahkan menulis "1-50 dari 50" — angka yang membantah header
 * "Total: 12488 kategori" tepat di atasnya.
 *
 * Potongan itu juga percuma: <tbody> SUDAH memotong per halaman sendiri, jadi
 * berapa pun panjang daftarnya hanya 50 baris yang benar-benar dirender.
 *
 * KENAPA UJI INI MEMBACA SUMBER, BUKAN MERENDER: repo ini belum memasang
 * @testing-library (lihat tugas tertunda "uji render komponen"), jadi tak ada
 * cara memasang komponen dan mengklik tombolnya. Yang bisa dijaga adalah
 * invariannya di tempat ia hidup — dan justru di sanalah cacatnya berada.
 */
const fs = require("fs");
const path = require("path");

const BERKAS = path.resolve(
  __dirname, "..", "..", "components", "assets", "CategoryManagerDialog.jsx");
const SRC = fs.readFileSync(BERKAS, "utf8");

/** Badan `useMemo` milik `filteredCategories`. */
function memoSaring() {
  const mulai = SRC.indexOf("const filteredCategories = useMemo(");
  expect(mulai).toBeGreaterThan(-1);
  return SRC.slice(mulai, SRC.indexOf("}, [categories, categorySearch]);", mulai));
}

describe("Paginasi kategori — daftar tak boleh dipotong sebelum dipaginasi", () => {
  test("cabang tanpa-pencarian mengembalikan SELURUH daftar", () => {
    const memo = memoSaring();
    expect(memo).toContain("return cats;");
    expect(memo).not.toMatch(/cats\.slice\(\s*0\s*,/);
  });

  test("hanya ADA SATU sumber angka total halaman", () => {
    // Dulu `Math.ceil(...)` ditulis ulang di tiga tempat, dan hanya salah
    // satunya berekor `|| 1`. Bentuk begitu membuat label halaman dan keadaan
    // tombol bisa berbeda pendapat pada daftar kosong.
    expect(SRC).toContain("const totalHalaman = Math.max(1, Math.ceil(");
    const hitungLain = SRC.match(/Math\.ceil\(filteredCategories\.length/g) || [];
    expect(hitungLain).toHaveLength(1);
  });

  test("kedua tombol memakai totalHalaman yang sama", () => {
    expect(SRC).toContain("Math.min(totalHalaman, p + 1)");
    expect(SRC).toContain("disabled={categoryPage >= totalHalaman}");
    expect(SRC).toContain("disabled={categoryPage <= 1}");
  });

  test("halaman aktif dijepit saat daftar menyusut", () => {
    // Menghapus baris terakhir di halaman terakhir dulu meninggalkan tabel
    // kosong dengan kedua tombol mati — pengguna terjebak.
    expect(SRC).toContain("setCategoryPage(p => Math.min(p, totalHalaman));");
  });

  test("pencarian mereset ke halaman 1", () => {
    expect(SRC).toContain("setCategoryPage(1)");
  });
});

/**
 * Aritmetika paginasinya sendiri — disalin persis dari komponen agar batas
 * atas/bawahnya teruji, bukan cuma keberadaan barisnya.
 */
const UKURAN = 50;
const total = (n) => Math.max(1, Math.ceil(n / UKURAN));

describe("Aritmetika halaman", () => {
  test("12.488 kategori jadi 250 halaman, bukan 1", () => {
    expect(total(12488)).toBe(250);
  });

  test("daftar kosong tetap 1 halaman (bukan 0)", () => {
    // `Math.ceil(0/50)` = 0. Tanpa penjepit `Math.max(1, …)`, labelnya jadi
    // "1 / 0" dan tombol Berikutnya justru AKTIF pada daftar kosong.
    expect(total(0)).toBe(1);
  });

  test("batas kelipatan tepat tak menambah halaman kosong", () => {
    expect(total(50)).toBe(1);
    expect(total(51)).toBe(2);
    expect(total(100)).toBe(2);
  });

  test("irisan halaman terakhir berisi sisa, bukan kosong", () => {
    const n = 12488;
    const hal = total(n);
    const awal = (hal - 1) * UKURAN;
    expect(n - awal).toBe(38);
    expect(awal).toBeLessThan(n);
  });
});
