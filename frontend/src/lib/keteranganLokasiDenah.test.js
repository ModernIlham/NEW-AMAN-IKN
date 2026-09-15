import { keteranganLokasiDenah } from "./koordinatAset";

test("cache lama tidak mengaku belum ditempatkan ketika metadata belum ada", () => {
  expect(keteranganLokasiDenah({ location: "Manual" }, { dariCache: true }))
    .toBe("Informasi denah belum tersinkron");
});

test.each([
  [{ lokasi_spasial: { node_id: "r1", jalur_nama: "Gedung / Lantai / Ruang" } }, "Gedung / Lantai / Ruang"],
  [{ di_denah: true, denah_jalur: "Gedung / Ruang" }, "Gedung / Ruang"],
  [{ lokasi_spasial: { node_id: "", titik: [116.9, -1.5] } }, "Di luar kawasan terpetakan"],
  [{ di_denah: false, denah_titik: [116.9, -1.5] }, "Di luar kawasan terpetakan"],
  [{ lokasi_spasial: null }, "Belum ditempatkan di denah"],
  [{ koordinat_latitude: "-1.5", koordinat_longitude: "116.9" }, "Belum ditempatkan di denah"],
  [{ denah_titik: [116.9, 95] }, "Belum ditempatkan di denah"],
  [{ denah_titik: [null, null] }, "Belum ditempatkan di denah"],
  [{ denah_titik: [0, 0] }, "Belum ditempatkan di denah"],
])("keterangan dari detail/daftar sama dan tidak menebak lokasi manual: %s", (aset, label) => {
  expect(keteranganLokasiDenah({ ...aset, location: "Tidak boleh dipakai sebagai nama denah" })).toBe(label);
});
