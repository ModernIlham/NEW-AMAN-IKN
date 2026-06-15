import React, { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { Filter, Search, X, Check, ChevronDown } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../ui/popover";

// ============================================================================
// CATEGORY SELECT - Virtualized + searchable dropdown for 12k+ categories
// ============================================================================

const ITEM_HEIGHT = 32;
const VISIBLE_COUNT = 10;
const CONTAINER_HEIGHT = ITEM_HEIGHT * VISIBLE_COUNT;
const RENDER_LIMIT = 200; // Only render up to 200 items, search narrows the rest

const CategorySelect = ({ 
  categories = [], 
  value, 
  onValueChange, 
  placeholder = "Semua Kategori",
  className = "",
  size = "default"
}) => {
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

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return categories;
    const query = searchQuery.toLowerCase();
    return categories.filter(c => {
      const label = c.label?.toLowerCase() || "";
      const kode = c.kode_aset?.toLowerCase() || "";
      return label.includes(query) || kode.includes(query);
    });
  }, [categories, searchQuery]);

  // Limit rendered items for performance
  const limitedCategories = useMemo(() => {
    return filteredCategories.slice(0, RENDER_LIMIT);
  }, [filteredCategories]);

  const totalHeight = limitedCategories.length * ITEM_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - 2);
  const endIndex = Math.min(limitedCategories.length, Math.ceil((scrollTop + CONTAINER_HEIGHT) / ITEM_HEIGHT) + 2);
  const visibleItems = limitedCategories.slice(startIndex, endIndex);

  const displayLabel = useMemo(() => {
    if (!value || value === "Semua") return placeholder;
    const found = categories.find(c => c.label === value);
    if (found && found.kode_aset) return `${found.kode_aset} - ${found.label}`;
    return value;
  }, [value, categories, placeholder]);

  const handleSelect = useCallback((categoryLabel) => {
    onValueChange(categoryLabel);
    setOpen(false);
  }, [onValueChange]);

  const handleClear = (e) => {
    e.stopPropagation();
    onValueChange("Semua");
  };

  const handleScroll = useCallback((e) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

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
            {value && value !== "Semua" && (
              <span onClick={handleClear} className="hover:bg-muted rounded p-0.5 cursor-pointer">
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

        {/* "Semua Kategori" fixed at top */}
        <div className="px-1 pt-1">
          <button
            onClick={() => handleSelect("Semua")}
            className={`w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted transition-colors ${
              value === "Semua" || !value ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300" : "text-foreground"
            }`}
            data-testid="category-option-all"
          >
            <Check className={`w-4 h-4 flex-shrink-0 ${value === "Semua" || !value ? "opacity-100" : "opacity-0"}`} />
            <span>Semua Kategori</span>
            <span className="ml-auto text-xs text-muted-foreground">{categories.length}</span>
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
                const isSelected = value === category.label;
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

        {/* Footer */}
        <div className="p-1.5 border-t bg-muted/50 text-[11px] text-muted-foreground text-center">
          {searchQuery ? (
            <span>
              {filteredCategories.length > RENDER_LIMIT
                ? `Menampilkan ${RENDER_LIMIT} dari ${filteredCategories.length} hasil (ketik lebih spesifik)`
                : `${filteredCategories.length} dari ${categories.length} kategori`}
            </span>
          ) : (
            <span>
              {categories.length > RENDER_LIMIT
                ? `Menampilkan ${RENDER_LIMIT} dari ${categories.length} kategori — ketik untuk filter`
                : `Total ${categories.length} kategori`}
            </span>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default CategorySelect;
