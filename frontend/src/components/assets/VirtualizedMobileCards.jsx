import React, { memo, useRef, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";
import AssetMobileCard from "./AssetMobileCard";

// ============================================================================
// MOBILE INFINITE SCROLL CARDS - Auto loads more when scrolling to bottom
// ============================================================================
const VirtualizedMobileCards = memo(({ 
  assets, 
  editId, 
  onEdit, 
  onDelete, 
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
  const observerRef = useRef(null);
  const loadMoreRef = useRef(null);
  
  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!onLoadMore) return;
    
    const options = {
      root: null,
      rootMargin: '100px',
      threshold: 0.1
    };
    
    observerRef.current = new IntersectionObserver((entries) => {
      const [entry] = entries;
      if (entry.isIntersecting && hasMore && !isLoadingMore) {
        onLoadMore();
      }
    }, options);
    
    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }
    
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [onLoadMore, hasMore, isLoadingMore]);

  return (
    <div className="space-y-0">
      {/* Asset Cards */}
      {assets.map((asset) => {
        const lock = rowLocks[asset.id];
        const isLockedByOther = lock && lock.session_id !== currentSessionId;
        return (
          <AssetMobileCard 
            key={asset.id}
            asset={asset} 
            editId={editId} 
            onEdit={isLockedByOther ? undefined : onEdit} 
            onDelete={isLockedByOther ? undefined : onDelete}
            lockedBy={isLockedByOther ? lock.user_name : null}
            syncStatus={syncStatuses[asset.id]}
            onRetrySync={onRetrySync}
            onDismissSync={onDismissSync}
            selected={selectedAssets?.has(asset.id)}
            onToggleSelect={onToggleSelect ? () => onToggleSelect(asset.id) : undefined}
          />
        );
      })}
      
      {/* Load More Trigger & Indicator */}
      <div ref={loadMoreRef} className="py-4">
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
    </div>
  );
});
VirtualizedMobileCards.displayName = "VirtualizedMobileCards";

export default VirtualizedMobileCards;
