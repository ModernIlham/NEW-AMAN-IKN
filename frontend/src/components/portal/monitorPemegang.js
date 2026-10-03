// Ringkasan hanya berasal dari penugasan yang masih diberikan API kepada sesi
// pemegang. Laporan lama tidak pernah dipasangkan lewat nama/kode barang.
export const FILTER_MONITOR = [
  ["semua", "Semua barang"], ["belum", "Belum dilaporkan"],
  ["menunggu", "Menunggu pemeriksaan"], ["perhatian", "Perlu perhatian"],
];
export const OPERASIONAL_MONITOR = {
  digunakan: "Sedang digunakan", tidak_digunakan: "Tidak digunakan",
  diperbaiki: "Sedang diperbaiki", tidak_diketahui: "Belum diketahui",
};
const waktu = value => Date.parse(value || "") || 0;

export function urutLaporanPemegang(laporan = []) {
  return [...laporan].sort((a, b) => waktu(b.created_at) - waktu(a.created_at)
    || String(b.id || "").localeCompare(String(a.id || "")));
}

export function laporanTerbaruPemegang(laporan = []) {
  const hasil = new Map();
  for (const item of urutLaporanPemegang(laporan)) {
    if (item.penugasan_id && !hasil.has(item.penugasan_id)) hasil.set(item.penugasan_id, item);
  }
  return hasil;
}

export function perluPerhatianPemegang(aset, laporan) {
  return aset.status !== "diterima" || ["perlu_perbaikan", "ditolak"].includes(laporan?.status)
    || (laporan?.status !== "ditolak" && (laporan?.jenis === "kehilangan"
      || ["Rusak Ringan", "Rusak Berat"].includes(laporan?.kondisi)
      || laporan?.status_operasional === "diperbaiki"));
}

export function cocokMonitorPemegang(aset, laporan, filter) {
  if (filter === "belum") return aset.status === "diterima" && !laporan;
  if (filter === "menunggu") return ["diajukan", "menunggu_verifikasi"].includes(laporan?.status);
  if (filter === "perhatian") return perluPerhatianPemegang(aset, laporan);
  return true;
}

export function ringkasanMonitorPemegang(aset = [], terbaru = new Map()) {
  return Object.fromEntries(FILTER_MONITOR.map(([id]) => [id,
    aset.filter(a => cocokMonitorPemegang(a, terbaru.get(a.id), id)).length,
  ]));
}

export function cariAsetPemegang(aset, laporan, query) {
  const teks = [aset.asset_name, aset.asset_code, aset.NUP, aset.location,
    aset.sumber_bast?.nomor, laporan?.lokasi_laporan].filter(v => v !== undefined && v !== null).join(" ").toLocaleLowerCase("id");
  return teks.includes(query.trim().toLocaleLowerCase("id"));
}

export function tanggalMonitor(value, hanyaTanggal = false) {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime()) ? date.toLocaleString("id-ID", {
    day: "numeric", month: "short", year: "numeric",
    ...(!hanyaTanggal ? { hour: "2-digit", minute: "2-digit" } : {}),
  }) : "Belum tercatat";
}
