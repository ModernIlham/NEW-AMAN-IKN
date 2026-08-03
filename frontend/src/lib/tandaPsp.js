/**
 * Penanda "sudah ber-PSP DAN sudah tersinkron SIMAN V2" — satu aturan, dipakai
 * mode list (tabel desktop + kartu HP) dan mode galeri.
 *
 * Titik hijau kecil itu sebuah KLAIM tentang aset: penetapan status
 * penggunaannya sudah ada, dan datanya sudah cocok dengan SIMAN V2. Karena
 * klaim, syaratnya harus ketat dan ditulis di satu tempat — bukan diulang
 * sebagai `asset.siman?.status === "cocok" && ...` di tiga komponen yang
 * pelan-pelan menyimpang.
 *
 * `psp` datang dari server (`routes/assets.lengkapi_psp`), gabungan register
 * SK PSP dan referensi SIMAN — lihat `penggunaan_utils.info_psp_aset`.
 */

/** Keterangan PSP aset, atau null bila belum ber-PSP. */
export function infoPsp(aset) {
  const p = (aset || {}).psp;
  return p && String(p.no_psp || "").trim() ? p : null;
}

/** Sudah ber-PSP (register SK PSP atau referensi SIMAN V2). */
export function terPsp(aset) {
  return infoPsp(aset) !== null;
}

/**
 * Sudah TUNTAS tersinkron dengan SIMAN V2.
 *
 * - `cocok`         → impor SIMAN menemukan aset ini dan tak ada selisih;
 * - `selisih`       → BELUM, kecuali `sudahSinkron` (petugas baru saja menekan
 *                     tombol sinkron di sesi ini dan server menyatakan selisih
 *                     habis — lihat lib/simanSync.js);
 * - `tidak_di_siman`→ impor berjalan tapi aset ini tak ada di SIMAN → BUKAN
 *                     tersinkron, justru sebaliknya;
 * - tanpa subdok    → aset belum pernah tersentuh impor sama sekali.
 */
export function tersinkronSiman(aset, sudahSinkron = false) {
  const status = ((aset || {}).siman || {}).status;
  if (status === "cocok") return true;
  return status === "selisih" && !!sudahSinkron;
}

/** Syarat titik hijau: KEDUANYA benar, tidak salah satu. */
export function berTitikHijau(aset, sudahSinkron = false) {
  return terPsp(aset) && tersinkronSiman(aset, sudahSinkron);
}

/** `YYYY-MM-DD` → `12 Mar 2024`; nilai tak terbaca dikembalikan apa adanya. */
export function tanggalSingkat(iso) {
  const s = String(iso || "").trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(`${s}T00:00:00`);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString("id-ID",
    { day: "2-digit", month: "short", year: "numeric" });
}

const LABEL_SUMBER = {
  register: "tercatat di register SK PSP",
  siman: "dari referensi SIMAN V2",
};

/**
 * Kalimat penjelas titik hijau — dipakai sebagai `title`/isi tooltip.
 *
 * Menyebut SUMBER angkanya dengan terus terang: nomor dari register SK adalah
 * keputusan yang dibuat di aplikasi ini, sedangkan nomor dari referensi SIMAN
 * adalah potret impor terakhir. Menyamarkan keduanya membuat pengguna tak bisa
 * tahu mana yang perlu ditindaklanjuti.
 */
export function keteranganPsp(aset, sudahSinkron = false) {
  const p = infoPsp(aset);
  if (!p) return "";
  const bagian = [`No. PSP ${p.no_psp}`];
  const tgl = tanggalSingkat(p.tanggal);
  if (tgl) bagian.push(tgl);
  const sumber = LABEL_SUMBER[p.sumber];
  if (sumber) bagian.push(sumber);
  if (tersinkronSiman(aset, sudahSinkron)) bagian.push("tersinkron SIMAN V2");
  return bagian.join(" · ");
}
