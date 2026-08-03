/** Uji aturan cakupan cetak: seleksi aktif menang atas isi halaman. */
import {
  CAKUPAN, cakupanAwal, idsCakupanStiker, idsCetakKartu, jumlahCakupanStiker,
} from "./cakupanCetak";

const HALAMAN = [{ id: "a1" }, { id: "a2" }, { id: "a3" }];

test("tanpa seleksi, kartu dicetak untuk seisi halaman", () => {
  expect(idsCetakKartu(new Set(), HALAMAN)).toEqual(["a1", "a2", "a3"]);
  expect(idsCetakKartu(undefined, HALAMAN)).toEqual(["a1", "a2", "a3"]);
});

test("seleksi aktif → HANYA yang ditandai yang dicetak", () => {
  // Inti permintaan: 2 dipilih dari 3 yang tampil ⇒ 2 kartu, bukan 3.
  expect(idsCetakKartu(new Set(["a2", "a3"]), HALAMAN)).toEqual(["a2", "a3"]);
});

test("seleksi lintas halaman tak disaring terhadap isi halaman", () => {
  // "Pilih semua N aset" mengisi id dari SELURUH hasil filter; menyaringnya
  // terhadap halaman yang tampil akan diam-diam membuang sebagian besar.
  const lintas = new Set(["a1", "z9", "z10"]);
  expect(idsCetakKartu(lintas, HALAMAN)).toEqual(["a1", "z9", "z10"]);
});

test("id kosong/rusak dibuang, bukan dikirim ke server", () => {
  expect(idsCetakKartu(new Set(["", null, "a1"]), HALAMAN)).toEqual(["a1"]);
  expect(idsCetakKartu(new Set(), [{ id: "a1" }, {}, null])).toEqual(["a1"]);
});

test("dialog stiker terbuka pada cakupan terpilih saat seleksi aktif", () => {
  expect(cakupanAwal(2)).toBe(CAKUPAN.TERPILIH);
  expect(cakupanAwal(0)).toBe(CAKUPAN.FILTER);
});

test("cakupan filter tak mengirim daftar id (server pakai parameter filter)", () => {
  expect(idsCakupanStiker(CAKUPAN.FILTER, new Set(["a1"]), HALAMAN)).toEqual([]);
});

test("cakupan halaman & terpilih memberi daftarnya masing-masing", () => {
  expect(idsCakupanStiker(CAKUPAN.HALAMAN, new Set(["a1"]), HALAMAN))
    .toEqual(["a1", "a2", "a3"]);
  expect(idsCakupanStiker(CAKUPAN.TERPILIH, new Set(["a3"]), HALAMAN))
    .toEqual(["a3"]);
});

test("jumlah yang dilaporkan ke pengguna sama dengan yang dikirim", () => {
  const arg = { idsTerpilih: new Set(["a1", "a2"]), asetHalaman: HALAMAN, totalFilter: 812 };
  expect(jumlahCakupanStiker(CAKUPAN.TERPILIH, arg)).toBe(2);
  expect(jumlahCakupanStiker(CAKUPAN.HALAMAN, arg)).toBe(3);
  expect(jumlahCakupanStiker(CAKUPAN.FILTER, arg)).toBe(812);
});
