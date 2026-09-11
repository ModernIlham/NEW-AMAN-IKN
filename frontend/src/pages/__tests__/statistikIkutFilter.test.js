/**
 * Kartu ringkasan dan daftar harus BERANGKAT dari perakit parameter yang sama.
 *
 * Keluhan pemilik: filter lanjutan menyaring daftar aset, tetapi "Total Aset /
 * Total Nilai / Aktif / Maintenance" di atasnya tidak bergerak. Sebabnya bukan
 * efek yang lupa dipicu — statistiknya memang dimuat ulang — melainkan
 * `doFetchStats` yang hanya merakit tiga parameter dan tak pernah memanggil
 * `buildFilterParams`.
 *
 * Uji ini memindai sumbernya, bukan merender halaman. Merender DashboardPage
 * berarti menghidupkan peta, kamera, IndexedDB, dan antrean simpan hanya untuk
 * memeriksa satu baris pemanggilan — dan uji seperti itu gagal karena hal-hal
 * yang tak ada hubungannya dengan yang dijaga di sini.
 */
import fs from "fs";
import path from "path";

const SUMBER = fs.readFileSync(
  path.join(__dirname, "..", "..", "lib", "pemuatDaftarAset.js"), "utf8");
const HALAMAN = fs.readFileSync(path.join(__dirname, "..", "DashboardPage.jsx"), "utf8");

test("Dashboard benar-benar memakai pemuat yang diuji, dengan perakit filter dan semua setter", () => {
  expect(HALAMAN).toContain('import { buatPemuatDaftarAset } from "@/lib/pemuatDaftarAset"');
  const wiring = HALAMAN.match(/const \{ doFetch, doFetchStats, loadMoreMobile, loadPrevMobile \} = buatPemuatDaftarAset\(\{([\s\S]*?)\}\)/)?.[1];
  expect(wiring).toBeDefined();
  for (const nama of ["activity", "filters", "buildFilterParams", "penjaga", "lingkupPermintaan", "getPendingItems", "filterSnapshotRows", "sortSnapshotRows", "setAssets", "setStats", "setMobileAssets"]) {
    expect(wiring).toMatch(new RegExp(`\\b${nama}\\b`));
  }
  const lingkup = HALAMAN.match(/const lingkupPermintaan = JSON.stringify\(\[([^\]]+)\]\)/)?.[1];
  expect(lingkup).toBeDefined();
  for (const nama of ["activity?.id", "user?.id", "user?.kode_satker", "filterLaporan", "sortBy", "pageSize"]) expect(lingkup).toContain(nama);
  expect(lingkup).not.toContain("currentPage");
  expect(HALAMAN).toContain("const penjaga = usePenjagaPermintaan(lingkupPermintaan)");
});

test("Simpan Lanjut berhenti sebelum menutup form untuk hasil usang", () => {
  const navigasi = HALAMAN.slice(HALAMAN.indexOf("const fresh = isDesktopList"));
  expect(navigasi.indexOf("if (fresh === HASIL_USANG) return;")).toBeGreaterThan(-1);
  expect(navigasi.indexOf("if (fresh === HASIL_USANG) return;")).toBeLessThan(navigasi.indexOf("const nextAsset"));
  expect(navigasi.indexOf("if (fresh === HASIL_USANG) return;")).toBeLessThan(navigasi.indexOf("setEditAssetForForm(null)"));
});

/** Potong badan satu fungsi `const nama = async (...) => {` sampai seimbang. */
function badanFungsi(nama) {
  const awal = SUMBER.indexOf(`const ${nama} = `);
  expect(awal).toBeGreaterThan(-1);
  const mulai = SUMBER.indexOf("{", SUMBER.indexOf("=>", awal));
  let dalam = 0;
  for (let i = mulai; i < SUMBER.length; i++) {
    if (SUMBER[i] === "{") dalam++;
    else if (SUMBER[i] === "}") {
      dalam--;
      if (dalam === 0) return SUMBER.slice(mulai, i + 1);
    }
  }
  throw new Error(`badan ${nama} tak seimbang`);
}

describe("parameter statistik", () => {
  test("doFetchStats memakai perakit filter yang sama dengan daftar", () => {
    expect(badanFungsi("doFetchStats")).toContain("buildFilterParams(params)");
  });

  test("doFetch memang perakit pembandingnya", () => {
    // Penjaga anti-hampa: bila daftar suatu saat berhenti memakai
    // `buildFilterParams`, uji di atas kehilangan artinya tanpa memerah.
    expect(badanFungsi("doFetch")).toContain("buildFilterParams(params)");
  });

  test("statistik luring dihitung dari baris tersaring, bukan dibiarkan basi", () => {
    const badan = badanFungsi("serveFromSnapshot");
    expect(badan).toContain("statistikUntukKartu(filtered)");
    // Dihitung dari `filtered`, BUKAN `merged`: `merged` menyertakan baris
    // antrean simpan yang belum tersinkron, sedangkan angka total yang
    // ditampilkan daftar (`setTotalItems`) memakai `filtered`. Memakai
    // `merged` membuat kartu dan daftar berselisih satu-dua baris.
    expect(badan).not.toContain("statistikUntukKartu(merged)");
  });
});
