/**
 * Tampilan nomor urut buku agenda — satu sumber untuk PersuratanPage dan
 * BookingNomorButton, supaya nomor SISIPAN (backdate, "005.01") tampil sama
 * di kartu HP, tabel desktop, dan panel hasil booking.
 */

/** 15 → "015"; sisipan 1 → "015.01". */
export function noAgendaTampil(noAgenda, sisipan = 0) {
  const dasar = String(Number(noAgenda) || 0).padStart(3, "0");
  const s = Number(sisipan) || 0;
  return s > 0 ? `${dasar}.${String(s).padStart(2, "0")}` : dasar;
}

/**
 * Lencana agenda lengkap.
 *
 * Server merakitnya (`label_agenda`) karena bentuknya bergantung pada METODE
 * DERET satker: deret bulanan menyertakan bulan — "K-005/VIII/2026" — sebab
 * tanpa itu nomor 001 bulan Juli dan 001 bulan Agustus tampil identik, dan
 * buku agenda kehilangan sifat paling mendasarnya: satu nomor menunjuk satu
 * surat.
 *
 * Perakitan di sini hanya JARING PENGAMAN untuk data yang datang tanpa
 * lencana (respons lama, hasil booking sebelum daftar disegarkan). Ia sengaja
 * memakai bentuk tahunan: menebak bulan di klien berarti menebak setelan
 * satker, dan tebakan yang salah lebih menyesatkan daripada bentuk ringkas.
 */
export function labelAgenda(s) {
  const dariServer = String((s || {}).label_agenda || "").trim();
  if (dariServer) return dariServer;
  const awalan = (s || {}).jenis === "keluar" ? "K" : "M";
  return `${awalan}-${noAgendaTampil(s?.no_agenda, s?.sisipan)}/${s?.tahun}`;
}
