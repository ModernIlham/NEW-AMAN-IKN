import React, { memo, useState, useRef } from "react";
import { Camera, MapPin, Briefcase, Tag, Trash2, Lock, Cloud, Check, RotateCcw } from "lucide-react";

// ============================================================================
// MOBILE CARD WITH SWIPE GESTURES
// OPTIMIZED: Only uses thumbnail from API (photos are lazy-loaded when editing)
// ============================================================================
const AssetMobileCard = memo(({ asset, editId, onEdit, onDelete, lockedBy, syncStatus, onRetrySync, onDismissSync, selected, onToggleSelect }) => {
  const [swipeX, setSwipeX] = useState(0);
  const [startX, setStartX] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const cardRef = useRef(null);
  
  // Use thumbnail only (photos array is not included in list API for performance)
  const coverPhoto = asset.thumbnail;
  const hasPhoto = coverPhoto && coverPhoto.length > 10;
  const stikerTerpasang = asset.stiker_status === "Sudah Terpasang";
  
  // Format price
  const formatPrice = (price) => {
    if (!price) return null;
    const num = typeof price === 'string' ? parseFloat(price) : price;
    if (isNaN(num)) return null;
    return num.toLocaleString('id-ID');
  };
  
  const priceFormatted = formatPrice(asset.purchase_price);
  
  // Swipe handlers
  const handleTouchStart = (e) => {
    setStartX(e.touches[0].clientX);
    setIsSwiping(true);
  };
  
  const handleTouchMove = (e) => {
    if (!isSwiping) return;
    const currentX = e.touches[0].clientX;
    const diff = currentX - startX;
    // Limit swipe distance
    const limitedDiff = Math.max(-100, Math.min(100, diff));
    setSwipeX(limitedDiff);
  };
  
  const handleTouchEnd = () => {
    setIsSwiping(false);
    // Snap to positions
    if (swipeX < -50) {
      setSwipeX(-90); // Show delete
    } else if (swipeX > 50) {
      setSwipeX(90); // Show SPM info
    } else {
      setSwipeX(0); // Reset
    }
  };
  
  const resetSwipe = () => setSwipeX(0);
  
  // Format SPM number for display
  const formatSPM = (spm) => {
    if (!spm) return null;
    // Expected format: "02847T/621001/2024"
    const parts = spm.split('/');
    if (parts.length === 3) {
      return { code: parts[0], account: parts[1], year: parts[2] };
    }
    return { full: spm };
  };
  
  const spmData = formatSPM(asset.nomor_spm);
  
  return (
    <div className="relative overflow-hidden">
      {/* Left action - SPM Info (swipe right to reveal) */}
      <div 
        className="absolute inset-y-0 left-0 w-24 flex items-center justify-center"
        style={{ 
          background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
          transform: `translateX(${swipeX > 0 ? 0 : -100}%)`,
          opacity: swipeX > 0 ? 1 : 0,
          transition: isSwiping ? 'none' : 'all 0.3s ease'
        }}
      >
        {spmData ? (
          <div className="text-center px-2" onClick={(e) => { e.stopPropagation(); resetSwipe(); }}>
            <div className="text-[9px] text-blue-200 uppercase tracking-wider mb-0.5">No. SPM</div>
            {spmData.code ? (
              <>
                <div className="text-white font-bold text-sm leading-tight">{spmData.code}</div>
                <div className="text-blue-100 text-[10px] font-medium">{spmData.account}</div>
                <div className="text-blue-200 text-[10px]">{spmData.year}</div>
              </>
            ) : (
              <div className="text-white text-xs font-medium">{spmData.full}</div>
            )}
          </div>
        ) : (
          <div className="text-center px-2" onClick={(e) => { e.stopPropagation(); resetSwipe(); }}>
            <div className="text-blue-200 text-[10px]">Belum ada</div>
            <div className="text-white text-xs font-medium">No. SPM</div>
          </div>
        )}
      </div>
      
      {/* Right action - Delete (swipe left to reveal) - only render when onDelete is provided */}
      {onDelete && (
        <div 
          className="absolute inset-y-0 right-0 w-20 flex items-center justify-center"
          style={{ 
            background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
            transform: `translateX(${swipeX < 0 ? 0 : 100}%)`,
            opacity: swipeX < 0 ? 1 : 0,
            transition: isSwiping ? 'none' : 'all 0.3s ease'
          }}
        >
          <button 
            onClick={(e) => { e.stopPropagation(); onDelete(asset.id); }}
            className="flex flex-col items-center gap-1 text-white"
          >
            <Trash2 className="w-5 h-5" />
            <span className="text-[10px] font-medium">Hapus</span>
          </button>
        </div>
      )}
      
      {/* Main card content */}
      <div 
        ref={cardRef}
        onClick={() => swipeX === 0 && onEdit && onEdit(asset)}
        onTouchStart={onDelete ? handleTouchStart : undefined}
        onTouchMove={onDelete ? handleTouchMove : undefined}
        onTouchEnd={onDelete ? handleTouchEnd : undefined}
        className={`bg-card p-2.5 ${onEdit && !syncStatus?.status?.match?.(/saving/) ? 'cursor-pointer' : ''} border-y relative ${
          syncStatus?.status === 'failed' ? "border-rose-300 bg-rose-50/50" :
          syncStatus?.status === 'saving' ? "border-blue-200 bg-blue-50/30 dark:border-blue-800 dark:bg-blue-900/20" :
          syncStatus?.status === 'saved' ? "border-emerald-200 bg-emerald-50/20 dark:border-emerald-800 dark:bg-emerald-900/20" :
          lockedBy ? "border-red-200 bg-red-50/30 dark:border-red-800 dark:bg-red-900/20" :
          editId === asset.id ? "border-amber-300 bg-amber-50/50 dark:border-amber-700 dark:bg-amber-900/30" : "border-border"
        }`}
        style={{ 
          transform: `translateX(${swipeX}px)`,
          transition: isSwiping ? 'none' : 'transform 0.3s ease'
        }}
      >
        <div className="flex gap-2.5 items-start">
          {syncStatus?.status === 'saving' && (
            <div className="absolute top-0 left-0 right-0 bg-blue-500 text-white text-[10px] px-2 py-0.5 flex items-center gap-1 z-10">
              <Cloud className="w-2.5 h-2.5 animate-pulse" />
              <span>Menyimpan...</span>
            </div>
          )}
          {syncStatus?.status === 'saved' && (
            <div className="absolute top-0 left-0 right-0 bg-emerald-500 text-white text-[10px] px-2 py-0.5 flex items-center gap-1 z-10">
              <Check className="w-2.5 h-2.5" />
              <span>Tersimpan</span>
            </div>
          )}
          {syncStatus?.status === 'failed' && (
            <div className="absolute top-0 left-0 right-0 bg-rose-500 text-white text-[10px] px-2 py-0.5 flex items-center gap-1 z-10">
              <RotateCcw className="w-2.5 h-2.5" />
              <span className="flex-1">{syncStatus.error || 'Gagal menyimpan'}</span>
              <button onClick={e => { e.stopPropagation(); onRetrySync?.(asset.id); }} className="underline text-[10px] ml-1">Coba lagi</button>
              <button onClick={e => { e.stopPropagation(); onDismissSync?.(asset.id); }} className="ml-1 opacity-70">&times;</button>
            </div>
          )}
          {lockedBy && !syncStatus && (
            <div className="absolute top-0 left-0 right-0 bg-red-500 text-white text-[10px] px-2 py-0.5 flex items-center gap-1 z-10">
              <Lock className="w-2.5 h-2.5" />
              <span>Sedang diedit oleh {lockedBy}</span>
            </div>
          )}
          {/* Selection checkbox */}
          {onToggleSelect && (
            <div className="flex items-center mr-1" onClick={e => { e.stopPropagation(); onToggleSelect(); }}>
              <input
                type="checkbox"
                checked={selected || false}
                readOnly
                className="w-4 h-4 rounded cursor-pointer accent-blue-600"
              />
            </div>
          )}
          <div className="w-14 h-14 rounded-lg border border-border overflow-hidden bg-muted flex items-center justify-center flex-shrink-0">
            {hasPhoto ? <img src={coverPhoto} alt="" className="w-full h-full object-cover" loading="lazy" /> : <Camera className="w-5 h-5 text-muted-foreground" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-1">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-foreground text-sm truncate">{asset.asset_code}</span>
                  {asset.NUP && (
                    <span className="text-[9px] bg-muted text-muted-foreground px-1 py-0.5 rounded font-medium flex-shrink-0">
                      NUP {asset.NUP}
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate">{asset.asset_name}</div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                {/* Document count not shown (lazy loaded) */}
                <span className={`badge text-[10px] ${
                  asset.status === "Aktif" ? "badge-success" :
                  asset.status === "Idle" ? "badge-info" :
                  asset.status === "Maintenance" ? "badge-warning" :
                  "badge-error"
                }`}>{asset.status}</span>
              </div>
            </div>
            {/* Row 2: Category & Location */}
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
              <span className="truncate max-w-[120px]">{asset.category}</span>
              {asset.location && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3 text-muted-foreground" /><span className="truncate max-w-[60px]">{asset.location}</span></span>}
            </div>
            {/* Row 3: Eselon, Price, Stiker */}
            <div className="flex items-center gap-2 mt-1 text-xs flex-wrap">
              {asset.eselon1 && (
                <span className="flex items-center gap-0.5 text-muted-foreground">
                  <Briefcase className="w-3 h-3 text-muted-foreground" />
                  <span className="truncate max-w-[80px]">{asset.eselon1}</span>
                </span>
              )}
              {priceFormatted && (
                <span className="text-blue-600 font-medium">
                  Rp {priceFormatted}
                </span>
              )}
              <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${stikerTerpasang ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400' : 'bg-muted text-muted-foreground'}`}>
                <Tag className="w-2.5 h-2.5" />
                {stikerTerpasang ? `Stiker ${asset.stiker_ukuran || ''}` : 'Belum Stiker'}
              </span>
              <span className={`inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                asset.inventory_status === "Ditemukan" ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400' : 
                asset.inventory_status === "Tidak Ditemukan" ? 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400' : 
                asset.inventory_status === "Berlebih" ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-400' :
                asset.inventory_status === "Sengketa" ? 'bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-400' :
                'bg-muted text-muted-foreground'
              }`}>
                {asset.inventory_status === "Ditemukan" ? '✓ Ditemukan' : 
                 asset.inventory_status === "Tidak Ditemukan" ? '✗ Tdk Ditemukan' : 
                 asset.inventory_status === "Berlebih" ? '⊕ Berlebih' :
                 asset.inventory_status === "Sengketa" ? '⚖ Sengketa' :
                 'Blm Inventarisasi'}
              </span>
            </div>
          </div>
        </div>
        {/* Subtle swipe indicator bar */}
        <div className="absolute right-1 top-1/2 -translate-y-1/2 w-1 h-8 bg-border rounded-full opacity-40"></div>
      </div>
    </div>
  );
});
AssetMobileCard.displayName = "AssetMobileCard";

export default AssetMobileCard;
