import React, { memo, useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Loader2, X, ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import { useBackGuard } from "../../hooks/useBackGuard";
import { SKALA_MIN, jepitGeser, jarak, skalaCubit, skalaGulir, titikTengah, zoomKeTitik } from "../../lib/zoomPan";

export const FullscreenPhoto = memo(({ src, alt, rot = 0, onClose, children, requestFullscreen = true }) => {
  const containerRef = useRef(null);
  const [imgLoading, setImgLoading] = useState(true);
  // Zoom & geser TANPA tombol: gulir roda tetikus / cubit dua jari untuk
  // perbesar-perkecil, seret untuk menggeser saat sudah diperbesar. State
  // dicermin ke ref agar terbaca di listener native (non-passive) tanpa
  // memasang ulang listener tiap perubahan.
  const [view, setViewState] = useState({ scale: SKALA_MIN, tx: 0, ty: 0 });
  const viewRef = useRef(view);
  const gestureRef = useRef({ mode: "none" });
  const pannedRef = useRef(false); // menandai gestur menggeser → jangan tutup saat klik
  useBackGuard(onClose);

  const setView = useCallback((next) => { viewRef.current = next; setViewState(next); }, []);
  const resetView = useCallback(() => setView({ scale: SKALA_MIN, tx: 0, ty: 0 }), [setView]);
  // Terapkan skala+geser dengan jepit batas; skala kembali ke pas layar → nol.
  const terapkan = useCallback((scale, tx, ty) => {
    if (scale <= SKALA_MIN) { setView({ scale: SKALA_MIN, tx: 0, ty: 0 }); return; }
    const c = jepitGeser(tx, ty, scale, window.innerWidth, window.innerHeight);
    setView({ scale, tx: c.tx, ty: c.ty });
  }, [setView]);

  // Ganti foto / rotasi → kembalikan ke pas layar.
  useEffect(() => { resetView(); setImgLoading(true); }, [src, rot, resetView]);

  useEffect(() => {
    const el = containerRef.current;
    let requested = false;
    if (requestFullscreen && el && el.requestFullscreen) {
      requested = true;
      el.requestFullscreen().catch(() => { /* ditolak (mis. iOS) → overlay fixed tetap penuh layar */ });
    }
    // Keluar fullscreen via Escape/tombol sistem → tutup penampil juga.
    const onFsChange = () => { if (!document.fullscreenElement) onClose(); };
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("fullscreenchange", onFsChange);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      window.removeEventListener("keydown", onKey);
      try { if (requested && document.fullscreenElement) document.exitFullscreen?.(); } catch { /* abaikan */ }
    };
  }, [onClose, requestFullscreen]);

  // Listener native non-passive (React memasang wheel/touchmove sebagai passive
  // sehingga preventDefault tak berlaku) → pasang manual agar zoom lancar &
  // tak menggulir/zoom halaman.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const dxPusat = () => window.innerWidth / 2;
    const dyPusat = () => window.innerHeight / 2;

    const onWheel = (e) => {
      e.preventDefault();
      const cur = viewRef.current;
      const fx = e.clientX - dxPusat(), fy = e.clientY - dyPusat();
      const s = skalaGulir(cur.scale, e.deltaY);
      const t = zoomKeTitik(cur.scale, cur.tx, cur.ty, s, fx, fy);
      terapkan(s, t.tx, t.ty);
    };

    const onTouchStart = (e) => {
      pannedRef.current = false;
      const cur = viewRef.current;
      if (e.touches.length === 2) {
        const [a, b] = e.touches;
        const mid = titikTengah(a.clientX, a.clientY, b.clientX, b.clientY);
        gestureRef.current = {
          mode: "pinch",
          startDist: jarak(a.clientX, a.clientY, b.clientX, b.clientY),
          startScale: cur.scale, startTx: cur.tx, startTy: cur.ty,
          startMidX: mid.x - dxPusat(), startMidY: mid.y - dyPusat(),
        };
        e.preventDefault();
      } else if (e.touches.length === 1 && cur.scale > SKALA_MIN) {
        const t = e.touches[0];
        gestureRef.current = { mode: "pan", startX: t.clientX, startY: t.clientY, startTx: cur.tx, startTy: cur.ty };
        e.preventDefault();
      } else {
        gestureRef.current = { mode: "none" };
      }
    };

    const onTouchMove = (e) => {
      const g = gestureRef.current;
      if (g.mode === "pinch" && e.touches.length >= 2) {
        const [a, b] = e.touches;
        const d = jarak(a.clientX, a.clientY, b.clientX, b.clientY);
        const mid = titikTengah(a.clientX, a.clientY, b.clientX, b.clientY);
        const s = skalaCubit(g.startScale, g.startDist, d);
        const t1 = zoomKeTitik(g.startScale, g.startTx, g.startTy, s, g.startMidX, g.startMidY);
        const curMidX = mid.x - dxPusat(), curMidY = mid.y - dyPusat();
        pannedRef.current = true;
        terapkan(s, t1.tx + (curMidX - g.startMidX), t1.ty + (curMidY - g.startMidY));
        e.preventDefault();
      } else if (g.mode === "pan" && e.touches.length === 1) {
        const t = e.touches[0];
        pannedRef.current = true;
        terapkan(viewRef.current.scale, g.startTx + (t.clientX - g.startX), g.startTy + (t.clientY - g.startY));
        e.preventDefault();
      }
    };

    const onTouchEnd = (e) => {
      if (e.touches.length === 0) {
        if (viewRef.current.scale <= SKALA_MIN) resetView();
        gestureRef.current = { mode: "none" };
      } else if (e.touches.length === 1) {
        // Satu jari terlepas dari cubit → lanjutkan sebagai geser bila diperbesar.
        const t = e.touches[0];
        const cur = viewRef.current;
        gestureRef.current = cur.scale > SKALA_MIN
          ? { mode: "pan", startX: t.clientX, startY: t.clientY, startTx: cur.tx, startTy: cur.ty }
          : { mode: "none" };
      }
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("touchstart", onTouchStart, { passive: false });
    el.addEventListener("touchmove", onTouchMove, { passive: false });
    el.addEventListener("touchend", onTouchEnd);
    el.addEventListener("touchcancel", onTouchEnd);
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
      el.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [terapkan, resetView]);

  // Seret tetikus (desktop) untuk menggeser saat sudah diperbesar.
  const onMouseDown = useCallback((e) => {
    const cur = viewRef.current;
    if (cur.scale <= SKALA_MIN) return;
    e.preventDefault();
    pannedRef.current = false;
    const startX = e.clientX, startY = e.clientY, startTx = cur.tx, startTy = cur.ty;
    const move = (ev) => {
      pannedRef.current = true;
      terapkan(viewRef.current.scale, startTx + (ev.clientX - startX), startTy + (ev.clientY - startY));
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }, [terapkan]);

  // Klik-ganda: sudah diperbesar → kembali pas layar; pas layar → perbesar ke titik.
  const onDoubleClick = useCallback((e) => {
    e.stopPropagation();
    const cur = viewRef.current;
    if (cur.scale > SKALA_MIN) { resetView(); return; }
    const fx = e.clientX - window.innerWidth / 2, fy = e.clientY - window.innerHeight / 2;
    const t = zoomKeTitik(SKALA_MIN, 0, 0, 2.5, fx, fy);
    terapkan(2.5, t.tx, t.ty);
  }, [resetView, terapkan]);

  const onContainerClick = useCallback(() => {
    if (pannedRef.current) { pannedRef.current = false; return; } // habis menggeser → jangan tutup
    onClose();
  }, [onClose]);

  const swapped = rot % 180 === 90; // 90°/270° → tinggi↔lebar bertukar
  const zoomed = view.scale > SKALA_MIN;
  return createPortal(
    <div
      ref={containerRef}
      className="fixed inset-0 z-[150] bg-black flex items-center justify-center overflow-hidden"
      onClick={onContainerClick}
      style={{ touchAction: "none" }}
      role="dialog" aria-modal="true" aria-label="Pratinjau foto"
      data-testid="lightbox-fullscreen-view"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        title="Tutup layar penuh"
        aria-label="Tutup layar penuh"
        className="absolute top-3 right-3 z-10 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors"
        data-testid="lightbox-fullscreen-close"
      >
        <X className="w-5 h-5" />
      </button>
      {children}
      {imgLoading && <Loader2 className="absolute w-10 h-10 text-white animate-spin" />}
      <img
        src={src}
        alt={alt || "Foto"}
        onLoad={() => setImgLoading(false)}
        onError={() => setImgLoading(false)}
        onClick={(e) => e.stopPropagation()}
        onDoubleClick={onDoubleClick}
        onMouseDown={onMouseDown}
        className={`object-contain select-none transition-opacity duration-200 ${imgLoading ? "opacity-0" : "opacity-100"}`}
        style={{
          transform: `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})${rot ? ` rotate(${rot}deg)` : ""}`,
          transformOrigin: "center center",
          maxHeight: swapped ? "100vw" : "100vh",
          maxWidth: swapped ? "100vh" : "100vw",
          cursor: zoomed ? "grab" : "auto",
          willChange: "transform",
          touchAction: "none",
        }}
        draggable={false}
      />
    </div>,
    document.body
  );
});
FullscreenPhoto.displayName = "FullscreenPhoto";

export default function PhotoPreview({ photos, initialIndex = 0, onClose, onRequestDelete, busy = false }) {
  const [selected, setSelected] = useState(() => photos[initialIndex]?.key);
  const lastIndex = useRef(initialIndex);
  const found = photos.findIndex(p => p.key === selected);
  const index = found >= 0 ? found : Math.min(lastIndex.current, photos.length - 1);
  const photo = photos[index];
  useEffect(() => { if (!photos.length) onClose(); }, [photos.length, onClose]);
  const move = delta => {
    const next = (index + delta + photos.length) % photos.length;
    lastIndex.current = next;
    setSelected(photos[next].key);
  };
  if (!photo) return null;
  return <FullscreenPhoto src={photo.src} alt={`Foto ${index + 1}`} onClose={onClose} requestFullscreen={false}>
    <div className="absolute left-3 top-3 z-10 flex items-center gap-2" onClick={e => e.stopPropagation()}>
      <span className="rounded-full bg-black/60 px-3 py-2 text-xs text-white">{index + 1}/{photos.length}</span>
      {onRequestDelete && <button type="button" disabled={busy} onClick={() => onRequestDelete(index)} aria-label="Hapus foto yang ditampilkan"
        className="w-11 h-11 rounded-full bg-red-600/90 text-white flex items-center justify-center disabled:opacity-50" data-testid="photo-preview-delete"><Trash2 className="w-5 h-5" /></button>}
    </div>
    {photos.length > 1 && <>
      <button type="button" disabled={busy} onClick={e => { e.stopPropagation(); move(-1); }} aria-label="Foto sebelumnya"
        className="absolute left-2 top-1/2 z-10 w-11 h-11 rounded-full bg-black/60 text-white flex items-center justify-center"><ChevronLeft /></button>
      <button type="button" disabled={busy} onClick={e => { e.stopPropagation(); move(1); }} aria-label="Foto berikutnya"
        className="absolute right-2 top-1/2 z-10 w-11 h-11 rounded-full bg-black/60 text-white flex items-center justify-center"><ChevronRight /></button>
    </>}
    <p className="absolute bottom-3 inset-x-0 text-center text-xs text-white/80 pointer-events-none">Cubit atau ketuk dua kali untuk memperbesar</p>
  </FullscreenPhoto>;
}
