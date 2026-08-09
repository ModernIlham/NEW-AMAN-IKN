import {
  CONDITION_COLORS, KELAS_STATUS_INVENTARISASI, STATUS_COLORS,
  STATUS_DEFAULT, kelasStatusInventarisasi,
} from "./warnaAset";

describe("warnaAset — satu sumber warna status & kondisi aset", () => {
  test("lima status inventarisasi punya hex marker; default = Belum Diinventarisasi", () => {
    expect(Object.keys(STATUS_COLORS)).toHaveLength(5);
    expect(STATUS_COLORS["Ditemukan"]).toBe("#2563eb");
    expect(STATUS_COLORS["Tidak Ditemukan"]).toBe("#dc2626");
    expect(STATUS_DEFAULT).toBe(STATUS_COLORS["Belum Diinventarisasi"]);
  });

  test("kondisi memakai hijau/amber/merah baku", () => {
    expect(CONDITION_COLORS["Baik"]).toBe("#059669");
    expect(CONDITION_COLORS["Rusak Berat"]).toBe("#dc2626");
  });

  test("chip status dikenal memakai kelas terang/gelap berpasangan", () => {
    expect(kelasStatusInventarisasi("Ditemukan")).toContain("emerald");
    for (const kelas of Object.values(KELAS_STATUS_INVENTARISASI)) {
      expect(kelas).toContain("dark:bg-");
      expect(kelas).toContain("dark:text-");
    }
  });

  test("status tak dikenal / kosong jatuh ke muted", () => {
    expect(kelasStatusInventarisasi("Belum Diinventarisasi"))
      .toBe("bg-muted text-muted-foreground");
    expect(kelasStatusInventarisasi("")).toBe("bg-muted text-muted-foreground");
    expect(kelasStatusInventarisasi(undefined))
      .toBe("bg-muted text-muted-foreground");
  });
});
