import {
  susunPohonUnit, jalurUnit, ringkasLingkup,
  unitDalamLingkup, fieldEselon, unitDariField, perubahanEselonMassal,
  unitTerdalam, jalurEselon, kelompokPilihanUnit,
  opsiEselonBertingkat, pilihanEselonUsang,
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

// ── Penyebutan unit aset pada tampilan sempit ───────────────────────────

const ASET_DALAM = {
  eselon1: "Setjen", eselon2: "Biro Umum", eselon3: "Bagian RT",
  eselon4: "Subbag Perlengkapan", eselon5: "Urusan Gudang",
};

test("unit terdalam yang disebut, bukan Eselon II", () => {
  // Aset sebuah Urusan yang ditampilkan sebagai Bironya menyebut unit yang
  // bukan pemegangnya.
  expect(unitTerdalam(ASET_DALAM)).toBe("Urusan Gudang");
  expect(unitTerdalam({ eselon1: "Setjen", eselon2: "Biro Umum" })).toBe("Biro Umum");
  expect(unitTerdalam({ eselon1: "Setjen" })).toBe("Setjen");
});

test("jalur putus di tengah tetap menyebut yang terdalam terisi", () => {
  expect(unitTerdalam({ eselon1: "Setjen", eselon3: "Bagian RT" })).toBe("Bagian RT");
});

test("aset tanpa unit tak menyebut apa pun", () => {
  expect(unitTerdalam({})).toBe("");
  expect(unitTerdalam(null)).toBe("");
  expect(unitTerdalam({ eselon2: "   " })).toBe("");
});

test("jalur menulis seluruh tingkat yang terisi", () => {
  expect(jalurEselon(ASET_DALAM)).toBe(
    "Setjen / Biro Umum / Bagian RT / Subbag Perlengkapan / Urusan Gudang");
});

test("jalur yang dipotong membuang bagian AWAL dan menandainya", () => {
  // Eselon I sama untuk hampir semua aset satker, jadi ia yang paling sedikit
  // membedakan; yang menjelaskan letak barang adalah unit terdalamnya.
  expect(jalurEselon(ASET_DALAM, 2)).toBe("… / Subbag Perlengkapan / Urusan Gudang");
  expect(jalurEselon(ASET_DALAM, 5)).not.toContain("…");
});

test("jalur pendek tak pernah ditandai terpotong", () => {
  expect(jalurEselon({ eselon1: "Setjen" }, 2)).toBe("Setjen");
  expect(jalurEselon({}, 2)).toBe("");
});

// ── Pengelompokan pilihan unit untuk pemilih bawaan ─────────────────────

test("pilihan dikelompokkan menurut jalur induknya", () => {
  const pohon = susunPohonUnit([
    ...POHON,
    { id: "e4", nama_unit: "Subbag Perlengkapan", eselon: "4", parent_id: "e3" },
  ]);
  // Lingkup mencatat Biro Umum: yang boleh dipilih Biro Umum + turunannya.
  const grup = kelompokPilihanUnit(unitDalamLingkup(pohon, ["e2"]), pohon);
  expect(grup.map((g) => g.label)).toEqual([
    "Setjen", "Setjen / Biro Umum", "Setjen / Biro Umum / Bagian RT"]);
  expect(grup.map((g) => g.opsi.map((u) => u.id))).toEqual([
    ["e2"], ["e3"], ["e4"]]);
});

test("beberapa unit seinduk masuk satu kelompok", () => {
  // Inilah keadaan yang dilaporkan: lingkup mencatat beberapa Direktorat,
  // seluruhnya sedalam yang sama, sehingga daftarnya rata tanpa hierarki.
  const pohon = susunPohonUnit(POHON);
  const grup = kelompokPilihanUnit(unitDalamLingkup(pohon, ["e2", "e2b"]), pohon);
  const setjen = grup.filter((g) => g.label === "Setjen");
  expect(setjen).toHaveLength(1);
  expect(setjen[0].opsi.map((u) => u.nama_unit))
    .toEqual(["Biro Keuangan", "Biro Umum"]);
});

test("unit puncak tak berlabel kelompok", () => {
  const pohon = susunPohonUnit(POHON);
  const grup = kelompokPilihanUnit(pohon, pohon);
  expect(grup[0].label).toBe("");
  expect(grup[0].opsi.map((u) => u.id)).toEqual(["e1"]);
});

test("daftar kosong menghasilkan kelompok kosong", () => {
  expect(kelompokPilihanUnit([], [])).toEqual([]);
  expect(kelompokPilihanUnit(null, null)).toEqual([]);
});

// ── Opsi filter eselon: bertingkat, dan hanya yang berdata ─────────────

const JALUR = [
  ["Setjen", "Biro Umum", "Bagian RT", "", ""],
  ["Setjen", "Biro Umum", "Bagian Keuangan", "", ""],
  ["Setjen", "Biro Keuangan", "", "", ""],
  ["Kedeputian X", "Direktorat Y", "", "", ""],
];

test("tingkat tanpa data tak ditawarkan sama sekali", () => {
  // Satker yang mencatat sampai Eselon III mendapat tiga kotak "Semua" yang
  // tak pernah punya isi — memakan ruang dan mengesankan datanya hilang.
  const o = opsiEselonBertingkat(JALUR, {});
  expect(o.eselon4s).toEqual([]);
  expect(o.eselon5s).toEqual([]);
  expect(o.eselon1s).toEqual(["Kedeputian X", "Setjen"]);
});

test("Eselon II menyempit mengikuti Eselon I yang terpilih", () => {
  const o = opsiEselonBertingkat(JALUR, { eselon1: ["Setjen"] });
  expect(o.eselon2s).toEqual(["Biro Keuangan", "Biro Umum"]);
  expect(o.eselon2s).not.toContain("Direktorat Y");
});

test("penyempitan berlanjut ke tingkat berikutnya", () => {
  const o = opsiEselonBertingkat(
    JALUR, { eselon1: ["Setjen"], eselon2: ["Biro Umum"] });
  expect(o.eselon3s).toEqual(["Bagian Keuangan", "Bagian RT"]);
  const p = opsiEselonBertingkat(
    JALUR, { eselon1: ["Setjen"], eselon2: ["Biro Keuangan"] });
  expect(p.eselon3s).toEqual([]);
});

test("pemilih TAK menyempitkan dirinya sendiri", () => {
  // Kalau ia ikut menyaring dirinya, memilih satu nilai membuat nilai lain
  // lenyap dari daftarnya dan penggunanya terkurung tanpa kotak untuk
  // mengembalikannya.
  const o = opsiEselonBertingkat(JALUR, { eselon1: ["Setjen"] });
  expect(o.eselon1s).toEqual(["Kedeputian X", "Setjen"]);
});

test("dua pilihan pada satu tingkat menggabungkan cabangnya", () => {
  const o = opsiEselonBertingkat(
    JALUR, { eselon1: ["Setjen", "Kedeputian X"] });
  expect(o.eselon2s).toEqual(["Biro Keuangan", "Biro Umum", "Direktorat Y"]);
});

test("tanpa pilihan apa pun, seluruh nilai yang ada ditawarkan", () => {
  const o = opsiEselonBertingkat(JALUR, {});
  expect(o.eselon2s).toEqual(
    ["Biro Keuangan", "Biro Umum", "Direktorat Y"]);
});

test("masukan kosong dan cacat tak melempar", () => {
  const o = opsiEselonBertingkat(null, null);
  expect(o.eselon1s).toEqual([]);
  expect(opsiEselonBertingkat([["A"]], {}).eselon1s).toEqual([]);
});

test("pilihan yang jadi mustahil dilaporkan sebagai usang", () => {
  // Filter yang tertinggal di tingkat bawah menyaring diam-diam: daftarnya
  // menyusut, kotaknya masih menyebut nilai yang sudah tak ada pilihannya.
  const usang = pilihanEselonUsang(
    JALUR, { eselon1: ["Kedeputian X"], eselon2: ["Biro Umum"] });
  expect(usang).toEqual({ eselon2: ["Biro Umum"] });
});

test("pilihan yang masih sah tak dilaporkan usang", () => {
  expect(pilihanEselonUsang(
    JALUR, { eselon1: ["Setjen"], eselon2: ["Biro Umum"] })).toEqual({});
  expect(pilihanEselonUsang(JALUR, {})).toEqual({});
});

test("tanpa data jalur, tak satu pun pilihan dianggap usang", () => {
  // Keadaan paling lumrah: sebelum filter-options selesai dimuat, dan ketika
  // pemuatannya gagal — yang memang sengaja diam karena bersifat pelengkap.
  // Tanpa penjagaan ini, setiap filter eselon yang sudah dipasang pengguna
  // terhapus sendiri pada saat itu juga.
  const dipasang = { eselon1: ["Setjen"], eselon2: ["Biro Umum"] };
  expect(pilihanEselonUsang([], dipasang)).toEqual({});
  expect(pilihanEselonUsang(null, dipasang)).toEqual({});
  expect(pilihanEselonUsang(undefined, dipasang)).toEqual({});
});
