import React, { memo, useState, useCallback, useRef, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Loader2, X, ChevronLeft, ChevronRight, MapPin, Tag, User, Building2, QrCode, ClipboardCheck, Calendar, FileCheck, FileX, StickyNote } from "lucide-react";
import AssetGalleryCard from "./AssetGalleryCard";
import { TooltipProvider } from "../ui/tooltip";
import { authMediaUrl } from "../../lib/mediaUrl";
import { useBackGuard } from "../../hooks/useBackGuard";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatPrice = (p) => {
  if (!p) return null;
  const num = typeof p === "string" ? parseFloat(p) : p;
  return isNaN(num) ? null : `Rp ${num.toLocaleString("id-ID")}`;
};

// ============================================================================
// LIGHTBOX - Photo gallery with full asset info
// ============================================================================
const Lightbox = memo(({ asset, onClose, onEdit }) => {
  const [fullAsset, setFullAsset] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [thumbs, setThumbs] = useState([]); // placeholder kecil per-foto (instan)
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [imgLoading, setImgLoading] = useState(false); // foto berikutnya sedang dimuat
  const startX = useRef(0);

  useEffect(() => {
    if (!asset?.id) return;
    setLoading(true);
    // Light fetch only (no base64 media): text fields + photo_count + version.
    // Each photo then streams directly into <img src=".../photos/{i}?v=...">,
    // so the first photo renders as soon as ITS bytes arrive (progressive) and
    // the browser caches every photo — no more waiting for one huge JSON blob.
    // ?v={version} busts the cache when the asset is edited; the endpoint is a
    // public GET (like the other media streams) since <img> can't send auth
    // headers. Legacy inline photos are handled server-side by the same URL.
    axios.get(`${API}/assets/${asset.id}?exclude_media=true`)
      .then(r => {
        const data = r.data;
        setFullAsset(data);
        const count = Number(data.photo_count) || 0;
        const version = Number(data.version) || 1;
        // w=1280: varian preview (~100-250KB) — jauh lebih cepat dari full-res
        // (~900KB) dan tetap tajam untuk layar; server me-resize sekali lalu
        // meng-cache (ETag/Cache-Control tetap berlaku).
        const p = count > 0
          ? Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${asset.id}/photos/${i}?v=${version}&w=1280`))
          : (asset.thumbnail ? [asset.thumbnail] : []); // data-URI fallback (legacy inline cover)
        // Thumbnail kecil per-foto sebagai placeholder instan saat berpindah.
        setThumbs(count > 0
          ? Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${asset.id}/photos/${i}?v=${version}&thumb=1`))
          : (asset.thumbnail ? [asset.thumbnail] : []));
        setPhotos(p);
        setIdx(0);
      })
      .catch(() => {
        setFullAsset(asset);
        setPhotos(asset.thumbnail ? [asset.thumbnail] : []); // data-URI support kept
        setThumbs(asset.thumbnail ? [asset.thumbnail] : []);
        setIdx(0);
      })
      .finally(() => setLoading(false));
  }, [asset?.id, asset?.thumbnail]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setIdx(i => (i - 1 + photos.length) % photos.length);
      if (e.key === "ArrowRight") setIdx(i => (i + 1) % photos.length);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [photos.length, onClose]);

  // Foto berpindah → tandai "sedang memuat" agar tampil spinner (bukan foto lama
  // yang terlihat "freeze"). Dibersihkan oleh onLoad/onError <img>. Bila foto
  // sudah di-cache (mis. hasil preload), onLoad langsung memicu clear.
  useEffect(() => { if (photos.length > 0) setImgLoading(true); }, [idx, photos]);

  // Preload foto tetangga (berikutnya & sebelumnya) agar navigasi mulus — saat
  // ditampilkan sudah dari cache sehingga tak terkesan freeze.
  useEffect(() => {
    if (photos.length <= 1) return undefined;
    const imgs = [];
    [(idx + 1) % photos.length, (idx - 1 + photos.length) % photos.length].forEach((i) => {
      if (i === idx) return;
      const im = new Image();
      im.src = photos[i];
      imgs.push(im);
    });
    return () => { imgs.forEach((im) => { im.src = ""; }); };
  }, [idx, photos]);

  // Back/Undo browser saat lightbox terbuka → tutup lightbox, bukan pindah
  // halaman. Komponen ini hanya ter-mount saat terbuka, jadi guard aktif penuh.
  useBackGuard(onClose);

  // Lock background scroll while the lightbox is open (stops the page
  // behind from scrolling / "bocor" under the popup on mobile).
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  const onTouchStart = useCallback((e) => { startX.current = e.touches[0].clientX; }, []);
  const onTouchEnd = useCallback((e) => {
    const diff = e.changedTouches[0].clientX - startX.current;
    if (Math.abs(diff) > 50) {
      if (diff > 0) setIdx(i => (i - 1 + photos.length) % photos.length);
      else setIdx(i => (i + 1) % photos.length);
    }
  }, [photos.length]);

  if (!asset) return null;
  const a = fullAsset || asset;
  const price = formatPrice(a.purchase_price);
  const invStatus = a.inventory_status || "Belum Diinventarisasi";
  const docChecked = a.doc_checked || 0;
  const docTotal = a.doc_total || 0;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-md flex flex-col items-center justify-center"
      onClick={onClose}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      data-testid="gallery-lightbox"
    >
      {/* Close button */}
      <button
        className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors"
        onClick={onClose}
        data-testid="lightbox-close"
      >
        <X className="w-5 h-5" />
      </button>

      {/* Photo area */}
      <div className="relative flex-1 flex items-center justify-center w-full max-w-4xl px-4" onClick={(e) => e.stopPropagation()}>
        {loading ? (
          <Loader2 className="w-10 h-10 text-slate-700 dark:text-white animate-spin" />
        ) : photos.length > 0 ? (
          <>
            <img
              key={photos[idx]}
              src={photos[idx]}
              alt={a.name || "Asset"}
              onLoad={() => setImgLoading(false)}
              onError={() => setImgLoading(false)}
              className={`max-h-[60vh] max-w-full object-contain rounded-lg shadow-2xl transition-opacity duration-200 ${imgLoading ? "opacity-0" : "opacity-100"}`}
              draggable={false}
            />
            {imgLoading && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none" data-testid="lightbox-img-loading">
                {/* Placeholder instan: thumbnail kecil diperbesar + blur, supaya
                    pengguna langsung melihat foto yang DITUJU (bukan foto lama)
                    selagi versi tajamnya diunduh. */}
                {thumbs[idx] && (
                  <img src={thumbs[idx]} alt="" aria-hidden="true" draggable={false}
                    className="max-h-[60vh] max-w-full object-contain rounded-lg blur-md scale-[1.02] opacity-80" />
                )}
                <Loader2 className="absolute w-10 h-10 text-white drop-shadow animate-spin" />
              </div>
            )}
            {photos.length > 1 && (
              <>
                <button className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors" onClick={(e) => { e.stopPropagation(); setIdx(i => (i - 1 + photos.length) % photos.length); }}>
                  <ChevronLeft className="w-6 h-6" />
                </button>
                <button className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors" onClick={(e) => { e.stopPropagation(); setIdx(i => (i + 1) % photos.length); }}>
                  <ChevronRight className="w-6 h-6" />
                </button>
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-xs px-2 py-0.5 rounded-full backdrop-blur-sm">
                  {idx + 1} / {photos.length}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="text-slate-700 dark:text-white/60 text-sm font-medium">Tidak ada foto</div>
        )}
      </div>

      {/* Info panel */}
      <div className="w-full max-w-4xl px-4 pb-4 pt-2" onClick={(e) => e.stopPropagation()}>
        <div className="bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-xl p-3 border border-white/50 dark:border-white/15 shadow-xl">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0 space-y-1.5">
              <h3 className="text-slate-900 dark:text-white font-semibold text-sm truncate">{a.name || "Tanpa Nama"}</h3>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-700 dark:text-white/80">
                {a.asset_code && <span className="flex items-center gap-0.5"><QrCode className="w-3 h-3" /> {a.asset_code}</span>}
                {a.nup && <span>NUP: {a.nup}</span>}
                {a.location && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" /> {a.location}</span>}
                {a.category && <span className="flex items-center gap-0.5"><Tag className="w-3 h-3" /> {a.category}</span>}
                {a.person_responsible && <span className="flex items-center gap-0.5"><User className="w-3 h-3" /> {a.person_responsible}</span>}
                {price && <span className="font-semibold text-emerald-700 dark:text-emerald-300">{price}</span>}
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {a.condition && <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.condition === 'Baik' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/50 dark:text-emerald-100' : a.condition === 'Rusak Ringan' ? 'bg-amber-100 text-amber-700 dark:bg-amber-600/50 dark:text-amber-100' : 'bg-red-100 text-red-700 dark:bg-red-600/50 dark:text-red-100'}`}>{a.condition}</span>}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${invStatus === 'Ditemukan' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/40 dark:text-emerald-200' : invStatus === 'Tidak Ditemukan' ? 'bg-red-100 text-red-700 dark:bg-red-600/40 dark:text-red-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-600/40 dark:text-slate-200'}`}>{invStatus}</span>
                {docTotal > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5 font-medium ${docChecked === docTotal ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/40 dark:text-emerald-200' : 'bg-amber-100 text-amber-700 dark:bg-amber-600/40 dark:text-amber-200'}`}>
                    {docChecked === docTotal ? <FileCheck className="w-2.5 h-2.5" /> : <FileX className="w-2.5 h-2.5" />}
                    Dok {docChecked}/{docTotal}
                  </span>
                )}
                {a.stiker_status && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.stiker_status === 'Sudah Terpasang' ? 'bg-violet-100 text-violet-700 dark:bg-violet-600/40 dark:text-violet-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-600/40 dark:text-slate-200'}`}>
                    <StickyNote className="w-2.5 h-2.5 inline mr-0.5" />
                    {a.stiker_status === 'Sudah Terpasang' ? 'Stiker ✓' : 'Stiker ✗'}
                  </span>
                )}
              </div>
            </div>
            {onEdit && (
              <button
                className="flex-shrink-0 text-xs bg-blue-500/80 hover:bg-blue-600 text-white px-3 py-1.5 rounded-lg transition-colors"
                onClick={(e) => { e.stopPropagation(); onClose(); onEdit(a); }}
              >
                Edit
              </button>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
});
Lightbox.displayName = "Lightbox";

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
        <Lightbox asset={lightboxAsset} onClose={closeLightbox} onEdit={onEdit} />
      )}
    </TooltipProvider>
  );
});
AssetGalleryView.displayName = "AssetGalleryView";

export default AssetGalleryView;
