/**
 * Penataan label nama aset di peta.
 *
 * Permintaan pemilik: label nama aset yang rapi walau ada cluster dan marker
 * berdekatan; lalu — setelah melihat hasilnya — *"tolong perbaiki agar
 * pelabelannya mirip seperti screenshoot yang saya berikan, tidak pakai label
 * langsung tulisannya dan jelas terbacanya ... pastikan dari marker baik pin
 * maupun foto, labelnya masih tetap rapi berada ditengah ... jangan buat label
 * terlalu panjang bagi menjadi 2 baris saja dan '...' jika sudah terlalu
 * panjang."*
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

/**
 * Lebar rata-rata satu karakter label, dalam piksel.
 *
 * DIUKUR di Chromium pada huruf label yang sebenarnya (600 12px system-ui),
 * atas delapan nama aset nyata: rata-ratanya 7.39 px dan yang paling boros
 * 8.45 px. Yang diambil UJUNG ATAS rentang itu, bukan reratanya — kotak yang
 * ditaksir terlalu sempit membuat dua label dinilai tak bertabrakan padahal
 * bertindih di layar, dan bertindihnya label itulah yang justru sedang
 * dicegah. Menaksir terlalu lebar hanya menyembunyikan satu-dua label lebih
 * awal.
 */
export const LEBAR_KARAKTER = 8;

/** Lebar maksimum satu label sebelum teksnya membungkus ke bawah. */
export const LEBAR_MAKS = 150;

/**
 * Batas baris label. Label yang mengalir lebih panjang menutupi marker
 * tetangganya — dan justru marker itulah yang sedang dicari mata. Baris
 * ketiga dan seterusnya dipotong ber-elipsis oleh CSS (`-webkit-line-clamp`),
 * jadi angka ini harus SAMA dengan yang di `index.css`: kotak tabrakan yang
 * dihitung untuk tiga baris sementara yang tergambar dua akan menyembunyikan
 * label yang sebenarnya tak bertabrakan.
 */
export const MAKS_BARIS = 2;

/** Tinggi satu baris teks label — diukur 14.0px pada huruf 600 12px/14px. */
export const TINGGI_BARIS = 14;

/**
 * Jarak label dari titik markernya (ke BAWAH) dan sisipan kotaknya.
 *
 * Label kini duduk di bawah-tengah marker, bukan di kanannya: titik jangkar
 * kedua gaya marker (pin 22×22 dan marker foto 46×54) sama-sama berada di
 * TENGAH-BAWAH ikonnya, sehingga satu penempatan "bawah" membuat label rapi
 * di tengah pada keduanya — permintaan pemilik.
 *
 * Sisipannya kecil karena labelnya kini tulisan telanjang tanpa kartu; yang
 * disisakan hanya selebar halo putihnya supaya dua label bersebelahan tak
 * saling menggerus tepinya.
 */
export const JARAK_DARI_MARKER = 6;
export const SISIPAN_X = 2;
export const SISIPAN_Y = 2;

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
  const barisPenuh = Math.max(1, Math.ceil(lebarPenuh / Math.max(1, lebarMaks)));
  const baris = Math.min(MAKS_BARIS, barisPenuh);
  const lebar = barisPenuh > 1 ? lebarMaks : lebarPenuh;
  return {
    lebar: lebar + SISIPAN_X * 2,
    tinggi: baris * TINGGI_BARIS + SISIPAN_Y * 2,
    baris,
  };
}

/**
 * Kotak layar sebuah label bagi marker di titik `(x, y)`.
 *
 * `(x, y)` adalah titik JANGKAR marker — tengah-bawah ikonnya pada kedua gaya
 * marker. Label duduk tepat di bawahnya dan rata tengah terhadapnya, arah yang
 * sama dengan tooltip Leaflet `direction: "bottom"`, supaya kotak yang
 * dihitung di sini benar-benar kotak yang tergambar. Kotak yang tak sejalan
 * dengan gambarnya membuat penata anti-tindih menyembunyikan label yang
 * sebenarnya lega dan meloloskan label yang sebenarnya bertindih.
 */
export function kotakLabel(x, y, teks, opsi) {
  const { lebar, tinggi } = ukurLabel(teks, opsi);
  return {
    kiri: x - lebar / 2,
    atas: y + JARAK_DARI_MARKER,
    kanan: x + lebar / 2,
    bawah: y + JARAK_DARI_MARKER + tinggi,
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
