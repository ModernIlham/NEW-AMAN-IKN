import React from "react";
import { CheckSquare, ChevronUp, Pen, X } from "lucide-react";

export default function SelectionToolbar({ count, expanded, onSelectAll, onClear, onTogglePanel, disabled = false }) {
  return (
    <div className={`border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 p-3 ${expanded ? "rounded-t-lg border-b-0" : "rounded-lg"}`} data-testid="selection-toolbar">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-blue-900 dark:text-blue-200"><b>{count}</b> aset terpilih</span>
        <button type="button" onClick={onClear} disabled={disabled} className="flex items-center gap-1.5 min-h-11 px-2 rounded-md text-xs text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50" data-testid="clear-selection-btn">
          <X className="w-4 h-4" />Hapus seleksi
        </button>
      </div>
      <div className="flex flex-wrap items-stretch gap-2 mt-2">
        <button type="button" onClick={onSelectAll} disabled={disabled} title="Pilih atau batalkan semua aset di tampilan ini" className="flex items-center justify-center gap-1.5 min-h-11 px-3 rounded-md border border-blue-200 dark:border-blue-700 bg-card text-xs font-medium hover:bg-accent disabled:opacity-50" data-testid="select-all-visible-btn">
          <CheckSquare className="w-4 h-4" />Pilih semua
        </button>
        <button type="button" onClick={onTogglePanel} aria-expanded={expanded} aria-controls="asset-batch-panel" className="flex flex-1 items-center justify-center gap-1.5 min-h-11 px-3 rounded-md bg-teal-700 hover:bg-teal-800 text-white text-xs font-semibold" data-testid="toggle-batch-panel-btn">
          {expanded ? <ChevronUp className="w-4 h-4" /> : <Pen className="w-4 h-4" />}{expanded ? "Sembunyikan panel" : "Ubah massal"}
        </button>
      </div>
      <p className="text-[11px] leading-relaxed text-blue-800 dark:text-blue-300 mt-2">{expanded ? "Sembunyikan panel untuk kembali ke daftar; seleksi dan isian tetap disimpan." : "Buka Ubah massal untuk mengisi perubahan pada aset terpilih."}</p>
    </div>
  );
}
