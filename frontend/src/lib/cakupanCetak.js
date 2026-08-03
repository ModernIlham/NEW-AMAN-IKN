/**
 * Cakupan aset yang dicetak (Kartu Inventaris & Stiker Label).
 *
 * Aturan pokok: **seleksi menang.** Saat mode seleksi aktif, "cetak" berarti
 * mencetak yang DITANDAI — bukan seisi halaman. Sebelumnya kedua tombol cetak
 * mengabaikan seleksi dan diam-diam mencetak seluruh halaman, sehingga memilih
 * 3 aset lalu menekan Cetak Kartu menghasilkan 50 kartu.
 *
 * Seleksi bisa MELAMPAUI halaman yang tampil ("Pilih semua N aset" mengisi id
 * dari seluruh hasil filter), jadi id terpilih tak boleh disaring terhadap isi
 * halaman — cukup dikirim apa adanya ke server.
 */

/** Nilai cakupan stiker (dipakai sebagai nilai radio & kunci parameter). */
export const CAKUPAN = {
  TERPILIH: "terpilih",
  HALAMAN: "halaman",
  FILTER: "filter",
};

function bersihkanIds(ids) {
  return Array.from(ids || []).filter((x) => typeof x === "string" && x);
}

function idsAset(aset) {
  return (aset || []).map((a) => a?.id).filter((x) => typeof x === "string" && x);
}

/**
 * Aset yang benar-benar dicetak sebagai Kartu Inventaris: yang terpilih bila
 * ada, selain itu seisi halaman yang sedang tampil.
 */
export function idsCetakKartu(idsTerpilih, asetHalaman) {
  const dipilih = bersihkanIds(idsTerpilih);
  return dipilih.length > 0 ? dipilih : idsAset(asetHalaman);
}

/**
 * Cakupan awal dialog stiker saat dibuka. Dengan seleksi aktif, membuka dialog
 * lalu menekan "Buat PDF" harus mencetak yang ditandai — bukan diam-diam
 * kembali ke seluruh hasil filter.
 */
export function cakupanAwal(jumlahTerpilih) {
  return jumlahTerpilih > 0 ? CAKUPAN.TERPILIH : CAKUPAN.FILTER;
}

/**
 * Daftar id untuk sebuah cakupan stiker. String kosong = tak ada daftar id
 * eksplisit; server memakai parameter filter (cakupan "filter").
 */
export function idsCakupanStiker(cakupan, idsTerpilih, asetHalaman) {
  if (cakupan === CAKUPAN.TERPILIH) return bersihkanIds(idsTerpilih);
  if (cakupan === CAKUPAN.HALAMAN) return idsAset(asetHalaman);
  return [];
}

/** Jumlah stiker yang akan tercetak untuk cakupan terpilih. */
export function jumlahCakupanStiker(cakupan, { idsTerpilih, asetHalaman, totalFilter }) {
  if (cakupan === CAKUPAN.FILTER) return totalFilter || 0;
  return idsCakupanStiker(cakupan, idsTerpilih, asetHalaman).length;
}
