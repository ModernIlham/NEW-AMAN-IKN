import {
  labelKoordinat, normalisasiKoordinat, parseKoordinat, punyaKoordinat,
} from "./koordinatAset";

describe("parseKoordinat", () => {
  test("angka biasa terbaca", () => {
    expect(parseKoordinat("-1.234567")).toBe(-1.234567);
    expect(parseKoordinat(116.7)).toBe(116.7);
  });

  test("koma desimal gaya Indonesia terbaca", () => {
    expect(parseKoordinat("-1,234567")).toBe(-1.234567);
  });

  test("spasi tepi tak menggagalkan", () => {
    expect(parseKoordinat("  116.7  ")).toBe(116.7);
  });

  test("nol adalah koordinat yang SAH", () => {
    // Garis khatulistiwa & meridian utama. Kalau 0 dianggap kosong, aset di
    // sana akan selamanya ditandai "belum berkoordinat".
    expect(parseKoordinat("0")).toBe(0);
    expect(parseKoordinat(0)).toBe(0);
  });

  test("kosong / bukan angka / di luar jangkauan → null", () => {
    for (const v of ["", "  ", null, undefined, "abc", "181", "-999", NaN, Infinity]) {
      expect(parseKoordinat(v)).toBeNull();
    }
  });
});

describe("punyaKoordinat", () => {
  const aset = (lat, lng) => ({ koordinat_latitude: lat, koordinat_longitude: lng });

  test("kedua sumbu terisi → ya", () => {
    expect(punyaKoordinat(aset("-1.23", "116.7"))).toBe(true);
  });

  test("titik nol,nol tetap terhitung berkoordinat", () => {
    expect(punyaKoordinat(aset("0", "0"))).toBe(true);
  });

  test("satu sumbu saja BUKAN titik", () => {
    // Lintang tanpa bujur tak bisa dipetakan; menandainya "sudah" akan
    // menyuruh petugas melewati aset yang justru masih perlu diambil titiknya.
    expect(punyaKoordinat(aset("-1.23", ""))).toBe(false);
    expect(punyaKoordinat(aset("", "116.7"))).toBe(false);
  });

  test("nilai cacat → tidak", () => {
    expect(punyaKoordinat(aset("abc", "116.7"))).toBe(false);
    expect(punyaKoordinat({})).toBe(false);
    expect(punyaKoordinat(null)).toBe(false);
    expect(punyaKoordinat(undefined)).toBe(false);
  });
});

describe("labelKoordinat", () => {
  test("menyebut kedua sumbunya", () => {
    expect(labelKoordinat({ koordinat_latitude: "-1.5", koordinat_longitude: "116.7" }))
      .toBe("-1.5, 116.7");
  });

  test("kosong bila belum berkoordinat", () => {
    expect(labelKoordinat({ koordinat_latitude: "-1.5" })).toBe("");
    expect(labelKoordinat(null)).toBe("");
  });
});

// ── Penempatan denah ───────────────────────────────────────────────────
//
// Dijawab fungsi yang sama untuk DUA bentuk data: ringkasan `di_denah` yang
// dihitung server untuk baris daftar, dan subdoc `lokasi_spasial` utuh pada
// layar detail. Kalau tiap layar memeriksa bentuknya sendiri, akan ada aset
// yang di daftar tampak sudah di denah tetapi di detailnya tidak.

import { diDenah, labelDenah, labelBarisLokasi } from "./koordinatAset";

const KOORD = { koordinat_latitude: "-1.23", koordinat_longitude: "116.7" };

test("bentuk daftar (di_denah) dan bentuk detail (lokasi_spasial) sepakat", () => {
  expect(diDenah({ di_denah: true })).toBe(true);
  expect(diDenah({ di_denah: false })).toBe(false);
  expect(diDenah({ lokasi_spasial: { node_id: "n1" } })).toBe(true);
});

test("penempatan yang DILEPAS tak lagi dihitung sudah di denah", () => {
  // Melepas penempatan menyisakan subdoc dengan node_id kosong; memeriksa
  // adanya subdoc saja akan menandai aset itu masih di denah selamanya.
  expect(diDenah({ lokasi_spasial: { node_id: "" } })).toBe(false);
  expect(diDenah({ lokasi_spasial: { node_id: "   " } })).toBe(false);
  expect(diDenah({ lokasi_spasial: {} })).toBe(false);
});

