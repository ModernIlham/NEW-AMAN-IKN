/**
 * Kosakata status job di dialog impor kategori — temuan lintas-butir C29.
 *
 * `done: true` BUKAN berarti berhasil. Dua jalur menyetel `done` bersama
 * `status: "error"`: galat parse di endpoint (categories.py) dan sapuan job
 * macet (jobs.py `bersihkan_job_basi` — "Timeout (job macet)"). Dialog lama
 * hanya melihat `done` lalu toast "Import selesai: ..." — job yang mati di
 * tengah pun dirayakan, lengkap dengan angka 0 yang tampak sah.
 *
 * Uji ini struktural (membaca sumber komponen) mengikuti pola plafonKartu:
 * komentar DIKUPAS dulu — penjaga yang membaca sumber mentah bisa dipuaskan
 * atau dijatuhkan oleh prosa; KEBERADAAN diperiksa sebelum urutan supaya
 * `indexOf` −1 tidak meloloskan kode yang ceknya dihapus.
 */
import fs from "fs";
import path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "./CategoryManagerDialog.jsx"), "utf8");

// Fungsi yang diuji saja, tanpa baris komentar.
const fn = SRC
  .slice(SRC.indexOf("const handleCategoryBulkImport"),
         SRC.indexOf("const handleDragOver"))
  .replace(/^\s*\/\/.*$/gm, "");

describe("toast impor kategori memeriksa STATUS, bukan cuma done", () => {
  test("fungsinya masih ada dan masih polling done", () => {
    expect(fn).toContain("pr.data.done");
  });

  test("status error dicek SEBELUM toast sukses", () => {
    const iCek = fn.indexOf('pr.data.status === "error"');
    const iSukses = fn.indexOf("toast.success");
    expect(iCek).toBeGreaterThan(-1);
    expect(iSukses).toBeGreaterThan(-1);
    expect(iCek).toBeLessThan(iSukses);
  });

  test("pesan galatnya dari server (error_message), dengan cadangan", () => {
    // "Timeout (job macet)" dari sapuan basi harus sampai ke layar apa
    // adanya — bukan diganti pesan generik yang menyembunyikan penyebab.
    expect(fn).toContain("pr.data.error_message");
    expect(fn).toMatch(/toast\.error\(/);
  });

  test("polling putus tidak meninggalkan panel menggantung", () => {
    // Jalur catch lama hanya clearInterval — panel "Mengimport..." macet
    // selamanya dan pengguna tak diberi tahu apa-apa.
    const iCatch = fn.lastIndexOf("catch");
    expect(iCatch).toBeGreaterThan(-1);
    const badanCatch = fn.slice(iCatch);
    expect(badanCatch).toContain("setCatImportProgress(null)");
    expect(badanCatch).toMatch(/toast\.(warning|error)/);
  });
});

describe("label panel progres", () => {
  test("status error berlabel Gagal, bukan Selesai!", () => {
    const tanpaKomentar = SRC.replace(/^\s*\/\/.*$/gm, "");
    const iLabel = tanpaKomentar.indexOf("'Gagal'");
    expect(iLabel).toBeGreaterThan(-1);
    // Cabang error harus dievaluasi SEBELUM cabang done — keduanya benar
    // bersamaan pada job gagal, dan urutan ternary menentukan yang menang.
    const potongan = tanpaKomentar.slice(iLabel - 200, iLabel);
    expect(potongan).toContain("=== 'error'");
    expect(tanpaKomentar.indexOf("'Gagal'"))
      .toBeLessThan(tanpaKomentar.indexOf("'Selesai!'"));
  });
});
