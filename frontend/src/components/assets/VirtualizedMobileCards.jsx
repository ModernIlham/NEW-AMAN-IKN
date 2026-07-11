import React, { memo, useRef, useEffect } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Loader2 } from "lucide-react";
import AssetMobileCard from "./AssetMobileCard";

// ============================================================================
// MOBILE INFINITE SCROLL CARDS — kini BENAR-BENAR tervirtualisasi.
// Sebelumnya semua kartu hasil infinite-scroll dirender sekaligus (500 aset =
// 500 kartu di DOM) sehingga HP low-end tersendat. useVirtualizer hanya
// merender kartu yang terlihat (+overscan); tinggi kartu diukur dinamis
// (measureElement) karena teks nama/lokasi bisa membungkus beda-beda.
// ============================================================================
const VirtualizedMobileCards = memo(({
  assets,
  editId,
  onEdit,
  onDelete,
  onOpenKartu,
  onViewAudit,
  onPrintCard,
  onLoadMore,
  isLoadingMore = false,
  hasMore = true,
  totalItems = 0,
  rowLocks = {},
  currentSessionId,
  syncStatuses = {},
  onRetrySync,
  onDismissSync,
  selectedAssets,
  onToggleSelect
}) => {
  // Own scroll container (mirrors AssetGalleryView) so "Barang Serupa" and the
  // panels above settle at the top when scrolling down, instead of the whole
  // list scrolling away with the page.
  const scrollRef = useRef(null);

  const virtualizer = useVirtualizer({
    count: assets.length + 1, // +1 baris sentinel load-more / ringkasan
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (index === assets.length ? 64 : 112),
    overscan: 6,
  });

  // Muat halaman berikutnya saat baris sentinel masuk viewport virtual —
  // menggantikan IntersectionObserver (elemen sentinel kini absolut/virtual).
  const virtualItems = virtualizer.getVirtualItems();
  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoadingMore) return;
    const last = virtualItems[virtualItems.length - 1];
    if (last && last.index >= assets.length) onLoadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [virtualItems, onLoadMore, hasMore, isLoadingMore, assets.length]);

  return (
    <div
      ref={scrollRef}
      className="overflow-y-auto overflow-x-hidden h-[calc(100dvh-140px)] sm:h-[calc(100dvh-280px)]"
      style={{ contain: "layout style" }}
      data-testid="mobile-cards-scroll"
    >
      <div style={{ height: `${virtualizer.getTotalSize()}px`, width: "100%", position: "relative" }}>
        {virtualItems.map((vItem) => {
          // Baris sentinel: indikator memuat / ringkasan jumlah
          if (vItem.index === assets.length) {
            return (
              <div
                key="load-more"
                ref={virtualizer.measureElement}
                data-index={vItem.index}
                style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${vItem.start}px)` }}
                className="py-4"
              >
                {isLoadingMore && (
                  <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Memuat data lanjutan...</span>
                  </div>
                )}
                {!isLoadingMore && hasMore && assets.length > 0 && (
                  <div className="text-center text-xs text-muted-foreground">
                    Scroll ke bawah untuk memuat lebih banyak
                  </div>
                )}
                {!hasMore && assets.length > 0 && (
                  <div className="text-center py-2">
                    <span className="text-xs text-muted-foreground bg-muted px-3 py-1 rounded-full">
                      Menampilkan {assets.length} dari {totalItems} aset
                    </span>
                  </div>
                )}
              </div>
            );
          }
          const asset = assets[vItem.index];
          if (!asset) return null;
          const lock = rowLocks[asset.id];
          const isLockedByOther = lock && lock.session_id !== currentSessionId;
          return (
            <div
              key={asset.id}
              ref={virtualizer.measureElement}
              data-index={vItem.index}
              style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${vItem.start}px)` }}
            >
              <AssetMobileCard
                asset={asset}
                editId={editId}
                onEdit={isLockedByOther ? undefined : onEdit}
                onDelete={isLockedByOther ? undefined : onDelete}
                onOpenKartu={onOpenKartu}
                onViewAudit={onViewAudit}
                onPrintCard={onPrintCard}
                lockedBy={isLockedByOther ? lock.user_name : null}
                syncStatus={syncStatuses[asset.id]}
                onRetrySync={onRetrySync}
                onDismissSync={onDismissSync}
                selected={selectedAssets?.has(asset.id)}
                onToggleSelect={onToggleSelect ? () => onToggleSelect(asset.id) : undefined}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
});
VirtualizedMobileCards.displayName = "VirtualizedMobileCards";

export default VirtualizedMobileCards;
