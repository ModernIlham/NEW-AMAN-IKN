import React, { useState } from "react";
import { X, Flower2 } from "lucide-react";

export default function CameraLensPanel({ lensa, fokus, busy, onClose, onPilih, onFokus }) {
  const [id, setId] = useState(lensa.kandidat?.id || "");
  const tersedia = lensa.daftar.some(d => d.id === id);
  return <div className="absolute inset-0 z-20 bg-black/60 flex items-end sm:items-center justify-center p-3" onClick={onClose}>
    <div role="dialog" aria-label="Pilih lensa makro" aria-modal="true" data-testid="camera-lens-panel"
      className="w-full max-w-sm max-h-[85dvh] overflow-y-auto rounded-2xl bg-slate-950 text-white border border-white/20 p-4 space-y-3"
      onClick={e => e.stopPropagation()}>
      <div className="flex items-center gap-2">
        <Flower2 className="w-5 h-5 text-amber-300" /><h3 className="font-semibold flex-1">Pilih lensa makro</h3>
        <button type="button" aria-label="Tutup pilihan lensa" onClick={onClose} data-testid="camera-lens-close"
          className="w-11 h-11 flex items-center justify-center rounded-full bg-white/10"><X className="w-4 h-4" /></button>
      </div>
      <p className="text-xs text-white/75">Makro mengganti sumber kamera, bukan sekadar zoom atau fokus. Pilih lensa yang sesuai lalu periksa pratinjaunya.</p>
      <p className="text-xs">Kamera aktif: {lensa.daftar.find(d => d.id === lensa.idAktif)?.label || "Kamera bawaan"}</p>
      <label className="block text-xs space-y-1">
        <span>Lensa untuk makro</span>
        <select value={tersedia ? id : ""} onChange={e => setId(e.target.value)} disabled={busy || lensa.memuat}
          data-testid="camera-lens-select" className="w-full h-11 rounded-lg border border-white/20 bg-slate-900 px-2 text-base">
          <option value="">Pilih kamera…</option>
          {lensa.daftar.map(d => <option key={d.id} value={d.id}>{d.label}{d.id === lensa.idAktif ? " (sedang dipakai)" : ""}</option>)}
        </select>
      </label>
      <p className="text-xs text-amber-200" data-testid="camera-lens-availability">
        {lensa.memuat ? "Membaca kamera yang tersedia…" : lensa.galat || (lensa.daftar.length < 2
          ? "Browser hanya menyediakan satu kamera atau tidak menyediakan lensa tambahan. Aplikasi tidak dapat memaksa akses lensa makro yang tidak terdaftar."
          : "Nama dari browser tidak selalu menjelaskan jenis lensa. Kamera 2 atau ultra-wide tidak otomatis berarti makro.")}
      </p>
      <button type="button" onClick={() => onPilih(id)} disabled={busy || lensa.memuat || !tersedia || id === lensa.idAktif}
        data-testid="camera-lens-apply" className="w-full h-11 rounded-lg bg-amber-400 text-black text-sm font-semibold disabled:opacity-40">Gunakan lensa ini untuk makro</button>
      <p className="text-[11px] text-white/60">Pilihan disimpan hanya di browser perangkat ini setelah perpindahan terkonfirmasi. Jika lensa tidak terdaftar, gunakan kamera bawaan HP lalu unggah foto dari form aset.</p>
      <div className="border-t border-white/15 pt-3 space-y-2">
        <button type="button" onClick={onFokus} disabled={busy || fokus.kemampuan.jenis === "none" || fokus.status === "memulihkan"}
          data-testid="camera-lens-focus" className="w-full min-h-11 rounded-lg bg-white/10 text-sm disabled:opacity-40">
          {fokus.status === "mencari" ? "Batalkan pencarian fokus" : fokus.status === "aktif" ? "Matikan bantuan fokus dekat" : "Bantu fokus dekat (tanpa ganti lensa)"}
        </button>
        <p className="text-[11px] text-white/60">Bantuan fokus memakai kamera aktif; tidak mengaktifkan lensa makro fisik.</p>
      </div>
    </div>
  </div>;
}
