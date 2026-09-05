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

test("input Eselon I setinggi tombol hapusnya di layar sempit", () => {
  // Ruang mati muncul justru ketika keduanya berbeda tinggi.
  expect(baris("eselon1-input-${idx}")).toContain("h-11 lg:h-7");
  expect(baris("remove-eselon1-${idx}")).toContain("h-11 w-11 lg:h-7 lg:w-7");
});

test("input Eselon II setinggi tombol hapusnya di layar sempit", () => {
  expect(baris("eselon2-input-${idx}-${j}")).toContain("h-11 lg:h-6");
  expect(baris("remove-eselon2-${idx}-${j}")).toContain("h-11 w-11 lg:h-6 lg:w-6");
});

test("tap-target tombol hapus TIDAK dikecilkan untuk merapatkan jarak", () => {
  // Jalan pintas yang salah: `min-h-0` pada tombolnya akan merapatkan barisnya
  // juga, tetapi dengan mengorbankan area sentuh 44px yang justru dijaga
  // aturan global. Yang benar adalah menyamakan tinggi inputnya.
  for (const penanda of ["remove-eselon1-${idx}", "remove-eselon2-${idx}-${j}"]) {
    expect(baris(penanda)).not.toContain("min-h-0");
  }
});
