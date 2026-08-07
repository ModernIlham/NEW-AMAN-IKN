/**
 * Penjaga: kepala halaman modul siklus tak boleh pecah ke baris kedua.
 *
 * Laporan pemilik (dengan tangkapan layar halaman Pengadaan): tombol Booking
 * Nomor "sampai ke bawah"; minta aksi dikumpulkan berkategori, kecuali tombol
 * tambah. Penelusuran lanjutan menemukan LIMA halaman berbentuk kepala persis
 * sama — [Ekspor CSV] + [tombol utama] + [Booking Nomor] — dan hanya Pengadaan
 * (yang punya satu aksi tambahan) yang sudah benar-benar tumpah. Empat sisanya
 * berjarak tepat SATU tombol dari nasib yang sama.
 *
 * Polanya kini satu komponen bersama (`components/ui/MenuKepala`), bukan lima
 * salinan. Uji ini menjaga tiga hal yang mudah rusak diam-diam:
 *
 *   1. Kepala kelima halaman tetap dua tombol saja (menu + tombol utama).
 *   2. Tombol utama TIDAK ikut masuk menu — ia alasan halamannya dibuka.
 *   3. BookingNomorButton dipasang sebagai SAUDARA DropdownMenu, bukan di
 *      dalam `DropdownMenuContent`. Radix melepas isi menu dari DOM begitu
 *      menu tertutup; komponen booking memiliki dialognya sendiri, jadi
 *      menaruhnya di dalam menu membuat dialog itu lenyap pada detik yang sama
 *      butir menunya ditekan — gejalanya "menu menutup, lalu tak terjadi
 *      apa-apa".
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..");
const baca = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

const KOMPONEN = "components/ui/MenuKepala.jsx";
const TOMBOL = "components/persuratan/BookingNomorButton.jsx";

/** Lima halaman yang memakai menu kepala bersama + testid tombol utamanya. */
const HALAMAN = [
  ["pages/PengadaanPage.jsx", "pengadaan", "pengadaan-tambah"],
  ["pages/PenganggaranPage.jsx", "penganggaran", "penganggaran-tambah"],
  ["pages/PemusnahanPage.jsx", "pemusnahan", "pemusnahan-tambah"],
  ["pages/PemindahtangananPage.jsx", "pemindahtanganan", "pemindahtanganan-tambah"],
  ["pages/PemanfaatanPage.jsx", "pemanfaatan", "pemanfaatan-tambah"],
];

