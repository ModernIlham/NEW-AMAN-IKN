import React, { memo, useState, useEffect, useMemo, useRef } from "react";
import {
  Search, Filter, Download, Upload, Settings,
  Loader2, Trash2, Eye, FileText, FileSpreadsheet, CreditCard,
  List, LayoutGrid, MapPinned, Tags,
} from "lucide-react";
import { labelDilepas } from "@/lib/labelRingkas";
import useLebarElemen from "@/hooks/useLebarElemen";
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
import { InventoryModeSwitch } from "@/components/assets/StatsBar";

// Kotak cari dengan state LOKAL: tiap ketukan hanya me-render komponen kecil
// ini, lalu nilainya didorong ke halaman (setSearchInput) setelah jeda 250 ms.
// Sebelumnya setiap huruf me-render ulang seluruh dashboard (~1.400 baris +
// form aset) — terasa berat mengetik di HP low-end.
const SearchInput = memo(function SearchInput({ value, onCommit }) {
  const [local, setLocal] = useState(value || "");
  const lastCommitRef = useRef(value || "");

  // Sinkron turun bila halaman mengubah nilai secara programatik
  // (hasil scan QR mengisi kotak cari / tombol reset mengosongkannya).
  useEffect(() => {
    if (value !== lastCommitRef.current) {
      lastCommitRef.current = value || "";
      setLocal(value || "");
    }
  }, [value]);

  // Dorong ke halaman ber-debounce
  useEffect(() => {
    if (local === lastCommitRef.current) return undefined;
    const t = setTimeout(() => { lastCommitRef.current = local; onCommit(local); }, 250);
    return () => clearTimeout(t);
  }, [local, onCommit]);

  return (
    <Input
      placeholder="Cari kode, nama, lokasi..."
      value={local}
      onChange={e => setLocal(e.target.value)}
      className="pl-8 h-9 lg:h-8 text-sm"
      data-testid="search-input"
    />
  );
});

