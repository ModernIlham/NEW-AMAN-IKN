/**
 * Tata letak panel eselon pada form kegiatan — dipindai dari sumber.
 *
 * Dua cacat yang dilaporkan pemilik, keduanya hanya terlihat di layar sempit
 * dan tak terjangkau uji perilaku mana pun:
 *
 * 1. **Kotak centang lingkup berbeda-beda ukuran.** Tanpa `flex-shrink-0`,
 *    kotaknya IKUT MENYUSUT saat nama unitnya panjang — dan nama terpanjang
 *    justru ada di baris yang paling menjorok, sehingga daftarnya terbaca
 *    seperti dua jenis kontrol yang berbeda.
 *
 * 2. **Baris input Eselon I/II renggang.** Aturan tap-target global di
 *    `index.css` (`button, a { min-height: 44px }` pada ≤1023px) hanya
 *    mengenai TOMBOL, bukan input. Tombol X karenanya membengkak jadi 44px
 *    sementara inputnya 24–28px, menyisakan ruang mati di atas dan bawah tiap
 *    input. Yang diperbaiki adalah ruang matinya — tap-target-nya TIDAK
 *    dikecilkan, sebab itu melanggar aturan yang sama.
 *
 * Dipindai dari sumber: merender ActivitySelectionPage utuh berarti
 * menghidupkan peta, kamera, dan belasan dependensi lain hanya untuk memeriksa
 * beberapa kelas tata letak.
 */
import fs from "fs";
import path from "path";

const HAL = fs.readFileSync(
  path.join(__dirname, "..", "ActivitySelectionPage.jsx"), "utf8");

/**
 * Potongan sumber di sekitar penanda uji — enam baris sebelum dan sesudahnya.
 * `className` sebuah elemen kerap berada pada baris LAIN dari `data-testid`-nya,
 * jadi mencocokkan satu baris saja tak pernah menemukannya.
 */
function baris(penanda) {
  const semua = HAL.split("\n");
  const i = semua.findIndex((l) => l.includes(penanda));
  expect(i).toBeGreaterThanOrEqual(0);
  return semua.slice(Math.max(0, i - 6), i + 7).join("\n");
}

test("kotak centang lingkup tak ikut menyusut oleh nama unit yang panjang", () => {
  const b = baris("lingkup-unit-${u.id}");
  const kotak = HAL.split("\n").find((l) => l.includes('type="checkbox"')
    && l.includes("accent-emerald-600"));
  expect(kotak).toContain("flex-shrink-0");
  expect(b).toBeTruthy();
});

test("kotak centang lingkup berukuran seragam, satu kelas untuk semua baris", () => {
  // Ukurannya tak boleh bergantung kedalaman: satu deklarasi saja.
  const kotak = HAL.split("\n").filter((l) => l.includes('type="checkbox"')
    && l.includes("accent-emerald-600"));
  expect(kotak).toHaveLength(1);
  expect(kotak[0]).toMatch(/w-4 h-4/);
});

/**
 * `className` milik ELEMEN yang membawa penanda itu — bukan seluruh jendela.
 * Jendela ikut memuat elemen tetangga (mis. lencana nomor `h-6`), dan
 * mencocokkan kelas di dalamnya akan menghitung tinggi yang bukan miliknya.
 */
function kelas(penanda) {
  const i = HAL.indexOf(penanda);
  expect(i).toBeGreaterThanOrEqual(0);
  const awal = HAL.lastIndexOf("<", i);
  const potong = HAL.slice(awal, i);
  const m = potong.match(/className="([^"]*)"/g) || [];
  return m.length ? m[m.length - 1].slice(11, -1) : "";
}

/** Kelas tinggi (`h-…` / `lg:h-…`) pada elemen itu saja. */
function tinggi(penanda) {
  return kelas(penanda).split(/\s+/)
    .filter((c) => /^(lg:)?h-/.test(c)).sort();
}

test("input dan tombol hapus Eselon I SETINGGI satu sama lain", () => {
  // Ruang mati muncul justru ketika keduanya berbeda tinggi. Yang diuji
  // kesepadanannya, bukan angkanya — angka boleh berubah saat tata letaknya
  // dirapikan, kesepadanannya tidak.
  expect(tinggi("eselon1-input-${idx}"))
    .toEqual(tinggi("remove-eselon1-${idx}"));
});

test("input dan tombol hapus Eselon II SETINGGI satu sama lain", () => {
  expect(tinggi("eselon2-input-${idx}-${j}"))
    .toEqual(tinggi("remove-eselon2-${idx}-${j}"));
});

test("kedua tingkat memakai tinggi baris yang SAMA", () => {
  // Tingkat anak yang lebih pendek daripada induknya membuat kolomnya
  // bergelombang, dan itulah yang terbaca sebagai tak rapi.
  expect(tinggi("eselon1-input-${idx}"))
    .toEqual(tinggi("eselon2-input-${idx}-${j}"));
});

test("kolom nomor kedua tingkat berlebar SAMA supaya tepi kirinya sejajar", () => {
  // Sebelumnya w-4 pada induk dan w-6 pada anak: tepi kirinya tak pernah
  // sejajar, dan itulah yang terbaca sebagai penempatan yang tak rapi.
  // Dijangkarkan pada testid barisnya: penanda nomornya sendiri (`{idx + 1}`)
  // juga muncul di tempat lain pada berkas ini.
  for (const penanda of ["eselon1-input-${idx}", "eselon2-input-${idx}-${j}"]) {
    const i = HAL.indexOf(penanda);
    expect(i).toBeGreaterThanOrEqual(0);
    const awal = HAL.lastIndexOf("<span", i);
    expect(awal).toBeGreaterThanOrEqual(0);
    expect(HAL.slice(awal, i)).toMatch(/className="w-6[\s"]/);
  }
});

test("Eselon II bersarang ditandai GARIS, bukan sekadar margin", () => {
  // Margin saja tak menyatakan hubungan apa pun; garis tegak menyatakannya.
  expect(HAL).toContain("border-l-2 border-emerald-200");
});

test("input tak mendorong tata letak saat namanya panjang", () => {
  // Tanpa `min-w-0`, input di dalam flex menolak menyusut dan mendorong
  // tombol hapusnya keluar baris.
  for (const p of ["eselon1-input-${idx}", "eselon2-input-${idx}-${j}"]) {
    expect(baris(p)).toContain("min-w-0");
  }
});

test("tap-target tombol hapus TIDAK dikecilkan untuk merapatkan jarak", () => {
  // Jalan pintas yang salah: `min-h-0` pada tombolnya akan merapatkan barisnya
  // juga, tetapi dengan mengorbankan area sentuh 44px yang justru dijaga
  // aturan global. Yang benar adalah menyamakan tinggi inputnya.
  for (const penanda of ["remove-eselon1-${idx}", "remove-eselon2-${idx}-${j}"]) {
    expect(baris(penanda)).not.toContain("min-h-0");
  }
});
