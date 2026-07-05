import React, { useRef, memo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Camera, Briefcase, MapPin, Tag, CreditCard, Trash2, History, ClipboardCheck, Lock, Cloud, CloudOff, Check, RotateCcw, Clock, Loader2, AlertTriangle, BookOpen } from "lucide-react";
import { Button } from "../ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../ui/tooltip";

// Helper: truncated cell with optional icon
const TruncatedCell = memo(({ text, icon: Icon }) => {
  if (!text) return <span className="text-[10px] text-muted-foreground">-</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-0.5 min-w-0">
          {Icon && <Icon className="w-3 h-3 text-muted-foreground flex-shrink-0" />}
          <span className="text-[11px] text-muted-foreground truncate">{text}</span>
        </div>
      </TooltipTrigger>
      {text.length > 15 && (
        <TooltipContent side="bottom" className="max-w-xs"><p className="text-xs">{text}</p></TooltipContent>
      )}
    </Tooltip>
  );
});
TruncatedCell.displayName = "TruncatedCell";

const formatPrice = (price) => {
  if (!price) return '-';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return '-';
  if (num >= 1e9) return `${(num / 1e9).toFixed(1)}M`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(1)}Jt`;
  return num.toLocaleString('id-ID');
};

// ============================================================================
// VIRTUALIZED ASSET TABLE - Responsive for md (768px) to xl (1280px+)
// md-lg: Foto, Identitas, Nama, Kondisi, Status, INV, Actions
// xl+: + Eselon, Lokasi, Harga, Dok, Stiker
// ============================================================================
const VirtualizedAssetTable = memo(({ assets, editId, onEdit, onDelete, onPrintCard, onOpenKartu, onViewAudit, pageSize, rowLocks = {}, currentSessionId, syncStatuses = {}, onRetrySync, onDismissSync, selectedAssets, onToggleSelect, onToggleSelectAll }) => {
  const parentRef = useRef(null);
  const ROW_HEIGHT = 52;
  const HEADER_HEIGHT = 32;
  const maxVisibleRows = Math.min(pageSize, 15);
  const containerHeight = Math.min(assets.length, maxVisibleRows) * ROW_HEIGHT + HEADER_HEIGHT;
  const hasSelection = selectedAssets && selectedAssets.size > 0;
  const allSelected = assets.length > 0 && selectedAssets && selectedAssets.size === assets.length;

  const virtualizer = useVirtualizer({
    count: assets.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
  });

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="bg-muted/50 border-b border-border flex items-center text-[9px] font-bold text-muted-foreground uppercase tracking-widest select-none" style={{ height: HEADER_HEIGHT }}>
        {onToggleSelectAll && (
          <div className="w-7 flex-shrink-0 flex justify-center">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={onToggleSelectAll}
              className="w-3 h-3 rounded cursor-pointer accent-blue-600"
              data-testid="select-all-checkbox"
            />
          </div>
        )}
        <div className="w-10 flex-shrink-0 text-center">Foto</div>
        <div className="flex-[2] min-w-0 px-1">Identitas</div>
        <div className="flex-[2] min-w-0 px-1">Nama Barang</div>
        {/* Eselon/Lokasi: proportional (flex-1) instead of fixed w-20 — full
            text shows on wide screens, truncation only when space runs out.
            Header and body cells must keep identical classes to stay aligned. */}
        <div className="hidden xl:block flex-1 min-w-0 px-1">Eselon</div>
        <div className="hidden xl:block flex-1 min-w-0 px-1">Lokasi</div>
        <div className="hidden xl:block w-20 flex-shrink-0 px-1 text-right">Harga</div>
        <div className="w-14 flex-shrink-0 text-center">Kondisi</div>
        <div className="w-14 flex-shrink-0 text-center">Status</div>
        <div className="hidden xl:block w-9 flex-shrink-0 text-center">Dok</div>
        <div className="hidden xl:block w-10 flex-shrink-0 text-center">Stiker</div>
        <div className="w-9 flex-shrink-0 text-center">INV</div>
        <div className="w-[116px] flex-shrink-0" />
      </div>

      {/* Virtualized Body */}
      <div ref={parentRef} className="overflow-auto" style={{ height: containerHeight - HEADER_HEIGHT }}>
        <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
          {virtualizer.getVirtualItems().map((vr) => {
            const a = assets[vr.index];
            const photo = a.thumbnail;
            const hasPhoto = photo && photo.length > 10;
            const stiker = a.stiker_status === "Sudah Terpasang";
            const docT = a.doc_total || 0;
            const docC = a.doc_checked || 0;
            const docsOk = docT > 0 && docC === docT;
            const lock = rowLocks[a.id];
            const locked = lock && lock.session_id !== currentSessionId;
            const sync = syncStatuses[a.id];
            const isQueued = sync?.status === "queued";
            const isSyncing = sync?.status === "saving";
            const isSynced = sync?.status === "saved";
            const isFailed = sync?.status === "failed";
            const isConflict = sync?.status === "conflict";
            const isBusy = isQueued || isSyncing; // Row not clickable during queue/saving
            // A row is operable (mouse + keyboard) only when editing is allowed
            // and it isn't locked/queued/saving/failed. Conflict rows stay
            // operable (reload-then-edit), matching the onClick guard below.
            const rowClickable = !!onEdit && !locked && !isBusy && !isFailed;

            return (
              <div
                key={a.id}
                onClick={rowClickable ? () => onEdit(a) : undefined}
                {...(rowClickable ? {
                  role: "button",
                  tabIndex: 0,
                  "aria-label": `Edit aset ${a.asset_code || ''}${a.asset_name ? ' - ' + a.asset_name : ''}`.trim(),
                  onKeyDown: (e) => {
                    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onEdit(a); }
                  },
                } : {})}
                className={`absolute left-0 right-0 flex items-center border-b border-border/50 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 ${
                  isConflict ? 'bg-orange-50 dark:bg-orange-900/20 border-l-2 border-l-orange-400 cursor-pointer'
                  : isFailed ? 'bg-rose-50 dark:bg-rose-900/20 border-l-2 border-l-rose-400 cursor-not-allowed opacity-70'
                  : isSyncing ? 'bg-blue-50/50 dark:bg-blue-900/20 border-l-2 border-l-blue-400 cursor-not-allowed opacity-70'
                  : isQueued ? 'bg-amber-50/40 dark:bg-amber-900/10 border-l-2 border-l-amber-300 cursor-not-allowed opacity-60'
                  : isSynced ? 'bg-emerald-50/30 dark:bg-emerald-900/10'
                  : locked ? 'bg-red-50/30 dark:bg-red-900/10 cursor-not-allowed opacity-60'
                  : editId === a.id ? 'bg-amber-50 dark:bg-amber-900/20 border-l-2 border-l-amber-400 cursor-pointer'
                  : onEdit ? 'cursor-pointer hover:bg-accent/10' : ''
                }`}
                style={{ height: ROW_HEIGHT, top: vr.start }}
                title={
                  isConflict ? `Konflik versi: ${sync.error}`
                  : isSyncing ? 'Sedang menyimpan ke server...'
                  : isQueued ? 'Menunggu antrian penyimpanan...'
                  : isFailed ? `Gagal: ${sync.error}`
                  : locked ? `Diedit oleh ${lock.user_name}`
                  : ''
                }
              >
                {/* Sync status indicator */}
                {(isQueued || isSyncing || isSynced || isFailed || isConflict) && (
                  <div className="absolute left-0 top-0 bottom-0 w-6 flex items-center justify-center z-10" onClick={e => e.stopPropagation()}>
                    {isSyncing && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="w-4 h-4 rounded-full bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
                            <Loader2 className="w-2.5 h-2.5 text-blue-500 animate-spin" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="right"><p className="text-xs">Sedang menyimpan ke server...</p></TooltipContent>
                      </Tooltip>
                    )}
                    {isQueued && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="w-4 h-4 rounded-full bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center">
                            <Clock className="w-2.5 h-2.5 text-amber-500" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="right"><p className="text-xs">Menunggu antrian penyimpanan...</p></TooltipContent>
                      </Tooltip>
                    )}
                    {isSynced && <Check className="w-3 h-3 text-emerald-500" />}
                    {isConflict && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="w-4 h-4 rounded-full bg-orange-100 dark:bg-orange-900/40 flex items-center justify-center">
                            <AlertTriangle className="w-2.5 h-2.5 text-orange-600" />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p className="text-xs text-orange-600 font-medium">Konflik versi</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">{sync.error}</p>
                          <p className="text-[10px] text-muted-foreground mt-1">Data sudah dimuat ulang. Silakan edit ulang dan simpan.</p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {isFailed && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            onClick={() => onRetrySync?.(a.id)}
                            className="w-4 h-4 rounded-full bg-rose-100 flex items-center justify-center hover:bg-rose-200 transition-colors"
                          >
                            <RotateCcw className="w-2.5 h-2.5 text-rose-600" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p className="text-xs text-rose-600 font-medium">{sync.error}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5">Klik untuk coba lagi. Auto-unlock dalam 60 detik.</p>
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                )}
                {/* Failed / conflict dismiss button */}
                {(isFailed || isConflict) && (
                  <button
                    onClick={e => { e.stopPropagation(); onDismissSync?.(a.id); }}
                    className="absolute right-1 top-0.5 z-10 text-[8px] text-rose-400 hover:text-rose-600 px-1"
                    title="Abaikan"
                  >
                    &times;
                  </button>
                )}
                {/* Row checkbox */}
                {onToggleSelect && (
                  <div className="w-7 flex-shrink-0 flex justify-center" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedAssets?.has(a.id) || false}
                      onChange={() => onToggleSelect(a.id)}
                      className="w-3 h-3 rounded cursor-pointer accent-blue-600"
                      data-testid={`select-asset-${a.id}`}
                    />
                  </div>
                )}
                {/* Foto */}
                <div className="w-10 flex-shrink-0 flex justify-center relative">
                  {locked && (
                    <div className="absolute -top-0.5 -right-0.5 z-10 bg-red-500 text-white rounded-full w-3 h-3 flex items-center justify-center">
                      <Lock className="w-1.5 h-1.5" />
                    </div>
                  )}
                  <div className="w-8 h-8 rounded overflow-hidden bg-muted flex items-center justify-center">
                    {hasPhoto ? <img src={photo} alt="" className="w-full h-full object-cover" loading="lazy" /> : <Camera className="w-3 h-3 text-muted-foreground" />}
                  </div>
                </div>

                {/* Identitas: Code + NUP + Category */}
                <div className="flex-[2] min-w-0 px-1">
                  <div className="flex items-center gap-1">
                    <span className="font-semibold text-[11px] text-foreground truncate">{a.asset_code}</span>
                    {a.NUP && <span className="text-[8px] bg-muted text-muted-foreground px-1 rounded flex-shrink-0">{a.NUP}</span>}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate leading-tight">{a.category || '-'}</div>
                </div>

                {/* Nama + Merk */}
                <div className="flex-[2] min-w-0 px-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="text-[11px] text-foreground/80 font-medium truncate cursor-default">{a.asset_name}</div>
                    </TooltipTrigger>
                    {a.asset_name && a.asset_name.length > 18 && (
                      <TooltipContent side="bottom" className="max-w-xs"><p className="text-xs">{a.asset_name}</p></TooltipContent>
                    )}
                  </Tooltip>
                  {(a.brand || a.model) && <div className="text-[9px] text-muted-foreground truncate leading-tight">{[a.brand, a.model].filter(Boolean).join(' / ')}</div>}
                </div>

                {/* Eselon I/II - xl (flex-1: matches header, truncates only when needed) */}
                <div className="hidden xl:block flex-1 min-w-0 px-1"><TruncatedCell text={a.eselon1 ? `${a.eselon1}${a.eselon2 ? ' / '+a.eselon2 : ''}` : ''} /></div>
                {/* Lokasi - xl */}
                <div className="hidden xl:block flex-1 min-w-0 px-1"><TruncatedCell text={a.location} /></div>
                {/* Harga - xl */}
                <div className="hidden xl:block w-20 flex-shrink-0 px-1 text-right">
                  <span className="text-[10px] text-muted-foreground font-medium">{formatPrice(a.purchase_price)}</span>
                </div>

                {/* Kondisi */}
                <div className="w-14 flex-shrink-0 flex justify-center">
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none ${
                    a.condition === "Baik" ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400" : a.condition === "Rusak Ringan" ? "bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400" : "bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                  }`}>{a.condition === "Rusak Ringan" ? "R.Ringan" : a.condition === "Rusak Berat" ? "R.Berat" : (a.condition || '-')}</span>
                </div>

                {/* Status — column widened to w-14 + "Maintenance" abbreviated so
                    the larger (legible) font never overflows into INV. */}
                <div className="w-14 flex-shrink-0 flex justify-center">
                  <span title={a.status || ''} className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none ${
                    a.status === "Aktif" ? "bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400" :
                    a.status === "Idle" ? "bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-400" :
                    a.status === "Maintenance" ? "bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400" :
                    "bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400"
                  }`}>{a.status === "Maintenance" ? "Maint." : (a.status || '-')}</span>
                </div>

                {/* Dok - xl */}
                <div className="hidden xl:flex w-9 flex-shrink-0 justify-center">
                  <span className={`text-[10px] font-medium px-1 py-0.5 rounded ${docsOk ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400' : docC > 0 ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400' : 'text-muted-foreground'}`}>
                    {docT > 0 ? `${docC}/${docT}` : '-'}
                  </span>
                </div>
                {/* Stiker - xl */}
                <div className="hidden xl:flex w-10 flex-shrink-0 justify-center">
                  <span className={`text-[10px] font-medium px-1 py-0.5 rounded-full ${stiker ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'}`}>{stiker ? 'Ya' : '-'}</span>
                </div>

                {/* INV — single glyph is cryptic on its own, so expose the full
                    status via title + aria-label (role=img) for a11y/tooltip. */}
                <div className="w-9 flex-shrink-0 flex justify-center">
                  <span
                    role="img"
                    title={a.inventory_status || 'Belum Diinventarisasi'}
                    aria-label={`Status inventarisasi: ${a.inventory_status || 'Belum Diinventarisasi'}`}
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                    a.inventory_status === "Ditemukan" ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400' :
                    a.inventory_status === "Tidak Ditemukan" ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400' :
                    a.inventory_status === "Berlebih" ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400' :
                    a.inventory_status === "Sengketa" ? 'bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-400' :
                    'bg-muted text-muted-foreground'
                  }`}>{a.inventory_status === "Ditemukan" ? '✓' : a.inventory_status === "Tidak Ditemukan" ? '✗' : a.inventory_status === "Berlebih" ? '+' : a.inventory_status === "Sengketa" ? '!' : '-'}</span>
                </div>

                {/* Actions — hit targets bumped to 28px (h-7 w-7). min-h-0/min-w-0
                    keeps the global ≤1023px 44px rule from overinflating them. */}
                <div className="w-[116px] flex-shrink-0 flex items-center justify-end gap-0 pr-0.5" onClick={e => e.stopPropagation()}>
                  <button onClick={() => onPrintCard(a.id)} className="min-h-0 min-w-0 h-7 w-7 flex items-center justify-center rounded hover:bg-blue-50 dark:hover:bg-blue-900/30" title="Cetak" aria-label={`Cetak kartu ${a.asset_code || ''}`.trim()}><CreditCard className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400" /></button>
                  {onOpenKartu && <button onClick={() => onOpenKartu(a)} className="min-h-0 min-w-0 h-7 w-7 flex items-center justify-center rounded hover:bg-emerald-50 dark:hover:bg-emerald-900/30" title="Kartu Inventarisasi" aria-label={`Kartu inventarisasi ${a.asset_code || ''}`.trim()} data-testid={`kartu-inventarisasi-btn-${a.id}`}><BookOpen className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400" /></button>}
                  {onViewAudit && <button onClick={() => onViewAudit(a.id, a.asset_code)} className="min-h-0 min-w-0 h-7 w-7 flex items-center justify-center rounded hover:bg-amber-50 dark:hover:bg-amber-900/30" title="Riwayat" aria-label={`Riwayat ${a.asset_code || ''}`.trim()}><History className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400" /></button>}
                  {onDelete && <button onClick={() => onDelete(a.id)} className="min-h-0 min-w-0 h-7 w-7 flex items-center justify-center rounded hover:bg-red-50 dark:hover:bg-red-900/30" title="Hapus" aria-label={`Hapus ${a.asset_code || ''}`.trim()}><Trash2 className="w-3.5 h-3.5 text-red-500 dark:text-red-400" /></button>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
});

VirtualizedAssetTable.displayName = "VirtualizedAssetTable";

export default VirtualizedAssetTable;
