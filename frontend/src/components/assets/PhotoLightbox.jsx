import React, { memo, useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Loader2, X, ChevronLeft, ChevronRight, MapPin, Tag, User, QrCode, FileCheck, FileX, StickyNote } from "lucide-react";
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
// Dipakai bersama oleh galeri (AssetGalleryView) dan popup marker peta
// (AssetMapFullView) — supaya pengalaman "buka foto" identik di kedua tempat.
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
              <h3 className="text-slate-900 dark:text-white font-semibold text-sm truncate">{a.name || a.asset_name || "Tanpa Nama"}</h3>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-700 dark:text-white/80">
                {a.asset_code && <span className="flex items-center gap-0.5"><QrCode className="w-3 h-3" /> {a.asset_code}</span>}
                {(a.nup || a.NUP) && <span>NUP: {a.nup || a.NUP}</span>}
                {a.location && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" /> {a.location}</span>}
                {a.category && <span className="flex items-center gap-0.5"><Tag className="w-3 h-3" /> {a.category}</span>}
                {(a.person_responsible || a.user) && <span className="flex items-center gap-0.5"><User className="w-3 h-3" /> {a.person_responsible || a.user}</span>}
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

export default Lightbox;
