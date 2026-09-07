/**
 * Penataan label nama aset di peta.
 *
 * Permintaan pemilik: *"pada halaman peta tambahkan fitur label yang
 * menampilkan nama-nama asetnya dengan font putih dan diberikan stroke hitam
 * agar terlihat di segala macam background latar, pastikan rapi mengingat ada
 * cluster dan berdekatan satu dengan lainnya."*
 *
 * Bagian yang sulit bukan menggambar labelnya, melainkan membuatnya RAPI:
 * label permanen pada peta padat saling menimpa sampai tak satu pun terbaca,
 * dan yang tertimpa tak menghilang — ia menjadi coretan hitam-putih di atas
 * peta. Modul ini memilih label mana yang tampil sehingga tak ada dua yang
 * bertindih.
 *
 * MURNI: tak menyentuh DOM dan tak mengenal Leaflet. Pemanggilnya yang
 * mengukur posisi marker di layar dan memasang/melepas labelnya.
 */

/** Lebar rata-rata satu karakter pada huruf tebal 11px, dalam piksel. */
export const LEBAR_KARAKTER = 6.2;

/** Lebar maksimum satu label sebelum teksnya membungkus ke bawah. */
export const LEBAR_MAKS = 150;

/** Tinggi satu baris teks label, berikut sisipan atas-bawahnya. */
export const TINGGI_BARIS = 13;

/** Jarak label dari titik markernya (ke kanan) dan sisipan kotaknya. */
export const JARAK_DARI_MARKER = 14;
export const SISIPAN_X = 6;
export const SISIPAN_Y = 4;

/**
 * Banyaknya label yang masih pantas dihitung tabrakannya dalam satu sapuan.
 * Di atas ini, peta memang terlalu padat untuk dilabeli seluruhnya — dan
 * menghitung tabrakan n² untuk ribuan marker membekukan peta saat digeser.
 */
export const MAKS_LABEL = 120;

/**
 * Ukuran kotak label untuk sebuah teks: `{lebar, tinggi, baris}`.
 *
 * Pembungkusan terjadi pada BATAS KATA, jadi lebar yang terpakai tak pernah
 * penuh; taksiran ini sengaja tak pernah terlalu kecil, sebab kotak yang
 * ditaksir terlalu sempit membuat dua label dinilai tak bertabrakan padahal
 * bertindih di layar.
 */
export function ukurLabel(teks, { lebarMaks = LEBAR_MAKS } = {}) {
  const t = String(teks || "").trim();
  if (!t) return { lebar: 0, tinggi: 0, baris: 0 };
  const lebarPenuh = t.length * LEBAR_KARAKTER;
  const baris = Math.max(1, Math.ceil(lebarPenuh / Math.max(1, lebarMaks)));
  const lebar = baris > 1 ? lebarMaks : lebarPenuh;
  return {
    lebar: lebar + SISIPAN_X * 2,
    tinggi: baris * TINGGI_BARIS + SISIPAN_Y * 2,
    baris,
  };
}

/**
 * Kotak layar sebuah label bagi marker di titik `(x, y)`.
 *
 * Label duduk di KANAN marker dan rata tengah terhadapnya — arah yang sama
 * dengan tooltip Leaflet `direction: "right"`, supaya kotak yang dihitung di
 * sini benar-benar kotak yang tergambar.
 */
export function kotakLabel(x, y, teks, opsi) {
  const { lebar, tinggi } = ukurLabel(teks, opsi);
  return {
    kiri: x + JARAK_DARI_MARKER,
    atas: y - tinggi / 2,
    kanan: x + JARAK_DARI_MARKER + lebar,
    bawah: y + tinggi / 2,
  };
}

function bertabrakan(a, b) {
  return !(a.kanan <= b.kiri || b.kanan <= a.kiri
    || a.bawah <= b.atas || b.bawah <= a.atas);
}

/**
 * Pilih label mana yang tampil sehingga TAK ADA DUA yang bertindih.
 *
 * `kandidat` = `[{id, kotak}, …]` sudah dalam urutan prioritas. Urutannya
 * ditentukan pemanggil dan harus TETAP (mis. urutan baris data), bukan
 * bergantung posisi di layar: prioritas yang berubah saat peta digeser membuat
 * label berkedip-kedip muncul-hilang padahal petanya hanya bergeser sedikit.
 *
 * Kembalikan `Set` berisi id yang tampil.
 */
export function pilihLabelTampil(kandidat, { maks = MAKS_LABEL } = {}) {
  const tampil = new Set();
  const dipakai = [];
  if (!Array.isArray(kandidat) || kandidat.length === 0) return tampil;
  // Peta yang terlalu padat tak dilabeli sama sekali: label yang tersisa
  // setelah tabrakan hanya segelintir yang tersebar acak, dan pembaca tak
  // punya cara menebak mengapa justru yang itu yang bernama.
  if (kandidat.length > maks) return tampil;
  for (const k of kandidat) {
    if (!k || !k.kotak) continue;
    if (dipakai.some((r) => bertabrakan(r, k.kotak))) continue;
    dipakai.push(k.kotak);
    tampil.add(k.id);
  }
  return tampil;
}
