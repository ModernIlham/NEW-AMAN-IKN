/**
 * Kelola Kategori Aset — kendalinya seragam, angkanya terbaca, barisnya utuh.
 *
 * Permintaan pemilik: *"bagian halaman kelola kategori aset sederhanakan dan
 * seragamkan agar terlihat rapi dan proporsional."*
 *
 * Yang membuatnya tak proporsional BUKAN tombolnya yang kebesaran, melainkan
 * tingginya yang tak seragam: aturan tap-target global (`index.css`, ≤1023px)
 * memaksa setiap `button` menjadi 44×44, sementara input di sebelahnya tetap
 * `h-8` = 32px. Tombol "+" karenanya berdiri satu setengah kali lebih tinggi
 * daripada dua kotak isian di kirinya. Yang diperbaiki tinggi kendali lain,
 * bukan tombolnya — mengecilkan tombol di layar sentuh melanggar aturan yang
 * sama, dan kotak isian pun memang layak 44px oleh jari.
 */
import fs from "fs";
import path from "path";
import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("axios", () => ({
  get: jest.fn(() => Promise.resolve({ data: {} })),
  post: jest.fn(), delete: jest.fn(),
}));

import CategoryManagerDialog from "../CategoryManagerDialog";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../CategoryManagerDialog.jsx"), "utf8");
//: Sumber TANPA komentar — prosa yang menyebut "h-8" tak boleh menjatuhkan
//: maupun memuaskan penjaga struktural di bawah.
const KODE = SRC.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

const KATEGORI = Array.from({ length: 12488 }, (_, i) => ({
  id: `c${i}`, kode_aset: String(3050104000 + i), label: `Barang ${i}`,
}));

function buka(categories = KATEGORI) {
  render(<CategoryManagerDialog open onClose={jest.fn()}
    categories={categories} onCategoriesChanged={jest.fn()} />);
}

// ── 1. Tinggi kendali SERAGAM ───────────────────────────────────────────

describe("satu tinggi untuk semua kendali", () => {
  test("tingginya satu tetapan, bukan angka yang ditulis ulang per kendali", () => {
    expect(KODE).toMatch(/const TINGGI_KENDALI = "h-11 lg:h-8"/);
  });

  test("tiap kendali menyatakan ukuran SENTUH dan ukuran layar lebar", () => {
    // Kendali yang memakai satu tinggi saja mengabaikan aturan tap-target:
    // tombolnya tetap dipaksa 44px oleh `index.css` sementara input di
    // sebelahnya bertahan 32px, dan barisnya jadi timpang. Yang sah hanya dua
    // bentuk: tetapan bersama, atau pasangan `h-11 … lg:h-N` yang eksplisit.
    const kendali = KODE.split("\n")
      .filter((b) => /<(Button|Input)\b/.test(b) || /^\s+className=/.test(b));
    const nakal = kendali.filter((b) => {
      const m = b.match(/className=[^\n]*/);
      if (!m) return false;
      const kelas = m[0];
      if (!/\bh-\d/.test(kelas)) return false;             // tak mengatur tinggi
      if (kelas.includes("TINGGI_KENDALI")) return false;   // ikut tetapan
      return !(/\bh-11\b/.test(kelas) && /\blg:h-\d/.test(kelas));
    });
    expect(nakal).toEqual([]);
  });

  test("keempat kendali utama memakai tetapan yang sama", () => {
    for (const testid of ["category-code-input", "category-name-input",
                          "category-add-btn", "category-search-input"]) {
      const i = KODE.indexOf(`data-testid="${testid}"`);
      expect(i).toBeGreaterThan(-1);
      // Potongan JSX di sekitar penanda ujinya memuat kelas tingginya.
      const awal = KODE.lastIndexOf("<", i - 400 > 0 ? i - 400 : 0);
      expect(KODE.slice(awal, i + 40)).toContain("TINGGI_KENDALI");
    }
  });

  test("tombol + berbentuk PERSEGI, bukan pil yang lebih tinggi dari isian", () => {
    const i = KODE.indexOf('data-testid="category-add-btn"');
    const potongan = KODE.slice(i - 300, i);
    expect(potongan).toContain("w-11 lg:w-8");
    expect(potongan).toContain("p-0");
  });
});

// ── 2. Angka terbaca ────────────────────────────────────────────────────

describe("angka ribuan diberi pemisah", () => {
  test("total memakai pemisah ribuan gaya Indonesia", async () => {
    buka();
    expect(await screen.findByText(/Total: 12\.488 kategori/)).toBeInTheDocument();
  });

  test("rentang halaman menyebut total yang sama, tanpa membungkus", async () => {
    buka();
    const rentang = await screen.findByTestId("kategori-rentang");
    expect(rentang).toHaveTextContent("1–50 dari 12.488");
    // "1-50 dari" + "12488" yang patah terbaca sebagai dua keterangan.
    expect(rentang.className).toContain("whitespace-nowrap");
  });

  test("penunjuk halaman utuh sebaris", async () => {
    buka();
    const hal = await screen.findByTestId("kategori-halaman");
    expect(hal).toHaveTextContent("1 / 250");
    expect(hal.className).toContain("whitespace-nowrap");
  });
});

// ── 3. Keterangan yang tetap terlihat & tombol yang bernama ─────────────

describe("keterangan dan nama tombol", () => {
  test("aturan 10 digit pindah ke baris tetap, bukan placeholder yang terpotong", async () => {
    // Placeholder "Kode Aset (10 digit)" tak pernah muat di kotak selebar itu —
    // terbaca "Kode Ase…" — dan lenyap begitu diketik.
    buka();
    expect(await screen.findByPlaceholderText("Kode Aset")).toBeInTheDocument();
    expect(screen.getByText(/10 digit sesuai kodefikasi BMN/)).toBeInTheDocument();
  });

  test("tombol tanpa teks tetap punya nama yang terbaca pembaca layar", async () => {
    buka();
    expect(await screen.findByLabelText("Tambah kategori")).toBeInTheDocument();
    expect(screen.getByLabelText("Halaman sebelumnya")).toBeInTheDocument();
    expect(screen.getByLabelText("Halaman berikutnya")).toBeInTheDocument();
  });

  test("label pager disembunyikan di layar sempit, panahnya yang bicara", async () => {
    buka();
    const prev = await screen.findByTestId("kategori-prev");
    expect(prev).toHaveTextContent("Sebelumnya");
    expect(prev.querySelector(".hidden.sm\\:inline")).not.toBeNull();
  });
});

// ── 4. Paginasi tetap bekerja ───────────────────────────────────────────

test("daftar kosong tak menampilkan baris paginasi sama sekali", () => {
  buka([]);
  expect(screen.queryByTestId("kategori-halaman")).toBeNull();
});

test("tombol hapus baris TERLIHAT di layar sentuh, bukan hanya saat hover", async () => {
  // `opacity-0` tanpa hover di layar sentuh = tombol HAPUS yang tak kelihatan
  // namun tetap 44×44 dan tetap dapat tertekan jari.
  buka();
  const hapus = await screen.findByLabelText("Hapus Barang 0");
  expect(hapus.className).toContain("opacity-100");
  expect(hapus.className).toContain("lg:opacity-0");
});

test("hanya 50 baris yang dirender dari 12.488 kategori", async () => {
  buka();
  await screen.findByTestId("kategori-halaman");
  expect(screen.getAllByText(/^Barang \d+$/)).toHaveLength(50);
});
