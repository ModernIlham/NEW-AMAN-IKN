/**
 * Kartu ringkasan saat LURING dihitung dari baris yang sedang ditampilkan.
 *
 * Sebelum ini kartu offline memakai angka daring terakhir: filter diubah,
 * daftar menyusut, kartu diam. Sama persis dengan keluhan pada jalur daring,
 * hanya lebih sulit disadari karena layar sedang offline dan orang cenderung
 * memaafkannya.
 *
 * Yang paling gampang salah di sini adalah `purchase_price`: di snapshot ia
 * bisa berupa angka, teks, string kosong, null, atau tidak ada sama sekali.
 * Satu NaN saja membuat seluruh "Total Nilai" tampil sebagai NaN.
 */
import { angkaAman, hitungStatistikBaris, statistikUntukKartu } from "./statistikAset";

describe("angkaAman", () => {
  test("teks angka dibaca, sampah jadi nol", () => {
    expect(angkaAman(1500)).toBe(1500);
    expect(angkaAman("1500")).toBe(1500);
    expect(angkaAman("")).toBe(0);
    expect(angkaAman(null)).toBe(0);
    expect(angkaAman(undefined)).toBe(0);
    expect(angkaAman("bukan angka")).toBe(0);
    expect(angkaAman(NaN)).toBe(0);
    expect(angkaAman(Infinity)).toBe(0);
  });
});

describe("hitungStatistikBaris", () => {
  const BARIS = [
    { status: "Aktif", purchase_price: 1000000 },
    { status: "Maintenance", purchase_price: "500000" },
    { status: "Aktif", purchase_price: null },
    { status: "Rusak", purchase_price: 250000 },
  ];

  test("menghitung jumlah, nilai, aktif, dan maintenance", () => {
    expect(hitungStatistikBaris(BARIS)).toEqual({
      totalAssets: 4,
      totalValue: 1750000,
      activeCount: 2,
      maintenanceCount: 1,
    });
  });

  test("harga tak terbaca tidak meracuni total", () => {
    const s = hitungStatistikBaris([
      { status: "Aktif", purchase_price: "" },
      { status: "Aktif" },
      { status: "Aktif", purchase_price: "abc" },
    ]);
    expect(Number.isFinite(s.totalValue)).toBe(true);
    expect(s.totalValue).toBe(0);
  });

  test("status dicocokkan PERSIS, seperti $eq di server", () => {
    // "aktif" huruf kecil BUKAN "Aktif". Pencocokan longgar akan membuat angka
    // luring berbeda dari angka daring untuk data yang sama persis.
    const s = hitungStatistikBaris([{ status: "aktif" }, { status: "AKTIF" }]);
    expect(s.activeCount).toBe(0);
  });

  test("masukan kosong / bukan array tidak meledak", () => {
    expect(hitungStatistikBaris([]).totalAssets).toBe(0);
    expect(hitungStatistikBaris(null).totalAssets).toBe(0);
    expect(hitungStatistikBaris(undefined).totalValue).toBe(0);
  });
});

describe("statistikUntukKartu", () => {
  test("total nilai diformat gaya Indonesia", () => {
    const s = statistikUntukKartu([{ status: "Aktif", purchase_price: 1750000 }]);
    expect(s.totalValue).toBe((1750000).toLocaleString("id-ID"));
    expect(s.totalAssets).toBe(1);
  });
});
