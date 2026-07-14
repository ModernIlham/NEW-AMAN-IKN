import { koordinatValid, akurasiValid, lebihAkurat, pilihKoordinatTerbaik } from "./gpsAkurasi";

const fix = (lat, lng, accuracy) => ({ lat, lng, accuracy });

describe("koordinatValid", () => {
  test("lat/lng angka atau string angka → valid", () => {
    expect(koordinatValid(fix(-6.1, 106.8, 5))).toBe(true);
    expect(koordinatValid(fix("-6.175110", "106.865036", 5))).toBe(true);
  });
  test("null/kosong/non-angka → tak valid", () => {
    expect(koordinatValid(null)).toBe(false);
    expect(koordinatValid(fix("", "", 5))).toBe(false);
    expect(koordinatValid(fix("abc", 106.8, 5))).toBe(false);
  });
});

describe("akurasiValid", () => {
  test("accuracy ≥ 0 & finite → valid", () => {
    expect(akurasiValid(fix(-6.1, 106.8, 0))).toBe(true);
    expect(akurasiValid(fix(-6.1, 106.8, 8))).toBe(true);
  });
  test("null/negatif/tanpa koordinat → tak valid", () => {
    expect(akurasiValid(fix(-6.1, 106.8, null))).toBe(false);
    expect(akurasiValid(fix(-6.1, 106.8, -3))).toBe(false);
    expect(akurasiValid(fix(-6.1, 106.8, undefined))).toBe(false);
    expect(akurasiValid(null)).toBe(false);
  });
});

describe("lebihAkurat", () => {
  test("accuracy lebih kecil → lebih akurat", () => {
    expect(lebihAkurat(fix(-6, 106, 3), fix(-6, 106, 8))).toBe(true);
    expect(lebihAkurat(fix(-6, 106, 8), fix(-6, 106, 3))).toBe(false);
    expect(lebihAkurat(fix(-6, 106, 5), fix(-6, 106, 5))).toBe(false); // sama → bukan lebih
  });
  test("lama tak valid (null/akurasi null) tapi baru valid → baru menang", () => {
    expect(lebihAkurat(fix(-6, 106, 7), null)).toBe(true);
    expect(lebihAkurat(fix(-6, 106, 7), fix(-6, 106, null))).toBe(true);
  });
  test("baru tak valid akurasinya → tak pernah menang", () => {
    expect(lebihAkurat(fix(-6, 106, null), fix(-6, 106, 9))).toBe(false);
    expect(lebihAkurat(null, fix(-6, 106, 9))).toBe(false);
  });
});

describe("pilihKoordinatTerbaik", () => {
  test("pilih accuracy terkecil dari daftar", () => {
    const daftar = [fix(-6, 106, 12), fix(-6.1, 106.1, 4), fix(-6.2, 106.2, 9)];
    expect(pilihKoordinatTerbaik(daftar)).toEqual(fix(-6.1, 106.1, 4));
  });
  test("abaikan entri tak valid; kembalikan yang valid terbaik", () => {
    const daftar = [fix("", "", 1), fix(-6, 106, null), fix(-6.3, 106.3, 6)];
    expect(pilihKoordinatTerbaik(daftar)).toEqual(fix(-6.3, 106.3, 6));
  });
  test("kosong / tak ada yang valid / bukan array → null", () => {
    expect(pilihKoordinatTerbaik([])).toBe(null);
    expect(pilihKoordinatTerbaik([fix(-6, 106, null), null])).toBe(null);
    expect(pilihKoordinatTerbaik(null)).toBe(null);
  });
});
