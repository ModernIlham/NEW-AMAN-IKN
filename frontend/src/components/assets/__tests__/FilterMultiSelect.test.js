/**
 * Filter multi-pilih: satu filter boleh memuat lebih dari satu nilai.
 *
 * Yang dijaga:
 *  1. Fungsi murni ringkasTerpilih/alihNilai — termasuk TIDAK memutasi array
 *     state (mutasi diam-diam bikin React melewatkan render).
 *  2. Mencentang nilai kedua MENAMBAH, bukan mengganti — inti fiturnya.
 *  3. buildFilterParams mengirim PARAMETER BERULANG, dan nilai bermuatan koma
 *     tetap utuh sebagai satu nilai.
 *  4. "Pilih semua" — MENGGABUNG dengan pilihan lama (bukan mengganti),
 *     bekerja pada hasil pencarian, dan MATI bila daftarnya terlalu panjang
 *     ketimbang memilih sebagian diam-diam.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import FilterMultiSelect, { alihNilai, gabungPilihan, ringkasTerpilih,
  MAKS_PILIH_SEMUA } from "../FilterMultiSelect";

describe("fungsi murni", () => {
  test("ringkasan pemicu ikut jumlah nilai", () => {
    expect(ringkasTerpilih([])).toBe("Semua");
    expect(ringkasTerpilih(["Baik"])).toBe("Baik");
    expect(ringkasTerpilih(["Baik", "Rusak"])).toBe("Baik, Rusak");
    // Tiga ke atas diringkas agar pemicu tak melebar merusak grid.
    expect(ringkasTerpilih(["Baik", "Rusak", "Hilang"])).toBe("Baik +2");
  });

  test("alihNilai menambah & melepas tanpa memutasi masukan", () => {
    const awal = ["Baik"];
    const tambah = alihNilai(awal, "Rusak");
    expect(tambah).toEqual(["Baik", "Rusak"]);
    expect(awal).toEqual(["Baik"]);          // tak dimutasi

    expect(alihNilai(tambah, "Baik")).toEqual(["Rusak"]);
    expect(alihNilai(undefined, "Baik")).toEqual(["Baik"]);
  });
});

describe("interaksi panel", () => {
  const OPSI = ["Baik", "Rusak Ringan", "Rusak Berat"];

  test("mencentang nilai kedua MENAMBAH, bukan mengganti", () => {
    const onChange = jest.fn();
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI} terpilih={["Baik"]}
        onChange={onChange} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    fireEvent.click(screen.getByText("Rusak Berat"));
    expect(onChange).toHaveBeenCalledWith(["Baik", "Rusak Berat"]);
  });

  test("mengklik nilai yang sudah dicentang melepasnya", () => {
    const onChange = jest.fn();
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI}
        terpilih={["Baik", "Rusak Berat"]} onChange={onChange}
        testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    fireEvent.click(screen.getByText("Baik"));
    expect(onChange).toHaveBeenCalledWith(["Rusak Berat"]);
  });

  test("tombol Kosongkan melepas seluruh nilai", () => {
    const onChange = jest.fn();
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI} terpilih={["Baik"]}
        onChange={onChange} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    fireEvent.click(screen.getByTestId("filter-condition-kosongkan"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  test("pemicu menampilkan jumlah nilai saat lebih dari satu", () => {
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI}
        terpilih={["Baik", "Rusak Berat"]} onChange={() => {}}
        testid="filter-condition" />
    );
    expect(screen.getByTestId("filter-condition-jumlah")).toHaveTextContent("2");
  });

  test("daftar panjang mendapat kotak cari yang menyaring", () => {
    const banyak = Array.from({ length: 12 }, (_, i) => `Lokasi ${i}`);
    render(
      <FilterMultiSelect label="Lokasi" opsi={banyak} terpilih={[]}
        onChange={() => {}} testid="filter-location" />
    );
    fireEvent.click(screen.getByTestId("filter-location"));
    const cari = screen.getByTestId("filter-location-cari");
    fireEvent.change(cari, { target: { value: "Lokasi 11" } });
    expect(screen.getAllByTestId("filter-location-opsi")).toHaveLength(1);
  });

  test("daftar pendek tanpa kotak cari", () => {
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI} terpilih={[]}
        onChange={() => {}} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    expect(screen.queryByTestId("filter-condition-cari")).toBeNull();
  });
});


describe("pilih semua", () => {
  const OPSI = ["Baik", "Rusak Ringan", "Rusak Berat"];

  test("gabungPilihan menambah tanpa menghapus & tanpa memutasi", () => {
    const awal = ["Hilang"];
    expect(gabungPilihan(awal, ["Baik", "Hilang"])).toEqual(["Hilang", "Baik"]);
    expect(awal).toEqual(["Hilang"]);
    expect(gabungPilihan(undefined, ["Baik"])).toEqual(["Baik"]);
    expect(gabungPilihan(["Baik"], [])).toEqual(["Baik"]);
  });

  test("memilih seluruh nilai yang tampil", () => {
    const onChange = jest.fn();
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI} terpilih={[]}
        onChange={onChange} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    fireEvent.click(screen.getByTestId("filter-condition-pilih-semua"));
    expect(onChange).toHaveBeenCalledWith(OPSI);
  });

  test("saat mencari, hanya hasil pencarian yang ditambahkan — pilihan lama tetap", () => {
    const onChange = jest.fn();
    const banyak = ["Gedung A Lt1", "Gedung A Lt2", "Gedung B Lt1", "Aula",
                    "Gudang", "Pos Jaga", "Kantin", "Masjid", "Parkir"];
    render(
      <FilterMultiSelect label="Lokasi" opsi={banyak} terpilih={["Masjid"]}
        onChange={onChange} testid="filter-location" />
    );
    fireEvent.click(screen.getByTestId("filter-location"));
    // Daftar ≥ AMBANG_CARI sehingga kotak cari muncul.
    fireEvent.change(screen.getByTestId("filter-location-cari"),
      { target: { value: "gedung a" } });
    fireEvent.click(screen.getByTestId("filter-location-pilih-semua"));
    expect(onChange).toHaveBeenCalledWith(["Masjid", "Gedung A Lt1", "Gedung A Lt2"]);
  });

  test("label menyebut jumlah hasil saat pencarian aktif", () => {
    const banyak = ["Gedung A Lt1", "Gedung A Lt2", "Gedung B Lt1", "Aula",
                    "Gudang", "Pos Jaga", "Kantin", "Masjid", "Parkir"];
    render(
      <FilterMultiSelect label="Lokasi" opsi={banyak} terpilih={[]}
        onChange={() => {}} testid="filter-location" />
    );
    fireEvent.click(screen.getByTestId("filter-location"));
    expect(screen.getByTestId("filter-location-pilih-semua")).toHaveTextContent("Pilih semua");
    fireEvent.change(screen.getByTestId("filter-location-cari"),
      { target: { value: "gedung a" } });
    expect(screen.getByTestId("filter-location-pilih-semua")).toHaveTextContent("Pilih 2 hasil");
  });

  test("mati bila semua yang tampil sudah tercentang", () => {
    render(
      <FilterMultiSelect label="Kondisi" opsi={OPSI} terpilih={OPSI}
        onChange={() => {}} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    expect(screen.getByTestId("filter-condition-pilih-semua")).toBeDisabled();
  });

  test("mati bila daftar melampaui batas — bukan memilih sebagian diam-diam", () => {
    // Memilih 200 pertama dari 300 menghasilkan filter yang SALAH tanpa satu
    // pun tanda di layar; dan 300 nilai di querystring GET berisiko 414.
    const onChange = jest.fn();
    const raksasa = Array.from({ length: MAKS_PILIH_SEMUA + 100 },
      (_, i) => `Ruang ${i + 1}`);
    render(
      <FilterMultiSelect label="Lokasi" opsi={raksasa} terpilih={[]}
        onChange={onChange} testid="filter-location" />
    );
    fireEvent.click(screen.getByTestId("filter-location"));
    const tombol = screen.getByTestId("filter-location-pilih-semua");
    expect(tombol).toBeDisabled();
    fireEvent.click(tombol);
    expect(onChange).not.toHaveBeenCalled();
  });

  test("mati saat tak ada satu pun pilihan", () => {
    render(
      <FilterMultiSelect label="Kondisi" opsi={[]} terpilih={[]}
        onChange={() => {}} testid="filter-condition" />
    );
    fireEvent.click(screen.getByTestId("filter-condition"));
    expect(screen.getByTestId("filter-condition-pilih-semua")).toBeDisabled();
  });
});
