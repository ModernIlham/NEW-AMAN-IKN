import { susunPohonUnit, jalurUnit, ringkasLingkup } from "../pohonUnit";

// Setjen → Biro Umum → Bagian RT; Biro Keuangan sebagai saudara.
const POHON = [
  { id: "e3", nama_unit: "Bagian RT", eselon: "3", parent_id: "e2" },
  { id: "e2b", nama_unit: "Biro Keuangan", eselon: "2", parent_id: "e1" },
  { id: "e1", nama_unit: "Setjen", eselon: "1", parent_id: null },
  { id: "e2", nama_unit: "Biro Umum", eselon: "2", parent_id: "e1" },
];

test("induk selalu mendahului anaknya, saudara terurut nama", () => {
  const hasil = susunPohonUnit(POHON);
  // Biro Keuangan mendahului Biro Umum secara abjad, dan Bagian RT mengikuti
  // induknya — bukan mengikuti urutan kedatangannya dari server.
  expect(hasil.map((u) => u.id)).toEqual(["e1", "e2b", "e2", "e3"]);
  expect(hasil.map((u) => u.depth)).toEqual([0, 1, 1, 2]);
});

test("jalur menyebut seluruh leluhurnya", () => {
  const hasil = susunPohonUnit(POHON);
  expect(jalurUnit("e3", hasil)).toBe("Setjen / Biro Umum / Bagian RT");
  expect(jalurUnit("e1", hasil)).toBe("Setjen");
});

test("unit yatim jadi AKAR, dan cabang di bawahnya tetap berjenjang", () => {
  // parent_id menunjuk unit yang sudah terhapus. Memperlakukannya sebagai akar
  // bukan sekadar soal ia muncul — jaring terakhir di ujung fungsi sudah
  // menjamin itu. Yang hilang tanpa perlakuan ini adalah JENJANG di bawahnya:
  // anak si yatim ikut jatuh ke jaring yang sama dan tercetak sejajar dengan
  // induknya, sehingga cabang yang utuh terbaca sebagai daftar rata.
  const hasil = susunPohonUnit([
    ...POHON,
    { id: "y1", nama_unit: "Bagian Yatim", eselon: "3", parent_id: "sudah-hilang" },
    { id: "y2", nama_unit: "Subbagian Ikut", eselon: "4", parent_id: "y1" },
  ]);
  const yatim = hasil.find((u) => u.id === "y1");
  const anak = hasil.find((u) => u.id === "y2");
  expect(yatim.depth).toBe(0);
  expect(yatim.jalur).toBe("Bagian Yatim");
  expect(anak.depth).toBe(1);
  expect(anak.jalur).toBe("Bagian Yatim / Subbagian Ikut");
  expect(hasil.indexOf(yatim)).toBeLessThan(hasil.indexOf(anak));
});

test("pohon yang melingkar tidak membekukan penelusuran", () => {
  const hasil = susunPohonUnit([
    { id: "a", nama_unit: "A", eselon: "2", parent_id: "b" },
    { id: "b", nama_unit: "B", eselon: "3", parent_id: "a" },
  ]);
  expect(hasil.map((u) => u.id).sort()).toEqual(["a", "b"]);
  expect(hasil).toHaveLength(2);
});

test("daftar kosong dan masukan cacat tak melempar", () => {
  expect(susunPohonUnit([])).toEqual([]);
  expect(susunPohonUnit(null)).toEqual([]);
  expect(susunPohonUnit([null, { nama_unit: "tanpa id" }])).toEqual([]);
});

test("id yang tak dikenal tetap dihitung dan ditandai", () => {
  // Lingkup adalah penyaring: id mati tidak menyaring apa pun, dan
  // menyembunyikannya membuat kegiatan yang dikira terbatas menampilkan
  // seluruh satker.
  const hasil = susunPohonUnit(POHON);
  const r = ringkasLingkup(["e2", "hantu"], hasil);
  expect(r.jumlah).toBe(2);
  expect(r.tak_dikenal).toEqual(["hantu"]);
  expect(r.jalur).toEqual(["Setjen / Biro Umum", "hantu"]);
});

test("lingkup kosong berarti tak ada penyaring", () => {
  expect(ringkasLingkup([], susunPohonUnit(POHON)).jumlah).toBe(0);
  expect(ringkasLingkup(null, []).tak_dikenal).toEqual([]);
});
