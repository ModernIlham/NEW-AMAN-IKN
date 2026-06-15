import React from "react";
import { AlertTriangle } from "lucide-react";

const fmtRp = (val) => {
  try { return `Rp ${Math.round(val).toLocaleString("id-ID")}`; }
  catch { return "Rp 0"; }
};

export default function TidakDitemukanBreakdown({ tidakDitemukan, subBreakdown }) {
  if (!tidakDitemukan || tidakDitemukan.count <= 0) return null;

  return (
    <div className="bg-red-50/50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 rounded-lg p-2.5 space-y-2" data-testid="tidak-ditemukan-breakdown">
      <p className="text-xs font-medium text-red-700 dark:text-red-400 flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" /> Breakdown BMN Tidak Ditemukan
      </p>
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-card rounded p-2 border border-red-100 dark:border-red-800">
          <p className="text-[10px] text-orange-600 dark:text-orange-400 font-medium">Kesalahan Pencatatan</p>
          <p className="text-sm font-bold text-orange-800 dark:text-orange-200">{tidakDitemukan.kesalahan_pencatatan?.count || 0} NUP</p>
          <p className="text-[10px] text-orange-500 dark:text-orange-400">{fmtRp(tidakDitemukan.kesalahan_pencatatan?.value || 0)}</p>
        </div>
        <div className="bg-card rounded p-2 border border-red-100 dark:border-red-800">
          <p className="text-[10px] text-red-600 dark:text-red-400 font-medium">Tidak Ditemukan Lainnya</p>
          <p className="text-sm font-bold text-red-800 dark:text-red-200">{tidakDitemukan.tidak_ditemukan_lainnya?.count || 0} NUP</p>
          <p className="text-[10px] text-red-500 dark:text-red-400">{fmtRp(tidakDitemukan.tidak_ditemukan_lainnya?.value || 0)}</p>
        </div>
      </div>
      {Object.keys(subBreakdown || {}).length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground font-medium">Detail Sub-Klasifikasi:</p>
          {Object.entries(subBreakdown).map(([key, val]) => (
            <div key={key} className="flex items-center justify-between text-[10px] bg-card rounded px-2 py-1 border border-red-50 dark:border-red-900">
              <span className="text-muted-foreground truncate max-w-[60%]">{key}</span>
              <span className="text-red-700 dark:text-red-400 font-medium">{val.count} NUP · {fmtRp(val.value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
