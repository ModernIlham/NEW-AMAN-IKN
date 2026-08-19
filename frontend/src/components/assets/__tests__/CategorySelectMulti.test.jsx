/**
 * Dropdown kategori: sekarang MULTI-PILIH.
 *
 * Master kodefikasi berisi belasan ribu kategori, jadi dua perilaku menentukan
 * apakah kontrol ini bisa dipakai sama sekali:
 *
 *  1. Popover TIDAK menutup saat satu kategori dipilih. Kalau menutup, memilih
 *     lima kategori berarti membuka daftar lima kali dan mengetik ulang kata
 *     kuncinya lima kali.
 *  2. "Pilih semua" dibatasi sama seperti filter lain — daftar yang lebih
 *     panjang dari batas MEMATIKAN tombolnya, bukan memilih sebagiannya
 *     diam-diam.
 *
 * Baris "Semua Kategori" bukan salah satu pilihan yang bisa dicentang bersama
 * kategori lain: memilih "semua" sekaligus "Meja" tak punya arti. Ia tombol
 * kembali-ke-tanpa-filter.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import CategorySelect from "../CategorySelect";
import { MAKS_PILIH_SEMUA } from "../FilterMultiSelect";

const KATEGORI = [
  { id: "1", label: "Meja Kerja", kode_aset: "3050102001" },
  { id: "2", label: "Kursi Rapat", kode_aset: "3050102002" },
  { id: "3", label: "Lemari Arsip", kode_aset: "3050102003" },
];

const buka = () => fireEvent.click(screen.getByTestId("category-select-trigger"));

describe("pemilihan", () => {
  test("mencentang kategori kedua MENAMBAH, bukan mengganti", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value={["Meja Kerja"]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-option-2"));
    expect(onValueChange).toHaveBeenCalledWith(["Meja Kerja", "Kursi Rapat"]);
  });

  test("mengklik kategori yang sudah dicentang melepasnya", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI}
      value={["Meja Kerja", "Kursi Rapat"]} onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-option-1"));
    expect(onValueChange).toHaveBeenCalledWith(["Kursi Rapat"]);
  });

  test("daftar tetap terbuka setelah memilih", () => {
    render(<CategorySelect categories={KATEGORI} value={[]}
      onValueChange={() => {}} />);
    buka();
    fireEvent.click(screen.getByTestId("category-option-1"));
    expect(screen.getByTestId("category-select-dropdown")).toBeInTheDocument();
  });

  test('"Semua Kategori" mengosongkan pilihan', () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value={["Meja Kerja"]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-option-all"));
    expect(onValueChange).toHaveBeenCalledWith([]);
  });
});

describe("nilai lama tetap dipahami", () => {
  test("string tunggal dibaca sebagai satu pilihan", () => {
    // State tersimpan / pemanggil yang belum diperbarui tak boleh pecah.
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value="Meja Kerja"
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-option-2"));
    expect(onValueChange).toHaveBeenCalledWith(["Meja Kerja", "Kursi Rapat"]);
  });

  test('sentinel "Semua" dibaca sebagai tanpa filter', () => {
    render(<CategorySelect categories={KATEGORI} value="Semua"
      onValueChange={() => {}} />);
    expect(screen.getByTestId("category-select-trigger"))
      .toHaveTextContent("Semua Kategori");
  });
});

describe("pilih semua", () => {
  test("memilih seluruh kategori yang tampil", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value={[]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-select-pilih-semua"));
    expect(onValueChange).toHaveBeenCalledWith(
      ["Meja Kerja", "Kursi Rapat", "Lemari Arsip"]);
  });

  test("saat mencari, hanya hasil pencarian yang ditambahkan", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value={["Lemari Arsip"]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.change(screen.getByTestId("category-search-input"),
      { target: { value: "kursi" } });
    fireEvent.click(screen.getByTestId("category-select-pilih-semua"));
    expect(onValueChange).toHaveBeenCalledWith(["Lemari Arsip", "Kursi Rapat"]);
  });

  test("mati bila daftar melampaui batas — bukan memilih sebagian", () => {
    const onValueChange = jest.fn();
    const raksasa = Array.from({ length: MAKS_PILIH_SEMUA + 50 }, (_, i) => ({
      id: String(i), label: `Kategori ${i}`, kode_aset: `30501${i}`,
    }));
    render(<CategorySelect categories={raksasa} value={[]}
      onValueChange={onValueChange} />);
    buka();
    const tombol = screen.getByTestId("category-select-pilih-semua");
    expect(tombol).toBeDisabled();
    fireEvent.click(tombol);
    expect(onValueChange).not.toHaveBeenCalled();
  });

  test("Kosongkan melepas seluruh kategori", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={KATEGORI} value={["Meja Kerja"]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-select-kosongkan"));
    expect(onValueChange).toHaveBeenCalledWith([]);
  });
});

describe("pemicu", () => {
  test("menyebut jumlah saat lebih dari satu kategori", () => {
    render(<CategorySelect categories={KATEGORI}
      value={["Meja Kerja", "Kursi Rapat"]} onValueChange={() => {}} />);
    expect(screen.getByTestId("category-select-jumlah")).toHaveTextContent("2");
    expect(screen.getByTestId("category-select-trigger"))
      .toHaveTextContent("Meja Kerja +1");
  });

  test("satu kategori tampil beserta kodenya", () => {
    render(<CategorySelect categories={KATEGORI} value={["Meja Kerja"]}
      onValueChange={() => {}} />);
    expect(screen.getByTestId("category-select-trigger"))
      .toHaveTextContent("3050102001 - Meja Kerja");
  });
});
