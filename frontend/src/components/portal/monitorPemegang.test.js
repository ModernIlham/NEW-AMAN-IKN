import { cariAsetPemegang, cocokMonitorPemegang, laporanTerbaruPemegang, perluPerhatianPemegang, ringkasanMonitorPemegang, tanggalMonitor, urutLaporanPemegang } from "./monitorPemegang";

test("terbaru memakai penerimaan server per penugasan, tidak waktu bukti maupun tinjauan", () => {
  const lama = { id: "lama", penugasan_id: "p1", created_at: "2026-10-01", updated_at: "2026-11-01", diambil_pada: "2026-12-01" };
  const baru = { id: "baru", penugasan_id: "p1", created_at: "2026-10-02", asset_id: "a1" };
  const pemegangLama = { id: "lama-pemegang", penugasan_id: "p0", created_at: "2026-10-03", asset_id: "a1" };
  const rows = [lama, baru, pemegangLama];
  const terbaru = laporanTerbaruPemegang(rows);
  expect(terbaru.get("p1")).toBe(baru);
  expect(terbaru.get("p0")).toBe(pemegangLama);
  expect(urutLaporanPemegang(rows)).toEqual([pemegangLama, baru, lama]);
  expect(rows).toEqual([lama, baru, pemegangLama]);
});

test("ringkasan tidak menghitung laporan yatim dan penugasan lama bukan barang diterima", () => {
  const aset = [{ id: "a", status: "diterima" }, { id: "b", status: "menunggu_konfirmasi" }];
  const reports = new Map([["c", { status: "diajukan" }]]);
  expect(ringkasanMonitorPemegang(aset, reports)).toEqual({ semua: 2, belum: 1, menunggu: 0, perhatian: 1 });
  expect(cocokMonitorPemegang(aset[1], null, "belum")).toBe(false);
});

test.each(["perlu_perbaikan", "ditolak"])("keputusan %s tampil sebagai tindak lanjut", status => {
  expect(perluPerhatianPemegang({ status: "diterima" }, { status, kondisi: "Baik" })).toBe(true);
});

test.each([{ jenis: "kehilangan" }, { kondisi: "Rusak Berat" }, { status_operasional: "diperbaiki" }])("pengamatan masalah tetap terlihat tanpa klaim keputusan resmi %j", report => {
  expect(perluPerhatianPemegang({ status: "diterima", condition: "Baik" }, { ...report, status: "terverifikasi" })).toBe(true);
});

test("barang baik yang dipakai tidak memunculkan peringatan palsu", () => {
  expect(perluPerhatianPemegang({ status: "diterima" }, { kondisi: "Baik", status_operasional: "digunakan", status: "terverifikasi" })).toBe(false);
});

test("pencarian aman saat field kosong, mencakup BAST dan lokasi laporan tanpa nama pegawai lain", () => {
  expect(cariAsetPemegang({ NUP: 0, sumber_bast: { nomor: "BAST-1" } }, { lokasi_laporan: "Bengkel" }, " bast-1 ")).toBe(true);
  expect(cariAsetPemegang({}, null, "undefined")).toBe(false);
  expect(cariAsetPemegang({}, { lokasi_laporan: "Bengkel" }, "bengkel")).toBe(true);
  expect(tanggalMonitor("bukan tanggal")).toBe("Belum tercatat");
});
