// Chip status register — kanon bersama seluruh modul siklus BMN.
//
// Pola dominan yang dikanonkan (dipakai register Penggunaan, Pemanfaatan,
// Pemusnahan, Pemindahtanganan, Penghapusan/TGR, Pengamanan, Penganggaran,
// Perencanaan, dll.):
//
//   <span className={kelasChipStatus(PETA, status)}>{label}</span>
//
// dengan PETA = peta warna per status yang nilainya diambil dari WARNA_CHIP.
// Status yang tak dikenal peta jatuh ke `muted` (netral) — status baru dari
// backend tidak pernah membuat chip tak terbaca.

export const KELAS_CHIP = "px-1.5 py-0.5 rounded text-[10px] font-semibold";

// Token warna chip: bg lembut 15% + teks kuat yang tetap terbaca di gelap.
export const WARNA_CHIP = {
  emerald: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  red: "bg-red-500/15 text-red-600 dark:text-red-400",
  sky: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  violet: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  blue: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  indigo: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
  muted: "bg-muted text-muted-foreground",
};

export function kelasChipStatus(peta, status) {
  return `${KELAS_CHIP} ${(peta || {})[status] || WARNA_CHIP.muted}`;
}
