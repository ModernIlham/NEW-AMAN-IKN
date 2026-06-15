import React from "react";
import {
  BarChart3, CheckCircle2, XCircle, FileWarning, Shield, Clock
} from "lucide-react";

const fmtRp = (val) => {
  try { return `Rp ${Math.round(val).toLocaleString("id-ID")}`; }
  catch { return "Rp 0"; }
};

const cards = [
  {
    key: "total", path: null, icon: BarChart3, label: "BMN Diteliti",
    bg: "bg-blue-50 dark:bg-blue-900/30",
    border: "border-blue-200 dark:border-blue-700",
    iconText: "text-blue-600 dark:text-blue-400",
    value: "text-blue-800 dark:text-blue-200",
    sub: "text-blue-500 dark:text-blue-400",
  },
  {
    key: "ditemukan", path: "ditemukan", icon: CheckCircle2, label: "Ditemukan",
    bg: "bg-emerald-50 dark:bg-emerald-900/30",
    border: "border-emerald-200 dark:border-emerald-700",
    iconText: "text-emerald-600 dark:text-emerald-400",
    value: "text-emerald-800 dark:text-emerald-200",
    sub: "text-emerald-500 dark:text-emerald-400",
  },
  {
    key: "tidak_ditemukan", path: "tidak_ditemukan", icon: XCircle, label: "Tidak Ditemukan",
    bg: "bg-red-50 dark:bg-red-900/30",
    border: "border-red-200 dark:border-red-700",
    iconText: "text-red-600 dark:text-red-400",
    value: "text-red-800 dark:text-red-200",
    sub: "text-red-500 dark:text-red-400",
  },
  {
    key: "berlebih", path: "berlebih", icon: FileWarning, label: "Berlebih",
    bg: "bg-purple-50 dark:bg-purple-900/30",
    border: "border-purple-200 dark:border-purple-700",
    iconText: "text-purple-600 dark:text-purple-400",
    value: "text-purple-800 dark:text-purple-200",
    sub: "text-purple-500 dark:text-purple-400",
  },
  {
    key: "sengketa", path: "sengketa", icon: Shield, label: "Sengketa",
    bg: "bg-rose-50 dark:bg-rose-900/30",
    border: "border-rose-200 dark:border-rose-700",
    iconText: "text-rose-600 dark:text-rose-400",
    value: "text-rose-800 dark:text-rose-200",
    sub: "text-rose-500 dark:text-rose-400",
  },
  {
    key: "belum", path: "belum_diinventarisasi", icon: Clock, label: "Belum Inventarisasi",
    bg: "bg-slate-50 dark:bg-slate-800/50",
    border: "border-slate-200 dark:border-slate-600",
    iconText: "text-slate-600 dark:text-slate-400",
    value: "text-slate-800 dark:text-slate-200",
    sub: "text-slate-500 dark:text-slate-400",
  },
];

export default function SummaryCards({ data, total }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-2" data-testid="summary-cards">
      {cards.map(({ key, path, icon: Icon, label, bg, border, iconText, value, sub }) => {
        const count = key === "total" ? total : (data[path]?.count || 0);
        const val = key === "total" ? data.total_nilai_diteliti : (data[path]?.value || 0);
        return (
          <div key={key} className={`${bg} border ${border} rounded-lg p-2.5`} data-testid={`summary-card-${key}`}>
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className={`w-3.5 h-3.5 ${iconText}`} />
              <span className={`text-[10px] ${iconText} font-medium`}>{label}</span>
            </div>
            <p className={`text-lg font-bold ${value}`}>{count}</p>
            <p className={`text-[10px] ${sub}`}>{fmtRp(val)}</p>
          </div>
        );
      })}
    </div>
  );
}
