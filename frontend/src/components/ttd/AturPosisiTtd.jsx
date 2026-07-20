import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft, ChevronRight, Loader2, MapPin, Maximize2, SkipForward,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * AturPosisiTtd — penanda tangan MEMILIH LETAK & UKURAN pembubuhan tanda
 * tangannya langsung di atas pratinjau halaman dokumen (gambar PNG yang
 * dirender server per halaman — tanpa unduh PDF penuh).
 *
 * - Geser kotak ttd: drag/sentuh di dalam kotak.
 * - Ubah ukuran: pegangan pojok kanan-bawah (drag) atau penggeser ukuran.
 * - Pindah halaman: tombol ◀ ▶ (default halaman terakhir).
 * - "Otomatis saja" → pembubuhan otomatis di halaman terakhir (perilaku lama).
 *
 * Rasio halaman dibaca dari DIMENSI GAMBAR yang termuat (bukan
 * getBoundingClientRect — wadah bisa kolaps saat gambar belum ada), dan
 * posisi DIJEPIT ULANG tiap rasio ttd/halaman berubah sehingga kotak tidak
 * pernah keluar halaman (termasuk halaman landscape / ttd tinggi).
 *
 * onKirim(posisi|null): posisi = {halaman 1-based, x, y, lebar} — fraksi
 * terhadap lebar/tinggi halaman, (x,y) pojok kiri-atas kotak.
 */
