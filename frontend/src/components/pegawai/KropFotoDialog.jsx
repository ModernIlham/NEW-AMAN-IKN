import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

const VIEW = 256;   // sisi viewport krop (px, persegi)
const OUT = 384;    // sisi keluaran (px) — tajam untuk avatar row & form

/**
 * KropFotoDialog — pilih PERSEGI bagian foto yang tampil di row: geser
 * (drag/sentuh) untuk memposisikan, zoom in/out (slider + roda mouse).
 * Hasil digambar ke canvas OUT×OUT → Blob JPEG dikembalikan via onSimpan.
 */
export default function KropFotoDialog({ src, onBatal, onSimpan }) {
  const imgRef = useRef(null);
  const [dim, setDim] = useState(null);        // {w, h} natural
  const [zoom, setZoom] = useState(1);          // 1 = cover viewport
  const [pos, setPos] = useState({ x: 0, y: 0 }); // offset px pada skala tampil
  const [drag, setDrag] = useState(null);       // {sx, sy, ox, oy}
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setZoom(1); setPos({ x: 0, y: 0 }); setDim(null);
  }, [src]);

  // Skala dasar "cover": sisi terpendek foto memenuhi viewport.
  const base = dim ? VIEW / Math.min(dim.w, dim.h) : 1;
  const skala = base * zoom;
  const lebar = dim ? dim.w * skala : VIEW;
  const tinggi = dim ? dim.h * skala : VIEW;
  // Pagari offset agar foto selalu menutupi viewport (tanpa area kosong).
  const jepit = useCallback((p, lb = lebar, tg = tinggi) => ({
    x: Math.min(0, Math.max(VIEW - lb, p.x)),
    y: Math.min(0, Math.max(VIEW - tg, p.y)),
  }), [lebar, tinggi]);

  const mulaiDrag = (e) => {
    const t = e.touches ? e.touches[0] : e;
    setDrag({ sx: t.clientX, sy: t.clientY, ox: pos.x, oy: pos.y });
  };
  const gerak = (e) => {
    if (!drag) return;
    const t = e.touches ? e.touches[0] : e;
    setPos(jepit({ x: drag.ox + (t.clientX - drag.sx), y: drag.oy + (t.clientY - drag.sy) }));
  };
  const setelZoom = (z) => {
    const zBaru = Math.min(4, Math.max(1, z));
    // Jaga titik tengah viewport tetap sama saat zoom berubah.
    const rasio = (base * zBaru) / skala;
    const cx = VIEW / 2 - pos.x, cy = VIEW / 2 - pos.y;
    const lb = dim ? dim.w * base * zBaru : VIEW;
    const tg = dim ? dim.h * base * zBaru : VIEW;
    setZoom(zBaru);
    setPos(jepit({ x: VIEW / 2 - cx * rasio, y: VIEW / 2 - cy * rasio }, lb, tg));
  };

  const simpan = async () => {
    if (!dim || !imgRef.current) return;
    setSaving(true);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = OUT; canvas.height = OUT;
      const ctx = canvas.getContext("2d");
      // Area sumber pada foto asli yang terlihat di viewport.
      const sx = -pos.x / skala, sy = -pos.y / skala, sw = VIEW / skala;
      ctx.drawImage(imgRef.current, sx, sy, sw, sw, 0, 0, OUT, OUT);
      const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.88));
      await onSimpan(blob);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!src} onOpenChange={(o) => !o && !saving && onBatal()}>
      <DialogContent className="max-w-sm p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle>Atur Foto Pegawai</DialogTitle>
          <DialogDescription>
            Geser foto untuk memilih bagian persegi yang tampil di daftar; zoom
            dengan penggeser atau roda mouse.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col items-center gap-3">
          <div
            className="relative overflow-hidden rounded-xl border-2 border-border bg-muted cursor-move touch-none select-none"
            style={{ width: VIEW, height: VIEW }}
            onMouseDown={mulaiDrag} onMouseMove={gerak}
            onMouseUp={() => setDrag(null)} onMouseLeave={() => setDrag(null)}
            onTouchStart={mulaiDrag} onTouchMove={gerak} onTouchEnd={() => setDrag(null)}
            onWheel={(e) => { e.preventDefault(); setelZoom(zoom + (e.deltaY < 0 ? 0.15 : -0.15)); }}
            data-testid="krop-viewport"
          >
            <img
              ref={imgRef} src={src} alt="Pratinjau krop foto" draggable={false}
              onLoad={(e) => setDim({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
              style={{ position: "absolute", left: pos.x, top: pos.y, width: lebar, height: tinggi, maxWidth: "none" }}
            />
            {/* Garis bantu rule-of-thirds tipis */}
            <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
              {Array.from({ length: 9 }).map((_, i) => (
                <div key={i} className="border border-white/20" />
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 w-full px-1">
            <button type="button" className="min-w-0 min-h-0 p-1 text-muted-foreground hover:text-foreground"
              onClick={() => setelZoom(zoom - 0.25)} aria-label="Perkecil"><ZoomOut className="w-4 h-4" /></button>
            <input type="range" min="1" max="4" step="0.05" value={zoom}
              onChange={(e) => setelZoom(parseFloat(e.target.value))}
              className="flex-1 accent-sky-600 min-w-0" data-testid="krop-zoom" />
            <button type="button" className="min-w-0 min-h-0 p-1 text-muted-foreground hover:text-foreground"
              onClick={() => setelZoom(zoom + 0.25)} aria-label="Perbesar"><ZoomIn className="w-4 h-4" /></button>
          </div>
        </div>
        <DialogFooter className="flex-row justify-end gap-1.5 space-x-0">
          <Button variant="outline" className="h-9 text-xs" disabled={saving} onClick={onBatal}>Batal</Button>
          <Button className="h-9 text-xs" disabled={saving || !dim} onClick={simpan} data-testid="krop-simpan">
            {saving ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}Pakai Foto Ini
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
