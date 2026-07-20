import React, { memo, useState, useCallback } from "react";
import { Camera, MapPin, Tag, Images, User, QrCode, CreditCard, Trash2, FileCheck, FileX, Calendar, Lock, ClipboardCheck, Building2, ImageIcon, FileText, ShieldCheck, RefreshCcw as RefreshCcwIcon, Check as CheckIcon } from "lucide-react";
import {
  Tooltip, TooltipContent, TooltipTrigger,
} from "../ui/tooltip";
import { authMediaUrl } from "../../lib/mediaUrl";
import { sisaGaransi } from "../../lib/garansi";
import { useSinkronSiman } from "../../lib/simanSync";
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COND = { "Baik": "bg-emerald-500", "Rusak Ringan": "bg-amber-500", "Rusak Berat": "bg-red-500" };

const INV_STATUS = {
  "Ditemukan": { cls: "text-emerald-600", bg: "bg-emerald-500/15", border: "border-l-emerald-500" },
  "Tidak Ditemukan": { cls: "text-red-600", bg: "bg-red-500/15", border: "border-l-red-500" },
  "Berlebih": { cls: "text-purple-600", bg: "bg-purple-500/15", border: "border-l-purple-500" },
  "Sengketa": { cls: "text-rose-600", bg: "bg-rose-500/15", border: "border-l-rose-500" },
  "Belum Diinventarisasi": { cls: "text-slate-500", bg: "bg-slate-500/10", border: "border-l-slate-400" },
};

const formatPrice = (price) => {
  if (!price) return null;
  const num = typeof price === "string" ? parseFloat(price) : price;
  if (isNaN(num)) return null;
  return `Rp ${num.toLocaleString("id-ID")}`;
};

const extractYear = (dateStr) => {
  if (!dateStr) return null;
  const match = String(dateStr).match(/(\d{4})/);
  return match ? match[1] : null;
};

