/**
 * Ringkasan "apa yang akan dan TIDAK akan tertandatangani" — MURNI.
 *
 * Laporan pemilik: *"ketika link bubuhkan tanda tangan diterima penanda
 * tangan, sering kali penandatangan tidak melihat semua halaman terkait
 * padahal ada lebih dari 1 kali tanda tangan yang seharusnya dia
 * tandatangani, tapi dia tidak memperhatikan dan langsung mengklik
 * membubuhkan tanpa mengecek ulang."*
 *
 * Penahanan jumlah yang sudah ada hanya bekerja bila pemilik dokumen
 * MENDEKLARASIKAN jumlahnya. Bila ia lupa — dan bawaannya 1 — tak ada apa pun
 * yang menahan, dan penanda tangan menekan Bubuhkan atas dokumen yang belum
 * ia lihat seluruhnya.
 *
 * Yang dipecahkan modul ini BUKAN "berapa yang wajib", melainkan "apa yang
 * SEDANG TERJADI": pada detik tombol ditekan, sebutkan halaman mana yang akan
 * berisi tanda tangannya, halaman mana yang akan terbit KOSONG, dan — ini
 * yang paling menentukan — halaman mana yang BELUM PERNAH IA BUKA.
 *
 * Halaman yang belum pernah dibuka adalah fakta yang diketahui layar dengan
 * pasti (pratinjaunya tak pernah dimuat), bukan tuduhan. Menyebutkannya
 * mengubah "saya kira sudah semua" menjadi "saya belum melihat halaman 3".
 */

/** Deret 1..n sebagai array. */
function semuaHalaman(n) {
  const total = Math.max(0, Math.floor(Number(n) || 0));
  return Array.from({ length: total }, (_, i) => i + 1);
}

/** Angka halaman yang sah & unik, terurut naik. */
function bersih(daftar, total) {
  const out = new Set();
  for (const v of daftar || []) {
    const n = Math.floor(Number(v));
    if (Number.isFinite(n) && n >= 1 && n <= total) out.add(n);
  }
  return [...out].sort((a, b) => a - b);
}

/**
 * → {ditandatangani, tanpaTtd, belumDibuka}
 *
 * `halamanDilihat` = halaman yang pratinjaunya BENAR-BENAR dimuat di layar.
 * Halaman yang berisi pembubuhan otomatis terhitung dilihat: mustahil
 * menempatkan kotak di halaman yang tak tampil.
 */
export function ringkasPembubuhan({ jumlahHalaman, halamanTtd, halamanDilihat } = {}) {
  const total = Math.max(0, Math.floor(Number(jumlahHalaman) || 0));
  const ttd = bersih(halamanTtd, total);
  const dilihat = new Set([...bersih(halamanDilihat, total), ...ttd]);
  return {
    ditandatangani: ttd,
    tanpaTtd: semuaHalaman(total).filter((h) => !ttd.includes(h)),
    belumDibuka: semuaHalaman(total).filter((h) => !dilihat.has(h)),
  };
}

/** Perlukah pemeriksaan akhir ditampilkan? */
export function perluPeriksaAkhir(jumlahHalaman) {
  // Dokumen SATU halaman tak punya halaman lain untuk terlewat — memaksa
  // konfirmasi di sana hanya melatih orang menekan "Ya" tanpa membaca, dan
  // pelatihan itu justru melumpuhkan konfirmasi yang benar-benar penting.
  return Math.max(0, Math.floor(Number(jumlahHalaman) || 0)) > 1;
}
