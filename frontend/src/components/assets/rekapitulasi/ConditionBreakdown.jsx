import React from "react";
import { CheckCircle2 } from "lucide-react";

const fmtRp = (val) => {
  try { return `Rp ${Math.round(val).toLocaleString("id-ID")}`; }
  catch { return "Rp 0"; }
};

const items = [
  {
    label: "Baik",
    key: "kondisi_baik",
    labelColor: "text-emerald-600 dark:text-emerald-400",
    valueColor: "text-emerald-800 dark:text-emerald-200",
    subColor: "text-emerald-500 dark:text-emerald-400",
  },
  {
    label: "Rusak Ringan",
    key: "kondisi_rusak_ringan",
    labelColor: "text-amber-600 dark:text-amber-400",
    valueColor: "text-amber-800 dark:text-amber-200",
    subColor: "text-amber-500 dark:text-amber-400",
  },
  {
    label: "Rusak Berat",
    key: "kondisi_rusak_berat",
    labelColor: "text-red-600 dark:text-red-400",
    valueColor: "text-red-800 dark:text-red-200",
    subColor: "text-red-500 dark:text-red-400",
  },
];

export default function ConditionBreakdown({ ditemukan }) {
  if (!ditemukan || ditemukan.count <= 0) return null;

  return (
    <div className="bg-emerald-50/50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800 rounded-lg p-2.5 space-y-1.5" data-testid="condition-breakdown">
      <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
        <CheckCircle2 className="w-3.5 h-3.5" /> Breakdown BMN Ditemukan (Kondisi)
      </p>
      <div className="grid grid-cols-3 gap-2">
        {items.map(({ label, key, labelColor, valueColor, subColor }) => (
          <div key={label} className="bg-card rounded p-2 border border-emerald-100 dark:border-emerald-800">
            <p className={`text-[10px] ${labelColor} font-medium`}>{label}</p>
            <p className={`text-sm font-bold ${valueColor}`}>{ditemukan[key]?.count || 0} NUP</p>
            <p className={`text-[10px] ${subColor}`}>{fmtRp(ditemukan[key]?.value || 0)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
