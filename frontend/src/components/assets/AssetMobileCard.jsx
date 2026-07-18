import React, { memo, useState, useRef } from "react";
import { Camera, MapPin, Briefcase, Tag, Trash2, Lock, Cloud, Check, RotateCcw, RefreshCcw, MoreVertical, BookOpen, History, CreditCard, AlertTriangle } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// ============================================================================
// MOBILE CARD WITH SWIPE GESTURES
// OPTIMIZED: Only uses thumbnail from API (photos are lazy-loaded when editing)
// ============================================================================
const AssetMobileCard = memo(({ asset, editId, onEdit, onDelete, onOpenKartu, onViewAudit, onPrintCard, onOpenPhoto, lockedBy, syncStatus, onRetrySync, onDismissSync, selected, onToggleSelect }) => {
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
        {...(onEdit ? {
          role: "button",
          tabIndex: 0,
          "aria-label": `Edit aset ${asset.asset_code || ''}${asset.asset_name ? ' - ' + asset.asset_name : ''}`.trim(),
          onKeyDown: (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onEdit(asset); }
          },
        } : {})}
        onTouchStart={onDelete ? handleTouchStart : undefined}
        onTouchMove={onDelete ? handleTouchMove : undefined}
        onTouchEnd={onDelete ? handleTouchEnd : undefined}
        className={`bg-card p-2.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 ${onEdit && !syncStatus?.status?.match?.(/saving/) ? 'cursor-pointer' : ''} border-y relative ${
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
          {/* Konflik versi (409): perlu tindakan manual — data server terbaru
              sudah dimuat, tinjau lalu simpan ulang atau abaikan. Tanpa banner
              ini item bentrok tak bisa ditindak dari tampilan HP. */}
          {syncStatus?.status === 'conflict' && (
            <div className="absolute top-0 left-0 right-0 bg-orange-500 text-white text-[10px] px-2 py-0.5 flex items-center gap-1 z-10">
              <AlertTriangle className="w-2.5 h-2.5" />
              <span className="flex-1">{syncStatus.error || 'Versi berbeda dari server'}</span>
              <button onClick={e => { e.stopPropagation(); onRetrySync?.(asset.id); }} className="underline text-[10px] ml-1">Tinjau</button>
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
          <div className="flex flex-col items-center gap-1 flex-shrink-0">
            {hasPhoto && onOpenPhoto ? (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); onOpenPhoto(asset); }}
                className="w-14 h-14 rounded-lg border border-border overflow-hidden bg-muted flex items-center justify-center flex-shrink-0 cursor-zoom-in active:ring-2 active:ring-blue-400 min-w-0 min-h-0"
                aria-label={`Lihat foto ${asset.asset_code || asset.asset_name || ''}`.trim()}
                data-testid={`card-photo-${asset.id}`}
              >
                <img src={coverPhoto} alt="" className="w-full h-full object-cover" loading="lazy" />
              </button>
            ) : (
              <div className="w-14 h-14 rounded-lg border border-border overflow-hidden bg-muted flex items-center justify-center flex-shrink-0">
                {hasPhoto ? <img src={coverPhoto} alt="" className="w-full h-full object-cover" loading="lazy" /> : <Camera className="w-5 h-5 text-muted-foreground" />}
              </div>
            )}
            {/* Penanda selisih SIMAN: ikon-saja di bawah foto (permintaan
                pemilik) — teks "≠ SIMAN" tidak lagi memakan ruang baris badge. */}
            {asset.siman?.status === "selisih" && (
              <span
                className="w-5 h-5 rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center"
                title="Data berbeda dengan SIMAN V2 — tinjau di Penatausahaan › Pelaporan"
                aria-label="Data berbeda dengan SIMAN V2"
                data-testid={`card-siman-${asset.id}`}
              >
                <RefreshCcw className="w-3 h-3 text-amber-600 dark:text-amber-400" />
              </span>
            )}
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
                {/* Aksi per-aset: Kartu Inventarisasi, Riwayat, Cetak Kartu.
                    Hapus TIDAK ada di menu ini di HP/tablet — hapus dilakukan
                    dengan menggeser baris (swipe). stopPropagation agar tak
                    memicu edit-on-tap / swipe. */}
                {(onOpenKartu || onViewAudit || onPrintCard) && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        onClick={(e) => e.stopPropagation()}
                        onTouchStart={(e) => e.stopPropagation()}
                        className="min-h-0 min-w-0 h-7 w-7 -mr-1 flex items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                        aria-label="Aksi lainnya"
                        data-testid={`mobile-card-actions-${asset.id}`}
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
                      {onOpenKartu && (
                        <DropdownMenuItem onClick={() => onOpenKartu(asset)} data-testid={`mobile-kartu-btn-${asset.id}`}>
                          <BookOpen className="w-4 h-4 mr-2 text-emerald-500" />Kartu Inventarisasi
                        </DropdownMenuItem>
                      )}
                      {onViewAudit && (
                        <DropdownMenuItem onClick={() => onViewAudit(asset.id, asset.asset_code)} data-testid={`mobile-audit-btn-${asset.id}`}>
                          <History className="w-4 h-4 mr-2 text-amber-500" />Riwayat
                        </DropdownMenuItem>
                      )}
                      {onPrintCard && (
                        <DropdownMenuItem onClick={() => onPrintCard(asset.id)} data-testid={`mobile-print-btn-${asset.id}`}>
                          <CreditCard className="w-4 h-4 mr-2 text-blue-500" />Cetak Kartu
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </div>
            </div>
            {/* Row 2: Category & Location — no fixed max-w caps: each item is a
                min-w-0 flex child so the full text shows while there is room,
                wraps to the next line where natural (flex-wrap), and only
                truncates when a single value exceeds the whole row width. */}
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground flex-wrap">
              <span className="truncate min-w-0">{asset.category}</span>
              {asset.location && (
                <span className="flex items-center gap-0.5 min-w-0">
                  <MapPin className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  <span className="truncate min-w-0">{asset.location}</span>
                </span>
              )}
            </div>
            {/* Row 3: Eselon, Price, Stiker — same flexible layout as row 2 */}
            <div className="flex items-center gap-2 mt-1 text-xs flex-wrap">
              {asset.eselon1 && (
                <span className="flex items-center gap-0.5 text-muted-foreground min-w-0">
                  <Briefcase className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  <span className="truncate min-w-0">{asset.eselon1}</span>
                </span>
              )}
              {priceFormatted && (
                <span className="text-blue-600 font-medium whitespace-nowrap flex-shrink-0">
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
