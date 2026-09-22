/**
 * Uji saringan peta kolaborasi: empat saringan bekerja bersama (AND), dan
 * pilihannya lahir dari data peta itu sendiri.
 */
import {
  SEMUA, STATUS_BAWAAN, daftarGrup, daftarNilai, hitungFilterAktif, kunciGrup, saringAset, cariPilihanPeta, pilihanSaringan, togglePilihanSaringan,
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

describe("pencarian pilihan, bukan penyaringan titik", () => {
  const pilihan = [
    { nilai: "a", label: "Gedung A Lantai 2" },
    { nilai: "b", label: "Laptop Rapat", kode: "3.10.01.02.001" },
    { nilai: "c", label: "Laptop Kerja", kode: "3.10.01.02.002" },
  ];
  test.each([
    ["  GEDUNG   lantai ", ["a"]], ["laptop", ["b", "c"]],
    ["3100102001", ["b"]], ["3.10.01 laptop", ["b", "c"]],
    ["3100102002 kerja", ["c"]], ["tidak ada", []], ["[.*", []], ["...", []],
  ])("%s mencocokkan label/kode tanpa regex pengguna", (cari, harapan) => {
    expect(cariPilihanPeta(pilihan, cari).map(p => p.nilai)).toEqual(harapan);
  });
  test("kosong mempertahankan daftar dan urutan asli", () => {
    expect(cariPilihanPeta(pilihan, "  ")).toBe(pilihan);
    expect(cariPilihanPeta(undefined, "x")).toEqual([]);
    expect(cariPilihanPeta(null, "")).toEqual([]);
  });
});

describe("pilihan jamak pada semua saringan", () => {
  test.each([
    ["status", ["Ditemukan", "Tidak Ditemukan"], ["1", "2", "3"]],
    ["kondisi", ["Baik", "Rusak Ringan"], ["1", "2", "3"]],
    ["lokasi", ["Gedung A", "Gedung B"], ["1", "2", "3"]],
    ["grup", [kunciGrup(ASET[0]), kunciGrup(ASET[2])], ["1", "2", "3"]],
  ])("%s memakai ATAU, tidak menggandakan aset", (field, values, expected) => {
    expect(id(saringAset(ASET, { [field]: [...values, values[0]] }))).toEqual(expected);
  });
  test("empat saringan jamak digabung dengan DAN dan mempertahankan urutan sumber", () => {
    expect(id(saringAset(ASET, { status: ["Ditemukan", "Tidak Ditemukan"],
      kondisi: ["Baik", "Rusak Berat"], lokasi: ["Gedung A", "Gedung B"],
      grup: [kunciGrup(ASET[0]), kunciGrup(ASET[3])] }))).toEqual(["1"]);
    expect(saringAset(ASET, { lokasi: ["tidak ada"], kondisi: ["Baik"] })).toEqual([]);
  });
  test("kosong tidak menyaring; scalar era lama tetap didukung", () => {
    expect(saringAset(ASET, { status: [], kondisi: [], lokasi: [], grup: [] })).toBe(ASET);
    expect(pilihanSaringan(SEMUA)).toEqual([]);
    expect(pilihanSaringan("Gedung A")).toEqual(["Gedung A"]);
    expect(pilihanSaringan([null, "", "Gedung A", "Gedung A"])).toEqual(["Gedung A"]);
    expect(hitungFilterAktif({ status: [], kondisi: [], lokasi: ["A", "B"], grup: ["x"] })).toBe(2);
  });
  test("toggle murni, menghapus terakhir kembali Semua, reset satu kelompok", () => {
    const prev = Object.freeze(["A", "B"]);
    expect(togglePilihanSaringan(prev, "A")).toEqual(["B"]);
    expect(togglePilihanSaringan(prev, "C")).toEqual(["A", "B", "C"]);
    expect(togglePilihanSaringan(["A"], "A")).toEqual([]);
    expect(togglePilihanSaringan(prev, SEMUA)).toEqual([]);
    expect(prev).toEqual(["A", "B"]);
  });
  test("pilihan status bawaan tersedia untuk aset era lama", () => {
    expect(daftarNilai(ASET, "status")).toContainEqual({ nilai: STATUS_BAWAAN, jumlah: 1 });
    expect(id(saringAset(ASET, { status: [STATUS_BAWAAN, "Tidak Ditemukan"] }))).toEqual(["3", "4"]);
  });
});
