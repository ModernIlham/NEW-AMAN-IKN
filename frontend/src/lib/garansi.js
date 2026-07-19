/**
 * Sisa masa garansi aset — dipakai badge di daftar aset (tabel/kartu HP).
 *
 * garansi_hingga = tanggal BERAKHIR garansi (ISO YYYY-MM-DD; rentang lazim
 * dihitung sejak tanggal perolehan). Badge hanya tampil bila tanggal
 * tercatat DAN belum lewat — lewat/kosong → null (badge hilang).
 */
export function sisaGaransi(garansiHingga, now = new Date()) {
  const s = String(garansiHingga || "").trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null;
  const akhir = new Date(`${s}T23:59:59`);
  if (Number.isNaN(akhir.getTime()) || akhir < now) return null;
  const hari = Math.ceil((akhir - now) / 86400000);
  let label;
  if (hari > 365) {
    const th = Math.floor(hari / 365);
    label = `Garansi ±${th} th lagi`;
  } else if (hari > 60) {
    label = `Garansi ${Math.floor(hari / 30)} bln lagi`;
  } else {
    label = `Garansi ${hari} hari lagi`;
  }
  // Durasi SINGKAT ikon-only (badge galeri/list): "45h" / "3bl" / "2th"
  const singkat = hari > 365 ? `${Math.floor(hari / 365)}th`
    : hari > 60 ? `${Math.floor(hari / 30)}bl` : `${hari}h`;
  // ≤60 hari = amber (segera habis), sisanya emerald
  return { hari, label, singkat, segera: hari <= 60, hingga: s };
}
