/**
 * Uji PARITAS pencarian luring ↔ server. Bila salah satu berubah tanpa yang
 * lain, kata kunci yang sama memberi hasil berbeda tergantung daring/luring —
 * penyebab keluhan "kadang ketemu, kadang tidak".
 */
import { cocokAset, pecahKata } from "./pencarianLokal";

const LAPTOP = {
  asset_code: "3.10.01.02.001", NUP: "00012",
  asset_name: "Laptop Lenovo ThinkPad X1", location: "Gudang Lantai 2",
  nomor_kontrak: "HK.02.03/123/2025",
};
const AC = { asset_code: "3.10.01.02.002", asset_name: "AC Split 1,5 PK Daikin" };
const MEJA = {
  asset_code: "3.05.01.04.007", NUP: 120,
  asset_name: "Meja Rapat Kayu Jati", year: 2021,
};

test("kata kunci terlalu pendek diabaikan (tanpa penyaringan)", () => {
  expect(pecahKata("a")).toEqual([]);
  expect(cocokAset(LAPTOP, "a")).toBe(true);
});

test("setiap kata wajib ada, boleh di field berbeda", () => {
  expect(cocokAset(LAPTOP, "lenovo gudang")).toBe(true);
  expect(cocokAset(LAPTOP, "thinkpad lenovo")).toBe(true);   // urutan bebas
  expect(cocokAset(MEJA, "lenovo gudang")).toBe(false);
  expect(cocokAset(MEJA, "meja jati")).toBe(true);
});

test("kode boleh diketik tanpa pemisah", () => {
  expect(cocokAset(LAPTOP, "3100102001")).toBe(true);
  expect(cocokAset(LAPTOP, "3.10.01.02.001")).toBe(true);
});

test("desimal koma vs titik", () => {
  expect(cocokAset(AC, "ac 1.5")).toBe(true);
  expect(cocokAset(AC, "ac 1,5")).toBe(true);
});

test("nilai bertipe angka tetap ketemu", () => {
  expect(cocokAset(MEJA, "120")).toBe(true);
  expect(cocokAset(MEJA, "2021")).toBe(true);
});

test("identitas dokumen ikut dicari", () => {
  expect(cocokAset(LAPTOP, "HK.02.03/123/2025")).toBe(true);
  expect(cocokAset(LAPTOP, "00012")).toBe(true);
});

test("kata yang tak ada menggugurkan baris", () => {
  expect(cocokAset(LAPTOP, "lenovo zzz")).toBe(false);
});