const DashboardToolbar = memo(function DashboardToolbar({
  searchInput, setSearchInput, onScanCode, onOpenMap, mapOpen = false,
  categories, filterCategory, setFilterCategory,
  activeFilterCount, showAdvancedFilter, setShowAdvancedFilter,
  sortBy, setSortBy,
  exporting, handleExport, handleExportExecutivePDF, handlePreviewExecutive,
  perms, openDialog,
  handlePrintBulkCards, onCetakStiker, assetsCount, selectedCount = 0,
  filters, filterOptions, handleAdvancedFilterChange,
  resetAdvancedFilters, handleCategoryReset,
  refreshData,
  viewMode, setViewMode,
  inventoryMode, setInventoryMode,
}) {
  // ── Satu baris di lebar berapa pun ────────────────────────────────────────
  // Lebar diukur dari KONTAINER (bukan viewport) lalu label dilepas satu per
  // satu sampai muat — lihat `lib/labelRingkas` untuk alasan lengkapnya.
  const [barisRef, lebarBaris] = useLebarElemen();

  // Urutan array = URUTAN PELEPASAN label. Disusun dari yang paling rela jadi
  // ikon ke yang paling perlu kata-katanya:
  //  · "Cetak Kartu (n)" & "Hapus Semua" — label terpanjang, ikonnya (kartu,
  //    tong sampah) sudah bicara sendiri, jadi paling banyak ruang ditebus
  //    dengan kerugian paling kecil;
  //  · Export & Import DITAHAN paling akhir di grup aksi: ikon panah turun dan
  //    panah naik gampang tertukar, kata-katanyalah yang membedakan;
  //  · dua Select paling akhir — keduanya tidak kehilangan teks, hanya
  //    menyempit, karena isinya menyatakan filter yang sedang aktif.
  // `lebarIkon` 38 px = lebar terukur tombol `size="sm" h-8` bentuk ikon-saja
  // (px-2 + garis + ikon 12 px). Saklar tampilan & dua Select memakai lebar
  // eksplisit karena keduanya menyempit, bukan kehilangan teks.
  // Seleksi aktif → tombol cetak bekerja pada yang DITANDAI saja; angkanya
  // ikut berubah supaya tak ada kejutan setelah PDF jadi.
  const jmlCetak = selectedCount > 0 ? selectedCount : assetsCount;
  const judulCetak = selectedCount > 0
    ? `Cetak Kartu ${selectedCount} aset terpilih`
    : `Cetak Kartu (${assetsCount})`;

  const itemLipat = useMemo(() => {
    const daftar = [
      { kunci: "kartu", lebarIkon: 38, label: `Cetak Kartu (${jmlCetak})` },
    ];
    if (perms.canBulkDelete) daftar.push({ kunci: "hapus", lebarIkon: 38, label: "Hapus Semua" });
    daftar.push({ kunci: "stiker", lebarIkon: 38, label: "Stiker" });
    if (perms.canImport) daftar.push({ kunci: "impor", lebarIkon: 38, label: "Import" });
    daftar.push({ kunci: "ekspor", lebarIkon: 38, label: "Export" });
    if (viewMode !== undefined && setViewMode) {
      daftar.push({ kunci: "tampilan", lebarIkon: 66, lebarPenuh: 145 });
    }
    daftar.push({ kunci: "filter", lebarIkon: 38, label: "Filter Lanjutan" });
    daftar.push({ kunci: "urut", lebarIkon: 88, lebarPenuh: 128 });
    daftar.push({ kunci: "kategori", lebarIkon: 112, lebarPenuh: 160 });
    return daftar;
  }, [jmlCetak, perms.canBulkDelete, perms.canImport, viewMode, setViewMode]);

  // `lebarTetap` = indikator kuota kompresi, satu-satunya penghuni baris yang
  // tak pernah melipat.
  const lepas = labelDilepas(lebarBaris, itemLipat, { celah: 6, lebarTetap: 90 });
  const tampil = (kunci) => !lepas.has(kunci);

  return (
    <div className="bg-card rounded-xl border border-border shadow-sm p-1.5 sm:p-2.5 print:hidden" data-testid="dashboard-toolbar">
      <div className="flex flex-col gap-1 sm:gap-2">
        {/* Baris 1: Cari + Scan QR stiker (+ Filter Lanjutan di mobile/tablet) */}
        <div className="flex items-center gap-1.5">
          <div className="relative flex-1 min-w-0">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
            <SearchInput value={searchInput} onCommit={setSearchInput} />
          </div>
          <QrScanButton onDetected={onScanCode || setSearchInput} />
          {/* Saklar mode Dashboard|Inventarisasi — KHUSUS HP (<sm), disisipkan
              di antara Scan & Peta (permintaan pemilik). Ikon-saja agar ringkas;
              di ≥sm saklar tetap di StatsBar. */}
          {setInventoryMode && (
            <InventoryModeSwitch
              inventoryMode={inventoryMode}
              setInventoryMode={setInventoryMode}
              mobileLabel={false}
              className="sm:hidden flex-shrink-0 gap-0.5 p-0.5 rounded-lg bg-muted"
            />
          )}
          {/* Lembar Peta Aset — di HP/tablet cukup ikon khasnya; toggle */}
          {onOpenMap && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onOpenMap}
              aria-pressed={mapOpen}
              className={`h-9 w-9 p-0 lg:w-auto lg:px-2.5 lg:h-8 min-h-0 min-w-0 text-xs flex-shrink-0 ${mapOpen
                ? "bg-teal-600 border-teal-600 text-white hover:bg-teal-700 hover:text-white"
                : "text-teal-600 dark:text-teal-400 border-teal-300 dark:border-teal-800 hover:bg-teal-50 hover:text-teal-700 dark:hover:bg-teal-950 dark:hover:text-teal-300"}`}
              title="Peta aset (mengikuti filter aktif)"
              aria-label="Peta aset"
              data-testid="map-open-btn"
            >
              <MapPinned className="w-4 h-4" />
              <span className="hidden lg:inline lg:ml-1">Peta</span>
            </Button>
          )}
          <Button
            variant={activeFilterCount > 0 ? "default" : "outline"}
            size="sm"
            className={`lg:hidden h-9 w-9 p-0 min-h-0 min-w-0 relative flex-shrink-0 ${activeFilterCount > 0 ? "bg-teal-700" : ""}`}
            onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
            aria-label="Filter lanjutan"
            data-testid="mobile-advanced-filter-btn"
          >
            <Filter className="w-4 h-4" />
            {activeFilterCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-white text-blue-600 rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-bold border border-teal-700">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </div>

        {/* Desktop toolbar (lg+ only) — SATU BARIS di lebar berapa pun.
            Riwayat: mula-mula `flex-nowrap` + `overflow-x-auto` (geser samping),
            lalu `flex-wrap` dua grup (grup aksi turun ke baris kedua). Keduanya
            ditolak pemilik: "jangan membuat row baris baru … usahakan
            dipersingkat dengan memberikan iconnya saja seiring terhimpitnya
            tampilan layar."
            Akar masalahnya: breakpoint `xl:` membaca lebar VIEWPORT, sedangkan
            yang menentukan muat/tidak adalah lebar KONTAINER — di halaman
            Kegiatan panel form kiri menyisakan ~880px pada layar 1366px, `xl`
            tetap menyala, label lengkap tetap dirender, barisnya meluber.
            Sekarang lebar baris diukur ResizeObserver dan label dilepas satu
            per satu (`lib/labelRingkas`). Bentuk paling ringkas — semua ikon
            saja — hanya butuh ±420px, jauh di bawah lebar kontainer mana pun
            yang bisa muncul di ≥lg, jadi tak perlu lagi katup scroll. */}
        <div ref={barisRef} className="hidden lg:flex flex-nowrap gap-1.5 items-center">
          <div className="flex flex-nowrap items-center gap-1.5">
            <CategorySelect
              categories={categories}
              value={filterCategory}
              onValueChange={setFilterCategory}   /* efek perubahan filter yang memuat ulang — lihat DashboardPage */
              placeholder="Semua Kategori"
              // TANPA `flex-shrink-0`, dan itu disengaja: setelah semua label
              // dilepas pun ada lebar kontainer ekstrem (panel form di layar
              // 1024) yang tetap kurang. Dua Select inilah katup terakhirnya —
              // isinya sudah `truncate`, jadi menyusut hanya memendekkan teks,
              // bukan memunculkan geser samping. Saudara-saudaranya tetap
              // `flex-shrink-0` supaya tak ada yang lain ikut tergencet.
              className={`min-w-0 ${tampil("kategori") ? "w-40" : "w-28"}`}
            />

            <Button
              variant={activeFilterCount > 0 ? "default" : "outline"}
              size="sm"
              className={`h-8 text-xs flex-shrink-0 ${tampil("filter") ? "" : "px-2"} ${activeFilterCount > 0 ? "bg-teal-700" : ""}`}
              onClick={() => setShowAdvancedFilter(!showAdvancedFilter)}
              title="Filter Lanjutan"
              data-testid="advanced-filter-btn"
            >
              <Filter className={`w-3 h-3 ${tampil("filter") ? "mr-1" : ""}`} />
              {tampil("filter") && <span>Filter Lanjutan</span>}
              {activeFilterCount > 0 && (
                <span className="ml-1.5 bg-white text-blue-600 rounded-full w-4 h-4 flex items-center justify-center text-[10px] font-bold">
                  {activeFilterCount}
                </span>
              )}
            </Button>

            <Select value={sortBy} onValueChange={v => { setSortBy(v); refreshData(1); }}>
              {/* Ikut jadi katup terakhir bersama Select kategori — lihat catatan di sana. */}
              <SelectTrigger className={`h-8 text-xs min-w-0 ${tampil("urut") ? "w-32" : "w-[88px]"}`}><SelectValue /></SelectTrigger>
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

            {/* View Mode Toggle — `flex-shrink-0` seperti seluruh saudaranya:
                item yang boleh menyusut akan menyerap SELURUH kelebihan lebar
                dan tergencet sendirian (lihat catatan di TinifyQuotaIndicator). */}
            {viewMode !== undefined && setViewMode && (
              <div className="flex flex-shrink-0 bg-muted rounded-lg p-0.5 gap-0.5" data-testid="view-mode-toggle">
                <button
                  className={`flex items-center gap-1 py-1 rounded-md text-xs font-medium transition-all ${tampil("tampilan") ? "px-2.5" : "px-2"} ${viewMode === 'list' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  onClick={() => setViewMode('list')}
                  title="Tampilan daftar"
                  data-testid="view-mode-list"
                >
                  <List className="w-3.5 h-3.5" />{tampil("tampilan") && <span>List</span>}
                </button>
                <button
                  className={`flex items-center gap-1 py-1 rounded-md text-xs font-medium transition-all ${tampil("tampilan") ? "px-2.5" : "px-2"} ${viewMode === 'gallery' ? 'bg-card text-blue-600 shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                  onClick={() => setViewMode('gallery')}
                  title="Tampilan galeri"
                  data-testid="view-mode-gallery"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />{tampil("tampilan") && <span>Galeri</span>}
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-nowrap items-center gap-1.5 ml-auto">
            <TinifyQuotaIndicator />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={exporting} className={`h-8 text-xs flex-shrink-0 ${tampil("ekspor") ? "" : "px-2"}`} title="Export data">
                  {exporting
                    ? <Loader2 className={`w-3 h-3 animate-spin ${tampil("ekspor") ? "mr-1" : ""}`} />
                    : <Download className={`w-3 h-3 ${tampil("ekspor") ? "mr-1" : ""}`} />}
                  {tampil("ekspor") && <span>Export</span>}
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
              <Button variant="outline" size="sm" className={`h-8 text-xs flex-shrink-0 ${tampil("impor") ? "" : "px-2"}`} onClick={() => openDialog('import')} title="Import data">
                <Upload className={`w-3 h-3 ${tampil("impor") ? "mr-1" : ""}`} />{tampil("impor") && <span>Import</span>}
              </Button>
            )}
            {perms.canBulkDelete && (
              <Button
                variant="outline"
                size="sm"
                className={`h-8 text-xs flex-shrink-0 text-red-500 hover:text-red-700 hover:bg-red-50 border-red-200 hover:border-red-300 ${tampil("hapus") ? "" : "px-2"}`}
                onClick={() => openDialog('bulkDelete')}
                disabled={assetsCount === 0}
                title="Hapus Semua aset yang terfilter"
              >
                <Trash2 className={`w-3 h-3 ${tampil("hapus") ? "mr-1" : ""}`} />{tampil("hapus") && <span>Hapus Semua</span>}
              </Button>
            )}
            {/* Jumlah aset ikut hilang bersama labelnya — `title` tetap
                menyebutnya agar informasi itu tak lenyap sama sekali. */}
            <Button variant="outline" size="sm" className={`h-8 text-xs flex-shrink-0 ${tampil("kartu") ? "" : "px-2"}`} onClick={handlePrintBulkCards} disabled={jmlCetak === 0}
              title={judulCetak} data-testid="toolbar-cetak-kartu">
              <CreditCard className={`w-3 h-3 ${tampil("kartu") ? "mr-1" : ""}`} />{tampil("kartu") && <span>Cetak Kartu ({jmlCetak})</span>}
            </Button>
            <Button variant="outline" size="sm" className={`h-8 text-xs flex-shrink-0 ${tampil("stiker") ? "" : "px-2"}`} onClick={onCetakStiker} disabled={jmlCetak === 0}
              title={selectedCount > 0 ? `Cetak Stiker Label BMN — ${selectedCount} aset terpilih` : "Cetak Stiker Label BMN"} data-testid="toolbar-cetak-stiker">
              <Tags className={`w-3 h-3 ${tampil("stiker") ? "mr-1" : ""}`} />{tampil("stiker") && <span>Stiker</span>}
            </Button>
          </div>
        </div>

        {/* Mobile/Tablet toolbar — satu baris kontrol ringkas (semua h-9).
            Kategori dominan (flex-1); pengesahan hanya di halaman Kegiatan. */}
        <div className="lg:hidden flex items-center gap-1.5">
          <CategorySelect
            categories={categories}
            value={filterCategory}
            onValueChange={setFilterCategory}   /* efek perubahan filter yang memuat ulang — lihat DashboardPage */
            placeholder="Semua Kategori"
            className="flex-1 min-w-0 h-9 min-h-0"
            size="compact"
          />

          <Select value={sortBy} onValueChange={v => { setSortBy(v); refreshData(1); }}>
            <SelectTrigger className="w-auto max-w-[38%] h-9 min-h-0 px-2 text-[11px] gap-1 flex-shrink-0" aria-label="Urutkan" data-testid="mobile-sort-select">
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
              <DropdownMenuItem onClick={handlePrintBulkCards} disabled={jmlCetak === 0} data-testid="mobile-cetak-kartu">
                <CreditCard className="w-4 h-4 mr-2" />Cetak Kartu ({jmlCetak})
              </DropdownMenuItem>
              {/* Tanpa embel-embel "(n terpilih)": labelnya sudah paling panjang
                  di menu ini, dan tambahan itu memecahnya jadi tiga baris di HP.
                  Jumlah yang akan dicetak tetap disebut di dalam dialog stiker,
                  di baris cakupan "Aset yang sedang diseleksi (n aset)". */}
              <DropdownMenuItem onClick={onCetakStiker} disabled={jmlCetak === 0} data-testid="mobile-cetak-stiker">
                <Tags className="w-4 h-4 mr-2" />Cetak Stiker Label
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
