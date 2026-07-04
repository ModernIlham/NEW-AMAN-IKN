import React from "react";
import { Skeleton } from "../ui/skeleton";

// ============================================================================
// LIST LOADING SKELETON
// Shown over the asset list while a page-size change, page navigation,
// filter, or sort request is in flight — so the user sees the app is
// processing instead of a frozen/unchanged list.
// Solid (opaque) background: the previous page's data must NOT show through
// while the new page loads. variant="gallery" renders a card-grid skeleton
// matching the gallery layout; default renders table/list rows.
// ============================================================================

const GalleryCardSkeleton = () => (
  <div className="rounded-xl border border-border overflow-hidden">
    <Skeleton className="w-full aspect-[16/10] rounded-none" />
    <div className="p-2 space-y-1.5">
      <Skeleton className="h-3 w-[80%]" />
      <Skeleton className="h-3 w-[55%]" />
      <Skeleton className="h-3 w-[40%]" />
    </div>
    <div className="flex items-center justify-around border-t border-border px-2 py-1.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-3.5 w-3.5 rounded" />
      ))}
    </div>
  </div>
);

const ListLoadingSkeleton = ({ rows = 10, message = "", variant = "list" }) => (
  <div
    className="absolute inset-0 z-10 bg-background rounded-lg p-2 overflow-hidden"
    data-testid="list-loading-skeleton"
    aria-busy="true"
    aria-live="polite"
  >
    <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
      <span className="w-3.5 h-3.5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
      <span>{message || "Memuat data..."}</span>
    </div>
    {variant === "gallery" ? (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 sm:gap-3">
        {Array.from({ length: Math.min(rows, 10) }).map((_, i) => (
          <GalleryCardSkeleton key={i} />
        ))}
      </div>
    ) : (
      <div className="space-y-2">
        <Skeleton className="h-8 w-full" />
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-2">
            <Skeleton className="h-9 w-9 rounded-lg flex-shrink-0" />
            <div className="flex-1 space-y-1.5 min-w-0">
              <Skeleton className="h-3 w-[60%]" />
              <Skeleton className="h-3 w-[35%]" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full hidden sm:block" />
            <Skeleton className="h-5 w-12 rounded-full hidden lg:block" />
          </div>
        ))}
      </div>
    )}
  </div>
);

export default ListLoadingSkeleton;
