// Warna status & kondisi aset — SATU sumber untuk peta dan chip.
//
// Hex dipakai marker/legenda peta (Peta Aset + Peta Kolaborasi — dua peta
// harus konsisten); kelas Tailwind dipakai chip status inventarisasi di
// daftar/kartu/galeri aset. Sebelum diangkat ke sini nilainya tersalin
// (dan mulai menyimpang) di lima berkas.

export const STATUS_COLORS = {
  "Ditemukan": "#2563eb",
  "Tidak Ditemukan": "#dc2626",
  "Berlebih": "#d97706",
  "Sengketa": "#7c3aed",
  "Belum Diinventarisasi": "#64748b",
};

export const STATUS_DEFAULT = STATUS_COLORS["Belum Diinventarisasi"];

export const CONDITION_COLORS = {
  "Baik": "#059669",
  "Rusak Ringan": "#d97706",
  "Rusak Berat": "#dc2626",
};

// Chip status inventarisasi (pasangan terang/gelap); status tak dikenal —
// termasuk kosong = Belum Diinventarisasi — jatuh ke muted.
export const KELAS_STATUS_INVENTARISASI = {
  "Ditemukan": "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400",
  "Tidak Ditemukan": "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400",
  "Berlebih": "bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400",
  "Sengketa": "bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-400",
};

export function kelasStatusInventarisasi(status) {
  return KELAS_STATUS_INVENTARISASI[status] || "bg-muted text-muted-foreground";
}
