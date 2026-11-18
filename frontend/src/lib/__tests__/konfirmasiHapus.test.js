import { frasaKonfirmasiHapus, konfirmasiCocok } from "@/lib/konfirmasiHapus";

test("frasa = nama kegiatan dirapikan; kosong → HAPUS", () => {
  expect(frasaKonfirmasiHapus("  Inventarisasi   2026 ")).toBe("Inventarisasi 2026");
  expect(frasaKonfirmasiHapus("")).toBe("HAPUS");
  expect(frasaKonfirmasiHapus(null)).toBe("HAPUS");
});

test("cocok mengabaikan spasi berlebih & huruf besar/kecil, bukan isi", () => {
  expect(konfirmasiCocok(" inventarisasi  2026", "Inventarisasi 2026")).toBe(true);
  expect(konfirmasiCocok("Inventarisasi 202", "Inventarisasi 2026")).toBe(false);
  expect(konfirmasiCocok("", "Inventarisasi 2026")).toBe(false);
  expect(konfirmasiCocok("", "")).toBe(false);
});
