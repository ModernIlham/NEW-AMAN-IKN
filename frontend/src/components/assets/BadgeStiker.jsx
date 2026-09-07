import React, { memo } from "react";
import { Tag } from "lucide-react";
import IkonStikerBelum from "./IkonStikerBelum";
import { keteranganStiker } from "@/lib/stikerAset";

/**
 * Badge status stiker: pil DUA BAGIAN — status di kiri, UKURAN di tutup kanan.
 *
 * Rancangannya mengikuti contoh yang diberikan pemilik: pil abu berisi ikon +
 * teks, lalu tutup berwarna pekat berisi satu huruf tebal (S/M/L).
 *
 * ── Kenapa tutupnya sewarna pilnya, bukan hijau seperti contoh ──────────
 * Di contoh, tutup S/M/L-nya hijau. Di aplikasi ini HIJAU sudah punya arti
 * tetap: "stiker sudah terpasang" (dipakai di baris HP, tabel, dan kartu
 * galeri). Tutup hijau pada badge "belum terpasang" akan membuat satu badge
 * mengatakan dua hal yang berlawanan sekaligus — persis kesalahpahaman yang
 * badge ini ada untuk mencegahnya. Jadi tutupnya memakai warna PEKAT dari
 * keluarga warna pilnya sendiri: warna tetap berarti STATUS, huruf tebal
 * berarti UKURAN, dan keduanya tak pernah bertengkar.
 *
 * ── Huruf yang tak dikenali ─────────────────────────────────────────────
 * Kolom ukuran pernah berupa isian bebas ("5x3cm"). Nilai lama seperti itu
 * tak punya huruf ringkas, jadi tutupnya tidak muncul sama sekali — lebih
 * baik daripada memaksakan satu huruf yang salah. Nilainya tetap disebut
 * utuh pada tooltip.
 */
const BadgeStiker = memo(({ asset, className = "" }) => {
  const { terpasang, huruf, label, status, ukuran } = keteranganStiker(asset);
  const Ikon = terpasang ? Tag : IkonStikerBelum;
  return (
    <span
      className={`inline-flex items-stretch rounded-full overflow-hidden text-[10px] font-medium flex-shrink-0 ${className}`}
      title={`Stiker: ${status}${ukuran ? ` — ukuran ${ukuran}` : ""}`}
      data-testid="badge-stiker"
    >
      <span
        className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 ${
          terpasang
            ? "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"
            : "bg-muted text-muted-foreground"
        }`}
      >
        <Ikon className="w-2.5 h-2.5 flex-shrink-0" />
        {label}
      </span>
      {huruf && (
        <span
          className={`inline-flex items-center px-1.5 font-bold ${
            terpasang
              ? "bg-emerald-600 text-white dark:bg-emerald-500 dark:text-emerald-950"
              : "bg-slate-500 text-white dark:bg-slate-400 dark:text-slate-900"
          }`}
          data-testid="badge-stiker-ukuran"
        >
          {huruf}
        </span>
      )}
    </span>
  );
});

BadgeStiker.displayName = "BadgeStiker";

export default BadgeStiker;
