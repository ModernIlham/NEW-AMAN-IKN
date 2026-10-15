import React, { useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { ringkasBatch } from "@/lib/operasiBatch";

const LABEL = { applied: "Berhasil", unchanged: "Sudah sesuai", conflict: "Konflik versi", missing: "Aset tidak ditemukan", failed: "Gagal", pending: "Menunggu" };
export default function BatchOperationStatus({ operation, busy, error, onRefresh, onResume, onReview, onAbandon }) {
  const [expanded, setExpanded] = useState(false);
  if (!operation) return null;
  const s = ringkasBatch(operation);
  const attention = s.results.filter(r => !["applied", "unchanged"].includes(r.status));
  const incomplete = operation.children.some(c => !c.prepared);
  return <section className="rounded-lg border border-blue-200 bg-blue-50/70 p-2 text-xs space-y-2 dark:border-blue-800 dark:bg-blue-900/10" data-asset-density="compact" data-testid="batch-operation-status" aria-label="Hasil ubah massal">
    <div className="flex flex-wrap justify-between items-center gap-2">
      <strong className="inline-flex items-center gap-1">{busy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}{s.done ? "Hasil ubah massal" : "Ubah massal belum selesai"}</strong>
      <span>{s.success}/{s.total} selesai</span>
    </div>
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
  </section>;
}
