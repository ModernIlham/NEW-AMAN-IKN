import React, { memo } from "react";
import { Filter, X, Check, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { OptimizedInput } from "../ui/optimized-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";

// Chip filter aktif — kompak & theme-aware. Tombol X memakai min-h-0/min-w-0
// agar tidak digelembungkan aturan tap-target 44px global (≤1023px), dan warna
// punya varian dark: sehingga tak jadi pil putih mencolok di mode gelap.
const BADGE_TONES = {
  blue: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800",
  violet: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-900/30 dark:text-violet-300 dark:border-violet-800",
  amber: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
};
function FilterBadge({ tone = "blue", children, onRemove, testid }) {
  return (
    <span className={`inline-flex items-center gap-1 h-6 pl-2 pr-0.5 rounded-full border text-[10px] font-medium max-w-full ${BADGE_TONES[tone]}`}>
      <span className="truncate">{children}</span>
      <button
        type="button"
        onClick={onRemove}
        data-testid={testid}
        aria-label="Hapus filter"
        className="min-h-0 min-w-0 inline-flex items-center justify-center w-4 h-4 rounded-full flex-shrink-0 hover:bg-black/10 dark:hover:bg-white/15"
      >
        <X className="w-3 h-3" />
      </button>
    </span>
  );
}

// ============================================================================
// ADVANCED FILTER - Controlled component for filter panel + active badges
// Receives all state from parent's useReducer, no internal state.
// ============================================================================
const AdvancedFilter = memo(({
  isOpen,
  onClose,
  filters,           // { condition, status, location, stiker, priceMin, priceMax, nomorSpm, perolehanDari, eselon1, eselon2 }
  filterOptions,     // { conditions, statuses, locations, stiker_statuses, eselon1s, eselon2s }
  onFilterChange,    // (field, value) => void
  onReset,           // () => void
  activeFilterCount,
  filterCategory,
  onCategoryReset,   // () => void
}) => {
  return (
    <>
      {/* Advanced Filter Panel */}
      {isOpen && (
        <div className="border-t pt-2 mt-1 space-y-2" data-testid="advanced-filter-panel">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-2">
            {/* Kondisi */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Kondisi</Label>
              <Select value={filters.condition || "all"} onValueChange={v => onFilterChange("condition", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-condition"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {filterOptions.conditions.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Status */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Status</Label>
              <Select value={filters.status || "all"} onValueChange={v => onFilterChange("status", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-status"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {filterOptions.statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Lokasi */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Lokasi</Label>
              <Select value={filters.location || "all"} onValueChange={v => onFilterChange("location", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-location"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {filterOptions.locations.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Eselon I */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Eselon I</Label>
              <Select value={filters.eselon1 || "all"} onValueChange={v => onFilterChange("eselon1", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-eselon1"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {(filterOptions.eselon1s || []).map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Eselon II */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Eselon II</Label>
              <Select value={filters.eselon2 || "all"} onValueChange={v => onFilterChange("eselon2", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-eselon2"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {(filterOptions.eselon2s || []).map(d => <SelectItem key={d} value={d}>{d}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Stiker */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Stiker</Label>
              <Select value={filters.stiker || "all"} onValueChange={v => onFilterChange("stiker", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-stiker"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  {filterOptions.stiker_statuses.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            
            {/* Inventarisasi */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Inventarisasi</Label>
              <Select value={filters.inventoryStatus || "all"} onValueChange={v => onFilterChange("inventoryStatus", v === "all" ? "" : v)}>
                <SelectTrigger className="h-7 text-xs" data-testid="filter-inventory-status"><SelectValue placeholder="Semua" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Semua</SelectItem>
                  <SelectItem value="Belum Diinventarisasi">Belum Diinventarisasi</SelectItem>
                  <SelectItem value="Ditemukan">Ditemukan</SelectItem>
                  <SelectItem value="Tidak Ditemukan">Tidak Ditemukan</SelectItem>
                  <SelectItem value="Berlebih">Berlebih</SelectItem>
                  <SelectItem value="Sengketa">Sengketa</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Price Range */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Harga (Rp)</Label>
              <div className="flex gap-1">
                <OptimizedInput 
                  type="number" 
                  placeholder="Min" 
                  name="filterPriceMin"
                  value={filters.priceMin} 
                  onChange={e => onFilterChange("priceMin", e.target.value)}
                  className="h-7 text-xs w-1/2"
                  debounceMs={400}
                  data-testid="filter-price-min"
                />
                <OptimizedInput 
                  type="number" 
                  placeholder="Max" 
                  name="filterPriceMax"
                  value={filters.priceMax} 
                  onChange={e => onFilterChange("priceMax", e.target.value)}
                  className="h-7 text-xs w-1/2"
                  debounceMs={400}
                  data-testid="filter-price-max"
                />
              </div>
            </div>
            
            {/* Nomor SPM */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Nomor SPM</Label>
              <OptimizedInput
                type="text"
                placeholder="Cari SPM..."
                name="filterNomorSpm"
                value={filters.nomorSpm || ""}
                onChange={e => onFilterChange("nomorSpm", e.target.value)}
                className="h-7 text-xs"
                debounceMs={400}
                data-testid="filter-nomor-spm"
              />
            </div>
            
            {/* Perolehan Dari */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Perolehan Dari</Label>
              <OptimizedInput
                type="text"
                placeholder="Sumber..."
                name="filterPerolehanDari"
                value={filters.perolehanDari || ""}
                onChange={e => onFilterChange("perolehanDari", e.target.value)}
                className="h-7 text-xs"
                debounceMs={400}
                data-testid="filter-perolehan-dari"
              />
            </div>

            {/* Rentang tanggal input aset */}
            <div className="col-span-2">
              <Label className="text-[10px] text-muted-foreground mb-1 block">Tanggal Input (Dari — Sampai)</Label>
              <div className="flex gap-1">
                <input
                  type="date"
                  value={filters.dateFrom || ""}
                  onChange={e => onFilterChange("dateFrom", e.target.value)}
                  className="h-7 text-xs w-1/2 px-1.5 rounded-md border border-border bg-background text-foreground"
                  data-testid="filter-date-from"
                />
                <input
                  type="date"
                  value={filters.dateTo || ""}
                  onChange={e => onFilterChange("dateTo", e.target.value)}
                  className="h-7 text-xs w-1/2 px-1.5 rounded-md border border-border bg-background text-foreground"
                  data-testid="filter-date-to"
                />
              </div>
            </div>
          </div>
          
          {/* Filter Actions */}
          <div className="flex justify-between items-center pt-1">
            <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={onReset} data-testid="filter-reset-btn">
              <X className="w-3 h-3 mr-1" />Reset Semua
            </Button>
            <div className="flex gap-1.5 items-center">
              <span className="text-[10px] text-muted-foreground">Filter langsung diterapkan</span>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={onClose} data-testid="filter-done-btn">
                <Check className="w-3 h-3 mr-1" />Selesai
              </Button>
            </div>
          </div>
        </div>
      )}
      
      {/* Active Filter Badges */}
      {activeFilterCount > 0 && !isOpen && (
        <div className="flex items-center gap-1.5 flex-wrap pt-2 border-t" data-testid="active-filter-badges">
          <span className="text-[10px] text-muted-foreground flex-shrink-0">Filter aktif:</span>
          {filterCategory !== "Semua" && filterCategory && (
            <FilterBadge onRemove={onCategoryReset} testid="badge-remove-category">Kategori: {filterCategory}</FilterBadge>
          )}
          {filters.condition && (
            <FilterBadge onRemove={() => onFilterChange("condition", "")} testid="badge-remove-condition">Kondisi: {filters.condition}</FilterBadge>
          )}
          {filters.status && (
            <FilterBadge onRemove={() => onFilterChange("status", "")} testid="badge-remove-status">Status: {filters.status}</FilterBadge>
          )}
          {filters.location && (
            <FilterBadge onRemove={() => onFilterChange("location", "")} testid="badge-remove-location">Lokasi: {filters.location}</FilterBadge>
          )}
          {filters.eselon1 && (
            <FilterBadge tone="violet" onRemove={() => onFilterChange("eselon1", "")} testid="badge-remove-eselon1">Es.I: {filters.eselon1}</FilterBadge>
          )}
          {filters.eselon2 && (
            <FilterBadge tone="violet" onRemove={() => onFilterChange("eselon2", "")} testid="badge-remove-eselon2">Es.II: {filters.eselon2}</FilterBadge>
          )}
          {filters.stiker && (
            <FilterBadge onRemove={() => onFilterChange("stiker", "")} testid="badge-remove-stiker">Stiker: {filters.stiker}</FilterBadge>
          )}
          {filters.inventoryStatus && (
            <FilterBadge tone="amber" onRemove={() => onFilterChange("inventoryStatus", "")} testid="badge-remove-inventory">Inventarisasi: {filters.inventoryStatus}</FilterBadge>
          )}
          {(filters.priceMin || filters.priceMax) && (
            <FilterBadge onRemove={() => { onFilterChange("priceMin", ""); onFilterChange("priceMax", ""); }} testid="badge-remove-price">Harga: {filters.priceMin || '0'} - {filters.priceMax || '\u221e'}</FilterBadge>
          )}
          {filters.nomorSpm && (
            <FilterBadge onRemove={() => onFilterChange("nomorSpm", "")} testid="badge-remove-spm">SPM: {filters.nomorSpm}</FilterBadge>
          )}
          {filters.perolehanDari && (
            <FilterBadge onRemove={() => onFilterChange("perolehanDari", "")} testid="badge-remove-perolehan">Perolehan: {filters.perolehanDari}</FilterBadge>
          )}
          {(filters.dateFrom || filters.dateTo) && (
            <FilterBadge onRemove={() => { onFilterChange("dateFrom", ""); onFilterChange("dateTo", ""); }} testid="badge-remove-date">Tanggal: {filters.dateFrom || '…'} – {filters.dateTo || '…'}</FilterBadge>
          )}
          <button
            type="button"
            onClick={onReset}
            className="min-h-0 min-w-0 text-[10px] text-red-500 hover:text-red-700 underline flex-shrink-0 ml-0.5"
            data-testid="badge-clear-all"
          >
            Hapus semua
          </button>
        </div>
      )}
    </>
  );
});

AdvancedFilter.displayName = "AdvancedFilter";

export default AdvancedFilter;
