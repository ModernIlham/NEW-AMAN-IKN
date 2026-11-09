import React, { useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Save, LogOut, Trash2 } from "lucide-react";
import { useBackGuard } from "../../hooks/useBackGuard";

// Dialog "keluar dari form padahal ada perubahan belum disimpan".
//
// Hanya dimunculkan bila memang ADA perubahan bermakna (lihat
// ringkasPerubahan) — form yang tak disentuh langsung tertutup tanpa dialog.
// Tombol Back HP saat dialog terbuka = "Lanjut Edit" (paling aman), sehingga
// menekan Back dua kali beruntun tidak pernah membuang data.
export default function KonfirmasiKeluarForm({ ringkasan, busy, onLanjut, onSimpan, onKeluarDraf, onBuang }) {
  const [jangan, setJangan] = useState(false);
  useBackGuard(useCallback(() => onLanjut(), [onLanjut]));
  const [yakinBuang, setYakinBuang] = useState(false);
  return createPortal(
    <div className="fixed inset-0 z-[130] bg-black/60 flex items-end sm:items-center justify-center p-4" data-testid="konfirmasi-keluar-form"
      role="dialog" aria-modal="true" aria-labelledby="konfirmasi-keluar-judul" onClick={onLanjut}>
      <div className="bg-card text-foreground rounded-2xl p-4 w-full max-w-sm space-y-3 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-amber-500 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <h3 id="konfirmasi-keluar-judul" className="text-sm font-bold">Perubahan belum disimpan</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5 break-words">{ringkasan || "Ada isian yang belum disimpan."}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 gap-2">
          <button type="button" onClick={onSimpan} disabled={busy} data-testid="konfirmasi-keluar-simpan"
            className="h-11 rounded-lg bg-teal-700 hover:bg-teal-800 disabled:opacity-60 text-white text-sm font-semibold flex items-center justify-center gap-1.5">
            <Save className="w-4 h-4" />Simpan Sekarang
          </button>
          <button type="button" onClick={() => onKeluarDraf(jangan)} data-testid="konfirmasi-keluar-draf"
            className="h-11 rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-900/40 text-sm font-medium flex items-center justify-center gap-1.5">
            <LogOut className="w-4 h-4" />Keluar, Simpan sebagai Draf
          </button>
          <button type="button" onClick={onLanjut} data-testid="konfirmasi-keluar-lanjut"
            className="h-11 rounded-lg border border-border bg-background text-foreground/80 hover:bg-muted text-sm font-medium">
            Lanjut Edit
          </button>
          <button type="button" data-testid="konfirmasi-keluar-buang"
            onClick={() => { if (yakinBuang) onBuang(); else setYakinBuang(true); }}
            className="h-11 rounded-lg text-sm font-medium flex items-center justify-center gap-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/30 dark:hover:text-red-300">
            <Trash2 className="w-4 h-4" />{yakinBuang ? "Ketuk lagi untuk membuang" : "Buang Perubahan"}
          </button>
        </div>
        <label className="flex items-start gap-2 text-[11px] text-muted-foreground cursor-pointer">
          <input type="checkbox" checked={jangan} onChange={(e) => setJangan(e.target.checked)} className="mt-0.5 min-w-0 min-h-0" data-testid="konfirmasi-keluar-jangan-tanya" />
          <span>Jangan tanya lagi selama sesi ini — saat keluar, perubahan otomatis disimpan sebagai draf.</span>
        </label>
      </div>
    </div>,
    document.body,
  );
}
