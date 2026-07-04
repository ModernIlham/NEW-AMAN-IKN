import React, { memo } from "react";
import { CloudOff, LayoutDashboard, ClipboardCheck } from "lucide-react";
import { Switch } from "@/components/ui/switch";

// "04 Jul 14.30" — waktu sinkron terakhir snapshot offline
function formatSyncTime(iso) {
  try {
    return new Date(iso).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "-";
  }
}

/**
 * Saklar segmen Dashboard | Inventarisasi (mobile portrait). Dipakai di dua
 * tempat dengan testid yang sama: berdiri sendiri sebagai kartu di StatsBar
 * (mode dashboard) dan menyatu di kartu header InventoryProgressBar (mode
 * inventarisasi) — hanya satu instans yang dirender pada satu waktu.
 */
export const InventoryModeSwitch = memo(({ inventoryMode, setInventoryMode, className = "" }) => (
  <div className={`grid grid-cols-2 ${className}`} data-testid="stats-mobile-inline">
    <button
      type="button"
      onClick={() => setInventoryMode(false)}
      aria-pressed={!inventoryMode}
      data-testid="inventory-mode-toggle-dashboard"
      className={`min-h-0 min-w-0 flex items-center justify-center gap-1.5 h-8 px-2 rounded-lg text-xs font-semibold transition-colors ${!inventoryMode ? 'bg-blue-600 text-white shadow-sm' : 'text-muted-foreground'}`}
    >
      <LayoutDashboard className="w-4 h-4 flex-shrink-0" /> Dashboard
    </button>
    <button
      type="button"
      onClick={() => setInventoryMode(true)}
      aria-pressed={inventoryMode}
      data-testid="inventory-mode-toggle"
      className={`min-h-0 min-w-0 flex items-center justify-center gap-1.5 h-8 px-2 rounded-lg text-xs font-semibold transition-colors ${inventoryMode ? 'bg-emerald-600 text-white shadow-sm' : 'text-muted-foreground'}`}
    >
      <ClipboardCheck className="w-4 h-4 flex-shrink-0" /> Inventarisasi
    </button>
  </div>
));
InventoryModeSwitch.displayName = "InventoryModeSwitch";

const StatsBar = memo(({ stats, inventoryMode, setInventoryMode, isOnline, pendingCount, snapshotServed, snapshotLastSync }) => (
  <div className="print:hidden">
    {/* Offline Banner — juga tampil saat daftar disajikan dari snapshot
        offline (server tak terjangkau meski browser mengaku online) */}
    {(!isOnline || snapshotServed) && (
      <div className="flex items-center gap-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl px-3 py-2 text-sm text-red-700 dark:text-red-400 mb-2 sm:mb-3" data-testid="offline-banner">
        <CloudOff className="w-4 h-4 flex-shrink-0" />
        <span className="flex-1">
          {snapshotServed
            ? `Mode offline — menampilkan data tersimpan${snapshotLastSync ? ` (terakhir sinkron ${formatSyncTime(snapshotLastSync)})` : ""}. Perubahan akan disinkronkan saat koneksi kembali.`
            : "Mode offline aktif. Perubahan akan disinkronkan saat koneksi kembali."}
        </span>
        {pendingCount > 0 && <span className="bg-red-600 text-white px-2 py-0.5 rounded-full text-xs font-bold">{pendingCount}</span>}
      </div>
    )}

    {/* Large Desktop (lg+): stats grid. Total Nilai gets a wider column
        (1.6fr) because the rupiah figure is far longer than the count cards. */}
    <div className="hidden lg:grid grid-cols-[1fr_1.6fr_1fr_1fr] gap-3">
      {[
        { label: "Total Aset", value: stats.totalAssets.toLocaleString('id-ID'), color: "text-foreground" },
        { label: "Total Nilai", value: `Rp ${stats.totalValue}`, color: "text-blue-600 dark:text-blue-400" },
        { label: "Aktif", value: stats.activeCount.toLocaleString('id-ID'), color: "text-emerald-600 dark:text-emerald-400" },
        { label: "Maintenance", value: stats.maintenanceCount.toLocaleString('id-ID'), color: "text-amber-600 dark:text-amber-400" },
      ].map((s, i) => (
        <div key={i} className="min-w-0 bg-card rounded-xl border border-border p-3.5 shadow-elev-1 hover:shadow-elev-2 transition-shadow duration-180" data-testid={`stat-card-${i}`}>
          <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">{s.label}</div>
          <div className={`text-2xl font-bold ${s.color} mt-1`}>{s.value}</div>
        </div>
      ))}
    </div>

    {/* Tablet / Phone Landscape (sm to lg): Compact stats + inline toggle.
        items-stretch so the toggle card matches the stat cards' height. */}
    <div className="hidden sm:flex lg:hidden items-stretch gap-2">
      {[
        { label: "Total Aset", value: stats.totalAssets.toLocaleString('id-ID'), color: "text-foreground" },
        { label: "Total Nilai", value: `Rp ${stats.totalValue}`, color: "text-blue-600 dark:text-blue-400" },
        { label: "Aktif", value: stats.activeCount.toLocaleString('id-ID'), color: "text-emerald-600 dark:text-emerald-400" },
        { label: "Maintenance", value: stats.maintenanceCount.toLocaleString('id-ID'), color: "text-amber-600 dark:text-amber-400" },
      ].map((s, i) => (
        <div key={i} className={`${i === 1 ? 'flex-[1.7]' : 'flex-1'} min-w-0 bg-card rounded-xl border border-border px-2.5 py-2 shadow-elev-1`} data-testid={`stat-card-compact-${i}`}>
          <div className="text-[9px] text-muted-foreground font-medium uppercase tracking-wider leading-tight">{s.label}</div>
          <div className={`text-base font-bold ${s.color} mt-0.5 truncate`}>{s.value}</div>
        </div>
      ))}
      <div className="flex-shrink-0 bg-card rounded-xl border border-border px-3 flex items-center justify-center shadow-elev-1" title="Mode Inventarisasi" data-testid="inventory-mode-toggle-tablet-wrapper">
        <Switch checked={inventoryMode} onCheckedChange={setInventoryMode} aria-label="Mode Inventarisasi" className="min-h-0 min-w-0" data-testid="inventory-mode-toggle-tablet" />
      </div>
    </div>

    {/* Mobile Portrait (< sm): kartu saklar mode full-width. Saat mode
        inventarisasi aktif, saklar pindah ke kartu header gabungan di
        InventoryProgressBar — kartu ini tidak dirender agar tidak ganda. */}
    {!inventoryMode && (
      <InventoryModeSwitch
        inventoryMode={inventoryMode}
        setInventoryMode={setInventoryMode}
        className="sm:hidden p-1 gap-1 rounded-xl border border-border bg-card shadow-sm"
      />
    )}
  </div>
));

StatsBar.displayName = "StatsBar";
export default StatsBar;
