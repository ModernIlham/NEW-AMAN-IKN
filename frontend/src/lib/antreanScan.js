// ANTREAN SCAN OPNAME LURING (Spasial Fase 11).
//
// Opname justru dikerjakan di tempat sinyal paling buruk: gudang di basement,
// ruang arsip di ujung lorong, gedung yang belum ada wifi-nya. Kalau setiap
// pindaian harus menunggu jaringan, petugas berhenti bekerja setiap kali sinyal
// hilang — dan yang sudah dipindai sebelum itu ikut hilang bersama layar yang
// tertutup.
//
// Antrean ini kecil dan SENGAJA sederhana: satu daftar di localStorage, tanpa
// IndexedDB, tanpa service worker. Alasannya, muatan satu scan hanyalah
// beberapa ratus byte (kode + node + waktu) — bukan foto — sehingga tak ada
// yang perlu ditawar dari batas localStorage.
//
// YANG MEMBUAT PENGIRIMAN ULANG AMAN adalah `scan_id`: server memakainya
// sebagai kunci idempotensi (indeks unik `opname_scan_idem`). Karena itu antrean
// ini boleh mengirim ulang seagresif apa pun — pengiriman kedua atas isi yang
// sama menghasilkan SATU catatan, bukan dua. Tanpa jaminan itu, mengirim ulang
// justru akan menggelembungkan rekap opname dengan barang yang seolah terpindai
// berkali-kali.
import { idUnik } from "./idAntrean";

const KUNCI = "aman_opname_tertunda";
// Plafon baris. Satu ruangan besar jarang melewati 200 barang; melewati batas
// ini berarti ada yang tak beres dengan pengiriman, dan menumpuk tanpa batas
// hanya akan membuat localStorage penuh lalu MENOLAK penulisan berikutnya —
// kegagalan yang jauh lebih buruk daripada membuang yang paling tua.
const MAKS_BARIS = 200;
// Scan yang tak terkirim selama ini hampir pasti milik opname yang sudah usai.
const MAKS_UMUR_MS = 7 * 24 * 60 * 60 * 1000;

/** ID pemindaian — kunci idempotensi sisi server. Satu tindakan pindai, satu id. */
export function buatScanId() {
  return idUnik("scan_");
}

function _baca() {
  try {
    const mentah = window.localStorage.getItem(KUNCI);
    const arr = mentah ? JSON.parse(mentah) : [];
    return Array.isArray(arr) ? arr.filter((x) => x && x.scan_id) : [];
  } catch {
    // localStorage bisa dimatikan (mode privasi Safari) atau isinya rusak.
    // Opname harus tetap jalan tanpa antrean — kehilangan penyangga luring
    // jauh lebih ringan daripada layar yang menolak memindai sama sekali.
    return [];
  }
}

function _tulis(daftar) {
  try {
    window.localStorage.setItem(KUNCI, JSON.stringify(daftar));
    return true;
  } catch {
    return false;
  }
}

/** Seluruh scan yang belum berhasil terkirim (terlama dulu — urutan kirim). */
export function bacaTertunda() {
  return _baca();
}

export function jumlahTertunda() {
  return _baca().length;
}

/**
 * Titipkan satu scan ke antrean. Idempoten terhadap `scan_id`: menitipkan
 * ulang isi yang sama MEMPERBARUI baris yang ada, bukan menambah baris kedua —
 * kalau tidak, satu pindaian yang dicoba tiga kali akan tampak seperti tiga
 * barang di layar "menunggu kirim".
 */
export function simpanTertunda(item) {
  if (!item || !item.scan_id) return false;
  const daftar = _baca().filter((x) => x.scan_id !== item.scan_id);
  daftar.push({ ...item, dititip_pada: item.dititip_pada || Date.now() });
  // Yang TERLAMA dibuang saat penuh: yang terbaru adalah yang paling mungkin
  // masih relevan bagi petugas yang sedang berdiri di ruangan itu.
  return _tulis(daftar.slice(-MAKS_BARIS));
}

/** Coret satu scan dari antrean (sudah pasti tersimpan di server). */
export function hapusTertunda(scanId) {
  const daftar = _baca();
  const sisa = daftar.filter((x) => x.scan_id !== scanId);
  if (sisa.length === daftar.length) return false;
  _tulis(sisa);
  return true;
}

/**
 * Buang baris yang terlalu tua untuk dikirim. Dipanggil saat panel opname
 * dibuka, supaya sisa opname bulan lalu tak diam-diam ikut terkirim ke rekap
 * opname yang sedang berjalan.
 */
export function bersihkanKedaluwarsa(sekarang = Date.now()) {
  const daftar = _baca();
  const sisa = daftar.filter(
    (x) => sekarang - (Number(x.dititip_pada) || 0) <= MAKS_UMUR_MS);
  if (sisa.length !== daftar.length) _tulis(sisa);
  return daftar.length - sisa.length;
}

/** Kosongkan antrean (dipakai uji & tombol "buang antrean"). */
export function kosongkanAntrean() {
  _tulis([]);
}

export const _KONSTANTA = { KUNCI, MAKS_BARIS, MAKS_UMUR_MS };
