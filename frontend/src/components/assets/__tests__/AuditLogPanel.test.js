/**
 * Panel Riwayat: satu simpanan aset tidak boleh terbaca sebagai dua suntingan.
 *
 * Laporan pemilik: mencatat satu aset memunculkan DUA baris "Edit" — satu
 * bernama pengguna, satu beralamat surel. Baris kedua sebenarnya PENEMPATAN
 * DENAH OTOMATIS yang lahir dari koordinat pada simpanan yang sama; aksinya
 * (`aset_lokasi_otomatis`) tak terdaftar sehingga jatuh ke label cadangan —
 * dan label cadangannya dulu "Edit".
 *
 * Yang dijaga:
 *  1. Ketiga aksi penempatan denah punya labelnya sendiri.
 *  2. Aksi TAK DIKENAL tidak pernah lagi mengaku "Edit" — hanya `update` boleh.
 *  3. Keterangan (`detail`) tampil meski barisnya punya kode barang; dulu
 *     justru disembunyikan tepat pada baris yang paling butuh penjelasan.
 */
import React from "react";
import { render, screen } from "@testing-library/react";

import { konfigAksi, TimelineEntry } from "../AuditLogPanel";

describe("konfigAksi", () => {
  test("aksi penempatan denah punya label sendiri, bukan Edit", () => {
    expect(konfigAksi("aset_lokasi_otomatis").label).toBe("Lokasi Otomatis");
    expect(konfigAksi("aset_lokasi_tandai").label).toBe("Tandai Lokasi");
    expect(konfigAksi("aset_lokasi_hapus").label).toBe("Cabut Lokasi");
  });

  test("hanya update yang boleh berlabel Edit", () => {
    expect(konfigAksi("update").label).toBe("Edit");
    // Inti perbaikannya: aksi asing tak boleh lagi meminjam label "Edit".
    for (const aksi of ["aset_lokasi_otomatis", "tgr_buka", "booking_surat",
                        "pemusnahan_buat", ""]) {
      expect(konfigAksi(aksi).label).not.toBe("Edit");
    }
  });

  test("aksi tak dikenal dieja dari namanya sendiri", () => {
    expect(konfigAksi("pemusnahan_usulan_buat").label)
      .toBe("Pemusnahan Usulan Buat");
    expect(konfigAksi(undefined).label).toBe("Aktivitas");
  });

  test("aksi yang terdaftar tetap menang atas ejaan otomatis", () => {
    expect(konfigAksi("create").label).toBe("Tambah");
    expect(konfigAksi("delete").label).toBe("Hapus");
  });
});

// Panel utuh memerlukan jaringan; yang diuji di sini satu baris timeline saja.
describe("baris timeline", () => {
  const LOG_PENEMPATAN = {
    id: "L1", action: "aset_lokasi_otomatis", timestamp: new Date().toISOString(),
    asset_code: "3100204023", nup: "16", asset_name: "ARUBA Instant On AP25",
    username: "Arif Fahmirridho", changes: [],
    detail: "Gedung A / Lantai 3 / Ruang 305",
  };

  test("keterangan tampil walau baris punya kode barang", () => {
    render(<TimelineEntry log={LOG_PENEMPATAN} showAssetInfo />);
    expect(screen.getByText("Gedung A / Lantai 3 / Ruang 305")).toBeInTheDocument();
    expect(screen.getByText("Lokasi Otomatis")).toBeInTheDocument();
    // Satu pelaku, satu ejaan — bukan alamat surel.
    expect(screen.getByText("Arif Fahmirridho")).toBeInTheDocument();
    // NUP ikut, sehingga jelas menunjuk barang yang sama dengan baris Edit.
    expect(screen.getByText("/ 16")).toBeInTheDocument();
  });
});
