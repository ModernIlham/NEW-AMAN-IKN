import {
  susunPohonUnit, jalurUnit, ringkasLingkup,
  unitDalamLingkup, fieldEselon, unitDariField, perubahanEselonMassal,
} from "../pohonUnit";

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

// ── Lingkup kegiatan dan penurunan kolom eselon aset ─────────────────────

const DALAM = susunPohonUnit([
  ...POHON,
  { id: "e4", nama_unit: "Subbag Perlengkapan", eselon: "4", parent_id: "e3" },
]);

test("lingkup mencakup unitnya sendiri DAN seluruh keturunannya", () => {
  const ids = unitDalamLingkup(DALAM, ["e2"]).map((u) => u.id);
  expect(ids).toEqual(["e2", "e3", "e4"]);
});

test("lingkup kosong berarti seluruh unit boleh dipilih", () => {
  expect(unitDalamLingkup(DALAM, []).length).toBe(DALAM.length);
  expect(unitDalamLingkup(DALAM, null).length).toBe(DALAM.length);
});

test("lingkup pada dua cabang menggabungkan keduanya", () => {
  const ids = unitDalamLingkup(DALAM, ["e2b", "e3"]).map((u) => u.id);
  expect(ids.sort()).toEqual(["e2b", "e3", "e4"]);
});

test("field eselon terisi tiap tingkat pada rantainya", () => {
  expect(fieldEselon("e4", DALAM)).toEqual({
    eselon1: "Setjen", eselon2: "Biro Umum", eselon3: "Bagian RT",
    eselon4: "Subbag Perlengkapan", eselon5: "",
  });
});

test("tingkat yang tak terpakai dikosongkan, bukan dihilangkan", () => {
  // Kolom yang dikosongkan itulah yang menghapus sisa unit sebelumnya saat
  // aset dipindahkan ke cabang yang lebih dangkal.
  const f = fieldEselon("e1", DALAM);
  expect(Object.keys(f)).toHaveLength(5);
  expect(f.eselon2).toBe("");
  expect(fieldEselon("", DALAM).eselon1).toBe("");
});

test("unit dikenali kembali dari kolom eselon aset", () => {
  expect(unitDariField(fieldEselon("e4", DALAM), DALAM)).toBe("e4");
  expect(unitDariField(fieldEselon("e2b", DALAM), DALAM)).toBe("e2b");
});

test("jalur yang tak cocok tidak ditebak", () => {
  // Nama unit terdalam sama, jalurnya beda → bukan unit yang sama.
  expect(unitDariField(
    { eselon1: "Kedeputian X", eselon2: "Biro Umum" }, DALAM)).toBe("");
  expect(unitDariField({}, DALAM)).toBe("");
  expect(unitDariField({ eselon1: "Entah" }, DALAM)).toBe("");
});

test("ubah massal MENGOSONGKAN tingkat yang tak dipakai unit terpilih", () => {
  // Ubah massal hanya menuliskan kunci yang dikirimnya. Aset yang dipindahkan
  // dari Subbagian ke Biro akan tetap membawa eselon3 lamanya kalau tingkat
  // itu tak dinyatakan sebagai perintah kosongkan.
  expect(perubahanEselonMassal("e2", DALAM)).toEqual({
    eselon1: "Setjen", eselon2: "Biro Umum",
    eselon3: "__clear__", eselon4: "__clear__", eselon5: "__clear__",
  });
});

test("ubah massal tanpa unit terpilih tidak menyentuh kolom mana pun", () => {
  expect(perubahanEselonMassal("", DALAM)).toEqual({});
  expect(perubahanEselonMassal(null, DALAM)).toEqual({});
});

test("unit terdalam mengisi kelima kolomnya tanpa satu pun perintah kosongkan", () => {
  const r = perubahanEselonMassal("e4", DALAM);
  expect(r.eselon4).toBe("Subbag Perlengkapan");
  expect(r.eselon5).toBe("__clear__");
  expect(Object.values(r).filter((v) => v === "__clear__")).toHaveLength(1);
});
