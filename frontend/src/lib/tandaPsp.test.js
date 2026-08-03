import {
  infoPsp, terPsp, tersinkronSiman, berTitikHijau, tanggalSingkat, keteranganPsp,
} from "./tandaPsp";

const aset = (psp, siman) => ({ id: "a1", psp, siman });

describe("terPsp", () => {
  test("aset tanpa keterangan psp belum ber-PSP", () => {
    expect(terPsp({ id: "a1" })).toBe(false);
    expect(terPsp(null)).toBe(false);
  });

  test("no_psp kosong / hanya spasi TIDAK dihitung ber-PSP", () => {
    expect(terPsp(aset({ no_psp: "" }))).toBe(false);
    expect(terPsp(aset({ no_psp: "   " }))).toBe(false);
  });

  test("no_psp terisi = ber-PSP", () => {
    expect(terPsp(aset({ no_psp: "SK-1/2024" }))).toBe(true);
  });
});

describe("tersinkronSiman", () => {
  test("status cocok = tersinkron", () => {
    expect(tersinkronSiman(aset(null, { status: "cocok" }))).toBe(true);
  });

  test("selisih BELUM tersinkron sampai sinkron sesi ini tuntas", () => {
    const a = aset(null, { status: "selisih" });
    expect(tersinkronSiman(a, false)).toBe(false);
    expect(tersinkronSiman(a, true)).toBe(true);
  });

  // Ini pembeda yang mudah salah: "ada di impor tapi tak ketemu" adalah
  // KEBALIKAN dari tersinkron, bukan varian lemah darinya.
  test("tidak_di_siman BUKAN tersinkron, bahkan setelah tombol sinkron", () => {
    const a = aset(null, { status: "tidak_di_siman" });
    expect(tersinkronSiman(a, false)).toBe(false);
    expect(tersinkronSiman(a, true)).toBe(false);
  });

  test("aset yang belum pernah tersentuh impor bukan tersinkron", () => {
    expect(tersinkronSiman({ id: "a1" })).toBe(false);
  });
});

describe("berTitikHijau — WAJIB dua syarat", () => {
  test("ber-PSP + tersinkron = titik hijau", () => {
    expect(berTitikHijau(aset({ no_psp: "SK-1" }, { status: "cocok" }))).toBe(true);
  });

  test("ber-PSP tapi belum tersinkron = TANPA titik", () => {
    expect(berTitikHijau(aset({ no_psp: "SK-1" }, { status: "selisih" }))).toBe(false);
    expect(berTitikHijau(aset({ no_psp: "SK-1" }, { status: "tidak_di_siman" }))).toBe(false);
    expect(berTitikHijau(aset({ no_psp: "SK-1" }, undefined))).toBe(false);
  });

  test("tersinkron tapi belum ber-PSP = TANPA titik", () => {
    expect(berTitikHijau(aset(null, { status: "cocok" }))).toBe(false);
  });

  test("selisih yang baru disinkronkan + ber-PSP = titik hijau", () => {
    expect(berTitikHijau(aset({ no_psp: "SK-1" }, { status: "selisih" }), true)).toBe(true);
  });
});

describe("tanggalSingkat", () => {
  test("ISO diformat gaya Indonesia", () => {
    expect(tanggalSingkat("2024-03-12")).toMatch(/12 Mar(et)?\.? 2024/);
  });

  test("ISO panjang dipangkas ke tanggal", () => {
    expect(tanggalSingkat("2024-03-12T08:00:00Z")).toMatch(/12 Mar(et)?\.? 2024/);
  });

  test("nilai tak terbaca dikembalikan apa adanya, tidak jadi Invalid Date", () => {
    expect(tanggalSingkat("-")).toBe("-");
    expect(tanggalSingkat("")).toBe("");
    expect(tanggalSingkat(null)).toBe("");
  });
});

describe("keteranganPsp", () => {
  test("kosong bila belum ber-PSP", () => {
    expect(keteranganPsp({ id: "a1" })).toBe("");
  });

  test("menyebut nomor, tanggal, SUMBER, dan status sinkron", () => {
    const t = keteranganPsp(
      aset({ no_psp: "SK-9/2024", tanggal: "2024-03-12", sumber: "register" },
           { status: "cocok" }));
    expect(t).toContain("No. PSP SK-9/2024");
    expect(t).toContain("2024");
    expect(t).toContain("register SK PSP");
    expect(t).toContain("tersinkron SIMAN V2");
  });

  test("sumber SIMAN disebut berbeda dari register — bukan disamarkan", () => {
    const t = keteranganPsp(aset({ no_psp: "SK-9", sumber: "siman" }, { status: "cocok" }));
    expect(t).toContain("referensi SIMAN V2");
    expect(t).not.toContain("register SK PSP");
  });

  test("tanpa tanggal, kalimat tetap rapi (tanpa pemisah menggantung)", () => {
    const t = keteranganPsp(aset({ no_psp: "SK-9", tanggal: "", sumber: "register" }, {}));
    expect(t).toBe("No. PSP SK-9 · tercatat di register SK PSP");
  });
});
