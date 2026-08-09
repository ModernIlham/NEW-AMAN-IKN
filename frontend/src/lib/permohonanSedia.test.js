/**
 * Penjaga pengkabelan SEDIA-KPB di PersediaanPage: saat saklar wajib-persetujuan
 * menyala, KETUJUH handler transaksi harus berbelok ke `ajukanPermohonan`
 * alih-alih menulis langsung.
 *
 * Kenapa pemindaian sumber, bukan uji perilaku: menekan submit ketujuh dialog
 * transaksi butuh merender halaman raksasa berisi peta + WebSocket + tujuh
 * form, sementara cacat yang dijaga di sini bentuknya justru TEKSTUAL —
 * seseorang menghapus satu cabang `if (wajibSetuju)` (atau lupa memasangnya
 * pada handler baru) dan submit-nya kembali menembak endpoint transaksi
 * langsung, yang saat gerbang menyala hanya menghasilkan toast 403.
 * Perilaku panelnya sendiri diuji nyata di PermohonanPanelRender.test.jsx;
 * gerbang servernya dikunci di test_persediaan_permohonan.py.
 */
const fs = require("fs");
const path = require("path");

const SUMBER = fs.readFileSync(
  path.join(__dirname, "..", "pages", "PersediaanPage.jsx"), "utf8");

// Ketujuh jalur permohonan — cermin JALUR_PERMOHONAN backend (tanpa jalur
// turunan). Handler baru yang menulis stok wajib menambah pasangannya di sini.
const JALUR = ["masuk", "keluar", "massal", "opname", "koreksi_nilai",
  "hapus_definitif", "pindah_gudang"];

test("tiap jalur transaksi punya belokan ajukanPermohonan-nya", () => {
  const hilang = JALUR.filter(
    (j) => !SUMBER.includes(`ajukanPermohonan("${j}"`));
  expect(hilang).toEqual([]);
});

test("tiap belokan dijaga cabang if (wajibSetuju) — tidak kurang", () => {
  const cabang = (SUMBER.match(/if \(wajibSetuju\)/g) || []).length;
  expect(cabang).toBeGreaterThanOrEqual(JALUR.length);
});

test("PersediaanPage merender PermohonanPanel (pintu daftar & saklar)", () => {
  expect(SUMBER).toMatch(/<PermohonanPanel\b/);
});
