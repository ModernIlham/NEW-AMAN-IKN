import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { Filter, Search, X, Check, ChevronDown } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../ui/popover";
import { gabungPilihan, MAKS_PILIH_SEMUA } from "./FilterMultiSelect";

// ============================================================================
// CATEGORY SELECT — dropdown kategori: virtual, bisa dicari, MULTI-PILIH
// ============================================================================
// Master kodefikasi berisi belasan ribu entri, jadi daftarnya divirtualkan dan
// dipotong `RENDER_LIMIT`; pencarian yang menyempitkan sisanya.
//
// `value` adalah ARRAY label kategori (daftar kosong = semua). Popover TIDAK
// menutup saat satu kategori dipilih — memilih lima kategori tak boleh berarti
// membuka daftar lima kali. Pola & batasnya disamakan dengan FilterMultiSelect
// yang dipakai tujuh filter lain, termasuk batas "Pilih semua".

const ITEM_HEIGHT = 32;
const VISIBLE_COUNT = 10;
const CONTAINER_HEIGHT = ITEM_HEIGHT * VISIBLE_COUNT;
const RENDER_LIMIT = 200; // Only render up to 200 items, search narrows the rest

const CategorySelect = ({
  categories = [],             // master kodefikasi (objek {id,label,kode_aset})
  kategoriTerpakai,            // label kategori yang ADA di kegiatan ini
  value,                       // array label kategori; [] = semua
  onValueChange,               // (arrayLabelBaru) => void
  placeholder = "Semua Kategori",
  className = "",
  size = "default"
}) => {
  // Bawaan: hanya kategori yang benar-benar dipakai dalam kegiatan. Master
  // berisi belasan ribu entri; menawarkan semuanya membuat kotak ini nyaris
  // tak berguna di lapangan. Seluruh master tetap SATU KETUKAN jauhnya lewat
  // sakelar di bawah — dibutuhkan saat operator mencari kategori yang memang
  // belum dipakai satu aset pun.
  const [semuaKategori, setSemuaKategori] = useState(false);
  // Toleran terhadap nilai lama (string / sentinel "Semua") supaya pemanggil
  // yang belum diperbarui — dan snapshot state yang tersimpan — tidak pecah.
  const terpilih = useMemo(() => {
    if (Array.isArray(value)) return value;
    return value && value !== "Semua" ? [value] : [];
  }, [value]);
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const inputRef = useRef(null);
  const scrollRef = useRef(null);
  const [scrollTop, setScrollTop] = useState(0);

  useEffect(() => {
    if (open) {
      setSearchQuery("");
      setScrollTop(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  /**
   * Kategori dalam kegiatan → objek master yang cocok, ditambah label yang
   * ada di data tapi TIDAK ada di master (itu aset nyata; membuangnya membuat
   * barisnya mustahil disaring). `null` = tak ada informasi pemakaian.
   */
  const daftarTerpakai = useMemo(() => {
    const pakai = (kategoriTerpakai || []).filter(Boolean);
    if (!pakai.length) return null;
    const set = new Set(pakai);
    const dariMaster = categories.filter(c => set.has(c.label));
    const adaDiMaster = new Set(dariMaster.map(c => c.label));
    const asing = pakai.filter(l => !adaDiMaster.has(l))
      .map(l => ({ id: `luar-master:${l}`, label: l, kode_aset: "" }));
    return [...dariMaster, ...asing];
  }, [categories, kategoriTerpakai]);

  const sumberKategori = useMemo(() => {
    // Jatuh ke master bila kegiatan belum punya aset, permintaan opsi gagal,
    // atau sakelarnya dinyalakan. Kotak filter tak boleh pernah tampil kosong.
    const dasar = (semuaKategori || !daftarTerpakai) ? categories : daftarTerpakai;
    // Kategori yang SEDANG TERPILIH selalu ikut ditampilkan meski di luar
    // daftar terpakai — kalau tidak, ia tetap menyaring tetapi barisnya lenyap
    // dari daftar dan tak ada cara melepasnya selain menghapus semuanya.
    const terlihat = new Set(dasar.map(c => c.label));
    const hilang = (Array.isArray(value) ? value : [])
      .filter(l => l && !terlihat.has(l))
      .map(l => ({ id: `terpilih:${l}`, label: l, kode_aset: "" }));
    return hilang.length ? [...dasar, ...hilang] : dasar;
  }, [semuaKategori, daftarTerpakai, categories, value]);

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return sumberKategori;
    const query = searchQuery.toLowerCase();
    return sumberKategori.filter(c => {
      const label = c.label?.toLowerCase() || "";
      const kode = c.kode_aset?.toLowerCase() || "";
      return label.includes(query) || kode.includes(query);
    });
  }, [sumberKategori, searchQuery]);

  // Limit rendered items for performance
  const limitedCategories = useMemo(() => {
    return filteredCategories.slice(0, RENDER_LIMIT);
  }, [filteredCategories]);

  const totalHeight = limitedCategories.length * ITEM_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - 2);
  const endIndex = Math.min(limitedCategories.length, Math.ceil((scrollTop + CONTAINER_HEIGHT) / ITEM_HEIGHT) + 2);
  const visibleItems = limitedCategories.slice(startIndex, endIndex);

  const displayLabel = useMemo(() => {
    if (terpilih.length === 0) return placeholder;
    if (terpilih.length > 1) return `${terpilih[0]} +${terpilih.length - 1}`;
    const found = categories.find(c => c.label === terpilih[0]);
    if (found && found.kode_aset) return `${found.kode_aset} - ${found.label}`;
    return terpilih[0];
  }, [terpilih, categories, placeholder]);

  /** Centang/lepas satu kategori — popover TETAP terbuka. */
  const handleSelect = useCallback((categoryLabel) => {
    onValueChange(terpilih.includes(categoryLabel)
      ? terpilih.filter(x => x !== categoryLabel)
      : [...terpilih, categoryLabel]);
  }, [onValueChange, terpilih]);

  const handleClear = (e) => {
    e.stopPropagation();
    onValueChange([]);
  };

  const handleScroll = useCallback((e) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  // Dihitung dari JUMLAH KECOCOKAN SEBENARNYA (`filteredCategories`), bukan
  // dari potongan yang dirender. `limitedCategories` sudah dipotong
  // RENDER_LIMIT, jadi panjangnya tak pernah melampaui batas — memakainya di
  // sini membuat penjaganya tak pernah menyala, dan menekan tombol akan
  // memilih 200 pertama dari 250 kecocokan tanpa satu pun tanda di layar.
  // Itu persis kegagalan yang hendak dicegah.
  const bolehPilihSemua = filteredCategories.length > 0
    && filteredCategories.length <= MAKS_PILIH_SEMUA
    && filteredCategories.some(c => !terpilih.includes(c.label));

  const isCompact = size === "compact";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={`justify-between ${isCompact ? "h-7 text-[11px] px-2" : "h-8 text-xs"} ${className}`}
          data-testid="category-select-trigger"
        >
          <span className="flex items-center gap-1 truncate">
            <Filter className="w-3 h-3 flex-shrink-0" />
            <span className="truncate max-w-[140px] lg:max-w-[200px]">{displayLabel}</span>
          </span>
          <div className="flex items-center gap-0.5 ml-1">
            {terpilih.length > 1 && (
              <span
                className="px-1 rounded bg-blue-500/15 text-blue-600 dark:text-blue-400 text-[9px] font-semibold tabular-nums"
                data-testid="category-select-jumlah"
              >
                {terpilih.length}
              </span>
            )}
            {terpilih.length > 0 && (
              <span onClick={handleClear} className="hover:bg-muted rounded p-0.5 cursor-pointer"
                data-testid="category-select-clear">
                <X className="w-3 h-3 text-muted-foreground" />
              </span>
            )}
            <ChevronDown className="w-3 h-3 text-muted-foreground" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(95vw,480px)] p-0" align="start" data-testid="category-select-dropdown">
        {/* Search */}
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              ref={inputRef}
              placeholder="Cari kategori..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-sm"
              data-testid="category-search-input"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery("")} className="absolute right-2 top-1/2 -translate-y-1/2 hover:bg-muted rounded p-0.5">
                <X className="w-3 h-3 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        {/* Baris "Semua Kategori" = kembali ke tanpa filter. Ia BUKAN salah
            satu pilihan yang bisa dicentang bersama kategori lain: memilih
            "semua" sekaligus "Meja" tak punya arti. */}
        <div className="px-1 pt-1">
          <button
            onClick={() => onValueChange([])}
            className={`w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors ${
              terpilih.length === 0 ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : "text-foreground"
            }`}
            data-testid="category-option-all"
          >
            <Check className={`w-4 h-4 flex-shrink-0 ${terpilih.length === 0 ? "opacity-100" : "opacity-0"}`} />
            <span>Semua Kategori</span>
            <span className="ml-auto text-xs text-muted-foreground">{sumberKategori.length}</span>
          </button>
          <div className="border-t my-1" />
        </div>

        {/* Virtualized category list */}
        {limitedCategories.length === 0 ? (
          <div className="px-2 py-6 text-center text-sm text-muted-foreground">
            Tidak ada kategori yang cocok
          </div>
        ) : (
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="overflow-y-auto px-1"
            style={{ height: Math.min(CONTAINER_HEIGHT, totalHeight) }}
          >
            <div style={{ height: totalHeight, position: "relative" }}>
              {visibleItems.map((category, i) => {
                const idx = startIndex + i;
                const isSelected = terpilih.includes(category.label);
                const label = category.kode_aset ? `${category.kode_aset} - ${category.label}` : category.label;
                return (
                  <button
                    key={category.id || idx}
                    onClick={() => handleSelect(category.label)}
                    className={`absolute left-0 right-0 flex items-center gap-2 px-2 text-sm rounded hover:bg-muted transition-colors ${
                      isSelected ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : "text-foreground"
                    }`}
                    style={{ height: ITEM_HEIGHT, top: idx * ITEM_HEIGHT }}
                    title={label}
                    data-testid={`category-option-${category.id || idx}`}
                  >
                    <Check className={`w-4 h-4 flex-shrink-0 ${isSelected ? "opacity-100" : "opacity-0"}`} />
                    <span className="text-left break-words leading-tight text-[13px]">{label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Aksi massal — batas & alasannya sama dengan FilterMultiSelect:
            memilih ribuan kategori berubah jadi querystring puluhan kilobyte
            yang ditolak 414, dan memilih sebagian diam-diam menghasilkan
            filter yang salah tanpa tanda di layar. */}
        <div className="flex items-center justify-between gap-2 border-t px-2 py-1">
          <span className="text-[11px] text-muted-foreground truncate">
            {terpilih.length ? `${terpilih.length} dipilih` : "Semua kategori"}
          </span>
          <span className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => onValueChange(gabungPilihan(terpilih, filteredCategories.map(c => c.label)))}
              disabled={!bolehPilihSemua}
              title={filteredCategories.length > MAKS_PILIH_SEMUA
                ? `Terlalu banyak (${filteredCategories.length}) untuk dipilih sekaligus — persempit dengan pencarian dulu`
                : undefined}
              className="min-h-0 min-w-0 text-[11px] text-primary hover:underline disabled:opacity-40 disabled:no-underline"
              data-testid="category-select-pilih-semua"
            >
              {searchQuery.trim() ? `Pilih ${filteredCategories.length} hasil` : "Pilih semua"}
            </button>
            <button
              type="button"
              onClick={() => onValueChange([])}
              disabled={terpilih.length === 0}
              className="min-h-0 min-w-0 text-[11px] text-muted-foreground hover:text-foreground disabled:opacity-40"
              data-testid="category-select-kosongkan"
            >
              Kosongkan
            </button>
          </span>
        </div>

        {/* Sakelar lingkup daftar. Tidak mengubah pilihan dan tidak memicu
            pemuatan ulang data — ia hanya mengganti sumber opsinya. */}
        {daftarTerpakai && (
          <div className="border-t px-2 py-1">
            <button
              type="button"
              onClick={() => setSemuaKategori(v => !v)}
              className="min-h-0 min-w-0 w-full text-left text-[11px] text-primary hover:underline"
              data-testid="category-select-lingkup"
            >
              {semuaKategori
                ? `← Hanya kategori dalam kegiatan ini (${daftarTerpakai.length})`
                : `Tampilkan semua kategori (${categories.length}) →`}
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="p-1.5 border-t bg-muted/50 text-[11px] text-muted-foreground text-center">
          {searchQuery ? (
            <span>
              {filteredCategories.length > RENDER_LIMIT
                ? `Menampilkan ${RENDER_LIMIT} dari ${filteredCategories.length} hasil (ketik lebih spesifik)`
                : `${filteredCategories.length} dari ${sumberKategori.length} kategori`}
            </span>
          ) : (
            <span>
              {categories.length > RENDER_LIMIT
                ? `Menampilkan ${RENDER_LIMIT} dari ${sumberKategori.length} kategori — ketik untuk filter`
                : `Total ${sumberKategori.length} kategori`}
            </span>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default CategorySelect;
