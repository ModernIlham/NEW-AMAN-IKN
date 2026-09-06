import {
  AKAR_BAWAAN, LEVEL_MAKS, bolehTambah, butuhInduk, labelLevel, levelAkar,
  levelSah, levelTampil, levelTersedia, unitAkar,
} from "./eselonSatker";

const lapas = { eselon: "3", id: "u3", parent_id: "" };

describe("eselonSatker — akar pohon unit mengikuti tingkat satkernya", () => {
  test("akar dibaca apa adanya bila sah", () => {
    expect(levelAkar(3)).toBe(3);
    expect(levelAkar("4")).toBe(4);
    expect(levelAkar(" 2 ")).toBe(2);
  });

  test("akar tak dinyatakan / tak sah jatuh ke Eselon I (perilaku lama)", () => {
    // Satker lama tak punya field ini; menolaknya akan mematikan pengelolaan
    // unit di seluruh pemasangan yang sudah berjalan.
    expect(levelAkar(undefined)).toBe(AKAR_BAWAAN);
    expect(levelAkar("")).toBe(AKAR_BAWAAN);
    expect(levelAkar(0)).toBe(AKAR_BAWAAN);
    expect(levelAkar(9)).toBe(AKAR_BAWAAN);
    expect(levelAkar("dua")).toBe(AKAR_BAWAAN);
    expect(levelAkar(2.5)).toBe(AKAR_BAWAAN);
  });

  test("levelSah hanya mengakui 1–5", () => {
    expect(levelSah("5")).toBe(5);
    expect([levelSah(0), levelSah(6), levelSah(""), levelSah(null)])
      .toEqual([null, null, null, null]);
  });

  test("label memakai angka Romawi, dan kosong bila tingkatnya tak dikenal", () => {
    expect(labelLevel(3)).toBe("Eselon III");
    expect(labelLevel(LEVEL_MAKS)).toBe("Eselon V");
    expect(labelLevel(7)).toBe("");
  });

  test("tingkat yang boleh ditambah bermula di akar, bukan di Eselon I", () => {
    expect(levelTersedia(3)).toEqual([3, 4, 5]);
    expect(levelTersedia()).toEqual([1, 2, 3, 4, 5]);
  });

  test("puncak satker TAK berinduk; di bawahnya tetap wajib", () => {
    expect(butuhInduk(3, 3)).toBe(false);
    expect(butuhInduk(4, 3)).toBe(true);
    expect(butuhInduk(5, 3)).toBe(true);
    // Satker Eselon I: persis seperti sebelumnya.
    expect(butuhInduk(1, 1)).toBe(false);
    expect(butuhInduk(2, 1)).toBe(true);
  });

  test("tingkat DI ATAS puncak bukan milik satker ini — tak boleh ditambah", () => {
    expect(bolehTambah(1, 3)).toBe(false);
    expect(bolehTambah(2, 3)).toBe(false);
    expect(bolehTambah(3, 3)).toBe(true);
    expect(bolehTambah(9, 3)).toBe(false);
  });

  test("tab menampilkan tingkat tersedia", () => {
    expect(levelTampil(3, [])).toEqual([3, 4, 5]);
  });

  test("tab IKUT menampilkan sisa unit di atas puncak agar dapat dibereskan", () => {
    // Satker yang baru menyatakan dirinya Eselon III masih menyimpan unit
    // Eselon II lama. Menyembunyikan tabnya membuat unit itu tak dapat
    // dipindah maupun dihapus — hilang dari layar, tetap hidup di data.
    expect(levelTampil(3, [{ eselon: "2" }, lapas])).toEqual([2, 3, 4, 5]);
    expect(levelTampil(3, [{ eselon: "x" }, { eselon: "" }]))
      .toEqual([3, 4, 5]);
  });

  test("akar bagan = unit tanpa induk terjangkau, apa pun eselonnya", () => {
    const units = [lapas, { id: "u4", eselon: "4", parent_id: "u3" }];
    expect(unitAkar(units).map((u) => u.id)).toEqual(["u3"]);
  });

  test("unit yang induknya sudah terhapus tetap muncul sebagai akar", () => {
    // Kalau tidak, seluruh cabangnya lenyap dari bagan tanpa satu pun tanda.
    const units = [{ id: "a", eselon: "4", parent_id: "hantu" }];
    expect(unitAkar(units).map((u) => u.id)).toEqual(["a"]);
    expect(unitAkar(null)).toEqual([]);
  });
});
