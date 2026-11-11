import { adalahLuar, bacaPilihan, kunciTingkat, labelLingkup, paramLingkup,
  ranah, simpanPilihan } from "../ranahPegawai";

beforeEach(() => window.localStorage.clear());

test("ranah internal memakai jalur lama persis", () => {
  expect(ranah("internal")).toEqual({ kelompok: "internal", luar: false,
    pegawai: "/pegawai", unit: "/unit-kerja" });
  expect(ranah("tak-dikenal").pegawai).toBe("/pegawai");
});

test("ranah luar memakai jalur direktori luar", () => {
  for (const k of ["eksternal", "pihak_ketiga"]) {
    expect(ranah(k)).toMatchObject({ luar: true, pegawai: "/pegawai-luar",
      unit: "/unit-kerja-luar" });
    expect(adalahLuar(k)).toBe(true);
  }
});

test("parameter lingkup: tataran hanya eksternal, internal kosong", () => {
  const lk = { provinsi: { id: "p" }, instansi: { id: "i" }, satker: { id: "s" } };
  expect(paramLingkup("internal", "pusat", lk)).toEqual({});
  expect(paramLingkup("eksternal", "daerah", lk)).toEqual({ kelompok: "eksternal",
    tataran: "daerah", provinsi_id: "p", instansi_id: "i", satker_luar_id: "s" });
  expect(paramLingkup("pihak_ketiga", "daerah", {})).toEqual({ kelompok: "pihak_ketiga" });
});

test("kunci tingkat dan label lingkup", () => {
  expect(kunciTingkat("eksternal", "daerah")).toBe("eksternal_daerah");
  expect(kunciTingkat("eksternal", "pusat")).toBe("eksternal_pusat");
  expect(kunciTingkat("pihak_ketiga", "pusat")).toBe("pihak_ketiga");
  expect(labelLingkup({ instansi: { nama: "Kementerian X" },
    satker: { nama_satker: "Sekretariat" } })).toBe("Kementerian X — Sekretariat");
  expect(labelLingkup({ instansi: { nama: "Kabupaten Y", jenis: "pemerintah_kabkota",
    provinsi_nama: "Provinsi Z" } })).toBe("Kabupaten Y, Provinsi Z");
});

test("pilihan tersimpan dibaca kembali; data rusak/ditolak → null", () => {
  expect(bacaPilihan()).toBeNull();
  simpanPilihan("eksternal", "daerah");
  expect(bacaPilihan()).toEqual({ kelompok: "eksternal", tataran: "daerah" });
  window.localStorage.setItem("aman.pegawai.ranah", "{rusak");
  expect(bacaPilihan()).toBeNull();
  const asli = Storage.prototype.getItem;
  Storage.prototype.getItem = () => { throw new Error("ditolak"); };
  expect(bacaPilihan()).toBeNull();
  Storage.prototype.getItem = asli;
});
