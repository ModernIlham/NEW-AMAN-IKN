import React, { memo } from "react";
import {
  Search, Filter, Download, Upload, Settings,
  Loader2, Trash2, Eye, FileText, FileSpreadsheet, CreditCard,
  List, LayoutGrid, ShieldCheck, Lock, CheckCircle2, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { CategorySelect, TinifyQuotaIndicator, TinifyQuotaMobile, AdvancedFilter } from "@/components/assets";
import QrScanButton from "@/components/assets/QrScanButton";

// Pill Pengesahan — entry point finalisasi kegiatan langsung dari dashboard.
// State: (1) disahkan → badge terkunci "Disahkan · {tiket}", (2) siap disahkan →
// hijau, (3) ada syarat belum → amber "{n} syarat belum". Admin only.
function PengesahanPill({ pengesahan, sealed, ticket, onOpen, compact }) {
  if (!pengesahan) return null; // status belum termuat / non-admin
  const disahkan = sealed || pengesahan.disahkan;

  if (disahkan) {
    return (
      <span
        className="inline-flex items-center gap-1 h-8 px-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-400 text-xs font-medium flex-shrink-0 whitespace-nowrap"
        title={ticket ? `Kegiatan telah disahkan (tiket ${ticket}) — data terkunci` : "Kegiatan telah disahkan — data terkunci"}
        data-testid="pengesahan-sealed-badge"
      >
        <Lock className="w-3.5 h-3.5" />
        <span>Disahkan{ticket && !compact ? ` · ${ticket}` : ""}</span>
      </span>
    );
  }

  const eligible = pengesahan.eligible;
  const tone = eligible
    ? "border-emerald-300 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-700 dark:text-emerald-400 dark:hover:bg-emerald-900/30"
    : "border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-900/30";
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onOpen}
      className={`h-8 min-h-0 text-xs gap-1.5 flex-shrink-0 ${tone}`}
      title={eligible ? "Kegiatan siap disahkan" : `${pengesahan.blockerCount} syarat pengesahan belum terpenuhi`}
      data-testid="pengesahan-pill"
    >
      <ShieldCheck className="w-3.5 h-3.5" />
      {!compact && <span className="whitespace-nowrap">Pengesahan</span>}
      {eligible ? (
        <span className="inline-flex items-center gap-0.5 whitespace-nowrap">
          <CheckCircle2 className="w-3 h-3" />{!compact && " Siap disahkan"}
        </span>
      ) : (
        <span className="inline-flex items-center gap-0.5 whitespace-nowrap">
          <AlertTriangle className="w-3 h-3" />{compact ? pengesahan.blockerCount : ` ${pengesahan.blockerCount} syarat belum`}
        </span>
      )}
    </Button>
  );
}

