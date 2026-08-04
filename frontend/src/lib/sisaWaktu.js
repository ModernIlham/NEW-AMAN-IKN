/**
 * Format sisa waktu tautan tanda tangan hingga kedaluwarsa.
 *
 * Angkanya datang dari SERVER (`sisa_detik`), bukan dihitung dari jam
 * perangkat: halaman penanda tangan dibuka orang luar yang jam ponselnya bisa
 * saja meleset, dan tulisan "kedaluwarsa" yang keliru akan membuat orang
 * berhenti menandatangani dokumen yang sebenarnya masih sah.
 *
 * `perkiraan` menandai permintaan LAMA yang dibuat sebelum waktu kedaluwarsa
 * dicatat per penanda tangan — angkanya diturunkan dari tanggal permintaan dan
 * bisa meleset bila tautannya pernah diterbitkan ulang. Karena itu ia
 * ditampilkan sebagai kira-kira ("±"), bukan sebagai angka pasti.
 */

const MENIT = 60;
const JAM = 60 * MENIT;
const HARI = 24 * JAM;

/** Ambang "segera kedaluwarsa" — dipakai UI untuk memberi warna peringatan. */
export const AMBANG_MENDESAK_DETIK = 2 * HARI;

/**
 * "3 hari lagi" / "5 jam lagi" / "12 menit lagi" / "Kedaluwarsa".
 * Mengembalikan "" bila datanya tak diketahui — pemanggil menyembunyikan barisnya.
 */
export function teksSisaWaktu(info) {
  const d = info?.sisa_detik;
  if (d === null || d === undefined || Number.isNaN(Number(d))) return "";
  const detik = Math.max(0, Math.floor(Number(d)));
  if (detik <= 0) return "Kedaluwarsa";

  const awalan = info?.perkiraan ? "±" : "";
  if (detik >= HARI) {
    const hari = Math.floor(detik / HARI);
    const jam = Math.floor((detik % HARI) / JAM);
    // Jam ikut disebut hanya pada sisa pendek — "13 hari 4 jam" tak menambah
    // keputusan apa pun, sedangkan "1 hari 3 jam" menentukan hari ini/besok.
    return hari <= 2 && jam > 0
      ? `${awalan}${hari} hari ${jam} jam lagi`
      : `${awalan}${hari} hari lagi`;
  }
  if (detik >= JAM) return `${awalan}${Math.floor(detik / JAM)} jam lagi`;
  if (detik >= MENIT) return `${awalan}${Math.floor(detik / MENIT)} menit lagi`;
  return `${awalan}kurang dari 1 menit lagi`;
}

/** true bila sudah lewat. */
export function sudahKedaluwarsa(info) {
  const d = info?.sisa_detik;
  return d !== null && d !== undefined && Number(d) <= 0;
}

/** true bila perlu ditagih segera (≤ 2 hari) dan belum kedaluwarsa. */
export function mendesak(info) {
  const d = info?.sisa_detik;
  if (d === null || d === undefined) return false;
  const n = Number(d);
  return n > 0 && n <= AMBANG_MENDESAK_DETIK;
}

/** Kelas warna Tailwind untuk badge sisa waktu. */
export function warnaSisaWaktu(info) {
  if (sudahKedaluwarsa(info)) return "bg-red-500/15 text-red-600 dark:text-red-400";
  if (mendesak(info)) return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
  return "bg-muted text-muted-foreground";
}
