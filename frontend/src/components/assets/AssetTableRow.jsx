import React, { memo, useRef, useState, useEffect } from "react";
import { Camera, Briefcase, MapPin, Tag, CreditCard, Trash2, ShieldCheck, RefreshCcw, Check } from "lucide-react";
import { sisaGaransi } from "../../lib/garansi";
import { useSinkronSiman } from "../../lib/simanSync";
import { Button } from "../ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "../ui/tooltip";

// ============================================================================
// TRUNCATED TEXT WITH TOOLTIP - Shows tooltip only when text is truncated
// ============================================================================
const TruncatedText = memo(({ text, maxWidth = "80px", className = "", icon: Icon = null }) => {
  const textRef = useRef(null);
  const [isTruncated, setIsTruncated] = useState(false);

  useEffect(() => {
    const checkTruncation = () => {
      if (textRef.current) {
        setIsTruncated(textRef.current.scrollWidth > textRef.current.clientWidth);
      }
    };
    checkTruncation();
    window.addEventListener('resize', checkTruncation);
    return () => window.removeEventListener('resize', checkTruncation);
  }, [text]);

  if (!text) return <span className="text-xs text-muted-foreground">-</span>;

  const content = (
    <span className={`flex items-center gap-1 ${className}`}>
      {Icon && <Icon className="w-3 h-3 text-muted-foreground flex-shrink-0" />}
      <span ref={textRef} className="truncate" style={{ maxWidth }}>{text}</span>
    </span>
  );

  if (isTruncated) {
    return (
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          {content}
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[300px] text-wrap bg-slate-800 text-white">
          <p>{text}</p>
        </TooltipContent>
      </Tooltip>
    );
  }

  return content;
});
TruncatedText.displayName = "TruncatedText";