const DashboardToolbar = memo(function DashboardToolbar({
  searchInput, setSearchInput,
  categories, filterCategory, setFilterCategory,
  activeFilterCount, showAdvancedFilter, setShowAdvancedFilter,
  sortBy, setSortBy,
  exporting, handleExport, handleExportExecutivePDF, handlePreviewExecutive,
  perms, openDialog,
  handlePrintBulkCards, assetsCount,
  filters, filterOptions, handleAdvancedFilterChange,
  resetAdvancedFilters, handleCategoryReset,
  refreshData,
  viewMode, setViewMode,
  showPengesahan, pengesahan, sealed, pengesahanTicket, onOpenPengesahan,
}) {
  return (
    <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-2.5 print:hidden" data-testid="dashboard-toolbar">
      <div className="flex flex-col gap-1.5 sm:gap-2">
        {/* Baris 1: Cari + Scan QR stiker (+ Filter Lanjutan di mobile/tablet) */}
        <div className="flex items-center gap-1.5">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
            <Input
              placeholder="Cari kode, nama, lokasi..."
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              className="pl-8 h-9 lg:h-8 text-sm"
              data-testid="search-input"
            />
          </div>
          <QrScanButton onDetected={setSearchInput} />
          <Button
            variant={activeFilterCount > 0 ? "default" : "outline"}
            size="sm"
            className={`lg:hidden h-9 w-9 p-0 min-h-0 min-w-0 relative flex-shrink-0 ${activeFilterCount > 0 ? "bg-blue-600" : ""}`}
            onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
            aria-label="Filter lanjutan"
            data-testid="mobile-advanced-filter-btn"
          >
            <Filter className="w-4 h-4" />
            {activeFilterCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-white text-blue-600 rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-bold border border-blue-600">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </div>

        {/* Desktop toolbar (lg+ only) */}
        <div className="hidden lg:flex gap-1.5 flex-wrap items-center">
          <CategorySelect
            categories={categories}
            value={filterCategory}
            onValueChange={v => { setFilterCategory(v); refreshData(1); }}
            placeholder="Semua Kategori"
            className="w-40"
          />

          <Button
            variant={activeFilterCount > 0 ? "default" : "outline"}
            size="sm"
            className={`h-8 text-xs ${activeFilterCount > 0 ? "bg-blue-600" : ""}`}
            onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
            data-testid="advanced-filter-btn"
          >
            <Filter className="w-3 h-3 mr-1" />
            Filter Lanjutan
            {activeFilterCount > 0 && (
              <span className="ml-1.5 bg-white text-blue-600 rounded-full w-4 h-4 flex items-center justify-center text-[10px] font-bold">
                {activeFilterCount}
              </span>
            )}
          </Button>

          <Select value={sortBy} onValueChange={v => { setSortBy(v); refreshData(1); }}>
            <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Terbaru</SelectItem>
              <SelectItem value="oldest">Terlama</SelectItem>
              <SelectItem value="name_asc">Nama A-Z</SelectItem>
              <SelectItem value="name_desc">Nama Z-A</SelectItem>
              <SelectItem value="price_asc">Harga Terendah</SelectItem>
              <SelectItem value="price_desc">Harga Tertinggi</SelectItem>
              <SelectItem value="category_asc">Kategori A-Z</SelectItem>
              <SelectItem value="location_asc">Lokasi A-Z</SelectItem>
              <SelectItem value="eselon1_asc">Eselon I A-Z</SelectItem>
            </SelectContent>
          </Select>

          {/* View Mode Toggle */}
          {viewMode !== undefined && setViewMode && (
            <div className="flex bg-muted rounded-lg p-0.5 gap-0.5" data-testid="view-mode-toggle">
              <button
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'list' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                onClick={() => setViewMode('list')}
                data-testid="view-mode-list"
              >
                <List className="w-3.5 h-3.5" /> List
              </button>
              <button
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'gallery' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                onClick={() => setViewMode('gallery')}
                data-testid="view-mode-gallery"
              >
                <LayoutGrid className="w-3.5 h-3.5" /> Galeri
              </button>
            </div>
          )}

          <div className="flex-1"></div>

          {showPengesahan && (
            <PengesahanPill
              pengesahan={pengesahan}
              sealed={sealed}
              ticket={pengesahanTicket}
              onOpen={onOpenPengesahan}
            />
          )}

          <TinifyQuotaIndicator />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={exporting} className="h-8 text-xs">
                {exporting ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Download className="w-3 h-3 mr-1" />}Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={() => handleExport('csv')} data-testid="export-csv-btn"><FileText className="w-4 h-4 mr-2" />CSV</DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('xlsx')} data-testid="export-xlsx-btn"><FileSpreadsheet className="w-4 h-4 mr-2" />Excel</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleExportExecutivePDF} data-testid="export-executive-pdf">
                <Download className="w-4 h-4 mr-2" />Laporan Eksekutif (PDF)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePreviewExecutive} data-testid="preview-executive-html">
                <Eye className="w-4 h-4 mr-2" />Preview Laporan Eksekutif
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {perms.canImport && (
            <Button variant="outline" size="sm" className="h-8 text-xs" onClick={() => openDialog('import')}>
              <Upload className="w-3 h-3 mr-1" />Import
            </Button>
          )}
          {perms.canBulkDelete && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 border-red-200 hover:border-red-300"
              onClick={() => openDialog('bulkDelete')}
              disabled={assetsCount === 0}
            >
              <Trash2 className="w-3 h-3 mr-1" />Hapus Semua
            </Button>
          )}
          <Button variant="outline" size="sm" className="h-8 text-xs" onClick={handlePrintBulkCards} disabled={assetsCount === 0}>
            <CreditCard className="w-3 h-3 mr-1" />Cetak Kartu ({assetsCount})
          </Button>
        </div>

        {/* Mobile/Tablet toolbar — satu baris kontrol ringkas (semua h-9) */}
        <div className="lg:hidden flex items-center gap-1.5">
          <CategorySelect
            categories={categories}
            value={filterCategory}
            onValueChange={v => { setFilterCategory(v); refreshData(1); }}
            placeholder="Kategori"
            className="flex-1 min-w-0 h-9 min-h-0"
            size="compact"
          />

          <Select value={sortBy} onValueChange={v => { setSortBy(v); refreshData(1); }}>
            <SelectTrigger className="w-auto h-9 min-h-0 px-2 text-[11px] gap-1 flex-shrink-0" aria-label="Urutkan" data-testid="mobile-sort-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="newest">Terbaru</SelectItem>
              <SelectItem value="oldest">Terlama</SelectItem>
              <SelectItem value="name_asc">A-Z</SelectItem>
              <SelectItem value="name_desc">Z-A</SelectItem>
              <SelectItem value="price_asc">Harga ↑</SelectItem>
              <SelectItem value="price_desc">Harga ↓</SelectItem>
            </SelectContent>
          </Select>

          <TinifyQuotaMobile className="flex-shrink-0" />

          {showPengesahan && (
            <PengesahanPill
              pengesahan={pengesahan}
              sealed={sealed}
              ticket={pengesahanTicket}
              onOpen={onOpenPengesahan}
              compact
            />
          )}

          {/* Mobile View Toggle */}
          {viewMode !== undefined && setViewMode && (
            <div className="flex bg-muted rounded-lg p-0.5 gap-0.5 flex-shrink-0" data-testid="view-mode-toggle-mobile">
              <button
                className={`min-h-0 min-w-0 h-8 w-8 flex items-center justify-center rounded-md transition-colors ${viewMode === 'list' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground'}`}
                onClick={() => setViewMode('list')}
                aria-label="Tampilan daftar"
                aria-pressed={viewMode === 'list'}
              >
                <List className="w-4 h-4" />
              </button>
              <button
                className={`min-h-0 min-w-0 h-8 w-8 flex items-center justify-center rounded-md transition-colors ${viewMode === 'gallery' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground'}`}
                onClick={() => setViewMode('gallery')}
                aria-label="Tampilan galeri"
                aria-pressed={viewMode === 'gallery'}
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Mobile actions dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-9 w-9 p-0 min-h-0 min-w-0 flex-shrink-0" aria-label="Menu aksi lainnya">
                <Settings className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem onClick={() => handleExport('xlsx')} disabled={exporting} data-testid="mobile-export-xlsx-btn">
                <FileSpreadsheet className="w-4 h-4 mr-2" />Export Excel
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('csv')} disabled={exporting} data-testid="mobile-export-csv-btn">
                <FileText className="w-4 h-4 mr-2" />Export CSV
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleExportExecutivePDF} disabled={exporting} data-testid="mobile-export-executive-pdf">
                <Download className="w-4 h-4 mr-2" />Lap. Eksekutif PDF
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePreviewExecutive} data-testid="mobile-preview-executive-html">
                <Eye className="w-4 h-4 mr-2" />Preview Eksekutif
              </DropdownMenuItem>
              {perms.canImport && (
                <DropdownMenuItem onClick={() => openDialog('import')}>
                  <Upload className="w-4 h-4 mr-2" />Import Data
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={handlePrintBulkCards} disabled={assetsCount === 0}>
                <CreditCard className="w-4 h-4 mr-2" />Cetak Kartu
              </DropdownMenuItem>
              {perms.canBulkDelete && (
                <DropdownMenuItem
                  onClick={() => openDialog('bulkDelete')}
                  disabled={assetsCount === 0}
                  className="text-red-600 focus:text-red-600"
                >
                  <Trash2 className="w-4 h-4 mr-2" />Hapus Semua
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Advanced Filter Panel + Active Filter Badges */}
        <AdvancedFilter
          isOpen={showAdvancedFilter}
          onClose={() => setShowAdvancedFilter(false)}
          filters={filters}
          filterOptions={filterOptions}
          onFilterChange={handleAdvancedFilterChange}
          onReset={resetAdvancedFilters}
          activeFilterCount={activeFilterCount}
          filterCategory={filterCategory}
          onCategoryReset={handleCategoryReset}
        />
      </div>
    </div>
  );
});

export default DashboardToolbar;
