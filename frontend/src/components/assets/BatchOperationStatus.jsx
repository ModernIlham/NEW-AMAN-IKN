import React, { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Loader2, RefreshCw, X } from "lucide-react";
import { identitasBatch, ringkasBatch } from "@/lib/operasiBatch";

const LABEL = { applied: "Berhasil", unchanged: "Sudah sesuai", conflict: "Konflik versi", missing: "Aset tidak ditemukan", failed: "Gagal", pending: "Menunggu" };
export default function BatchOperationStatus({ operation, busy, error, onRefresh, onResume, onReview, onAbandon, onDismiss }) {
  const [expanded, setExpanded] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const panelRef = useRef(null);
  const dismissRef = useRef(onDismiss);
  dismissRef.current = onDismiss;
  const s = ringkasBatch(operation);
  const identity = identitasBatch(operation);
  const canDismiss = s.done && !busy && !!onDismiss;
  const autoDismiss = canDismiss && s.total > 0 && s.success === s.total && !s.attention && !error && !operation?.error;
  useEffect(() => { setCollapsed(false); setExpanded(false); }, [identity]);
  useEffect(() => {
    if (!autoDismiss) return undefined;
    const panel = panelRef.current;
    let timer;
    const schedule = () => {
      clearTimeout(timer);
      if (!document.hidden) timer = setTimeout(() => {
        // Tombol dapat dilepas setelah "Lanjutkan" tanpa memicu blur React.
        // Periksa fokus DOM aktual supaya timer tidak terjeda selamanya.
        const hovering = window.matchMedia?.("(hover: hover)").matches && panel?.matches(":hover");
        if (panel?.contains(document.activeElement) || hovering) schedule();
        else dismissRef.current?.(operation);
      }, 10000);
    };
    schedule();
    panel?.addEventListener("mouseleave", schedule);
    panel?.addEventListener("focusout", schedule);
    document.addEventListener("visibilitychange", schedule);
    return () => {
      clearTimeout(timer);
      panel?.removeEventListener("mouseleave", schedule);
      panel?.removeEventListener("focusout", schedule);
      document.removeEventListener("visibilitychange", schedule);
    };
  }, [autoDismiss, identity, operation]);
  if (!operation) return null;
  const attention = s.results.filter(r => !["applied", "unchanged"].includes(r.status));
  const incomplete = operation.children.some(c => !c.prepared);
  return <section ref={panelRef} className="rounded-lg border border-blue-200 bg-blue-50/70 p-2 text-xs space-y-2 dark:border-blue-800 dark:bg-blue-900/10" data-asset-density="compact" data-testid="batch-operation-status" aria-label="Hasil ubah massal">
    <div className="flex flex-wrap justify-between items-center gap-2">
      <strong className="inline-flex items-center gap-1">{busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}{s.done ? "Hasil ubah massal" : "Ubah massal belum selesai"}</strong>
      <div className="flex items-center gap-2">
        <span>{s.success}/{s.total} selesai{collapsed && s.attention > 0 ? ` · ${s.attention} perlu ditinjau` : ""}</span>
        <button type="button" className="h-11 w-11 shrink-0 rounded inline-flex items-center justify-center hover:bg-blue-100 dark:hover:bg-blue-900/30"
          data-testid="batch-status-collapse" aria-label={collapsed ? "Buka rincian hasil massal" : "Ringkas hasil massal"} aria-expanded={!collapsed} onClick={() => setCollapsed(v => !v)}>
          {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
        {canDismiss && <button type="button" className="h-11 w-11 shrink-0 rounded inline-flex items-center justify-center hover:bg-blue-100 dark:hover:bg-blue-900/30"
          data-testid="batch-status-dismiss" aria-label="Tutup hasil ubah massal" title="Tutup ringkasan; hasil perubahan tetap tersimpan" onClick={() => onDismiss(operation)}><X className="w-4 h-4" /></button>}
      </div>
    </div>
    {!collapsed && <>
    <p role="status" aria-live="polite">Berhasil {s.applied} · Sudah sesuai {s.unchanged} · Konflik {s.conflicts} · Tidak ditemukan {s.missing} · Gagal {s.failed} · Menunggu {s.pending}</p>
    {operation.activityId && <p className="text-muted-foreground">Kegiatan: {operation.activityName || operation.activityId}</p>}
    {(error || operation.error) && <p role="alert" className="text-red-700 dark:text-red-300">{error || operation.error}</p>}
    {operation.children.filter(c => c.error).map(c => <p key={c.operation_id} className="break-words text-red-700 dark:text-red-300">{c.operation_id}: {c.error}</p>)}
    <div className="flex flex-wrap gap-1.5">
      <button type="button" className="h-8 rounded border px-2 inline-flex gap-1 items-center" disabled={busy} onClick={onRefresh}><RefreshCw className="w-3 h-3" />Periksa status</button>
      {!s.done && !incomplete && <button type="button" className="h-8 rounded bg-blue-700 text-white px-2" disabled={busy || !onResume} onClick={onResume}>Lanjutkan yang menunggu</button>}
      {s.done && s.attention > 0 && <button type="button" className="h-8 rounded border px-2" disabled={busy} onClick={onReview}>Tinjau aset bermasalah</button>}
      {incomplete && <button type="button" className="h-8 rounded border px-2" disabled={busy} onClick={onAbandon}>Batalkan persiapan yang belum diterapkan</button>}
      {attention.length > 0 && <button type="button" className="h-8 rounded border px-2" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? "Sembunyikan rincian" : `Rincian ${attention.length} aset`}</button>}
    </div>
    {!s.done && <p className="text-muted-foreground">Status diperiksa kembali setelah muat ulang atau koneksi pulih. Lanjutkan memakai operasi yang sama untuk menjaga hasil yang sudah tersimpan.</p>}
    {expanded && <ul className="max-h-52 overflow-auto space-y-1" aria-label="Aset yang perlu tindakan">{attention.map(r => <li key={r.id} className="break-words"><span className="font-mono">{r.id}</span> — {LABEL[r.status] || r.status}{r.reason ? ` (${r.reason})` : ""}</li>)}</ul>}
    {autoDismiss && <p className="text-muted-foreground">Menutup otomatis setelah 10 detik. Hasil perubahan tetap tersimpan.</p>}
    </>}
  </section>;
}
