import React, { memo, useState, useEffect } from "react";
import { CloudOff, Users, Loader2, HardDriveDownload } from "lucide-react";
import axios from "axios";
import { InventoryModeSwitch } from "./StatsBar";

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
 * Header mode inventarisasi lapangan: progres X/Y dari endpoint rekapitulasi,
 * chip filter cepat, indikator offline/antrian/rekan, dan status penyiapan
 * data offline (snapshotState dari DashboardPage).
 *
 * Mobile (<sm): SATU kartu gabungan — saklar Dashboard|Inventarisasi + persen,
 * bar progres tipis + status offline ringkas, lalu chip segmen kecil.
 * Tablet/desktop (sm+): satu baris ramping (saklar mode tetap di StatsBar).
 */
const InventoryProgressBar = memo(({ activityId, inventoryStatusFilter, onFilterChange, isOnline, pendingCount, rowLocks, sessionId, refreshKey, snapshotState, inventoryMode, setInventoryMode }) => {
  const [rekap, setRekap] = useState(null);

  // Refetch saat activity berubah, saat refreshKey di-bump (save selesai),
  // dan tiap 60 detik (rekan kerja lain juga mengubah progres).
  useEffect(() => {
    if (!activityId) return;
    let cancelled = false;
    // Offline / fetch gagal: tampilkan angka terakhir yang diketahui dari
    // cache lokal alih-alih 0/0 — progres bersifat indikatif, tanpa toast error.
    try {
      const cached = JSON.parse(localStorage.getItem(`aman_rekap_${activityId}`) || "null");
      if (cached) setRekap(prev => prev || cached);
    } catch { /* cache rusak — abaikan */ }
    const fetchRekap = async () => {
      try {
        const r = await axios.get(`${API}/inventory-activities/${activityId}/rekapitulasi`);
        if (!cancelled) {
          setRekap(r.data);
          // Simpan hanya dua angka yang dipakai bar ini — hemat localStorage
          try {
            localStorage.setItem(`aman_rekap_${activityId}`, JSON.stringify({
              total_bmn_diteliti: r.data?.total_bmn_diteliti || 0,
              belum_diinventarisasi: { count: r.data?.belum_diinventarisasi?.count || 0 },
            }));
          } catch { /* kuota penuh — abaikan */ }
        }
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

  // Kalimat lengkap status snapshot — dipakai sebagai title (tooltip) pada
  // varian ringkas agar informasinya tidak hilang.
  const snapshotReadyTitle = snapshotState?.phase === "ready"
    ? `Data offline siap — ${(snapshotState.count ?? 0).toLocaleString('id-ID')} aset, terakhir sinkron ${formatSyncTime(snapshotState.lastSync)}. Daftar aset dapat dibuka tanpa koneksi internet.`
    : "";

  // Indikator ringkas offline / antrian sinkron / rekan — dipakai kedua varian
  const hasStatus = !!snapshotState?.phase || !isOnline || pendingCount > 0 || peerCount > 0;
  const statusIcons = (suffix) => (
    <>
      {snapshotState?.phase === "syncing" && (
        <span className="flex items-center gap-1 text-[10px] font-medium text-blue-600 dark:text-blue-400 whitespace-nowrap" title={`Menyiapkan data offline… ${snapshotState.pct ?? 0}%`} data-testid={`snapshot-progress${suffix}`}>
          <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
          {snapshotState.pct ?? 0}%
        </span>
      )}
      {snapshotState?.phase === "ready" && (
        <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 whitespace-nowrap" title={snapshotReadyTitle} data-testid={`snapshot-ready${suffix}`}>
          <HardDriveDownload className="w-3 h-3 flex-shrink-0" />
          {(snapshotState.count ?? 0).toLocaleString('id-ID')} aset
        </span>
      )}
      {!isOnline && (
        <span className="flex items-center" title="Sedang offline — perubahan disinkronkan saat koneksi kembali" data-testid={`inventory-offline-icon${suffix}`}>
          <CloudOff className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
        </span>
      )}
      {pendingCount > 0 && (
        <span className="flex items-center gap-1 text-[10px] font-medium text-amber-600 dark:text-amber-400 whitespace-nowrap" title={`${pendingCount} perubahan menunggu sinkron`}>
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          {pendingCount} sinkron
        </span>
      )}
      {peerCount > 0 && (
        <span className="flex items-center gap-1 text-[10px] font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full whitespace-nowrap" title={`${peerCount} aset sedang dikerjakan rekan`} data-testid={`inventory-peer-badge${suffix}`}>
          <Users className="w-3 h-3" />
          {peerCount}
        </span>
      )}
    </>
  );

  return (
    <div className="print:hidden" data-testid="inventory-progress-bar">
      {/* ===== Mobile (<sm): kartu header gabungan ===== */}
      <div className="sm:hidden bg-card rounded-xl border border-border shadow-sm p-2 space-y-1.5">
        {/* Baris 1: saklar mode + persentase */}
        <div className="flex items-center gap-2">
          <InventoryModeSwitch
            inventoryMode={inventoryMode}
            setInventoryMode={setInventoryMode}
            className="flex-1 min-w-0 gap-0.5 p-0.5 rounded-lg bg-muted"
          />
          <span className="text-base font-bold text-emerald-600 dark:text-emerald-400 tabular-nums flex-shrink-0 pr-0.5" data-testid="inventory-progress-pct">{pct}%</span>
        </div>

        {/* Baris 2: bar progres tipis + teks progres kiri / status offline kanan */}
        <div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-1 flex items-center justify-between gap-2">
            <span className="text-[10px] text-muted-foreground truncate">
              {done.toLocaleString('id-ID')}/{total.toLocaleString('id-ID')} diinventarisasi
            </span>
            {hasStatus && (
              <span className="flex items-center gap-1.5 flex-shrink-0">
                {statusIcons("")}
              </span>
            )}
          </div>
        </div>

        {/* Baris 3: chip filter cepat — pil segmen kecil */}
        <div className="grid grid-cols-3 gap-0.5 p-0.5 rounded-lg bg-muted" data-testid="inventory-quick-chips">
          {QUICK_CHIPS.map(c => {
            const active = (inventoryStatusFilter || "") === c.value;
            return (
              <button
                key={c.label}
                type="button"
                onClick={() => onFilterChange("inventoryStatus", c.value)}
                aria-pressed={active}
                className={`min-h-0 min-w-0 h-7 rounded-md text-[11px] font-semibold transition-colors ${
                  active ? "bg-blue-600 text-white shadow-sm" : "text-muted-foreground"
                }`}
                data-testid={`inventory-chip-${c.label.toLowerCase()}`}
              >
                {c.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ===== Tablet/Desktop (sm+): satu baris ramping ===== */}
      <div className="hidden sm:flex items-center gap-3 bg-card rounded-xl border border-border shadow-sm px-3 py-1.5 overflow-hidden">
        <span className="text-[11px] font-medium text-foreground whitespace-nowrap">
          Diinventarisasi {done.toLocaleString('id-ID')} / {total.toLocaleString('id-ID')}
        </span>
        <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden min-w-[40px]">
          <div className="h-full bg-emerald-500 rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">{pct}%</span>

        <div className="flex items-center gap-1 flex-shrink-0" data-testid="inventory-quick-chips-lg">
          {QUICK_CHIPS.map(c => {
            const active = (inventoryStatusFilter || "") === c.value;
            return (
              <button
                key={c.label}
                type="button"
                onClick={() => onFilterChange("inventoryStatus", c.value)}
                aria-pressed={active}
                className={`min-h-0 min-w-0 h-6 px-2.5 rounded-full text-[10px] font-semibold border transition-colors ${
                  active ? "bg-blue-600 border-blue-600 text-white" : "bg-card border-border text-muted-foreground hover:text-foreground hover:border-blue-300"
                }`}
                data-testid={`inventory-chip-${c.label.toLowerCase()}-lg`}
              >
                {c.label}
              </button>
            );
          })}
        </div>

        {hasStatus && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {statusIcons("-lg")}
          </div>
        )}
      </div>
    </div>
  );
});

InventoryProgressBar.displayName = "InventoryProgressBar";
export default InventoryProgressBar;