export default function AturPosisiTtd({ srId, token, jumlahHalaman = 1, pngTtd, onKirim, onBatal, mengirim = false }) {
  const total = Math.max(1, jumlahHalaman || 1);
  const [halaman, setHalaman] = useState(total); // default: halaman terakhir
  const [muatHal, setMuatHal] = useState(true);
  const [gagalHal, setGagalHal] = useState(false);
  const [cobaKe, setCobaKe] = useState(0);
  // Posisi & ukuran kotak ttd sebagai FRAKSI halaman (tahan zoom/rotasi).
  const [pos, setPos] = useState({ x: 0.55, y: 0.72, lebar: 0.28 });
  const [rasio, setRasio] = useState(0.45);      // tinggi/lebar gambar ttd
  const [rasioHal, setRasioHal] = useState(1.414); // tinggi/lebar halaman
  const wadahRef = useRef(null);
  const dragRef = useRef(null); // {jenis:'geser'|'ukur', px, py, awal:{...}}

  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth > 0) setRasio(img.naturalHeight / img.naturalWidth);
    };
    img.src = pngTtd;
  }, [pngTtd]);

  useEffect(() => { setMuatHal(true); setGagalHal(false); }, [halaman, cobaKe]);

  const urlHalaman = `${API}/ttd/tandatangan/${srId}/dokumen/halaman/${halaman}?token=${encodeURIComponent(token)}&c=${cobaKe}`;

  // Jepit agar kotak SELALU utuh di dalam halaman: kecilkan lebar dulu bila
  // kotak terlalu tinggi untuk halaman (ttd tinggi / halaman landscape),
  // baru jepit x/y terhadap tepi.
  const jepit = useCallback((p) => {
    let lebar = Math.min(0.6, Math.max(0.08, p.lebar));
    let tinggiFrak = (lebar * rasio) / rasioHal;
    if (tinggiFrak > 0.85) {
      lebar = Math.max(0.08, (0.85 * rasioHal) / rasio);
      tinggiFrak = (lebar * rasio) / rasioHal;
    }
    return {
      lebar,
      x: Math.min(1 - lebar, Math.max(0, p.x)),
      y: Math.min(Math.max(0, 1 - tinggiFrak - 0.005), Math.max(0, p.y)),
    };
  }, [rasio, rasioHal]);

  // Rasio ttd/halaman berubah (gambar termuat, pindah halaman landscape…)
  // → jepit ulang posisi yang ada; nilai awal pun ikut terjepit di sini.
  useEffect(() => { setPos((p) => jepit(p)); }, [jepit]);

  const titik = (e) => (e.touches ? e.touches[0] : e);

  const mulai = (jenis) => (e) => {
    if (!e.touches) e.preventDefault(); // touchstart React = pasif; cukup mouse
    e.stopPropagation();
    const t = titik(e);
    dragRef.current = { jenis, px: t.clientX, py: t.clientY, awal: { ...pos } };
  };
  const gerak = (e) => {
    const d = dragRef.current;
    const rect = wadahRef.current?.getBoundingClientRect();
    if (!d || !rect || rect.width < 40 || rect.height < 40) return;
    const t = titik(e);
    const dx = (t.clientX - d.px) / rect.width;
    const dy = (t.clientY - d.py) / rect.height;
    if (d.jenis === "geser") {
      setPos(jepit({ ...d.awal, x: d.awal.x + dx, y: d.awal.y + dy }));
    } else {
      setPos(jepit({ ...d.awal, lebar: d.awal.lebar + dx }));
    }
  };
  const selesaiDrag = () => { dragRef.current = null; };

  const tinggiKotak = (pos.lebar * rasio) / rasioHal;

  return (
    <div className="space-y-3" data-testid="atur-posisi-ttd">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs font-bold flex items-center gap-1.5">
          <MapPin className="w-3.5 h-3.5 text-blue-600" />
          Atur letak tanda tangan di dokumen
        </p>
        {total > 1 && (
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" className="h-9 w-9 p-0 min-w-0 min-h-0"
              disabled={halaman <= 1} onClick={() => setHalaman((h) => h - 1)} aria-label="Halaman sebelumnya">
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-xs font-semibold whitespace-nowrap" data-testid="posisi-halaman">
              Hal. {halaman}/{total}
            </span>
            <Button type="button" variant="outline" size="sm" className="h-9 w-9 p-0 min-w-0 min-h-0"
              disabled={halaman >= total} onClick={() => setHalaman((h) => h + 1)} aria-label="Halaman berikutnya">
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>

      <div
        ref={wadahRef}
        className="relative w-full rounded-xl border border-border overflow-hidden bg-white select-none touch-none"
        style={muatHal || gagalHal ? { aspectRatio: `1 / ${rasioHal}` } : undefined}
        onMouseMove={gerak} onMouseUp={selesaiDrag} onMouseLeave={selesaiDrag}
        onTouchMove={gerak} onTouchEnd={selesaiDrag} onTouchCancel={selesaiDrag}
        data-testid="posisi-wadah"
      >
        {gagalHal ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <p className="text-xs">Gagal memuat pratinjau halaman.</p>
            <Button type="button" variant="outline" size="sm" className="h-8 text-xs min-w-0 min-h-0"
              onClick={() => setCobaKe((c) => c + 1)}>
              Coba lagi
            </Button>
          </div>
        ) : (
          <img
            key={urlHalaman}
            src={urlHalaman}
            alt={`Pratinjau halaman ${halaman}`}
            className="w-full block"
            draggable={false}
            onLoad={(e) => {
              setMuatHal(false);
              if (e.target.naturalWidth > 0) {
                setRasioHal(e.target.naturalHeight / e.target.naturalWidth);
              }
            }}
            onError={() => { setMuatHal(false); setGagalHal(true); }}
          />
        )}
        {muatHal && !gagalHal && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Kotak tanda tangan — geser untuk memindah, pegangan untuk ukuran.
            Pegangan DI DALAM kotak agar tak terpotong overflow saat kotak
            menempel tepi halaman. */}
        {!gagalHal && !muatHal && (
          <div
            className="absolute border-2 border-blue-500 bg-blue-500/10 rounded-md cursor-move shadow-[0_0_0_9999px_rgba(0,0,0,0.06)]"
            style={{
              left: `${pos.x * 100}%`, top: `${pos.y * 100}%`,
              width: `${pos.lebar * 100}%`, height: `${tinggiKotak * 100}%`,
            }}
            onMouseDown={mulai("geser")} onTouchStart={mulai("geser")}
            data-testid="posisi-kotak"
          >
            <img src={pngTtd} alt="Tanda tangan" draggable={false}
              className="w-full h-full object-contain pointer-events-none" />
            <span
              className="absolute right-0 bottom-0 w-7 h-7 rounded-tl-lg rounded-br-md bg-blue-600 text-white flex items-center justify-center cursor-nwse-resize shadow-md"
              onMouseDown={mulai("ukur")} onTouchStart={mulai("ukur")}
              aria-label="Ubah ukuran tanda tangan"
              data-testid="posisi-pegangan"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 px-0.5">
        <span className="text-[11px] text-muted-foreground whitespace-nowrap">Ukuran</span>
        <input
          type="range" min="0.08" max="0.6" step="0.01" value={pos.lebar}
          onChange={(e) => setPos((p) => jepit({ ...p, lebar: parseFloat(e.target.value) }))}
          className="flex-1 accent-blue-600 min-w-0" data-testid="posisi-ukuran"
        />
      </div>
      <p className="text-[11px] text-muted-foreground">
        Geser kotak ke tempat tanda tangan Anda ingin dibubuhkan; tarik pegangan
        biru untuk memperbesar/memperkecil. Kode QR verifikasi tetap tercetak di
        halaman terakhir.
      </p>

      <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" className="h-9 text-xs" disabled={mengirim} onClick={onBatal}>
            Kembali
          </Button>
          <Button type="button" variant="outline" size="sm" className="h-9 text-xs" disabled={mengirim}
            onClick={() => onKirim(null)} title="Tanpa memilih posisi — dibubuhkan otomatis di halaman terakhir"
            data-testid="posisi-lewati">
            <SkipForward className="w-3.5 h-3.5 mr-1.5" />Otomatis saja
          </Button>
        </div>
        <Button type="button" size="sm" className="h-9 text-xs" disabled={mengirim || gagalHal || muatHal}
          onClick={() => onKirim({ halaman, ...pos })} data-testid="posisi-kirim">
          {mengirim ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
          Bubuhkan di Posisi Ini
        </Button>
      </div>
    </div>
  );
}
