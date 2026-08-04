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

/** Lencana agenda lengkap: {jenis:"keluar",no_agenda:5,sisipan:1,tahun:2026} → "K-005.01/2026". */
export function labelAgenda(s) {
  const awalan = (s || {}).jenis === "keluar" ? "K" : "M";
  return `${awalan}-${noAgendaTampil(s?.no_agenda, s?.sisipan)}/${s?.tahun}`;
}
