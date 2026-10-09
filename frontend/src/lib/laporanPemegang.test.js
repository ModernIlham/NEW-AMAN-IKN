import { aturanCatatanLaporan, kesalahanCatatanLaporan, laporanPemegangBerubah } from "./laporanPemegang";

const normal = { jenis: "berkala", kondisi: "Baik", status_operasional: "digunakan", catatan: "" };
const jenisLaporan = ["berkala", "kerusakan", "kehilangan", "perbaikan", "pengembalian"];

test("laporan baru tanpa isian dapat ditutup tanpa konfirmasi", () => {
  expect(laporanPemegangBerubah(null)).toBe(false);
  expect(laporanPemegangBerubah({})).toBe(false);
  expect(laporanPemegangBerubah({ jenis: "berkala", kondisi: "Tidak diketahui", status_operasional: "tidak_diketahui", catatan: "", lokasi_laporan: "", diambil_pada: "", bukti: [], penugasan_id: "p1", penugasan_version: 2 })).toBe(false);
});

test.each([
  { jenis: "kehilangan" }, { kondisi: "Baik" }, { status_operasional: "digunakan" },
  { lokasi_laporan: "Ruang 1" }, { diambil_pada: "2026-10-09T10:20" },
  { catatan: "Isian" }, { bukti: [{ nama: "bukti.jpg" }] }, { laporan_sebelumnya_id: "laporan-lama" },
])("setiap isian pengamatan dilindungi saat tutup/pindai: %o", ubah => {
  expect(laporanPemegangBerubah(ubah)).toBe(true);
});

test.each(jenisLaporan)("aturan catatan %s jelas dan tidak mengubah payload", jenis => {
  const form = { ...normal, jenis };
  const sebelum = { ...form };
  const aturan = aturanCatatanLaporan(form);
  expect(aturan.wajib).toBe(jenis !== "berkala");
  expect(aturan.label).toBeTruthy(); expect(aturan.panduan).toBeTruthy();
  expect(form).toEqual(sebelum);
});

test.each(jenisLaporan.flatMap(jenis => ["", "   ", "abcd", "abcde", "  abcde  "].map(catatan => [jenis, catatan])))(
  "%s dengan catatan '%s' mengikuti batas wajib", (jenis, catatan) => {
    const error = kesalahanCatatanLaporan({ ...normal, jenis, catatan });
    expect(Boolean(error)).toBe(jenis !== "berkala" && catatan.trim().length < 5);
  });

test.each(["digunakan", "tidak_digunakan"])("berkala baik %s boleh tanpa narasi atau field catatan", status_operasional => {
  expect(kesalahanCatatanLaporan({ ...normal, status_operasional })).toBe("");
  expect(kesalahanCatatanLaporan({ jenis: "berkala", kondisi: "Baik", status_operasional })).toBe("");
});

test.each(["Baik", "Rusak Ringan", "Rusak Berat", "Tidak diketahui"].flatMap(kondisi =>
  ["digunakan", "tidak_digunakan", "diperbaiki", "tidak_diketahui"].map(status_operasional => [kondisi, status_operasional])))(
  "berkala %s / %s memerlukan alasan kecuali keadaan normal", (kondisi, status_operasional) => {
    const wajib = kondisi !== "Baik" || ["diperbaiki", "tidak_diketahui"].includes(status_operasional);
    expect(aturanCatatanLaporan({ ...normal, kondisi, status_operasional }).wajib).toBe(wajib);
    expect(Boolean(kesalahanCatatanLaporan({ ...normal, kondisi, status_operasional }))).toBe(wajib);
  });

test.each(jenisLaporan)("klarifikasi %s tetap wajib meski pemeriksaan normal", jenis => {
  const form = { ...normal, jenis, laporan_sebelumnya_id: "laporan-lama" };
  expect(aturanCatatanLaporan(form)).toEqual(expect.objectContaining({ wajib: true, label: "Tanggapan klarifikasi" }));
  expect(kesalahanCatatanLaporan(form)).toMatch(/minimal 5/);
  expect(kesalahanCatatanLaporan({ ...form, catatan: "Sudah diperiksa kembali" })).toBe("");
});

test("batas panjang memakai karakter Unicode, tanpa menambahkan narasi", () => {
  expect(kesalahanCatatanLaporan({ ...normal, jenis: "kerusakan", catatan: "😀😀😀😀" })).toMatch(/minimal 5/);
  expect(kesalahanCatatanLaporan({ ...normal, catatan: "x".repeat(5000) })).toBe("");
  expect(kesalahanCatatanLaporan({ ...normal, catatan: "x".repeat(5001) })).toMatch(/maksimal 5000/);
  expect(kesalahanCatatanLaporan()).toMatch(/Pilih jenis laporan/);
  expect(kesalahanCatatanLaporan({ ...normal, jenis: "tidak-tersedia", catatan: "Narasi lengkap" })).toMatch(/Pilih jenis laporan/);
});

test("kehilangan tidak mensyaratkan foto atau koordinat", () => {
  const form = { ...normal, jenis: "kehilangan", catatan: "Barang belum ditemukan setelah penelusuran", bukti: [] };
  expect(kesalahanCatatanLaporan(form)).toBe("");
  expect(aturanCatatanLaporan(form).panduan).toContain("Foto dan GPS tidak wajib");
});