test("masukan cacat tak melempar", () => {
  expect(diDenah(null)).toBe(false);
  expect(diDenah({})).toBe(false);
  expect(labelDenah(null)).toBe("");
});

test("ringkasan server MENANG atas subdoc bila keduanya ada", () => {
  // Baris daftar tak membawa lokasi_spasial; bila kelak ikut terbawa, yang
  // dipakai harus tetap satu supaya kedua layar tak berselisih.
  expect(diDenah({ di_denah: false, lokasi_spasial: { node_id: "n1" } })).toBe(false);
});

test("label denah mendahulukan jalur lengkap daripada nama node", () => {
  // "Ruang 201" ada di banyak gedung.
  expect(labelDenah({ di_denah: true, denah_jalur: "Gedung A / Lt 2 / R201",
                      denah_nama: "R201" })).toBe("Gedung A / Lt 2 / R201");
  expect(labelDenah({ di_denah: true, denah_nama: "R201" })).toBe("R201");
  expect(labelDenah({ lokasi_spasial: { node_id: "n1", jalur_nama: "G / L / R" } }))
    .toBe("G / L / R");
});

test("teks baris lokasi menyebut yang paling spesifik lebih dulu", () => {
  expect(labelBarisLokasi({ location: "Ruang 101", ...KOORD })).toBe("Ruang 101");
  expect(labelBarisLokasi({ ...KOORD })).toBe("Berkoordinat");
  expect(labelBarisLokasi({ di_denah: true, denah_jalur: "G / L / R" })).toBe("G / L / R");
  expect(labelBarisLokasi({ di_denah: true })).toBe("Di denah");
});

test("aset tanpa keterangan lokasi apa pun bertekskan kosong", () => {
  // Penanda bukan alasan menambah baris kosong pada aset yang memang belum
  // punya keterangan lokasi apa pun.
  expect(labelBarisLokasi({})).toBe("");
  expect(labelBarisLokasi(null)).toBe("");
  expect(labelBarisLokasi({ location: "   " })).toBe("");
});


// ── Bentuk SIMPAN: pemisah desimal TITIK ─────────────────────────────────
//
// Permintaan pemilik: *"ketika lat lng ditulis menggunakan koma ketika
// disimpan, tolong sesuaikan langsung menggunakan titik saja."*

describe("normalisasiKoordinat", () => {
  test("koma desimal menjadi titik", () => {
    expect(normalisasiKoordinat("-1,4001")).toBe("-1.4001");
    expect(normalisasiKoordinat("116,700100")).toBe("116.700100");
  });

  test("yang sudah bertitik tak diusik", () => {
    expect(normalisasiKoordinat("-1.4001")).toBe("-1.4001");
  });

  test("nol di belakang koma DIPERTAHANKAN", () => {
    // Angkanya tidak dirender ulang lewat parseFloat: "-1,40010" yang menjadi
    // "-1.4001" mengubah bentuk yang sengaja diketik petugas, dan pada
    // koordinat, digit terakhir itu ketelitian ~1 cm.
    expect(normalisasiKoordinat("-1,40010")).toBe("-1.40010");
  });

  test("kosong tetap kosong", () => {
    for (const v of ["", "   ", null, undefined]) {
      expect(normalisasiKoordinat(v)).toBe("");
    }
  });

  test("spasi tepi dibuang", () => {
    expect(normalisasiKoordinat("  -1,4001  ")).toBe("-1.4001");
  });

  test("yang BUKAN koordinat dikembalikan apa adanya", () => {
    // Mengubahnya berarti menebak maksud orang; mengosongkannya membuang
    // isian yang mungkin masih ingin diperbaiki pemiliknya.
    expect(normalisasiKoordinat("belum diukur")).toBe("belum diukur");
    expect(normalisasiKoordinat("999,9")).toBe("999,9");
  });

  test("nol adalah koordinat sah, bukan dianggap kosong", () => {
    expect(normalisasiKoordinat("0")).toBe("0");
    expect(normalisasiKoordinat(0)).toBe("0");
  });
});
