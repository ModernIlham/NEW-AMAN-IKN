import React, { memo, useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Loader2, X, ChevronLeft, ChevronRight, MapPin, Tag, User, QrCode, FileCheck, FileX, StickyNote, Download } from "lucide-react";
import { authMediaUrl } from "../../lib/mediaUrl";
import { peekAnim } from "../../lib/lightboxAnim";
import { useBackGuard } from "../../hooks/useBackGuard";
import { toast } from "sonner";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatPrice = (p) => {
  if (!p) return null;
  const num = typeof p === "string" ? parseFloat(p) : p;
  return isNaN(num) ? null : `Rp ${num.toLocaleString("id-ID")}`;
};

// Bangun URL foto (varian tajam w=1280) + thumbnail kecil dari data aset yang
// SUDAH di tangan — baris peta / kartu galeri sudah membawa photo_count +
// version. Dipakai agar foto MULAI dimuat SEKETIKA tanpa menunggu round-trip
// /assets/{id} (penyebab "loading lama walau fotonya sudah ada").
function buildPhotoUrls(src) {
  const id = src?.id;
  const count = Number(src?.photo_count) || 0;
  const version = Number(src?.version) || 1;
  if (id && count > 0) {
    return {
      count, version,
      photos: Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${id}/photos/${i}?v=${version}&w=1280`)),
      thumbs: Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${id}/photos/${i}?v=${version}&thumb=1`)),
    };
  }
  const uri = src?.thumbnail ? [src.thumbnail] : []; // fallback data-URI (cover legacy)
  return { count: uri.length, version, photos: uri, thumbs: uri };
}

