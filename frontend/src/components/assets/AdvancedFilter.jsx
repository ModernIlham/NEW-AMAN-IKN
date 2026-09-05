import React, { memo } from "react";
import { X, Check } from "lucide-react";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import { OptimizedInput } from "../ui/optimized-input";
import FilterMultiSelect, { ringkasTerpilih } from "./FilterMultiSelect";

// Pilihan tetap status inventarisasi — daftar kuratif (bukan nilai distinct
// dari data) supaya status yang belum pernah dipakai tetap bisa disaring.
const OPSI_INVENTARISASI = [
  "Belum Diinventarisasi", "Ditemukan", "Tidak Ditemukan", "Berlebih", "Sengketa",
];

// Chip filter aktif untuk filter multi-pilih — urutan sama dengan panelnya.
const CHIP_MULTI = [
  { field: "condition", prefix: "Kondisi", testid: "badge-remove-condition" },
  { field: "status", prefix: "Status", testid: "badge-remove-status" },
  { field: "location", prefix: "Lokasi", testid: "badge-remove-location" },
  { field: "eselon1", prefix: "Es.I", tone: "violet", testid: "badge-remove-eselon1" },
  { field: "eselon2", prefix: "Es.II", tone: "violet", testid: "badge-remove-eselon2" },
  { field: "eselon3", prefix: "Es.III", tone: "violet", testid: "badge-remove-eselon3" },
  { field: "eselon4", prefix: "Es.IV", tone: "violet", testid: "badge-remove-eselon4" },
  { field: "eselon5", prefix: "Es.V", tone: "violet", testid: "badge-remove-eselon5" },
  { field: "stiker", prefix: "Stiker", testid: "badge-remove-stiker" },
  { field: "inventoryStatus", prefix: "Inventarisasi", tone: "amber", testid: "badge-remove-inventory" },
];

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
  filterOptions,     // { conditions, statuses, locations, stiker_statuses, eselon1s … eselon5s }
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
          {/* Tujuh filter berbasis pilihan: masing-masing boleh memuat LEBIH
              DARI SATU nilai (mis. Kondisi = Rusak Berat + Rusak Ringan).
              Nilai dalam satu filter berarti ATAU; antar-filter tetap DAN. */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-2">
            {[
              { field: "condition", label: "Kondisi", opsi: filterOptions.conditions, testid: "filter-condition" },
              { field: "status", label: "Status", opsi: filterOptions.statuses, testid: "filter-status" },
              { field: "location", label: "Lokasi", opsi: filterOptions.locations, testid: "filter-location" },
              { field: "eselon1", label: "Eselon I", opsi: filterOptions.eselon1s, testid: "filter-eselon1" },
              { field: "eselon2", label: "Eselon II", opsi: filterOptions.eselon2s, testid: "filter-eselon2" },
              { field: "eselon3", label: "Eselon III", opsi: filterOptions.eselon3s, testid: "filter-eselon3" },
              { field: "eselon4", label: "Eselon IV", opsi: filterOptions.eselon4s, testid: "filter-eselon4" },
              { field: "eselon5", label: "Eselon V", opsi: filterOptions.eselon5s, testid: "filter-eselon5" },
              { field: "stiker", label: "Stiker", opsi: filterOptions.stiker_statuses, testid: "filter-stiker" },
              { field: "inventoryStatus", label: "Inventarisasi", opsi: OPSI_INVENTARISASI, testid: "filter-inventory-status" },
            ].map(f => (
              <div key={f.field}>
                <Label className="text-[10px] text-muted-foreground mb-1 block">{f.label}</Label>
                <FilterMultiSelect
                  label={f.label}
                  opsi={f.opsi || []}
                  terpilih={filters[f.field] || []}
                  onChange={nilai => onFilterChange(f.field, nilai)}
                  testid={f.testid}
                />
              </div>
            ))}

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

            {/* Nama Pengguna aset (field registry: user) */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">Nama Pengguna</Label>
              <OptimizedInput
                type="text"
                placeholder="Nama pemegang..."
                name="filterUser"
                value={filters.user || ""}
                onChange={e => onFilterChange("user", e.target.value)}
                className="h-7 text-xs"
                debounceMs={400}
                data-testid="filter-user"
              />
            </div>

            {/* NIK/NIP pengguna aset (field registry: pengguna_nip) */}
            <div>
              <Label className="text-[10px] text-muted-foreground mb-1 block">NIK/NIP Pengguna</Label>
              <OptimizedInput
                type="text"
                placeholder="NIK/NIP..."
                name="filterPenggunaNip"
                value={filters.penggunaNip || ""}
                onChange={e => onFilterChange("penggunaNip", e.target.value)}
                className="h-7 text-xs"
                debounceMs={400}
                data-testid="filter-pengguna-nip"
              />
            </div>

            {/* Rentang tanggal beli aset (bukan tanggal input) */}
            <div className="col-span-2">
              <Label className="text-[10px] text-muted-foreground mb-1 block">Tanggal Beli (Dari — Sampai)</Label>
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
          {/* Kategori kini boleh lebih dari satu — SATU chip yang menyebut
              seluruh nilainya, sama seperti chip filter multi lainnya. Tombol
              × melepas seluruh filter kategori; melepas satu nilai dilakukan
              di dropdown-nya. */}
          {(filterCategory || []).length > 0 && (
            <FilterBadge onRemove={onCategoryReset} testid="badge-remove-category">
              Kategori: {ringkasTerpilih(filterCategory, "")}
            </FilterBadge>
          )}
          {/* Filter multi-pilih: SATU chip per filter yang menyebut seluruh
              nilainya. Satu chip per NILAI akan meledak jadi belasan pil
              ketika enam lokasi dicentang — barisnya lebih panjang daripada
              daftar asetnya sendiri di layar HP. Tombol × melepas seluruh
              filter itu; melepas satu nilai dilakukan di panelnya. */}
          {CHIP_MULTI.map(({ field, prefix, tone, testid }) => {
            const nilai = filters[field] || [];
            if (!nilai.length) return null;
            return (
              <FilterBadge key={field} tone={tone} onRemove={() => onFilterChange(field, [])} testid={testid}>
                {prefix}: {nilai.join(", ")}
              </FilterBadge>
            );
          })}
          {(filters.priceMin || filters.priceMax) && (
            <FilterBadge onRemove={() => { onFilterChange("priceMin", ""); onFilterChange("priceMax", ""); }} testid="badge-remove-price">Harga: {filters.priceMin || '0'} - {filters.priceMax || '\u221e'}</FilterBadge>
          )}
          {filters.nomorSpm && (
            <FilterBadge onRemove={() => onFilterChange("nomorSpm", "")} testid="badge-remove-spm">SPM: {filters.nomorSpm}</FilterBadge>
          )}
          {filters.perolehanDari && (
            <FilterBadge onRemove={() => onFilterChange("perolehanDari", "")} testid="badge-remove-perolehan">Perolehan: {filters.perolehanDari}</FilterBadge>
          )}
          {filters.user && (
            <FilterBadge tone="violet" onRemove={() => onFilterChange("user", "")} testid="badge-remove-user">Pengguna: {filters.user}</FilterBadge>
          )}
          {filters.penggunaNip && (
            <FilterBadge tone="violet" onRemove={() => onFilterChange("penggunaNip", "")} testid="badge-remove-pengguna-nip">NIK/NIP: {filters.penggunaNip}</FilterBadge>
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