function tanpaKomentar(kode) {
  return kode.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Blok <header>…</header> pertama sebuah halaman. */
function kepala(kode) {
  const m = kode.match(/<header[\s\S]*?<\/header>/);
  return m ? m[0] : "";
}

/** Isi <DropdownMenuContent>…</DropdownMenuContent>. */
function isiMenu(kode) {
  const m = kode.match(/<DropdownMenuContent[\s\S]*?<\/DropdownMenuContent>/);
  return m ? m[0] : "";
}

describe("MenuKepala — komponen bersama", () => {
  const k = tanpaKomentar(baca(KOMPONEN));

  test("BookingNomorButton dipasang DI LUAR DropdownMenuContent", () => {
    // Inilah jebakan Radix. Diselesaikan sekali di sini, bukan lima kesempatan
    // untuk keliru di lima halaman.
    expect(isiMenu(k)).not.toContain("<BookingNomorButton");
    expect(k).toMatch(/<BookingNomorButton ref=\{bookingRef\} tanpaTombol/);
    expect(isiMenu(k)).toMatch(/onSelect=\{\(\) => bookingRef\.current\?\.mulai\(\)\}/);
  });

  test("butir menu berkategori & memenuhi tinggi sentuh", () => {
    const menu = isiMenu(k);
    expect(menu).toMatch(/Dokumen &amp; Nomor/);
    expect(menu).toMatch(/>\s*Ekspor\s*</);
    expect(menu).toMatch(/<DropdownMenuSeparator \/>/);
    const butir = menu.match(/<DropdownMenuItem/g) || [];
    const tinggi = menu.match(/min-h-\[42px\]/g) || [];
    expect(butir.length).toBeGreaterThan(0);
    expect(tinggi.length).toBe(butir.length);
  });

  test("bagian kosong tak menyisakan label kategori menggantung", () => {
    // Menu berlabel "Dokumen & Nomor" tanpa satu pun butir lebih membingungkan
    // daripada menu tanpa kategori sama sekali.
    expect(k).toMatch(/const adaDokumen = Boolean\(booking\) \|\| ekstra\.length > 0/);
    expect(k).toMatch(/\{adaDokumen && \(/);
    expect(k).toMatch(/\{adaDokumen && ekspor && <DropdownMenuSeparator \/>\}/);
  });

  test("tombol utama BUKAN urusan komponen ini", () => {
    // Kalau suatu saat "tambah" ikut ditarik ke dalam menu, aksi terpenting
    // tiap halaman jadi tersembunyi di balik satu ketukan tambahan.
    expect(k).not.toMatch(/tambah/i);
    expect(k).not.toMatch(/<Plus/);
  });
});

describe("kelima kepala halaman seragam", () => {
  test.each(HALAMAN)("%s: hanya menu + tombol utama", (berkas, modul, tid) => {
    const h = tanpaKomentar(kepala(baca(berkas)));
    expect(h).toMatch(/<MenuKepala/);
    expect(h).toMatch(new RegExp(`modul="${modul}"`));
    expect(h).toMatch(new RegExp(`data-testid="${tid}"`));

    // Tombol Ekspor CSV & Booking Nomor tak boleh kembali berdiri sendiri.
    expect(h).not.toMatch(new RegExp(`data-testid="${modul}-export"`));
    expect(h).not.toMatch(/<BookingNomorButton/);

    // Selain tombol Kembali, hanya SATU <Button> tersisa di kepala: tombol
    // utama. (MenuKepala merender tombol menunya sendiri, di luar berkas ini.)
    const tombol = h.match(/<Button[\s>]/g) || [];
    expect(tombol.length).toBe(1);
  });

  test.each(HALAMAN)("%s: ekspor CSV tetap ada, lewat menu", (berkas, modul) => {
    const h = kepala(baca(berkas));
    // Aksi tak boleh HILANG saat dipindahkan — hanya berpindah tempat.
    expect(h).toMatch(new RegExp(`url: \`\\$\\{API\\}/${modul}/export\``));
    expect(h).toMatch(/booking=\{\{ jenisNaskah:/);
  });
});

describe("BookingNomorButton: titik sisip untuk menu", () => {
  const t = tanpaKomentar(baca(TOMBOL));

  test("mengekspos mulai() lewat ref, tanpa membuka state internal", () => {
    expect(t).toMatch(/React\.forwardRef\(/);
    expect(t).toMatch(/useImperativeHandle\(ref, \(\) => \(\{ mulai \}\)\)/);
  });

  test("tombol bawaan bisa dilepas, dialognya tidak", () => {
    expect(t).toMatch(/tanpaTombol = false/);
    expect(t).toMatch(/\{!tanpaTombol && \(/);
    const dialog = t.indexOf("<Dialog open={buka}");
    expect(dialog).toBeGreaterThan(-1);
    expect(t.slice(0, dialog)).not.toMatch(/tanpaTombol \?/);
  });

  test("halaman lain tetap mendapat tombol seperti semula", () => {
    // `tanpaTombol` berdefault false, jadi 10+ halaman pemakai langsung tak
    // perlu disentuh. Satu-satunya yang melepasnya adalah MenuKepala.
    const semua = fs.readdirSync(path.join(SRC, "pages"))
      .filter((f) => f.endsWith(".jsx"))
      .map((f) => baca(path.join("pages", f)))
      .join("\n");
    const pakai = (semua.match(/<BookingNomorButton/g) || []).length;
    expect(pakai).toBeGreaterThan(8);
    expect(semua).not.toMatch(/<BookingNomorButton[^>]*tanpaTombol/);
  });
});