// ============================================================================
// TABLE ROW - photo fills row height precisely, fixed alignment for PC
// OPTIMIZED: Only uses thumbnail from API (photos are lazy-loaded when editing)
// ENHANCED: Tooltip on truncated text when hovering
// ============================================================================
const AssetTableRow = memo(({ asset, editId, onEdit, onDelete, onPrintCard }) => {
  // Use thumbnail only (photos array is not included in list API for performance)
  const coverPhoto = asset.thumbnail;
  const hasPhoto = coverPhoto && coverPhoto.length > 10;
  const stikerTerpasang = asset.stiker_status === "Sudah Terpasang";
  const { busy: simanBusy, synced: simanSynced, sinkron: sinkronSiman } = useSinkronSiman(asset);
  
  // Format price
  const formatPrice = (price) => {
    if (!price) return '-';
    const num = typeof price === 'string' ? parseFloat(price) : price;
    if (isNaN(num)) return '-';
    return num.toLocaleString('id-ID');
  };
  
  return (
    // Belum tersinkron SIMAN: gradasi orange halus dari pojok kiri-bawah ke
    // atas (pengganti badge teks) — cukup terlihat tanpa mencolok.
    <tr onClick={() => onEdit(asset)}
      title={asset.siman?.status === "selisih" && !simanSynced ? "Data berbeda dengan SIMAN V2 — klik ikon di samping NUP untuk sinkronkan" : undefined}
      style={asset.siman?.status === "selisih" && !simanSynced ? { backgroundImage: "linear-gradient(to top right, rgba(245,158,11,0.14), rgba(245,158,11,0.04) 45%, transparent 70%)" } : undefined}
      className={`hover:bg-blue-50/50 transition-colors cursor-pointer border-b border-border ${editId === asset.id ? "bg-amber-50 border-l-2 border-l-amber-400" : ""}`}>
      <td className="px-1 py-1 w-[60px] align-middle">
        <div className="w-[52px] h-[52px] rounded overflow-hidden bg-muted flex items-center justify-center flex-shrink-0">
          {hasPhoto ? (
            <img src={coverPhoto} alt="" className="w-full h-full object-cover" loading="lazy" />
          ) : (
            <Camera className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </td>
      <td className="px-2 py-1 align-middle">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-sm text-foreground leading-tight">{asset.asset_code}</span>
          {asset.NUP && (
            <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded font-medium">
              NUP {asset.NUP}
            </span>
          )}
          {/* Sinkron SIMAN tepat di samping kotak NUP — ukuran mengikuti
              kotak NUP; klik = langsung terapkan nilai SIMAN V2. */}
          {asset.siman?.status === "selisih" && !simanSynced && (
            <button
              type="button"
              onClick={sinkronSiman}
              disabled={simanBusy}
              className="min-w-0 min-h-0 inline-flex items-center justify-center px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/40 text-amber-600 dark:text-amber-400 hover:bg-amber-500/30 transition-colors"
              title="Belum tersinkron dengan SIMAN V2 — klik untuk sinkronkan sekarang"
              aria-label="Sinkronkan dengan SIMAN V2"
              data-testid={`row-siman-${asset.id}`}
            >
              <RefreshCcw className={`w-3 h-3 ${simanBusy ? "animate-spin" : ""}`} />
            </button>
          )}
          {simanSynced && (
            <span
              className="inline-flex items-center justify-center px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/40 text-emerald-600 dark:text-emerald-400"
              title="Tersinkron dengan SIMAN V2"
              data-testid={`row-siman-ok-${asset.id}`}
            >
              <Check className="w-3 h-3" />
            </span>
          )}
        </div>
        <TruncatedText text={asset.asset_name} maxWidth="180px" className="text-xs text-muted-foreground" />
      </td>
      <td className="px-2 py-1 text-sm align-middle max-w-[150px]">
        <TruncatedText text={asset.category} maxWidth="140px" className="text-sm text-foreground" />
      </td>
      <td className="px-2 py-1 align-middle">
        <TruncatedText text={asset.eselon1 ? `${asset.eselon1}${asset.eselon2 ? ' / '+asset.eselon2 : ''}` : ''} maxWidth="100px" className="text-sm text-foreground" icon={Briefcase} />
      </td>
      <td className="px-2 py-1 align-middle">
        <TruncatedText text={asset.location} maxWidth="100px" className="text-sm text-foreground" icon={MapPin} />
      </td>
      <td className="px-2 py-1 align-middle text-right">
        <span className="text-sm text-foreground font-medium whitespace-nowrap">
          {formatPrice(asset.purchase_price)}
        </span>
      </td>
      <td className="px-2 py-1 align-middle">
        <div className="flex flex-col gap-0.5 items-start">
          <span className={`badge text-xs ${asset.condition === "Baik" ? "badge-success" : asset.condition === "Rusak Ringan" ? "badge-warning" : "badge-error"}`}>{asset.condition || '-'}</span>
          {(() => {
            const g = sisaGaransi(asset.garansi_hingga);
            return g ? (
              <span className={`inline-flex items-center gap-0.5 px-1 py-0.5 rounded-full text-[9px] font-bold ${g.segera ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"}`}
                title={`Garansi${asset.garansi_jenis ? ` ${asset.garansi_jenis}` : ""} hingga ${g.hingga} (${g.hari} hari lagi)`}>
                <ShieldCheck className="w-2.5 h-2.5" />{g.singkat}
              </span>
            ) : null;
          })()}
        </div>
      </td>
      <td className="px-2 py-1 align-middle">
        <span className={`badge text-xs ${
          asset.status === "Aktif" ? "badge-success" :
          asset.status === "Idle" ? "badge-info" :
          asset.status === "Maintenance" ? "badge-warning" :
          "badge-error"
        }`}>{asset.status}</span>
      </td>
      <td className="px-2 py-1 align-middle">
        <div className="flex flex-col gap-0.5">
          <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${stikerTerpasang ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'}`}>
            <Tag className="w-2.5 h-2.5" />
            {stikerTerpasang ? 'Terpasang' : 'Belum'}
          </span>
          {stikerTerpasang && asset.stiker_ukuran && (
            <span className="text-[9px] text-muted-foreground pl-0.5">{asset.stiker_ukuran}</span>
          )}
        </div>
      </td>
      <td className="px-2 py-1 align-middle">
        {/* Document count not shown in list (lazy loaded) */}
      </td>
      <td className="px-2 py-1 align-middle">
        <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full whitespace-nowrap ${
          asset.inventory_status === "Ditemukan" ? 'bg-emerald-100 text-emerald-700' : 
          asset.inventory_status === "Tidak Ditemukan" ? 'bg-red-100 text-red-700' : 
          asset.inventory_status === "Berlebih" ? 'bg-purple-100 text-purple-700' :
          asset.inventory_status === "Sengketa" ? 'bg-rose-100 text-rose-700' :
          'bg-muted text-muted-foreground'
        }`}>
          {asset.inventory_status === "Ditemukan" ? '✓ Ditemukan' : 
           asset.inventory_status === "Tidak Ditemukan" ? '✗ Tidak Ditemukan' : 
           asset.inventory_status === "Berlebih" ? '⊕ Berlebih' :
           asset.inventory_status === "Sengketa" ? '⚖ Sengketa' :
           'Belum'}
        </span>
      </td>
      <td className="px-2 py-1 text-right align-middle" onClick={e => e.stopPropagation()}>
        <div className="flex gap-0.5 justify-end">
          <Button variant="ghost" size="sm" onClick={() => onPrintCard(asset.id)} className="h-7 w-7 p-0 hover:bg-blue-50" title="Cetak Kartu">
            <CreditCard className="w-3.5 h-3.5 text-blue-500" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onDelete(asset.id)} className="h-7 w-7 p-0 hover:bg-red-50">
            <Trash2 className="w-3.5 h-3.5 text-red-500" />
          </Button>
        </div>
      </td>
    </tr>
  );
});
AssetTableRow.displayName = "AssetTableRow";

export default AssetTableRow;
