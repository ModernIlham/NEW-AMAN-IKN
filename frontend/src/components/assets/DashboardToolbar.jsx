import React, { memo } from "react";
import {
  Search, Filter, Download, Upload, Settings,
  Loader2, Trash2, Eye, FileText, FileSpreadsheet, CreditCard,
  List, LayoutGrid,
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
}) {
  return (
    <div className="bg-card rounded-lg border border-border p-1.5 sm:p-2.5 print:hidden" data-testid="dashboard-toolbar">
      <div className="flex flex-col gap-1.5 sm:gap-2">
        {/* Search + Scan QR stiker */}
        <div className="flex items-center gap-1.5">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1.5 sm:top-2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-muted-foreground" />
            <Input
              placeholder="Cari kode, nama, lokasi..."
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              className="pl-8 sm:pl-9 h-7 sm:h-8 text-xs sm:text-sm"
              data-testid="search-input"
            />
          </div>
          <QrScanButton onDetected={setSearchInput} />
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

        {/* Mobile/Tablet toolbar - compact with wrapping */}
        <div className="lg:hidden flex flex-col gap-1.5">
          {/* Row 1: Category + Filter Lanjutan */}
          <div className="flex items-center gap-1.5">
            <CategorySelect
              categories={categories}
              value={filterCategory}
              onValueChange={v => { setFilterCategory(v); refreshData(1); }}
              placeholder="Kategori"
              className="flex-1 min-w-[100px]"
              size="compact"
            />
            <Button
              variant={activeFilterCount > 0 ? "default" : "outline"}
              size="sm"
              className={`h-7 w-7 p-0 relative flex-shrink-0 ${activeFilterCount > 0 ? "bg-blue-600" : ""}`}
              onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
              data-testid="mobile-advanced-filter-btn"
            >
              <Filter className="w-3 h-3" />
              {activeFilterCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-white text-blue-600 rounded-full w-3.5 h-3.5 flex items-center justify-center text-[8px] font-bold border border-blue-600">
                  {activeFilterCount}
                </span>
              )}
            </Button>
          </div>

          {/* Row 2: Sort + Tinify + View toggle + Settings */}
          <div className="flex items-center gap-1">
            <Select value={sortBy} onValueChange={v => { setSortBy(v); refreshData(1); }}>
              <SelectTrigger className="w-[70px] h-7 text-[10px] px-1.5"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Terbaru</SelectItem>
                <SelectItem value="oldest">Terlama</SelectItem>
                <SelectItem value="name_asc">A-Z</SelectItem>
                <SelectItem value="name_desc">Z-A</SelectItem>
                <SelectItem value="price_asc">Harga ↑</SelectItem>
                <SelectItem value="price_desc">Harga ↓</SelectItem>
              </SelectContent>
            </Select>

            <TinifyQuotaMobile />

            {/* Mobile View Toggle */}
            {viewMode !== undefined && setViewMode && (
              <div className="flex bg-muted rounded-md p-0.5 gap-0.5">
                <button
                  className={`p-1 rounded ${viewMode === 'list' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground'}`}
                  onClick={() => setViewMode('list')}
                >
                  <List className="w-3.5 h-3.5" />
                </button>
                <button
                  className={`p-1 rounded ${viewMode === 'gallery' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground'}`}
                  onClick={() => setViewMode('gallery')}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <div className="flex-1"></div>

            {/* Mobile actions dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-7 px-2">
                <Settings className="w-3.5 h-3.5" />
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
