/**
 * Penjaga: kepala halaman Pengadaan tak boleh pecah ke baris kedua lagi.
 *
 * Laporan pemilik (dengan tangkapan layar): tombol Booking Nomor "sampai ke
 * bawah" di HP — empat tombol berdampingan tak muat dalam satu baris. Aksi
 * sekundernya dikumpulkan ke satu menu berkategori; hanya "Catat Perolehan"
 * yang tetap berdiri sendiri.
 *
 * SATU JEBAKAN YANG DIJAGA KETAT DI SINI: Radix MELEPAS isi
 * `DropdownMenuContent` dari DOM begitu menu tertutup. `BookingNomorButton`
 * memiliki dialog bookingnya sendiri, jadi menaruh komponen itu DI DALAM menu
 * berarti dialognya ikut lenyap pada detik yang sama butir menunya ditekan —
 * gejalanya: menu menutup, lalu tak terjadi apa-apa. Komponennya wajib
 * dipasang di luar menu dan dipicu lewat ref.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const HALAMAN = "pages/PengadaanPage.jsx";
const TOMBOL = "components/persuratan/BookingNomorButton.jsx";

function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Isi elemen <DropdownMenuContent>…</DropdownMenuContent> pada satu berkas. */
function isiMenu(kode) {
  const m = kode.match(/<DropdownMenuContent[\s\S]*?<\/DropdownMenuContent>/);
  return m ? m[0] : "";
}

describe("kepala Pengadaan: aksi sekunder terkumpul", () => {
  const halaman = tanpaKomentar(baca(HALAMAN));

  test("hanya satu tombol aksi selain menu — Catat Perolehan", () => {
    expect(halaman).toMatch(/data-testid="pengadaan-menu"/);
    expect(halaman).toMatch(/data-testid="pengadaan-tambah"/);
    // Tombol-tombol lama tak boleh kembali berdiri sendiri di kepala halaman:
    // ketiganya kini butir menu, dan butir menu bukan <Button>.
    expect(halaman).not.toMatch(/<Button[^>]*data-testid="pengadaan-export"/);
    expect(halaman).not.toMatch(/<Button[^>]*data-testid="pengadaan-lpb-gabungan"/);
  });

  test("ketiga aksi ada di dalam menu, berkategori", () => {
    const menu = isiMenu(halaman);
    expect(menu).toBeTruthy();
    for (const t of ["pengadaan-menu-booking", "pengadaan-lpb-gabungan",
                     "pengadaan-export"]) {
      expect(menu).toContain(t);
    }
    // "Kategori" bukan hiasan: tanpa label, daftar ini terbaca sebagai
    // tumpukan aksi tanpa urutan yang bisa ditebak.
    expect(menu).toMatch(/<DropdownMenuLabel[\s\S]*?Dokumen/);
    expect(menu).toMatch(/<DropdownMenuLabel[\s\S]*?Ekspor/);
    expect(menu).toMatch(/<DropdownMenuSeparator \/>/);
  });

  test("BookingNomorButton dipasang DI LUAR menu, dipicu lewat ref", () => {
    const menu = isiMenu(halaman);
    // Inilah jebakan Radix. Komponen di dalam menu = dialog ikut dilepas.
    expect(menu).not.toContain("<BookingNomorButton");
    expect(halaman).toMatch(/<BookingNomorButton ref=\{bookingRef\} tanpaTombol/);
    expect(menu).toMatch(/onSelect=\{\(\) => bookingRef\.current\?\.mulai\(\)\}/);
  });

  test("butir menu memenuhi tinggi sentuh minimum", () => {
    const menu = isiMenu(halaman);
    const butir = menu.match(/<DropdownMenuItem/g) || [];
    const tinggi = menu.match(/min-h-\[42px\]/g) || [];
    expect(butir.length).toBe(3);
    expect(tinggi.length).toBe(butir.length);
  });
});

describe("BookingNomorButton: titik sisip untuk menu", () => {
  const tombol = tanpaKomentar(baca(TOMBOL));

  test("mengekspos mulai() lewat ref, tanpa membuka state internal", () => {
    expect(tombol).toMatch(/React\.forwardRef\(/);
    expect(tombol).toMatch(/useImperativeHandle\(ref, \(\) => \(\{ mulai \}\)\)/);
  });

  test("tombol bawaan bisa dilepas, dialognya tidak", () => {
    expect(tombol).toMatch(/tanpaTombol = false/);
    expect(tombol).toMatch(/\{!tanpaTombol && \(/);
    // Dialog HARUS tetap dirender tanpa syarat — ia satu-satunya jalan
    // booking, dan melepasnya bersama tombol akan mematikan fiturnya.
    const dialog = tombol.indexOf("<Dialog open={buka}");
    expect(dialog).toBeGreaterThan(-1);
    expect(tombol.slice(0, dialog)).not.toMatch(/tanpaTombol \?/);
  });

  test("15+ pemakai lama tetap dapat tombol seperti semula", () => {
    // `tanpaTombol` berdefault false, jadi tak satu pun call site lama perlu
    // disentuh. Uji ini menjaga default-nya tak terbalik.
    expect(tombol).toMatch(/tanpaTombol = false/);
    const semua = fs.readdirSync(path.join(SRC, "pages"))
      .filter((f) => f.endsWith(".jsx"))
      .map((f) => baca(path.join("pages", f)))
      .join("\n");
    const pakai = (semua.match(/<BookingNomorButton/g) || []).length;
    const dilepas = (semua.match(/<BookingNomorButton[^>]*tanpaTombol/g) || []).length;
    expect(pakai).toBeGreaterThan(10);
    expect(dilepas).toBe(1);          // hanya Pengadaan
  });
});
