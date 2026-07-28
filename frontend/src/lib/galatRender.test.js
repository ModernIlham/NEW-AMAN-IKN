import { galatUnduhPotongan, pesanGalatRender } from "./galatRender";

describe("galatUnduhPotongan", () => {
  test("mengenali ChunkLoadError dari nama galat (webpack)", () => {
    const e = new Error("Loading chunk 42 failed.");
    e.name = "ChunkLoadError";
    expect(galatUnduhPotongan(e)).toBe(true);
  });

  test("mengenali dari PESAN saja walau namanya cuma Error", () => {
    // Beberapa peramban membungkus ulang galatnya dan nama aslinya hilang.
    expect(galatUnduhPotongan(new Error("Loading chunk 7 failed. (missing)")))
      .toBe(true);
  });

  test("mengenali kalimat modul ES asli (Safari/Firefox/Chrome)", () => {
    for (const p of [
      "Failed to fetch dynamically imported module: https://x/static/js/9.js",
      "error loading dynamically imported module",
      "Importing a module script failed.",
    ]) {
      expect(galatUnduhPotongan(new Error(p))).toBe(true);
    }
  });

  test("BUKAN galat unduh: bug render biasa", () => {
    expect(galatUnduhPotongan(new TypeError("x is not a function"))).toBe(false);
    expect(galatUnduhPotongan(new Error("Cannot read properties of undefined")))
      .toBe(false);
  });

  test("aman terhadap null/undefined/objek aneh", () => {
    expect(galatUnduhPotongan(null)).toBe(false);
    expect(galatUnduhPotongan(undefined)).toBe(false);
    expect(galatUnduhPotongan({})).toBe(false);
  });

  test("string mentah pun dinilai dari isinya", () => {
    expect(galatUnduhPotongan("Loading CSS chunk 3 failed")).toBe(true);
    expect(galatUnduhPotongan("sesuatu yang lain")).toBe(false);
  });
});

describe("pesanGalatRender", () => {
  test("galat unduh potongan → menyebut sinyal & versi baru, BUKAN pesan mentah", () => {
    const e = new Error("Loading chunk 12 failed.");
    e.name = "ChunkLoadError";
    const p = pesanGalatRender(e);
    expect(p).toMatch(/gagal diunduh/i);
    expect(p).toMatch(/versi baru/i);
    // Pesan teknis webpack tak berarti apa-apa bagi operator lapangan.
    expect(p).not.toMatch(/chunk/i);
  });

  test("galat lain → pesan aslinya IKUT ditampilkan (bahan diagnosis)", () => {
    expect(pesanGalatRender(new TypeError("peta.setView is not a function")))
      .toContain("peta.setView is not a function");
  });

  test("galat tanpa pesan tetap menghasilkan kalimat utuh", () => {
    expect(pesanGalatRender(new Error(""))).toBe(
      "Terjadi galat saat menampilkan halaman ini.");
    expect(pesanGalatRender(null)).toBe(
      "Terjadi galat saat menampilkan halaman ini.");
  });

  test("pesan berspasi saja diperlakukan sebagai kosong", () => {
    expect(pesanGalatRender(new Error("   "))).toBe(
      "Terjadi galat saat menampilkan halaman ini.");
  });
});
