/**
 * Penjaga field `barang_bersejarah` di sisi frontend — kelas cacat yang
 * dijaga registry asset_fields: "ada di form tapi hilang di snapshot
 * luring" (atau sebaliknya). Uji perilaku penuh AssetForm terlalu berat;
 * kontrak tekstualnya yang dipaku di sini, perilaku laporannya dikunci
 * di test_lbp_utils.py backend.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");

test("snapshot luring menyertakan barang_bersejarah", () => {
  const snap = fs.readFileSync(path.join(SRC, "lib", "offlineSnapshot.js"), "utf8");
  expect(snap).toMatch(/"barang_bersejarah"/);
});

test("AssetForm punya checkbox barang bersejarah yang menulis Ya/kosong", () => {
  const form = fs.readFileSync(
    path.join(SRC, "components", "assets", "AssetForm.jsx"), "utf8");
  expect(form).toMatch(/data-testid="asset-barang-bersejarah"/);
  expect(form).toMatch(/name: "barang_bersejarah", value: e\.target\.checked \? "Ya" : ""/);
  // ikut daftar patch teks agar perubahan benar-benar terkirim saat simpan
  expect(form).toMatch(/"garansi_hingga", "garansi_jenis", "barang_bersejarah",/);
});
