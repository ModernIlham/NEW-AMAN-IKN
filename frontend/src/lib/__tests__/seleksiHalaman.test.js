import { statusSeleksiHalaman, toggleSeleksiHalaman } from "../seleksiHalaman";

test("halaman sama besar dengan ID berbeda tidak dianggap semuanya terpilih", () => {
  expect(statusSeleksiHalaman(new Set(["a", "b"]), ["c", "d"]))
    .toEqual({ count: 0, total: 2, all: false, partial: false });
});

test("halaman overlap memakai keanggotaan ID dan toggle menjaga ID halaman lain", () => {
  const selected = new Set(["a", "b"]);
  expect(statusSeleksiHalaman(selected, ["b", "c"]).partial).toBe(true);
  const all = toggleSeleksiHalaman(selected, ["b", "c"]);
  expect([...all]).toEqual(["a", "b", "c"]);
  expect(statusSeleksiHalaman(all, ["b", "c"]).all).toBe(true);
  expect([...toggleSeleksiHalaman(all, ["b", "c"])]).toEqual(["a"]);
  expect([...selected]).toEqual(["a", "b"]);
});

test("halaman kosong tidak checked dan tidak menghapus seleksi", () => {
  expect(statusSeleksiHalaman(new Set(["a"]), [])).toEqual({ count: 0, total: 0, all: false, partial: false });
  expect([...toggleSeleksiHalaman(new Set(["a"]), [])]).toEqual(["a"]);
});

test("pilihan semua halaman tetap checked meskipun jumlah ID melebihi baris terlihat", () => {
  const selected = new Set(["a", "b", "c", "d"]);
  expect(statusSeleksiHalaman(selected, ["b", "c"]).all).toBe(true);
  expect([...toggleSeleksiHalaman(selected, ["b", "c"])]).toEqual(["a", "d"]);
});
