/**
 * Dropdown kategori menawarkan yang ADA di kegiatan — master penuh opsional.
 *
 * Master kodefikasi berisi belasan ribu entri, satu kegiatan lazimnya memakai
 * puluhan. Bawaan yang benar adalah daftar terpakai; seluruh master tetap satu
 * ketukan jauhnya untuk kasus mencari kategori yang memang belum dipakai.
 *
 * Tiga hal yang paling mudah salah:
 *  1. Kotak filter tampil KOSONG saat kegiatan belum punya aset — jauh lebih
 *     buruk daripada menawarkan terlalu banyak.
 *  2. Label yang ada di data tapi tidak ada di master ikut hilang — padahal itu
 *     aset nyata yang jadi mustahil disaring.
 *  3. Kategori yang SEDANG TERPILIH lenyap dari daftar saat lingkupnya sempit,
 *     sehingga ia tetap menyaring tanpa ada cara melepasnya.
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

import CategorySelect from "../CategorySelect";

const MASTER = [
  { id: "1", label: "Meja Kerja", kode_aset: "3050102001" },
  { id: "2", label: "Kursi Rapat", kode_aset: "3050102002" },
  { id: "3", label: "Lemari Arsip", kode_aset: "3050102003" },
  { id: "4", label: "Kapal Motor", kode_aset: "3060101001" },
];

const buka = () => fireEvent.click(screen.getByTestId("category-select-trigger"));
const opsiTampil = () => screen.getAllByTestId(/^category-option-(?!all)/)
  .map(b => b.textContent);

describe("lingkup bawaan", () => {
  test("hanya kategori yang ada di kegiatan", () => {
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja", "Kursi Rapat"]}
      value={[]} onValueChange={() => {}} />);
    buka();
    const teks = opsiTampil().join(" | ");
    expect(teks).toContain("Meja Kerja");
    expect(teks).toContain("Kursi Rapat");
    expect(teks).not.toContain("Kapal Motor");
  });

  test("label di luar master tetap ditawarkan", () => {
    // Itu aset nyata. Membuangnya membuat barisnya mustahil disaring.
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja", "Barang Warisan Lama"]}
      value={[]} onValueChange={() => {}} />);
    buka();
    expect(opsiTampil().join(" | ")).toContain("Barang Warisan Lama");
  });

  test("kategori terpilih tetap terlihat meski di luar lingkup", () => {
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja"]}
      value={["Kapal Motor"]} onValueChange={() => {}} />);
    buka();
    expect(opsiTampil().join(" | ")).toContain("Kapal Motor");
  });
});

describe("jatuh ke master — kotak filter tak boleh kosong", () => {
  test.each([
    ["daftar terpakai kosong", []],
    ["belum ada informasi", undefined],
    ["berisi nilai hampa", ["", null]],
  ])("%s → master penuh", (_nama, terpakai) => {
    render(<CategorySelect categories={MASTER} kategoriTerpakai={terpakai}
      value={[]} onValueChange={() => {}} />);
    buka();
    expect(opsiTampil().length).toBe(MASTER.length);
  });
});

describe("sakelar lingkup", () => {
  test("membuka seluruh master lalu kembali", () => {
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja"]} value={[]} onValueChange={() => {}} />);
    buka();
    expect(opsiTampil().length).toBe(1);

    fireEvent.click(screen.getByTestId("category-select-lingkup"));
    expect(opsiTampil().length).toBe(MASTER.length);

    fireEvent.click(screen.getByTestId("category-select-lingkup"));
    expect(opsiTampil().length).toBe(1);
  });

  test("menyebut jumlah di kedua arah", () => {
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja"]} value={[]} onValueChange={() => {}} />);
    buka();
    const sakelar = () => screen.getByTestId("category-select-lingkup");
    expect(sakelar()).toHaveTextContent("Tampilkan semua kategori (4)");
    fireEvent.click(sakelar());
    expect(sakelar()).toHaveTextContent("Hanya kategori dalam kegiatan ini (1)");
  });

  test("tidak muncul saat memang tak ada informasi pemakaian", () => {
    render(<CategorySelect categories={MASTER} kategoriTerpakai={[]}
      value={[]} onValueChange={() => {}} />);
    buka();
    expect(screen.queryByTestId("category-select-lingkup")).toBeNull();
  });

  test("tidak mengubah pilihan", () => {
    const onValueChange = jest.fn();
    render(<CategorySelect categories={MASTER}
      kategoriTerpakai={["Meja Kerja"]} value={["Meja Kerja"]}
      onValueChange={onValueChange} />);
    buka();
    fireEvent.click(screen.getByTestId("category-select-lingkup"));
    expect(onValueChange).not.toHaveBeenCalled();
  });
});
