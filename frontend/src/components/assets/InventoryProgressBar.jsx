import React, { memo, useState, useEffect } from "react";
import { CloudOff, Users, Loader2, HardDriveDownload } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// "04 Jul 14.30" — waktu sinkron terakhir snapshot offline
function formatSyncTime(iso) {
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "-";
  }
}

// Chip filter cepat — memakai path filter yang sama dengan AdvancedFilter
// (handleAdvancedFilterChange) sehingga refetch + skeleton existing ikut jalan.
const QUICK_CHIPS = [
  { label: "Belum", value: "Belum Diinventarisasi" },
  { label: "Ditemukan", value: "Ditemukan" },
  { label: "Semua", value: "" },
];

/**
 * Bar progres mode inventarisasi lapangan: progres X/Y dari endpoint
 * rekapitulasi, chip filter cepat, indikator offline/antrian/rekan, dan
 * status penyiapan data offline (snapshotState dari DashboardPage).
 * Dirender DashboardPage tepat di bawah StatsBar saat inventoryMode aktif.
 */
const InventoryProgressBar = memo(({ activityId, inventoryStatusFilter, onFilterChange, isOnline, pendingCount, rowLocks, sessionId, refreshKey, snapshotState }) => {
  const [rekap, setRekap] = useState(null);

  // Refetch saat activity berubah, saat refreshKey di-bump (save selesai),
  // dan tiap 60 detik (rekan kerja lain juga mengubah progres).
  useEffect(() => {
    if (!activityId) return;
    let cancelled = false;
    const fetchRekap = async () => {
      try {
        const r = await axios.get(`${API}/inventory-activities/${activityId}/rekapitulasi`);
        if (!cancelled) setRekap(r.data);
      } catch { /* progres bersifat pelengkap — abaikan kegagalan */ }
    };
    fetchRekap();
    const t = setInterval(fetchRekap, 60000);
    return () => { cancelled = true; clearInterval(t); };
  }, [activityId, refreshKey]);

  const total = rekap?.total_bmn_diteliti || 0;
  const belum = rekap?.belum_diinventarisasi?.count || 0;
  const done = Math.max(0, total - belum);
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const peerCount = Object.values(rowLocks || {}).filter(l => l && l.session_id !== sessionId).length;

  return (
    <div className="bg-card rounded-lg border border-border px-3 py-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 print:hidden" data-testid="inventory-progress-bar">
      {/* Progres */}
      <div className="flex items-center gap-2 flex-1 min-w-[160px]">
        <span className="text-[11px] font-medium text-foreground whitespace-nowrap">
          Diinventarisasi {done.toLocaleString('id-ID')} / {total.toLocaleString('id-ID')}
        </span>
        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden min-w-[40px]">
          <div className="h-full bg-emerald-500 rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400">{pct}%</span>
      </div>

      {/* Chip filter cepat */}
      <div className="flex items-center gap-1" data-testid="inventory-quick-chips">
        {QUICK_CHIPS.map(c => {
          const active = (inventoryStatusFilter || "") === c.value;
          return (
            <button
              key={c.label}
              type="button"
              onClick={() => onFilterChange("inventoryStatus", c.value)}
              className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border transition-colors ${
                active ? "bg-blue-600 border-blue-600 text-white" : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-blue-300"
              }`}
              data-testid={`inventory-chip-${c.label.toLowerCase()}`}
            >
              {c.label}
            </button>
          );
        })}
      </div>

      {/* Status data offline (read cache) — ringkas & non-blocking */}
      {snapshotState?.phase === "syncing" && (
        <span className="flex items-center gap-1 text-[10px] font-medium text-blue-600 dark:text-blue-400 whitespace-nowrap" data-testid="snapshot-progress">
          <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
          Menyiapkan data offline… {snapshotState.pct ?? 0}%
        </span>
      )}
      {snapshotState?.phase === "ready" && (
        <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 whitespace-nowrap" data-testid="snapshot-ready" title="Daftar aset dapat dibuka tanpa koneksi internet">
          <HardDriveDownload className="w-3 h-3 flex-shrink-0" />
          Data offline siap · {(snapshotState.count ?? 0).toLocaleString('id-ID')} aset · terakhir {formatSyncTime(snapshotState.lastSync)}
        </span>
      )}

      {/* Indikator offline / antrian sinkron / rekan */}
      {(!isOnline || pendingCount > 0 || peerCount > 0) && (
        <div className="flex items-center gap-2 ml-auto">
          {!isOnline && <CloudOff className="w-3.5 h-3.5 text-red-500 flex-shrink-0" data-testid="inventory-offline-icon" />}
          {pendingCount > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-medium text-amber-600 dark:text-amber-400 whitespace-nowrap">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              {pendingCount} menunggu sinkron
            </span>
          )}
          {peerCount > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full whitespace-nowrap" data-testid="inventory-peer-badge">
              <Users className="w-3 h-3" />
              {peerCount} dikerjakan rekan
            </span>
          )}
        </div>
      )}
    </div>
  );
});

InventoryProgressBar.displayName = "InventoryProgressBar";
export default InventoryProgressBar;
