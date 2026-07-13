import React, { memo, useState, useCallback, useRef, useEffect, useLayoutEffect, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Loader2 } from "lucide-react";
import AssetGalleryCard from "./AssetGalleryCard";
import { TooltipProvider } from "../ui/tooltip";
import Lightbox from "./PhotoLightbox";

// ============================================================================
// BREAKPOINT COLUMN CALCULATOR
// ============================================================================
function getColumnCount(width) {
  if (width >= 1536) return 6;  // 2xl
  if (width >= 1280) return 5;  // xl
  if (width >= 1024) return 4;  // lg
  if (width >= 640) return 3;   // sm
  return 2;                      // default
}

// ============================================================================
// VIRTUALIZED GALLERY VIEW - Only renders visible cards
// ============================================================================
const AssetGalleryView = memo(({
  assets,
  editId,
  onEdit,
  onDelete,
  onPrintCard,
  onLoadMore,
  onLoadPrev,
  hasPrev = false,
  isLoadingMore = false,
  hasMore = true,
  totalItems = 0,
  rowLocks = {},
  currentSessionId,
  selectedAssets,
  onToggleSelect,
}) => {
  const [lightboxAsset, setLightboxAsset] = useState(null);
  const containerRef = useRef(null);
  const sentinelRef = useRef(null);
  const topSentinelRef = useRef(null);
  // Geometri scroll ({scrollHeight, scrollTop}) direkam SEBELUM prepend agar
  // posisi tampilan bisa dijangkar setelah baris disisipkan di atas.
  const prependAnchor = useRef(null);
  const lastScrolledEditId = useRef(null);
  // Mobile-first initial guess (based on viewport) so phones never flash a
  // 4-column grid before the ResizeObserver measures the real container width.
  // A 4-col first paint squeezes each card to ~65px and clips the footer's
  // last action icon (Hapus) on small screens.
  const [columns, setColumns] = useState(() =>
    typeof window !== "undefined" ? getColumnCount(window.innerWidth) : 2
  );
  const [containerWidth, setContainerWidth] = useState(0);
  const GAP = 12; // gap-3 = 12px

  // Dynamic row height based on actual card width so the photo (aspect-[4/3])
  // plus the info body never clip. Previously a static 280/300px was used,
  // which squeezed the body into ~30-60px at narrow widths and made the
  // asset-name / location / price text "tenggelam" to the footer edge.
  const ROW_HEIGHT = useMemo(() => {
    if (!containerWidth || !columns) return 320;
    const cardWidth = Math.max(160, (containerWidth - GAP * (columns - 1)) / columns);
    // Mobile (<640px -> 2 cols) uses a shorter photo + slightly tighter body
    // so more cards fit on small screens; sm+ keeps the roomier 4/3 layout.
    const isMobile = columns <= 2;
    const photoH = cardWidth * (isMobile ? 10 / 16 : 3 / 4); // aspect-[16/10] vs [4/3]
    const bodyH = isMobile ? 106 : 122;  // name(2L) + user + eselon + location + price + padding
    const footerH = 30;  // icon row with border-t
    return Math.ceil(photoH + bodyH + footerH + GAP);
  }, [containerWidth, columns]);

  // Track container width and calculate columns
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const width = entry.contentRect.width;
        setColumns(getColumnCount(width));
        setContainerWidth(width);
      }
    });

    observer.observe(el);
    // Initial calculation
    setColumns(getColumnCount(el.offsetWidth));
    setContainerWidth(el.offsetWidth);

    return () => observer.disconnect();
  }, []);

  // Group assets into rows
  const rows = useMemo(() => {
    const result = [];
    for (let i = 0; i < assets.length; i += columns) {
      result.push(assets.slice(i, i + columns));
    }
    return result;
  }, [assets, columns]);

  // Virtualizer for rows (tanpa baris sentinel virtual — pemicu load-more kini
  // via IntersectionObserver pada elemen sentinel NYATA di bawah daftar).
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 3,
  });

  // Re-measure virtual rows when the computed ROW_HEIGHT changes (container
  // resize / column breakpoint change) so cards don't overlap or stack
  // incorrectly.
  useEffect(() => {
    virtualizer.measure();
  }, [ROW_HEIGHT]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-muat halaman berikutnya saat sentinel MENDEKATI bawah (prefetch 600px)
  // — IntersectionObserver pada elemen nyata dengan root = kontainer galeri.
  // Jauh lebih andal & terasa lebih sigap daripada memeriksa indeks baris
  // virtual (yang hanya ter-mount saat sudah mepet ke bawah). rootMargin
  // membuatnya memuat sebelum benar-benar sampai ke ujung.
  useEffect(() => {
    const el = sentinelRef.current;
    const root = containerRef.current;
    if (!el || !root || !onLoadMore) return undefined;
    const io = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && hasMore && !isLoadingMore) onLoadMore();
    }, { root, rootMargin: "600px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [onLoadMore, hasMore, isLoadingMore]);

  // Scroll ke ATAS mendekati puncak → muat halaman SEBELUMNYA (dua arah).
  // Rekam geometri scroll dulu agar bisa dijangkar setelah prepend (A4).
  const handleLoadPrev = useCallback(() => {
    const el = containerRef.current;
    if (!el || !onLoadPrev) return;
    prependAnchor.current = { scrollHeight: el.scrollHeight, scrollTop: el.scrollTop };
    onLoadPrev();
  }, [onLoadPrev]);

  // Sentinel ATAS: rootMargin kecil (bukan 600px) agar tak memicu kaskade
  // memuat semua halaman sekaligus saat masuk dari halaman jauh.
  useEffect(() => {
    const el = topSentinelRef.current;
    const root = containerRef.current;
    if (!el || !root || !onLoadPrev) return undefined;
    const io = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && hasPrev && !isLoadingMore) handleLoadPrev();
    }, { root, rootMargin: "100px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [onLoadPrev, hasPrev, isLoadingMore, handleLoadPrev]);

  // Jangkar scroll setelah baris di-PREPEND: pertahankan konten yang sama tetap
  // di tampilan (tanpa "lompat"). Jalan sinkron pra-paint (useLayoutEffect).
  useLayoutEffect(() => {
    const anchor = prependAnchor.current;
    if (!anchor) return;
    const el = containerRef.current;
    if (el) {
      const delta = el.scrollHeight - anchor.scrollHeight;
      if (delta > 0) el.scrollTop = anchor.scrollTop + delta;
    }
    prependAnchor.current = null;
  }, [assets]);

  // Jaga aset terseleksi (yang sedang diedit) SELALU terlihat: saat editId
  // berubah (mis. auto-lanjut setelah simpan), gulir kartunya ke tengah layar.
  // Hanya saat editId benar-benar berubah — tak melawan gulir manual pengguna,
  // dan tak terpicu saat load-more/prev. Bila baris belum termuat (index -1),
  // efek jalan lagi ketika `assets` berubah.
  useEffect(() => {
    if (!editId || editId === lastScrolledEditId.current) return;
    const index = assets.findIndex((a) => a.id === editId);
    if (index < 0) return;
    lastScrolledEditId.current = editId;
    virtualizer.scrollToIndex(Math.floor(index / columns), { align: "center" });
  }, [editId, columns, assets, virtualizer]);

  const openLightbox = useCallback((asset) => {
    setLightboxAsset(asset);
  }, []);

  const closeLightbox = useCallback(() => {
    setLightboxAsset(null);
  }, []);

  return (
    <TooltipProvider>
      {/* Virtualized Gallery Grid */}
      <div
        ref={containerRef}
        className="overflow-y-auto overflow-x-hidden h-[calc(100dvh-140px)] sm:h-[calc(100dvh-280px)]"
        style={{
          contain: 'layout style',
          // Cegah momentum scroll "bocor" ke <main> (double-scroll) sehingga
          // gulir tetap dimiliki kontainer galeri & sentinel andal terpicu.
          overscrollBehavior: 'contain',
        }}
        data-testid="gallery-grid"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {/* Sentinel ATAS (absolut di offset 0 → tak menggeser origin virtualizer):
              IntersectionObserver memuat halaman SEBELUMNYA saat mendekati puncak. */}
          {hasPrev && (
            <div
              ref={topSentinelRef}
              data-testid="gallery-loadprev-sentinel"
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 1 }}
            />
          )}
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const row = rows[virtualRow.index];
            return (
              <div
                key={virtualRow.index}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div
                  className="grid gap-2 sm:gap-3 h-full"
                  style={{
                    gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                    paddingBottom: `${GAP}px`,
                  }}
                >
                  {row.map((asset) => {
                    const lock = rowLocks[asset.id];
                    const isLockedByOther = lock && lock.session_id !== currentSessionId;
                    return (
                      <AssetGalleryCard
                        key={asset.id}
                        asset={asset}
                        isEditing={editId === asset.id}
                        onEdit={isLockedByOther ? undefined : onEdit}
                        onDelete={isLockedByOther ? undefined : onDelete}
                        onPrintCard={onPrintCard}
                        onOpenLightbox={openLightbox}
                        isSelected={selectedAssets?.has(asset.id)}
                        onToggleSelect={onToggleSelect}
                        isLockedByOther={isLockedByOther}
                        lockedByName={lock?.user_name}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Sentinel prefetch nyata: IntersectionObserver memicu load-more saat
            elemen ini mendekati bawah (rootMargin 600px) — memuat otomatis
            SEBELUM benar-benar sampai ke ujung. */}
        {hasMore && (
          <div ref={sentinelRef} className="flex items-center justify-center py-4" data-testid="gallery-loadmore-sentinel">
            {isLoadingMore ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Memuat data lanjutan...</span>
              </div>
            ) : (
              <div className="text-center text-xs text-muted-foreground">
                Memuat otomatis saat digulir…
              </div>
            )}
          </div>
        )}

        {/* End of list indicator */}
        {!hasMore && assets.length > 0 && (
          <div className="text-center py-2">
            <span className="text-xs text-muted-foreground bg-muted px-3 py-1 rounded-full">
              Menampilkan {assets.length} dari {totalItems} aset
            </span>
          </div>
        )}
      </div>

      {/* Lightbox */}
      {lightboxAsset && (
        <Lightbox asset={lightboxAsset} onClose={closeLightbox} onEdit={onEdit} siblings={assets} onSelectAsset={setLightboxAsset} />
      )}
    </TooltipProvider>
  );
});
AssetGalleryView.displayName = "AssetGalleryView";

export default AssetGalleryView;
