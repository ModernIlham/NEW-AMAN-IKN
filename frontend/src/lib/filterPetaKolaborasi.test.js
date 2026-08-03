/**
 * Uji saringan peta kolaborasi: empat saringan bekerja bersama (AND), dan
 * pilihannya lahir dari data peta itu sendiri.
 */
import {
  SEMUA, STATUS_BAWAAN, daftarGrup, daftarNilai, hitungFilterAktif, kunciGrup, saringAset,
} from "./filterPetaKolaborasi";

const ASET = [
  { id: "1", kode: "3.10.01", nama: "Laptop", status: "Ditemukan", kondisi: "Baik", lokasi: "Gedung A" },
  { id: "2", kode: "3.10.01", nama: "Laptop", status: "Ditemukan", kondisi: "Rusak Ringan", lokasi: "Gedung B" },
  { id: "3", kode: "3.05.02", nama: "Meja", status: "Tidak Ditemukan", kondisi: "Baik", lokasi: "Gedung A" },
  { id: "4", kode: "3.05.03", nama: "Kursi", status: "", kondisi: "", lokasi: "  " },
];

const id = (list) => list.map((a) => a.id);

test("tanpa saringan, semua titik lolos", () => {
  expect(id(saringAset(ASET, {}))).toEqual(["1", "2", "3", "4"]);
  expect(id(saringAset(ASET))).toHaveLength(4);
  expect(saringAset(undefined)).toEqual([]);
});

test("saring lokasi & kondisi bekerja sendiri-sendiri", () => {
  expect(id(saringAset(ASET, { lokasi: "Gedung A" }))).toEqual(["1", "3"]);
  expect(id(saringAset(ASET, { kondisi: "Baik" }))).toEqual(["1", "3"]);
});

test("beberapa saringan berlaku bersamaan (AND), bukan salah satu saja", () => {
  expect(id(saringAset(ASET, { lokasi: "Gedung A", kondisi: "Baik", status: "Ditemukan" })))
    .toEqual(["1"]);
  // Kombinasi yang tak ada isinya menghasilkan kosong — bukan diam-diam
  // mengabaikan salah satu saringan.
  expect(saringAset(ASET, { lokasi: "Gedung B", kondisi: "Baik" })).toEqual([]);
});

test("aset tanpa status disaring lewat status bawaan", () => {
  expect(id(saringAset(ASET, { status: STATUS_BAWAAN }))).toEqual(["4"]);
});

test("saring barang serupa memakai kode+nama", () => {
  expect(id(saringAset(ASET, { grup: kunciGrup(ASET[0]) }))).toEqual(["1", "2"]);
});

test("pilihan lahir dari data, terbanyak di atas, nilai kosong dilewati", () => {
  expect(daftarNilai(ASET, "lokasi")).toEqual([
    { nilai: "Gedung A", jumlah: 2 }, { nilai: "Gedung B", jumlah: 1 },
  ]);
  // "  " (spasi) tak dihitung sebagai lokasi.
  expect(daftarNilai(ASET, "kondisi").map((k) => k.nilai)).toEqual(["Baik", "Rusak Ringan"]);
});

test("kelompok barang serupa hanya yang ≥2 unit", () => {
  expect(daftarGrup(ASET)).toEqual([
    { key: "3.10.01||Laptop", code: "3.10.01", name: "Laptop", count: 2 },
  ]);
});

test("lencana menghitung saringan yang aktif saja", () => {
  expect(hitungFilterAktif({ status: SEMUA, kondisi: SEMUA, lokasi: SEMUA, grup: SEMUA })).toBe(0);
  expect(hitungFilterAktif({ status: "Ditemukan", kondisi: SEMUA, lokasi: "Gedung A", grup: SEMUA })).toBe(2);
});
