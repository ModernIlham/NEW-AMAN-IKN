import React, { memo } from "react";
import { CloudOff } from "lucide-react";
import { Switch } from "@/components/ui/switch";

const StatsBar = memo(({ stats, inventoryMode, setInventoryMode, isOnline, pendingCount }) => (
  <div className="print:hidden">
    {/* Offline Banner */}
    {!isOnline && (
      <div className="flex items-center gap-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2 text-sm text-red-700 dark:text-red-400 mb-3" data-testid="offline-banner">
        <CloudOff className="w-4 h-4 flex-shrink-0" />
        <span className="flex-1">Mode offline aktif. Perubahan akan disinkronkan saat koneksi kembali.</span>
        {pendingCount > 0 && <span className="bg-red-600 text-white px-2 py-0.5 rounded-full text-xs font-bold">{pendingCount}</span>}
      </div>
    )}

    {/* Large Desktop (lg+): Full 4-column stats + toggle in header */}
    <div className="hidden lg:grid grid-cols-4 gap-3">
      {[
        { label: "Total Aset", value: stats.totalAssets.toLocaleString('id-ID'), color: "text-foreground" },
        { label: "Total Nilai", value: `Rp ${stats.totalValue}`, color: "text-blue-600 dark:text-blue-400" },
        { label: "Aktif", value: stats.activeCount.toLocaleString('id-ID'), color: "text-emerald-600 dark:text-emerald-400" },
        { label: "Maintenance", value: stats.maintenanceCount.toLocaleString('id-ID'), color: "text-amber-600 dark:text-amber-400" },
      ].map((s, i) => (
        <div key={i} className="bg-card rounded-xl border border-border p-3.5 shadow-elev-1 hover:shadow-elev-2 transition-shadow duration-180" data-testid={`stat-card-${i}`}>
          <div className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">{s.label}</div>
          <div className={`text-2xl font-bold ${s.color} mt-1`}>{s.value}</div>
        </div>
      ))}
    </div>

    {/* Tablet / Phone Landscape (sm to lg): Compact stats + inline toggle */}
    <div className="hidden sm:flex lg:hidden items-center gap-2">
      {[
        { label: "Total Aset", value: stats.totalAssets.toLocaleString('id-ID'), color: "text-foreground" },
        { label: "Total Nilai", value: `Rp ${stats.totalValue}`, color: "text-blue-600 dark:text-blue-400" },
        { label: "Aktif", value: stats.activeCount.toLocaleString('id-ID'), color: "text-emerald-600 dark:text-emerald-400" },
        { label: "Maintenance", value: stats.maintenanceCount.toLocaleString('id-ID'), color: "text-amber-600 dark:text-amber-400" },
      ].map((s, i) => (
        <div key={i} className="flex-1 bg-card rounded-xl border border-border px-2.5 py-2 shadow-elev-1" data-testid={`stat-card-compact-${i}`}>
          <div className="text-[9px] text-muted-foreground font-medium uppercase tracking-wider leading-tight">{s.label}</div>
          <div className={`text-base font-bold ${s.color} mt-0.5`}>{s.value}</div>
        </div>
      ))}
      <div className="flex-shrink-0 bg-card rounded-xl border border-border px-2.5 py-2 flex items-center gap-1.5 shadow-elev-1" data-testid="inventory-mode-toggle-tablet-wrapper">
        <span className="text-[9px] text-muted-foreground font-medium uppercase tracking-wider leading-tight whitespace-nowrap">Inventarisasi</span>
        <Switch checked={inventoryMode} onCheckedChange={setInventoryMode} className="scale-75" data-testid="inventory-mode-toggle-tablet" />
      </div>
    </div>

    {/* Mobile Portrait (< sm): Compact inline stats */}
    <div className="sm:hidden flex items-center gap-2.5 bg-card rounded-xl border border-border px-3 py-2 text-xs overflow-x-auto shadow-elev-1" data-testid="stats-mobile-inline">
      <span className="font-bold text-foreground whitespace-nowrap">{stats.totalAssets.toLocaleString('id-ID')} aset</span>
      <span className="text-border">|</span>
      <span className="font-bold text-blue-600 dark:text-blue-400 whitespace-nowrap">Rp {stats.totalValue}</span>
      <span className="text-border">|</span>
      <span className="text-emerald-600 dark:text-emerald-400 whitespace-nowrap">{stats.activeCount} aktif</span>
      <div className="ml-auto flex items-center gap-2 flex-shrink-0 pl-2.5 border-l border-border">
        <span className="text-[10px] text-muted-foreground whitespace-nowrap">{inventoryMode ? 'Inventarisasi' : 'Dashboard'}</span>
        <Switch checked={inventoryMode} onCheckedChange={setInventoryMode} className="scale-75" data-testid="inventory-mode-toggle" />
      </div>
    </div>
  </div>
));

StatsBar.displayName = "StatsBar";
export default StatsBar;
