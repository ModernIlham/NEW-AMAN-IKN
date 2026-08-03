import {
  BARIS_KEPALA, BLOK_JUDUL, JUDUL_KEPALA, SUBJUDUL_KEPALA,
  KEPALA_HALAMAN, TOMBOL_KEPALA, IKON_KEPALA, LANTAI_JUDUL,
} from "./kelasKepala";

// Uji ini menjaga DUA syarat yang harus berpasangan. Menghapus salah satunya
// mengembalikan cacat yang sudah terukur: judul halaman tergilas jadi 32 px di
// layar 360 px.
describe("kelasKepala — baris kepala boleh membungkus", () => {
  test("baris kepala memakai flex-wrap", () => {
    expect(BARIS_KEPALA).toContain("flex-wrap");
  });

  test("baris kepala memberi jarak antar-baris saat membungkus", () => {
    expect(BARIS_KEPALA).toContain("gap-y-");
  });
});

describe("kelasKepala — blok judul punya lantai lebar", () => {
  test("blok judul memakai lantai lebar, bukan min-w-0", () => {
    expect(BLOK_JUDUL).toContain(LANTAI_JUDUL);
    expect(BLOK_JUDUL).not.toContain("min-w-0");
  });

  test("lantai judul bernilai nyata (bukan 0)", () => {
    const m = LANTAI_JUDUL.match(/^min-w-\[(\d+(?:\.\d+)?)rem\]$/);
    expect(m).not.toBeNull();
    expect(Number(m[1])).toBeGreaterThanOrEqual(8);
  });

  test("blok judul tetap tumbuh mengisi sisa ruang", () => {
    expect(BLOK_JUDUL).toContain("flex-1");
  });
});

describe("kelasKepala — teks kepala tak pernah meluber", () => {
  test.each([
    ["judul", JUDUL_KEPALA],
    ["keterangan", SUBJUDUL_KEPALA],
  ])("%s dipangkas dengan elipsis", (_nama, kelas) => {
    expect(kelas).toContain("truncate");
  });
});

describe("kelasKepala — bilah & kontrol seragam", () => {
  test("bilah kepala menempel di atas", () => {
    expect(KEPALA_HALAMAN).toContain("sticky top-0");
  });

  test("tombol & ikon kepala tak ikut menyusut", () => {
    expect(TOMBOL_KEPALA).toContain("flex-shrink-0");
    expect(IKON_KEPALA).toContain("flex-shrink-0");
  });

  test("kotak ikon tidak menetapkan warna latar (milik tiap halaman)", () => {
    expect(IKON_KEPALA).not.toMatch(/\bbg-/);
  });
});
