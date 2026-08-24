import { labelKoordinat, parseKoordinat, punyaKoordinat } from "./koordinatAset";

describe("parseKoordinat", () => {
  test("angka biasa terbaca", () => {
    expect(parseKoordinat("-1.234567")).toBe(-1.234567);
    expect(parseKoordinat(116.7)).toBe(116.7);
  });

  test("koma desimal gaya Indonesia terbaca", () => {
    expect(parseKoordinat("-1,234567")).toBe(-1.234567);
  });

  test("spasi tepi tak menggagalkan", () => {
    expect(parseKoordinat("  116.7  ")).toBe(116.7);
  });

  test("nol adalah koordinat yang SAH", () => {
    // Garis khatulistiwa & meridian utama. Kalau 0 dianggap kosong, aset di
    // sana akan selamanya ditandai "belum berkoordinat".
    expect(parseKoordinat("0")).toBe(0);
    expect(parseKoordinat(0)).toBe(0);
  });

  test("kosong / bukan angka / di luar jangkauan → null", () => {
    for (const v of ["", "  ", null, undefined, "abc", "181", "-999", NaN, Infinity]) {
      expect(parseKoordinat(v)).toBeNull();
    }
  });
});

describe("punyaKoordinat", () => {
  const aset = (lat, lng) => ({ koordinat_latitude: lat, koordinat_longitude: lng });

  test("kedua sumbu terisi → ya", () => {
    expect(punyaKoordinat(aset("-1.23", "116.7"))).toBe(true);
  });

  test("titik nol,nol tetap terhitung berkoordinat", () => {
    expect(punyaKoordinat(aset("0", "0"))).toBe(true);
  });

  test("satu sumbu saja BUKAN titik", () => {
    // Lintang tanpa bujur tak bisa dipetakan; menandainya "sudah" akan
    // menyuruh petugas melewati aset yang justru masih perlu diambil titiknya.
    expect(punyaKoordinat(aset("-1.23", ""))).toBe(false);
    expect(punyaKoordinat(aset("", "116.7"))).toBe(false);
  });

  test("nilai cacat → tidak", () => {
    expect(punyaKoordinat(aset("abc", "116.7"))).toBe(false);
    expect(punyaKoordinat({})).toBe(false);
    expect(punyaKoordinat(null)).toBe(false);
    expect(punyaKoordinat(undefined)).toBe(false);
  });
});

describe("labelKoordinat", () => {
  test("menyebut kedua sumbunya", () => {
    expect(labelKoordinat({ koordinat_latitude: "-1.5", koordinat_longitude: "116.7" }))
      .toBe("-1.5, 116.7");
  });

  test("kosong bila belum berkoordinat", () => {
    expect(labelKoordinat({ koordinat_latitude: "-1.5" })).toBe("");
    expect(labelKoordinat(null)).toBe("");
  });
});
