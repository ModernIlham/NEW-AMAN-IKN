import { barisPilihanUnit, susunPohonUnit, unitDalamLingkup } from "../pohonUnit";

//: Struktur nyata yang dilaporkan pemilik: dua Kedeputian, masing-masing
//: membawahi beberapa Direktorat dengan nama panjang.
const MASTER = [
  { id: "k1", nama_unit: "Kedeputian Bidang Pengendalian Pembangunan",
    eselon: "1", parent_id: null },
  { id: "d11", nama_unit: "Direktorat Ketentraman dan Ketertiban Umum",
    eselon: "2", parent_id: "k1" },
  { id: "d12", nama_unit: "Direktorat Pengawasan, Pemantauan dan Evaluasi",
    eselon: "2", parent_id: "k1" },
  { id: "k2", nama_unit: "Kedeputian Bidang Transformasi Hijau dan Digital",
    eselon: "1", parent_id: null },
  { id: "d21", nama_unit: "Direktorat Data dan Kecerdasan Buatan",
    eselon: "2", parent_id: "k2" },
  { id: "b211", nama_unit: "Bagian Tata Usaha", eselon: "3", parent_id: "d21" },
];
const POHON = susunPohonUnit(MASTER);
const baris = (lingkup, kata) =>
  barisPilihanUnit(unitDalamLingkup(POHON, lingkup), POHON, kata);

describe("barisPilihanUnit — pemilih unit organisasi", () => {
  test("induk yang TAMPAK cukup dijorokkan, namanya tak diulang", () => {
    // Cacat yang dilaporkan: `<optgroup>` mencetak nama Kedeputian dua kali
    // berturut-turut — sekali sebagai pilihan, sekali sebagai judul kelompok
    // yang tak dapat disentuh.
    const r = baris([]);
    const k1 = r.find((b) => b.id === "k1");
    const d11 = r.find((b) => b.id === "d11");
    expect(k1.tingkat).toBe(0);
    expect(d11.tingkat).toBe(1);
    expect(d11.konteks).toBe("");
  });

  test("induk yang TAK tampak diceritakan sebagai konteks", () => {
    // Lingkup kegiatan yang hanya mencatat Direktorat: induknya di luar
    // daftar, jadi tak ada jorokan yang dapat menyatakan hubungannya.
    const r = baris(["d11", "d21"]);
    expect(r.map((b) => b.id)).toEqual(["d11", "d21", "b211"]);
    expect(r[0].tingkat).toBe(0);
    expect(r[0].konteks).toBe("Kedeputian Bidang Pengendalian Pembangunan");
    expect(r[1].konteks).toBe("Kedeputian Bidang Transformasi Hijau dan Digital");
  });

  test("keturunan lingkup ikut, dijorokkan di bawah induknya yang tampak", () => {
    const r = baris(["d21"]);
    const b211 = r.find((b) => b.id === "b211");
    expect(b211.tingkat).toBe(1);
    // Kedeputiannya tak tampak, jadi ia tetap disebut; Direktoratnya tampak
    // dan tidak diulang.
    expect(b211.konteks).toBe("Kedeputian Bidang Transformasi Hijau dan Digital");
  });

  test("pencarian MERATAKAN dan menyebut jalur induk lengkap", () => {
    // Induk sebuah baris bisa ikut tersaring keluar; jorokan yang menunjuk
    // induk yang tak ada di layar lebih menyesatkan daripada tak ada jorokan.
    // Tanpa saringan `b211` menjorok satu tingkat di bawah `d21`; dengan
    // saringan yang menyisakan `b211` saja, ia rata dan induknya diceritakan.
    const r = baris([], "tata usaha");
    expect(r.map((b) => b.id)).toEqual(["b211"]);
    expect(r[0].tingkat).toBe(0);
    expect(r[0].konteks).toBe(
      "Kedeputian Bidang Transformasi Hijau dan Digital / "
      + "Direktorat Data dan Kecerdasan Buatan");
    expect(baris([]).find((b) => b.id === "b211").tingkat).toBe(2);
  });

  test("mengetik nama INDUK memunculkan keturunannya", () => {
    expect(baris([], "kecerdasan").map((b) => b.id)).toEqual(["d21", "b211"]);
    // Yang dicari orang kerap Kedeputiannya, bukan nama Direktorat yang
    // panjang dan mirip satu sama lain.
    expect(baris([], "transformasi").map((b) => b.id))
      .toEqual(["k2", "d21", "b211"]);
  });

  test("kata kunci dicocokkan semuanya, bukan salah satu", () => {
    expect(baris([], "usaha tata").map((b) => b.id)).toEqual(["b211"]);
    expect(baris([], "direktorat hantu")).toEqual([]);
  });

  test("pencarian tak peduli besar-kecil huruf & spasi tepi", () => {
    // "kecerdasan" ada di nama `d21` DAN di jalur keturunannya `b211` —
    // keduanya memang harus muncul (lihat keputusan 3).
    expect(baris([], "  KECERDASAN  ").map((b) => b.id))
      .toEqual(["d21", "b211"]);
  });

  test("jalur lengkap ikut dibawa untuk keterangan pilihan terpilih", () => {
    const b211 = baris([]).find((b) => b.id === "b211");
    expect(b211.jalur).toBe(
      "Kedeputian Bidang Transformasi Hijau dan Digital / "
      + "Direktorat Data dan Kecerdasan Buatan / Bagian Tata Usaha");
    expect(b211.jalur_induk).toBe(
      "Kedeputian Bidang Transformasi Hijau dan Digital / "
      + "Direktorat Data dan Kecerdasan Buatan");
  });

  test("daftar kosong & masukan cacat tak meledak", () => {
    expect(barisPilihanUnit([], [])).toEqual([]);
    expect(barisPilihanUnit(null, null)).toEqual([]);
    expect(barisPilihanUnit([{}, null], POHON)).toEqual([]);
  });

  test("urutan pohon dipertahankan — daftar tak berpindah susunan", () => {
    expect(baris([]).map((b) => b.id))
      .toEqual(POHON.map((u) => u.id));
  });
});
