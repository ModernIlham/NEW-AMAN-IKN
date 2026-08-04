import {
  teksSisaWaktu, sudahKedaluwarsa, mendesak, warnaSisaWaktu,
} from "./sisaWaktu";

const JAM = 3600;
const HARI = 24 * JAM;

describe("teksSisaWaktu", () => {
  test("hari panjang tak menyebut jam (tak menambah keputusan apa pun)", () => {
    expect(teksSisaWaktu({ sisa_detik: 13 * HARI + 5 * JAM })).toBe("13 hari lagi");
  });

  test("sisa pendek menyebut jam — menentukan hari ini atau besok", () => {
    expect(teksSisaWaktu({ sisa_detik: 1 * HARI + 3 * JAM })).toBe("1 hari 3 jam lagi");
    expect(teksSisaWaktu({ sisa_detik: 2 * HARI + 1 * JAM })).toBe("2 hari 1 jam lagi");
  });

  test("hari bulat tak menempelkan '0 jam'", () => {
    expect(teksSisaWaktu({ sisa_detik: 2 * HARI })).toBe("2 hari lagi");
  });

  test("jam dan menit", () => {
    expect(teksSisaWaktu({ sisa_detik: 5 * JAM + 30 * 60 })).toBe("5 jam lagi");
    expect(teksSisaWaktu({ sisa_detik: 12 * 60 })).toBe("12 menit lagi");
    expect(teksSisaWaktu({ sisa_detik: 30 })).toBe("kurang dari 1 menit lagi");
  });

  test("nol dan negatif = kedaluwarsa", () => {
    expect(teksSisaWaktu({ sisa_detik: 0 })).toBe("Kedaluwarsa");
    expect(teksSisaWaktu({ sisa_detik: -500 })).toBe("Kedaluwarsa");
  });

  test("perkiraan diberi tanda ± — tak boleh tampil seolah angka pasti", () => {
    expect(teksSisaWaktu({ sisa_detik: 3 * HARI, perkiraan: true }))
      .toBe("±3 hari lagi");
  });

  test("data tak diketahui → string kosong, bukan 'NaN'", () => {
    expect(teksSisaWaktu(null)).toBe("");
    expect(teksSisaWaktu({})).toBe("");
    expect(teksSisaWaktu({ sisa_detik: null })).toBe("");
    expect(teksSisaWaktu({ sisa_detik: "bukan angka" })).toBe("");
  });
});

describe("penanda status", () => {
  test("sudahKedaluwarsa hanya untuk angka yang benar-benar ada", () => {
    expect(sudahKedaluwarsa({ sisa_detik: 0 })).toBe(true);
    expect(sudahKedaluwarsa({ sisa_detik: 10 })).toBe(false);
    expect(sudahKedaluwarsa({ sisa_detik: null })).toBe(false);
    expect(sudahKedaluwarsa(null)).toBe(false);
  });

  test("mendesak = ≤2 hari dan belum lewat", () => {
    expect(mendesak({ sisa_detik: 2 * HARI - 1 })).toBe(true);
    expect(mendesak({ sisa_detik: 2 * HARI + 1 })).toBe(false);
    expect(mendesak({ sisa_detik: 0 })).toBe(false);      // sudah lewat, bukan mendesak
    expect(mendesak({ sisa_detik: null })).toBe(false);
  });

  test("warna: merah bila lewat, amber bila mendesak, netral bila longgar", () => {
    expect(warnaSisaWaktu({ sisa_detik: 0 })).toContain("red");
    expect(warnaSisaWaktu({ sisa_detik: 6 * JAM })).toContain("amber");
    expect(warnaSisaWaktu({ sisa_detik: 10 * HARI })).toContain("muted");
  });
});
