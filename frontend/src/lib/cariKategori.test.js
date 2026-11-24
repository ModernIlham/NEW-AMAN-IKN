import { cariKategori, KODE_BARANG_BAWAAN } from "./cariKategori";

const CATS = [
  { id: "d", label: "Dummy", kode_aset: "0000000000" },
  { id: "1", label: "Laptop", kode_aset: "3100102003" },
  { id: "2", label: "Meja Kerja Pegawai", kode_aset: "3050104001" },
  { id: "3", label: "Kursi Kerja", kode_aset: "3050104004" },
];

test("kueri kosong mengembalikan daftar awal", () => {
  expect(cariKategori(CATS, "")).toHaveLength(4);
  expect(cariKategori(null, "x")).toEqual([]);
});

test("cari uraian multi-kata (AND, tak peka huruf)", () => {
  expect(cariKategori(CATS, "kerja meja").map((c) => c.id)).toEqual(["2"]);
  expect(cariKategori(CATS, "KERJA").map((c) => c.id)).toEqual(["2", "3"]);
});

test("cari kode, termasuk bertitik", () => {
  expect(cariKategori(CATS, "3.05.01.04").map((c) => c.id)).toEqual(["2", "3"]);
  expect(cariKategori(CATS, "31001").map((c) => c.id)).toEqual(["1"]);
});

test("awalan kode diurutkan lebih dulu", () => {
  const cats = [{ id: "a", label: "Barang 3100", kode_aset: "2000000000" }, { id: "b", label: "Laptop", kode_aset: "3100102003" }];
  expect(cariKategori(cats, "3100").map((c) => c.id)).toEqual(["b", "a"]);
});

test("batas jumlah hasil", () => {
  expect(cariKategori(CATS, "", 2)).toHaveLength(2);
  expect(KODE_BARANG_BAWAAN).toBe("0000000000");
});
