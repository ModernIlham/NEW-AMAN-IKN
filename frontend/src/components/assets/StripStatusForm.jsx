import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

// SATU baris status ringkas di bawah kepala form aset, menggantikan tumpukan
// banner (draf belum disimpan, cache luring, selisih SIMAN, tak di SIMAN) yang
// dulu bisa memakan sepertiga layar HP sebelum isian pertama terlihat.
// Ringkasan tiap status tampil sebagai pil dalam satu baris; rinciannya
// dibuka dengan satu ketuk. Status kritis (`buka: true`) terbuka sendiri.
//
// items: [{ key, nada: "amber"|"red", ringkas, testId?, rinci: ReactNode, utama? }]
//   utama → pil yang boleh melebar & terpotong (biasanya ringkasan draf).
const NADA = {
  amber: "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-700",
  red: "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/40 dark:text-red-200 dark:border-red-700",
};

export default function StripStatusForm({ items, bukaAwal = false }) {
  const [buka, setBuka] = useState(bukaAwal);
  if (!items.length) return null;
  const terbuka = buka || items.some((it) => it.buka);
  return (
    <div className="flex-shrink-0 border-b border-border bg-amber-50/60 dark:bg-amber-900/10" data-testid="strip-status-form">
      <button type="button" onClick={() => setBuka((b) => !b)} aria-expanded={terbuka}
        data-testid="strip-status-toggle"
        className="w-full flex items-center gap-1.5 px-3 py-1 text-left hover:bg-amber-100/60 dark:hover:bg-amber-900/20">
        {items.map((it) => (
          <span key={it.key} data-testid={it.testId}
            className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-px text-[10px] font-semibold leading-tight ${NADA[it.nada] || NADA.amber} ${it.utama ? "min-w-0 flex-1 truncate" : "shrink-0"}`}>
            {it.utama && <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />}
            <span className="truncate">{it.ringkas}</span>
          </span>
        ))}
        <ChevronDown className={`ml-auto w-3.5 h-3.5 shrink-0 text-amber-700 dark:text-amber-300 transition-transform ${terbuka ? "rotate-180" : ""}`} />
        <span className="sr-only">{terbuka ? "Sembunyikan rincian" : "Tampilkan rincian"}</span>
      </button>
      {terbuka && (
        <div className="px-3 pb-2 pt-0.5 space-y-2 max-h-[40vh] overflow-y-auto" data-testid="strip-status-rinci">
          {items.map((it) => <div key={it.key}>{it.rinci}</div>)}
        </div>
      )}
    </div>
  );
}
