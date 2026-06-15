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
        <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t" data-testid="active-filter-badges">
          <span className="text-[10px] text-muted-foreground">Filter aktif:</span>
          {filterCategory !== "Semua" && filterCategory && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Kategori: {filterCategory}
              <button onClick={onCategoryReset} data-testid="badge-remove-category"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.condition && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Kondisi: {filters.condition}
              <button onClick={() => onFilterChange("condition", "")} data-testid="badge-remove-condition"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.status && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Status: {filters.status}
              <button onClick={() => onFilterChange("status", "")} data-testid="badge-remove-status"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.location && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Lokasi: {filters.location}
              <button onClick={() => onFilterChange("location", "")} data-testid="badge-remove-location"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.eselon1 && (
            <span className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 text-[10px] px-2 py-0.5 rounded-full">
              Es.I: {filters.eselon1}
              <button onClick={() => onFilterChange("eselon1", "")} data-testid="badge-remove-eselon1"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.eselon2 && (
            <span className="inline-flex items-center gap-1 bg-violet-100 text-violet-700 text-[10px] px-2 py-0.5 rounded-full">
              Es.II: {filters.eselon2}
              <button onClick={() => onFilterChange("eselon2", "")} data-testid="badge-remove-eselon2"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.stiker && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Stiker: {filters.stiker}
              <button onClick={() => onFilterChange("stiker", "")} data-testid="badge-remove-stiker"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.inventoryStatus && (
            <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-700 text-[10px] px-2 py-0.5 rounded-full">
              Inventarisasi: {filters.inventoryStatus}
              <button onClick={() => onFilterChange("inventoryStatus", "")} data-testid="badge-remove-inventory"><X className="w-3 h-3" /></button>
            </span>
          )}
          {(filters.priceMin || filters.priceMax) && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Harga: {filters.priceMin || '0'} - {filters.priceMax || '\u221e'}
              <button onClick={() => { onFilterChange("priceMin", ""); onFilterChange("priceMax", ""); }} data-testid="badge-remove-price"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.nomorSpm && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              SPM: {filters.nomorSpm}
              <button onClick={() => onFilterChange("nomorSpm", "")} data-testid="badge-remove-spm"><X className="w-3 h-3" /></button>
            </span>
          )}
          {filters.perolehanDari && (
            <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 text-[10px] px-2 py-0.5 rounded-full">
              Perolehan: {filters.perolehanDari}
              <button onClick={() => onFilterChange("perolehanDari", "")} data-testid="badge-remove-perolehan"><X className="w-3 h-3" /></button>
            </span>
          )}
          <button 
            onClick={onReset}
            className="text-[10px] text-red-500 hover:text-red-700 underline"
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