const AssetGalleryCard = memo(({ asset, isEditing, onEdit, onDelete, onPrintCard, onOpenLightbox, isSelected, onToggleSelect, isLockedByOther, lockedByName }) => {
  const invInfo = INV_STATUS[asset.inventory_status] || INV_STATUS["Belum Diinventarisasi"];
  const stikerOk = asset.stiker_status === "Sudah Terpasang";
  const price = formatPrice(asset.purchase_price);
  const photoCount = asset.photo_count || asset.photos?.length || 0;
  const year = extractYear(asset.purchase_date);
  const [hovered, setHovered] = useState(false);
  // Sinkronisasi SIMAN langsung dari kartu galeri (liquid): logika bersama
  // di lib/simanSync.js — sukses → cairan terserap beranimasi.
  const { busy: simanBusy, synced: simanSynced, baruSaja: simanBaruSaja, sinkron: sinkronSiman } = useSinkronSiman(asset);
  // Foto sampul galeri via STREAMING ?w=256 (ter-cache browser + server) —
  // base64 gallery_thumbnail tak lagi dikirim di payload list. Fallback ke
  // data-URI lama (baris legacy/snapshot offline) lalu thumbnail 100px bila
  // streaming gagal (mis. offline tanpa cache).
  const [streamErr, setStreamErr] = useState(false);
  const legacyThumb = asset.gallery_thumbnail || asset.thumbnail;
  const streamThumb = photoCount > 0 && !String(asset.id).startsWith("temp_")
    ? authMediaUrl(`${API}/assets/${asset.id}/photos/${asset.thumbnail_index || 0}?v=${asset.version || 1}&w=256`)
    : null;
  const galleryThumb = (!streamErr && streamThumb) || legacyThumb;
  const hasPhoto = !!galleryThumb && (streamThumb ? true : galleryThumb.length > 10);

  // Open photo/document from document checklist in new tab via backend streaming endpoint
  const openDocFile = useCallback((assetId, itemIndex, type) => {
    const fileType = type === 'photo' ? 'photo' : 'document';
    const url = `${API}/assets/${assetId}/doc-file/${itemIndex}/${fileType}/0`;
    window.open(url, '_blank');
  }, []);

  const docTotal = asset.doc_total || 0;
  const docChecked = asset.doc_checked || 0;
  const docSummary = asset.doc_summary || [];
  const dokComplete = docTotal > 0 && docChecked === docTotal;
  const dokPartial = docTotal > 0 && docChecked > 0 && docChecked < docTotal;

  return (
    <div
      className={`group relative rounded-lg sm:rounded-xl overflow-hidden border-l-4 ${isEditing ? 'border-l-amber-400 border-amber-400 ring-2 ring-amber-400 bg-amber-50 dark:bg-amber-900/20' : `bg-card ${invInfo.border} border-border`} border hover:shadow-lg transition-all duration-200 flex flex-col h-full ${isSelected && !isEditing ? 'ring-2 ring-blue-500 bg-blue-50/50 dark:bg-blue-900/20' : ''} ${isLockedByOther ? 'ring-2 ring-red-400 opacity-60' : ''}`}
      data-testid={`gallery-card-${asset.id}`}
    >
      {/* Lock overlay */}
      {isLockedByOther && (
        <div className="absolute inset-0 z-20 bg-red-500/5 pointer-events-none flex items-start justify-end p-1.5">
          <span className="inline-flex items-center gap-0.5 bg-red-500/90 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full backdrop-blur-sm">
            <Lock className="w-2.5 h-2.5" />
            {lockedByName}
          </span>
        </div>
      )}

      {/* ===== PHOTO AREA (click → lightbox) ===== */}
      <div
        className="relative w-full aspect-[16/10] sm:aspect-[4/3] bg-muted overflow-hidden flex-shrink-0 cursor-pointer"
        onClick={() => { if (!isLockedByOther && hasPhoto && onOpenLightbox) onOpenLightbox(asset); }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {hasPhoto ? (
          <img
            src={galleryThumb}
            alt={asset.asset_name}
            onError={() => { if (!streamErr && streamThumb && galleryThumb === streamThumb) setStreamErr(true); }}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-1 text-muted-foreground">
            <Camera className="w-6 h-6" />
            <span className="text-[10px]">Belum ada foto</span>
          </div>
        )}

        {/* Batch select — area seleksi: <label> ber-padding lebar supaya ketuk
            di sekitar kotak = MENYELEKSI, dan onClick stopPropagation menahan
            klik agar TIDAK ikut membuka lightbox (fokus pengguna saat memilih
            adalah seleksi, bukan buka foto). */}
        {onToggleSelect && (
          <label
            className="absolute top-0 left-0 z-10 p-2 cursor-pointer"
            onClick={(e) => e.stopPropagation()}
            data-testid={`gallery-select-wrap-${asset.id}`}
          >
            <input
              type="checkbox"
              checked={!!isSelected}
              onChange={() => onToggleSelect(asset.id)}
              className="block w-5 h-5 rounded border-2 border-white/80 bg-black/30 cursor-pointer accent-blue-600"
              data-testid={`gallery-select-${asset.id}`}
            />
          </label>
        )}

        {/* SIMAN belum tersinkron: AIR satu permukaan penuh selebar kartu di
            dasar foto (pekat, warna permukaan kartu — menyatu dengan area
            informasi). Datar & tenang di pinggir; gembungan lembut bernafas
            hanya di sekitar bola; bola mengapung pelan di atasnya. Klik bola
            = sinkronkan nilai SIMAN V2; sukses = air surut beranimasi.
            CSS: .siman-air* & .siman-liquid* di index.css. */}
        {asset.siman?.status === "selisih" && !simanSynced && (
          <>
            <button
              type="button"
              onClick={sinkronSiman}
              disabled={simanBusy}
              data-busy={simanBusy ? "1" : "0"}
              title="Belum tersinkron dengan SIMAN V2 — klik untuk sinkronkan sekarang"
              aria-label="Sinkronkan dengan SIMAN V2"
              data-testid={`siman-drop-${asset.id}`}
              className="siman-liquid absolute bottom-0 left-1/2 -translate-x-1/2 z-10 w-11 h-8 flex items-end justify-center pb-px min-w-0 min-h-0"
            >
              <span className="siman-liquid-ball w-5 h-5 rounded-full bg-amber-500 dark:bg-amber-400 shadow-md ring-1 ring-black/10 dark:ring-white/15 flex items-center justify-center">
                <RefreshCcwIcon className={`w-3 h-3 text-white dark:text-amber-950 ${simanBusy ? "animate-spin" : ""}`} />
              </span>
            </button>
            <span className="siman-air" aria-hidden="true" />
            <span className="siman-air-alir" aria-hidden="true" />
            <span className="siman-air-alir2" aria-hidden="true" />
            <span className="siman-air-meniskus" aria-hidden="true" />
          </>
        )}
        {simanBaruSaja && (
          <span className="siman-liquid-sukses absolute inset-x-0 bottom-0 z-10 h-8 pointer-events-none">
            <span className="siman-air" aria-hidden="true" />
            <span className="siman-air-alir" aria-hidden="true" />
            <span className="siman-air-alir2" aria-hidden="true" />
            <span className="siman-air-meniskus" aria-hidden="true" />
            <span className="absolute bottom-px left-1/2 -translate-x-1/2 z-[10] w-5 h-5 rounded-full bg-emerald-500 dark:bg-emerald-400 shadow-md flex items-center justify-center">
              <CheckIcon className="w-3 h-3 text-white dark:text-emerald-950" />
            </span>
          </span>
        )}

        {/* Top-right badges (garansi ikut di sini — posisi bawah tertutup
            gradasi hitam + badge jumlah foto, di atas selalu terlihat) */}
        <div className="absolute top-1.5 right-1.5 z-[2] flex items-center gap-1">
          {(() => {
            const g = sisaGaransi(asset.garansi_hingga);
            return g ? (
              <span
                className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-bold text-white backdrop-blur-sm shadow-sm ${g.segera ? "bg-amber-500/90" : "bg-emerald-600/90"}`}
                title={`Garansi${asset.garansi_jenis ? ` ${asset.garansi_jenis}` : ""} hingga ${g.hingga} (${g.hari} hari lagi)`}
                data-testid={`gallery-garansi-${asset.id}`}
              >
                <ShieldCheck className="w-2.5 h-2.5" />{g.singkat}
              </span>
            ) : null;
          })()}
          {asset.condition && (
            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold text-white backdrop-blur-sm ${COND[asset.condition] || "bg-slate-500"}`}>
              {asset.condition}
            </span>
          )}
          {year && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold text-white bg-slate-800/80 backdrop-blur-sm">
              <Calendar className="w-2.5 h-2.5" />
              {year}
            </span>
          )}
        </div>

        {/* SPM hover overlay */}
        {hovered && asset.nomor_spm && (
          <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px] flex items-center justify-center z-[5] pointer-events-none">
            <div className="bg-black/70 text-white px-3 py-2 rounded-lg text-center">
              <span className="text-[9px] text-white/60 block">No. SPM</span>
              <span className="text-xs font-bold">{asset.nomor_spm}</span>
            </div>
          </div>
        )}

        {/* Bottom gradient with code/NUP */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 via-black/50 via-40% to-transparent h-2/3 pointer-events-none" />
        {/* Saat air SIMAN tampil di dasar foto, baris kode/NUP diangkat
            sedikit agar tetap terbaca di atas garis air (teks putih). */}
        <div className={`absolute bottom-0 left-0 right-0 z-[2] px-2 flex items-end justify-between pointer-events-none ${(asset.siman?.status === "selisih" && !simanSynced) || simanBaruSaja ? "pb-[13px]" : "pb-1.5"}`}>
          <div className="leading-tight pointer-events-auto">
            <Tooltip delayDuration={150}>
              <TooltipTrigger asChild>
                <span className="block text-[10px] font-extrabold text-white tracking-wide font-mono drop-shadow-lg cursor-help" onClick={e => e.stopPropagation()}>
                  {asset.asset_code}
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="text-[10px] max-w-[200px]">
                {asset.category || asset.asset_code}
              </TooltipContent>
            </Tooltip>
            {asset.NUP && <span className="block text-[9px] font-semibold text-white/90 font-mono drop-shadow">NUP: {asset.NUP}</span>}
          </div>
          {photoCount > 0 && (
            <span className="flex items-center gap-0.5 text-[9px] text-white/85 bg-black/40 backdrop-blur-sm px-1.5 py-0.5 rounded-full">
              <Images className="w-2.5 h-2.5" /> {photoCount}
            </span>
          )}
        </div>
      </div>

      {/* ===== BODY (click → edit) =====
          overflow-hidden → prevents the info rows from spilling under the
          footer border when a card has long/wrapping text.
          pb-1.5 → guarantees a visible gap between the last info row (harga)
          and the footer divider so the price never "sinks" into the edge. */}
      <div
        className="flex-1 flex flex-col px-1.5 sm:px-2 pt-1 sm:pt-2 pb-1 sm:pb-2 min-h-0 overflow-hidden cursor-pointer"
        onClick={() => { if (!isLockedByOther) onEdit?.(asset); }}
      >
        {/* Asset name */}
        <h3 className="text-[11px] sm:text-xs font-semibold text-foreground leading-snug line-clamp-2 mb-1 min-h-[1.25rem] sm:min-h-[2rem]" title={asset.asset_name}>
          {asset.asset_name || "-"}
        </h3>

        {/* Pengguna - full width, above eselon */}
        {asset.user && (
          <div className="flex items-center gap-1 mb-0.5 w-full">
            <User className="w-2.5 h-2.5 text-blue-500 flex-shrink-0" />
            <span className="text-[9px] sm:text-[10px] text-blue-600 dark:text-blue-400 truncate">{asset.user}</span>
          </div>
        )}

        {/* Eselon I/II - full width */}
        {(asset.eselon1) && (
          <div className="flex items-center gap-1 mb-0.5 w-full">
            <Building2 className="w-2.5 h-2.5 text-violet-500 flex-shrink-0" />
            <span className="text-[9px] sm:text-[10px] text-muted-foreground truncate">
              {asset.eselon1}{asset.eselon2 ? ` / ${asset.eselon2}` : ''}
            </span>
          </div>
        )}

        {/* Lokasi - full width, long range to edge */}
        {asset.location && (
          <div className="flex items-center gap-1 mb-0.5 w-full">
            <MapPin className="w-2.5 h-2.5 text-cyan-500 flex-shrink-0" />
            <span className="text-[9px] sm:text-[10px] text-muted-foreground truncate">{asset.location}</span>
          </div>
        )}

        {/* Harga (pinned to bottom by mt-auto; pt-1 + parent pb give breathing room above the divider) */}
        {price && (
          <div className="mt-auto flex items-center gap-0.5 pt-1">
            <Tag className="w-2.5 h-2.5 text-blue-500 flex-shrink-0" />
            <span className="text-[10px] sm:text-[11px] font-bold text-blue-600 dark:text-blue-400 truncate">{price}</span>
          </div>
        )}
      </div>

      {/* ===== FOOTER: Status icons + Actions (all icon-only with tooltips) =====
          overflow-hidden + min-w-0 buttons + flex-shrink-0 icons → the row stays
          tidy and the last action (Hapus) never gets clipped on small phones,
          even if a card is squeezed very narrow. */}
      <div className={`flex items-stretch justify-between gap-px overflow-hidden border-t ${isEditing ? 'border-amber-300 dark:border-amber-700' : 'border-border'} flex-shrink-0 px-0.5`}>
        {/* Status Inventarisasi */}
        <Tooltip delayDuration={150}>
          <TooltipTrigger asChild>
            <button className={`flex-1 min-w-0 min-h-0 flex items-center justify-center py-1.5 rounded-md transition-colors ${invInfo.cls}`} onClick={e => e.stopPropagation()} data-testid={`gallery-inv-${asset.id}`}>
              <ClipboardCheck className="w-3.5 h-3.5 flex-shrink-0" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="text-[10px]">Inventarisasi: {asset.inventory_status || "Belum"}</TooltipContent>
        </Tooltip>

        {/* Stiker status */}
        <Tooltip delayDuration={150}>
          <TooltipTrigger asChild>
            <button className={`flex-1 min-w-0 min-h-0 flex items-center justify-center py-1.5 rounded-md transition-colors ${stikerOk ? 'text-emerald-500' : 'text-slate-400'}`} onClick={e => e.stopPropagation()} data-testid={`gallery-stiker-${asset.id}`}>
              <QrCode className="w-3.5 h-3.5 flex-shrink-0" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="top" className="text-[10px]">Stiker: {asset.stiker_status || "Belum dipasang"}</TooltipContent>
        </Tooltip>

        {/* DOK - kelengkapan dokumen */}
        {docTotal > 0 ? (
          <Tooltip delayDuration={200}>
            <TooltipTrigger asChild>
              <button
                className={`flex-1 min-w-0 min-h-0 flex items-center justify-center py-1.5 rounded-md transition-colors ${dokComplete ? 'text-emerald-500' : dokPartial ? 'text-amber-500' : 'text-red-400'}`}
                onClick={e => e.stopPropagation()}
                data-testid={`gallery-dok-${asset.id}`}
              >
                {dokComplete ? <FileCheck className="w-3.5 h-3.5 flex-shrink-0" /> : <FileX className="w-3.5 h-3.5 flex-shrink-0" />}
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="bg-slate-900 text-white max-w-[260px] p-3" onClick={e => e.stopPropagation()}>
              <p className="text-[10px] font-bold mb-1.5">Kelengkapan Dokumen & Peralatan ({docChecked}/{docTotal})</p>
              <div className="space-y-1">
                {docSummary.map((doc, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-[10px]">
                    {doc.checked
                      ? <FileCheck className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                      : <FileX className="w-3 h-3 text-red-400 flex-shrink-0" />}
                    <span className={`flex-1 ${doc.checked ? 'text-white font-medium' : 'text-slate-400'}`}>{doc.name || "(tanpa judul)"}</span>
                    {doc.photo_count > 0 && (
                      <button
                        className="text-blue-400 hover:text-blue-300 flex-shrink-0 cursor-pointer"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); openDocFile(asset.id, i, 'photo'); }}
                        title="Buka foto"
                        data-testid={`dok-photo-${asset.id}-${i}`}
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {doc.doc_count > 0 && (
                      <button
                        className="text-orange-400 hover:text-orange-300 flex-shrink-0 cursor-pointer"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); openDocFile(asset.id, i, 'document'); }}
                        title="Buka dokumen"
                        data-testid={`dok-doc-${asset.id}-${i}`}
                      >
                        <FileText className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        ) : (
          <div className="flex-1 min-w-0 flex items-center justify-center py-1.5 text-slate-300 dark:text-slate-600">
            <FileX className="w-3.5 h-3.5 flex-shrink-0" />
          </div>
        )}

        {/* Divider */}
        <div className="w-px h-4 self-center bg-border mx-0.5 flex-shrink-0" />

        {/* Cetak Kartu */}
        {onPrintCard && (
          <Tooltip delayDuration={150}>
            <TooltipTrigger asChild>
              <button
                className="flex-1 min-w-0 min-h-0 flex items-center justify-center py-1.5 rounded-md text-muted-foreground hover:text-purple-600 hover:bg-purple-500/10 transition-colors"
                onClick={e => { e.stopPropagation(); onPrintCard(asset.id); }}
                data-testid={`gallery-card-btn-${asset.id}`}
              >
                <CreditCard className="w-3.5 h-3.5 flex-shrink-0" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-[10px]">Cetak Kartu</TooltipContent>
          </Tooltip>
        )}

        {/* Hapus */}
        {onDelete && (
          <Tooltip delayDuration={150}>
            <TooltipTrigger asChild>
              <button
                className="flex-1 min-w-0 min-h-0 flex items-center justify-center py-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 transition-colors"
                onClick={e => { e.stopPropagation(); onDelete(asset.id); }}
                data-testid={`gallery-delete-${asset.id}`}
              >
                <Trash2 className="w-3.5 h-3.5 flex-shrink-0" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top" className="text-[10px]">Hapus Aset</TooltipContent>
          </Tooltip>
        )}
      </div>
    </div>
  );
});
AssetGalleryCard.displayName = "AssetGalleryCard";

export default AssetGalleryCard;
