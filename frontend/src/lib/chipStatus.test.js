import { KELAS_CHIP, WARNA_CHIP, kelasChipStatus } from "./chipStatus";

describe("chipStatus — kanon chip status register", () => {
  test("kelas dasar memuat geometri kanon (rounded 10px semibold)", () => {
    expect(KELAS_CHIP).toContain("rounded");
    expect(KELAS_CHIP).toContain("text-[10px]");
    expect(KELAS_CHIP).toContain("font-semibold");
  });

  test("status dikenal memakai warna peta", () => {
    const peta = { selesai: WARNA_CHIP.emerald, berjalan: WARNA_CHIP.amber };
    const kelas = kelasChipStatus(peta, "selesai");
    expect(kelas).toContain(WARNA_CHIP.emerald);
    expect(kelas).toContain(KELAS_CHIP);
  });

  test("status tak dikenal / peta kosong jatuh ke muted (tetap terbaca)", () => {
    expect(kelasChipStatus({ a: WARNA_CHIP.sky }, "status_baru"))
      .toContain(WARNA_CHIP.muted);
    expect(kelasChipStatus(null, "apapun")).toContain(WARNA_CHIP.muted);
  });

  test("token warna memakai pasangan terang/gelap yang terbaca", () => {
    for (const [nama, kelas] of Object.entries(WARNA_CHIP)) {
      if (nama === "muted") continue;
      expect(kelas).toContain("/15");
      expect(kelas).toContain("dark:text-");
    }
  });
});
