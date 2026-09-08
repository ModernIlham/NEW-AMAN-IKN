/**
 * Pilihan ukuran stiker: SATU daftar, TANPA dimensi.
 *
 * Permintaan pemilik: *"hilangkan informasi ukuran stiker saat memilih kecil,
 * sedang atau besar pada halaman edit, tambah, massal dan kolom input lainnya
 * cukup di halaman Cetak Stiker Label BMN saja sudah cukup."*
 *
 * Angka itu bukan cuma mubazir, tetapi KELIRU: ukuran stiker yang sesungguhnya
 * tak tetap — grid merentangkan label mengisi penuh kertas, jadi stiker
 * "Sedang" keluar ±65×30 mm di A4 dan ±56×30 mm di A3, bukan 50×30 mm seperti
 * yang tertulis "(5x3cm)". Ukuran nyata hanya dapat disebut di tempat
 * kertasnya sudah dipilih, yaitu dialog Cetak Stiker Label BMN.
 */
const fs = require("fs");
const path = require("path");

const SUMBER = path.join(__dirname, "../../..");
const baca = (rel) => fs.readFileSync(path.join(SUMBER, rel), "utf8");

//: Isian yang memilih ukuran stiker. Diperiksa sebagai BERKAS, bukan render:
//: keempatnya berada di dalam layar besar berkondisi (form aset, lembar edit
//: cepat, lembar kamera, panel massal) yang mahal dirakit utuh — dan yang
//: dijaga di sini memang teksnya, bukan perilakunya.
const ISIAN = [
  "components/assets/AssetForm.jsx",
  "components/assets/InventoryFieldSheet.jsx",
  "components/assets/FullCameraSheet.jsx",
  "components/assets/BatchEditPanel.jsx",
];

const DIMENSI = /\d\s*x\s*[\d.]+\s*cm/i;

describe("dimensi stiker tak muncul di isian", () => {
  it.each(ISIAN)("%s tak menyebut dimensi apa pun", (rel) => {
    expect(baca(rel)).not.toMatch(DIMENSI);
  });

  it.each(ISIAN)("%s memakai daftar bersama, bukan menulis sendiri", (rel) => {
    // Konvensi repo: ekspor konstanta opsi, jangan duplikasi daftarnya.
    // Empat salinan berarti empat tempat yang bisa berpisah diam-diam.
    const isi = baca(rel);
    expect(isi).toMatch(/UKURAN_STIKER/);
    expect(isi).not.toMatch(/value="Kecil"/);
    expect(isi).not.toMatch(/\["Kecil",\s*"Sedang",\s*"Besar"\]/);
  });

  it("daftar bersamanya persis tiga nilai yang tersimpan di basis data", () => {
    const { UKURAN_STIKER } = require("@/lib/stikerAset");
    expect(UKURAN_STIKER).toEqual(["Kecil", "Sedang", "Besar"]);
  });

  it("dialog CETAK tetap menyebut ukuran nyata per kertas", () => {
    // Di sanalah angkanya berarti — kertasnya sudah dipilih.
    const cetak = baca("components/assets/CetakStikerDialog.jsx");
    expect(cetak).toMatch(/±98×46 mm/);
    expect(cetak).toMatch(/±65×30 mm/);
    expect(cetak).toMatch(/±48×22 mm/);
  });
});
