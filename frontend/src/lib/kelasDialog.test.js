/** Uji komposisi kelas DialogContent: bawaan aman, penimpaan tetap menang. */
import { DIALOG_DASAR, kelasDialog } from "./kelasDialog";

const kelas = (s) => kelasDialog(s).split(/\s+/);

test("tanpa penimpaan: batas tinggi + gulir vertikal terpasang", () => {
  const k = kelas("");
  expect(k).toContain("max-h-[var(--tinggi-dialog)]");
  expect(k).toContain("overflow-y-auto");
  expect(k).toContain("overflow-x-hidden");
});

test("padding HP lebih kecil daripada desktop", () => {
  const k = kelas("");
  expect(k).toContain("p-4");
  expect(k).toContain("sm:p-6");
});

test("dialog boleh menimpa batas tingginya sendiri", () => {
  // Kalau bawaan ikut terbawa, DUA max-h hidup bersama di DOM dan pemenangnya
  // ditentukan urutan stylesheet — penimpaan jadi tak berarti.
  const k = kelas("max-w-2xl max-h-[85vh]");
  expect(k).toContain("max-h-[85vh]");
  expect(k).not.toContain("max-h-[var(--tinggi-dialog)]");
});

test("dialog boleh menimpa padding & lebar", () => {
  const k = kelas("max-w-sm p-0");
  expect(k).toContain("p-0");
  expect(k).not.toContain("p-4");
  expect(k).toContain("max-w-sm");
  expect(k).not.toContain("max-w-lg");
});

test("dialog yang mengatur guliran sendiri tak dipaksa overflow-y-auto", () => {
  // Pola header/isi-bergulir/footer & dialog berpeta menulis `overflow-hidden`
  // dengan sengaja. tailwind-merge memperlakukan `overflow-hidden` sebagai
  // pembatal `overflow-x/y` yang mendahuluinya — tapi HANYA bila urutan
  // argumennya benar (bawaan dulu, className belakangan). Uji ini yang menjaga
  // urutan itu; menukarnya membuat ketiganya lolos ke DOM sekaligus.
  const k = kelas("max-h-[80vh] overflow-hidden flex flex-col p-0");
  expect(k).toContain("overflow-hidden");
  expect(k).not.toContain("overflow-y-auto");
  expect(k).not.toContain("overflow-x-hidden");
});

test("batas tinggi TETAP diberikan ke dialog yang tak menyebutkannya", () => {
  // Dialog berpeta hanya mematikan guliran, bukan meminta izin menjulang
  // melewati layar.
  const k = kelas("p-0 gap-0 overflow-hidden");
  expect(k).toContain("max-h-[var(--tinggi-dialog)]");
});

test("kelas dasar tak kehilangan pagar lebar & animasinya", () => {
  // Penjaga sederhana: `[&>*]:min-w-0` mencegah isi melebar menyamping
  // (lihat komentar di dialog.jsx) dan gampang terhapus saat menyusun ulang.
  expect(DIALOG_DASAR).toContain("[&>*]:min-w-0");
  expect(DIALOG_DASAR).toContain("w-[calc(100%-2rem)]");
  expect(kelas("")).toContain("[&>*]:min-w-0");
});
