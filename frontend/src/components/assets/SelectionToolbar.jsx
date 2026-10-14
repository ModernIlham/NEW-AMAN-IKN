import React from "react";
import { CheckSquare, ChevronUp, Pen, X } from "lucide-react";

export default function SelectionToolbar({ count, expanded, onSelectAll, onClear, onTogglePanel, disabled = false }) {
  return (
    <div className={`border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-2 ${expanded ? "rounded-t-lg border-b-0" : "rounded-lg"}`} data-testid="selection-toolbar" data-asset-density="compact">
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <span className="text-xs font-medium text-blue-900 dark:text-blue-200"><b>{count}</b> aset terpilih</span>
        <button type="button" onClick={onClear} disabled={disabled} className="flex items-center gap-1.5 h-9 px-2 rounded-md text-xs text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50" data-testid="clear-selection-btn">
          <X className="w-3.5 h-3.5" />Hapus seleksi
        </button>
      </div>
      <div className="flex flex-wrap items-stretch gap-1.5 mt-1.5">
        <button type="button" onClick={onSelectAll} disabled={disabled} title="Pilih atau batalkan semua aset di tampilan ini" className="flex items-center justify-center gap-1.5 h-9 px-3 rounded-md border border-blue-200 dark:border-blue-700 bg-card text-xs font-medium hover:bg-accent disabled:opacity-50" data-testid="select-all-visible-btn">
          <CheckSquare className="w-3.5 h-3.5" />Pilih semua
        </button>
        <button type="button" onClick={onTogglePanel} aria-expanded={expanded} aria-controls="asset-batch-panel" className="flex flex-1 sm:flex-none sm:ml-auto items-center justify-center gap-1.5 h-9 px-3 rounded-md bg-teal-700 hover:bg-teal-800 text-white text-xs font-semibold" data-testid="toggle-batch-panel-btn">
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <Pen className="w-3.5 h-3.5" />}{expanded ? "Sembunyikan panel" : "Ubah massal"}
        </button>
      </div>
      <p className="text-[10px] leading-snug text-blue-800 dark:text-blue-300 mt-1.5">{expanded ? "Sembunyikan panel tetap menyimpan seleksi dan isian." : "Buka Ubah massal untuk mengisi perubahan pada aset terpilih."}</p>
    </div>
  );
}