// ============================================================================
// LIGHTBOX - Photo gallery with full asset info
// Dipakai bersama oleh galeri (AssetGalleryView) dan popup marker peta
// (AssetMapFullView) — supaya pengalaman "buka foto" identik di kedua tempat.
// ============================================================================
const Lightbox = memo(({ asset, onClose, onEdit, siblings = null, onSelectAsset = null }) => {
  // Foto diseed SEKETIKA dari data aset yang diklik (peta/galeri sudah bawa
  // photo_count + version) supaya <img> mulai memuat langsung — bukan setelah
  // round-trip metadata. `builtRef` mengingat jumlah/versi terakhir yang
  // dipakai membangun URL agar hasil fetch tak mengganti array foto bila tak
  // berubah (array baru → efek imgLoading menyala → kedip cepat).
  const seed = useRef(null);
  if (seed.current === null) seed.current = buildPhotoUrls(asset);
  const [fullAsset, setFullAsset] = useState(null);
  const [photos, setPhotos] = useState(seed.current.photos);
  const [thumbs, setThumbs] = useState(seed.current.thumbs); // placeholder kecil per-foto (instan)
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(seed.current.photos.length === 0);
  // Mulai dalam keadaan "memuat" bila ada foto (varian tajam w=1280 belum
  // ter-cache) → langsung tampil placeholder blur + spinner, bukan berkedip
  // dari foto tajam-lalu-hilang saat efek menyalakan loading.
  const [imgLoading, setImgLoading] = useState(seed.current.photos.length > 0);
  const startX = useRef(0);
  const builtRef = useRef({ count: seed.current.count, version: seed.current.version });
  const [downloading, setDownloading] = useState(false);

  // Navigasi antar-ASET (bukan antar-foto): geser/klik pada kartu info → aset
  // sebelum/sesudah sesuai urutan & filter aktif (daftar `siblings` dari
  // pemanggil). Optional — bila tak diberi siblings, fitur ini nonaktif mulus.
  const sibIndex = (siblings && asset) ? siblings.findIndex((s) => s?.id === asset.id) : -1;
  const hasPrevAsset = sibIndex > 0;
  const hasNextAsset = sibIndex >= 0 && sibIndex < siblings.length - 1;
  const goAsset = useCallback((dir) => {
    if (!siblings || !onSelectAsset || sibIndex < 0) return;
    const ni = sibIndex + dir;
    if (ni < 0 || ni >= siblings.length) return;
    onSelectAsset(siblings[ni]);
  }, [siblings, onSelectAsset, sibIndex]);

  // Geser kartu info: umpan balik drag + snap; lepas melewati ambang → pindah
  // aset. stopPropagation agar TIDAK ikut memicu geser-foto pada overlay.
  const infoStartX = useRef(null);
  const [infoDragX, setInfoDragX] = useState(0);
  const onInfoTouchStart = useCallback((e) => { e.stopPropagation(); infoStartX.current = e.touches[0].clientX; }, []);
  const onInfoTouchMove = useCallback((e) => {
    e.stopPropagation();
    if (infoStartX.current == null) return;
    let dx = e.touches[0].clientX - infoStartX.current;
    if ((dx > 0 && !hasPrevAsset) || (dx < 0 && !hasNextAsset)) dx *= 0.25; // redam bila mentok
    setInfoDragX(Math.max(-120, Math.min(120, dx)));
  }, [hasPrevAsset, hasNextAsset]);
  const onInfoTouchEnd = useCallback((e) => {
    e.stopPropagation();
    const dx = infoStartX.current == null ? 0 : e.changedTouches[0].clientX - infoStartX.current;
    infoStartX.current = null;
    setInfoDragX(0);
    if (Math.abs(dx) > 60) { if (dx > 0) goAsset(-1); else goAsset(1); }
  }, [goAsset]);

  // Unduh foto ASLI (resolusi penuh) — yang tampil hanya varian preview w=1280.
  const downloadOriginal = useCallback(async () => {
    const cur = fullAsset || asset;
    const id = cur?.id;
    if (!id) return;
    setDownloading(true);
    try {
      const url = authMediaUrl(`${API}/assets/${id}/photos/${idx}?v=${builtRef.current.version}`); // tanpa w → asli
      const res = await axios.get(url, { responseType: "blob" });
      const type = res.data?.type || "";
      const ext = type.includes("png") ? "png" : type.includes("webp") ? "webp" : "jpg";
      const blobUrl = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `${(cur.asset_code || cur.NUP || id)}_foto-${idx + 1}.${ext}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1500);
    } catch {
      toast.error("Gagal mengunduh foto asli");
    } finally {
      setDownloading(false);
    }
  }, [fullAsset, asset, idx]);

  useEffect(() => {
    if (!asset?.id) return undefined;
    // Aset berganti (mis. dari galeri) → seed ulang foto. Pada MOUNT pertama
    // state sudah diseed via useState di atas, jadi lewati agar tak set ulang
    // (yang memicu kedip). w=1280: varian preview tajam (~100-250KB), di-resize
    // & di-cache server sekali (ETag/Cache-Control tetap berlaku).
    const init = buildPhotoUrls(asset);
    if (init.count !== builtRef.current.count || init.version !== builtRef.current.version) {
      builtRef.current = { count: init.count, version: init.version };
      setPhotos(init.photos);
      setThumbs(init.thumbs);
      setIdx(0);
      setLoading(init.photos.length === 0);
    }
    setFullAsset(asset);
    // Fetch ringan (tanpa base64) HANYA untuk memperkaya panel info +
    // rekonsiliasi jumlah/versi. Foto sudah tampil; array hanya dibangun ulang
    // bila jumlah/versi BERBEDA — sehingga tak me-reset foto yang sedang dimuat.
    let alive = true;
    axios.get(`${API}/assets/${asset.id}?exclude_media=true`)
      .then(r => {
        if (!alive) return;
        const data = r.data;
        setFullAsset(data);
        const c = Number(data.photo_count) || 0;
        const v = Number(data.version) || 1;
        if (c !== builtRef.current.count || v !== builtRef.current.version) {
          const next = buildPhotoUrls({ ...asset, photo_count: c, version: v });
          builtRef.current = { count: next.count, version: next.version };
          setPhotos(next.photos);
          setThumbs(next.thumbs);
          setIdx(i => Math.min(i, Math.max(0, next.photos.length - 1)));
        }
      })
      .catch(() => { /* tampilan awal dari data asset tetap dipakai */ })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [asset?.id, asset?.thumbnail]);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setIdx(i => (i - 1 + photos.length) % photos.length);
      if (e.key === "ArrowRight") setIdx(i => (i + 1) % photos.length);
      // ↑/↓ = pindah antar-ASET (bila daftar siblings tersedia)
      if (e.key === "ArrowUp") goAsset(-1);
      if (e.key === "ArrowDown") goAsset(1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [photos.length, onClose, goAsset]);

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

  // Preload DINI foto pertama + thumbnail aset TETANGGA (sebelum & sesudah)
  // sesuai urutan/filter aktif — sehingga pindah antar-aset terasa instan &
  // seamless (gambar tujuan sudah di cache saat kartu berganti). Baris
  // peta/galeri sudah membawa photo_count+version, jadi URL bisa dibangun
  // tanpa round-trip.
  useEffect(() => {
    if (!siblings || sibIndex < 0) return undefined;
    const imgs = [];
    [sibIndex - 1, sibIndex + 1].forEach((i) => {
      if (i < 0 || i >= siblings.length) return;
      const built = buildPhotoUrls(siblings[i]);
      if (built.thumbs[0]) { const t = new Image(); t.src = built.thumbs[0]; imgs.push(t); }
      if (built.photos[0]) { const im = new Image(); im.src = built.photos[0]; imgs.push(im); }
    });
    return () => { imgs.forEach((im) => { im.src = ""; }); };
  }, [siblings, sibIndex]);

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
  // Parameter animasi geser kartu info (opacity peek + skala kartu depan).
  const anim = peekAnim(infoDragX);

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
        {/* Unduh foto ASLI (resolusi penuh) — ikon di lingkaran gelap semi-
            transparan + cincin putih agar kontras di light/dark & di atas warna
            foto apa pun. Yang tampil hanya varian preview (w=1280). */}
        {!loading && photos.length > 0 && (
          <button
            onClick={(e) => { e.stopPropagation(); downloadOriginal(); }}
            disabled={downloading}
            title="Unduh foto asli (resolusi penuh)"
            aria-label="Unduh foto asli"
            className="absolute left-2 top-2 z-10 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors disabled:opacity-70"
            data-testid="lightbox-download"
          >
            {downloading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Download className="w-5 h-5" />}
          </button>
        )}
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

      {/* Info panel — GESER kiri/kanan untuk PINDAH ANTAR-ASET sesuai urutan/
          filter aktif (tanpa tombol panah — cukup swipe); FOTO tak ikut tergeser. */}
      <div className="w-full max-w-4xl px-4 pb-4 pt-2" onClick={(e) => e.stopPropagation()}>
        <div className="relative" onTouchStart={onInfoTouchStart} onTouchMove={onInfoTouchMove} onTouchEnd={onInfoTouchEnd}>
          {/* Peek kartu tetangga: mulai SAMAR (petunjuk bisa digeser antar-aset),
              opacity BERTAMBAH mengikuti geseran ke sisi itu (peekAnim) → kartu
              berikut/sebelumnya "muncul" makin jelas seiring jempol menggeser. */}
          {hasNextAsset && <div aria-hidden="true" style={{ opacity: anim.nextOpacity, transition: infoDragX ? "none" : "opacity 0.2s" }} className="absolute inset-y-2 left-10 -right-2 rounded-xl bg-white/70 dark:bg-slate-700/70 border border-white/40 dark:border-white/10 shadow-lg" />}
          {hasPrevAsset && <div aria-hidden="true" style={{ opacity: anim.prevOpacity, transition: infoDragX ? "none" : "opacity 0.2s" }} className="absolute inset-y-2 right-10 -left-2 rounded-xl bg-white/70 dark:bg-slate-700/70 border border-white/40 dark:border-white/10 shadow-lg" />}
          <div
            className="relative bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-xl p-3 border border-white/50 dark:border-white/15 shadow-xl"
            style={{ transform: infoDragX ? `translateX(${infoDragX}px) scale(${anim.frontScale})` : undefined, transition: infoDragX ? "none" : "transform 0.2s" }}
          >
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
            {sibIndex >= 0 && siblings.length > 1 && (
              <div className="mt-2 text-center text-[10px] text-slate-500 dark:text-white/50">
                Aset {sibIndex + 1} / {siblings.length} · geser untuk pindah aset
              </div>
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
