import { normalisasiJenisOperasional, OPERASIONAL_JENIS_OPTIONS } from "./jenisOperasional";

test.each([
  ["Kegiatan/Acara/Kebutuhan", "Unit/Tempat/Tugas"],
  [" kegiatan / acara / kebutuhan ", "Unit/Tempat/Tugas"],
  ["Unit/Tempat/Tugas", "Unit/Tempat/Tugas"],
  [" unit / tempat / tugas ", "Unit/Tempat/Tugas"],
  ["Ruangan", "Ruangan"], [" ruangan ", "Ruangan"],
  ["Khusus", "Khusus"], ["", ""], [null, ""], [undefined, ""],
])("jenis %s tetap dikenali sebagai %s", (lama, baru) => {
  expect(normalisasiJenisOperasional(lama)).toBe(baru);
});

test("pilihan baru tidak lagi menawarkan istilah lama", () => {
  expect(OPERASIONAL_JENIS_OPTIONS).toEqual(["Unit/Tempat/Tugas", "Ruangan"]);
});
