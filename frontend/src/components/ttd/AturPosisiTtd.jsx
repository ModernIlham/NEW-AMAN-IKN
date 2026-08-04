import React, { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft, ChevronRight, Loader2, MapPin, Maximize2, QrCode, SkipForward,
} from "lucide-react";

/**
 * AturPosisiTtd — memilih LETAK & UKURAN satu kotak di atas pratinjau halaman
 * dokumen (gambar PNG yang dirender server per halaman — tanpa unduh PDF).
 *
 * Dipakai dua peran dengan komponen yang SAMA supaya koordinat, jepitan, dan
 * rasa geser/ubah-ukurannya identik:
 *  - `jenis="ttd"` — PENANDA TANGAN memilih letak tanda tangannya (halaman
 *    publik e-sign).
 *  - `jenis="qr"`  — PEMILIK dokumen memilih letak QR verifikasi SEKALI di
 *    akhir, saat semua pihak sudah meneken dan dokumen hendak diunduh
 *    (mandat pemilik: bukan lagi diatur per penanda tangan).
 *
 * - Geser kotak: drag/sentuh di dalam kotak.
 * - Ubah ukuran: pegangan pojok kanan-bawah (drag) atau penggeser ukuran.
 * - Pindah halaman: tombol ◀ ▶ (default halaman terakhir).
 * - "Otomatis saja" → slot bawaan (ttd: halaman terakhir; QR: pojok
 *   kanan-bawah halaman terakhir).
 *
 * Rasio halaman dibaca dari DIMENSI GAMBAR yang termuat (bukan
 * getBoundingClientRect — wadah bisa kolaps saat gambar belum ada), dan
 * posisi DIJEPIT ULANG tiap rasio kotak/halaman berubah sehingga kotak tidak
 * pernah keluar halaman (termasuk halaman landscape / ttd tinggi).
 *
 * onKirim(posisi|null): {halaman 1-based, x, y, lebar} — fraksi terhadap
 * lebar/tinggi halaman, (x,y) pojok kiri-atas kotak. null = otomatis.
 */
export default function AturPosisiTtd({
  jenis = "ttd", bangunUrlHalaman, jumlahHalaman = 1, pngTtd,
  nilaiAwal = null, onKirim, onBatal, mengirim = false,
  labelKirim, labelOtomatis = "Otomatis saja",
}) {
  const qr = jenis === "qr";
  const MIN = qr ? 0.10 : 0.08;
  const MAKS = qr ? 0.40 : 0.6;
  const total = Math.max(1, jumlahHalaman || 1);
  const [halaman, setHalaman] = useState(
    Math.min(total, Math.max(1, nilaiAwal?.halaman || total)));
  const [muatHal, setMuatHal] = useState(true);
  const [gagalHal, setGagalHal] = useState(false);
  const [cobaKe, setCobaKe] = useState(0);
  // Posisi & ukuran kotak sebagai FRAKSI halaman (tahan zoom/rotasi).
  const [pos, setPos] = useState(() => ({
    x: nilaiAwal?.x ?? (qr ? 0.76 : 0.55),
    y: nilaiAwal?.y ?? (qr ? 0.84 : 0.72),
    lebar: nilaiAwal?.lebar ?? (qr ? 0.14 : 0.28),
  }));
  // rasio = tinggi/lebar ISI kotak. QR selalu persegi (1); ttd ikut gambarnya.
  const [rasio, setRasio] = useState(qr ? 1 : 0.45);
  const [rasioHal, setRasioHal] = useState(1.414); // tinggi/lebar halaman
  const wadahRef = useRef(null);
  const dragRef = useRef(null); // {jenis:'geser'|'ukur', px, py, awal:{...}}

  useEffect(() => {
    if (qr || !pngTtd) return;
    const img = new Image();
    img.onload = () => {
      if (img.naturalWidth > 0) setRasio(img.naturalHeight / img.naturalWidth);
    };
    img.src = pngTtd;
  }, [pngTtd, qr]);

  useEffect(() => { setMuatHal(true); setGagalHal(false); }, [halaman, cobaKe]);

  const urlHalaman = bangunUrlHalaman(halaman, cobaKe);

  // Jepit agar kotak SELALU utuh di dalam halaman: kecilkan lebar dulu bila
  // kotak terlalu tinggi untuk halaman (isi tinggi / halaman landscape),
  // baru jepit x/y terhadap tepi.
  const jepit = useCallback((p) => {
    const batasTinggi = qr ? 0.9 : 0.85;
    let lebar = Math.min(MAKS, Math.max(MIN, p.lebar));
    let tinggiFrak = (lebar * rasio) / rasioHal;
    if (tinggiFrak > batasTinggi) {
      lebar = Math.max(MIN, (batasTinggi * rasioHal) / rasio);
      tinggiFrak = (lebar * rasio) / rasioHal;
    }
    return {
      lebar,
      x: Math.min(1 - lebar, Math.max(0, p.x)),
      y: Math.min(Math.max(0, 1 - tinggiFrak - 0.005), Math.max(0, p.y)),
    };
  }, [rasio, rasioHal, qr, MIN, MAKS]);

  // Rasio isi/halaman berubah (gambar termuat, pindah halaman landscape…)
  // → jepit ulang posisi yang ada; nilai awal pun ikut terjepit di sini.
  useEffect(() => { setPos((p) => jepit(p)); }, [jepit]);

  const titik = (e) => (e.touches ? e.touches[0] : e);

  const mulai = (aksi) => (e) => {
    if (!e.touches) e.preventDefault(); // touchstart React = pasif; cukup mouse
    e.stopPropagation();
    const t = titik(e);
    dragRef.current = { jenis: aksi, px: t.clientX, py: t.clientY, awal: { ...pos } };
  };
  const gerak = (e) => {
    const d = dragRef.current;
    const rect = wadahRef.current?.getBoundingClientRect();
    if (!d || !rect || rect.width < 40 || rect.height < 40) return;
    const t = titik(e);
    const dx = (t.clientX - d.px) / rect.width;
    const dy = (t.clientY - d.py) / rect.height;
    if (d.jenis === "geser") setPos(jepit({ ...d.awal, x: d.awal.x + dx, y: d.awal.y + dy }));
    else setPos(jepit({ ...d.awal, lebar: d.awal.lebar + dx }));
  };
  const selesaiDrag = () => { dragRef.current = null; };

  const tinggiKotak = (pos.lebar * rasio) / rasioHal;
  const warna = qr
    ? { border: "border-emerald-500", bg: "bg-emerald-500/10", pegangan: "bg-emerald-600", accent: "accent-emerald-600", teks: "text-emerald-600" }
    : { border: "border-blue-500", bg: "bg-blue-500/10", pegangan: "bg-teal-700", accent: "accent-blue-600", teks: "text-blue-600" };

  return (
    <div className="space-y-3" data-testid={qr ? "atur-posisi-qr" : "atur-posisi-ttd"}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs font-bold flex items-center gap-1.5">
          {qr ? <QrCode className="w-3.5 h-3.5 text-emerald-600" />
              : <MapPin className="w-3.5 h-3.5 text-blue-600" />}
          {qr ? "Atur letak QR verifikasi" : "Atur letak tanda tangan di dokumen"}
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

        {/* Kotak — geser untuk memindah, pegangan untuk ukuran. Pegangan DI
            DALAM kotak agar tak terpotong overflow saat menempel tepi. */}
        {!gagalHal && !muatHal && (
          <div
            className={`absolute border-2 ${warna.border} ${warna.bg} rounded-md cursor-move ${qr ? "" : "shadow-[0_0_0_9999px_rgba(0,0,0,0.06)]"}`}
            style={{
              left: `${pos.x * 100}%`, top: `${pos.y * 100}%`,
              width: `${pos.lebar * 100}%`, height: `${tinggiKotak * 100}%`,
            }}
            onMouseDown={mulai("geser")} onTouchStart={mulai("geser")}
            data-testid={qr ? "posisi-qr-kotak" : "posisi-kotak"}
          >
            {qr ? (
              <div className={`w-full h-full flex items-center justify-center ${warna.teks} pointer-events-none`}>
                <QrCode className="w-2/3 h-2/3" />
              </div>
            ) : (
              <img src={pngTtd} alt="Tanda tangan" draggable={false}
                className="w-full h-full object-contain pointer-events-none" />
            )}
            <span
              className={`absolute right-0 bottom-0 w-7 h-7 rounded-tl-lg rounded-br-md ${warna.pegangan} text-white flex items-center justify-center cursor-nwse-resize shadow-md`}
              onMouseDown={mulai("ukur")} onTouchStart={mulai("ukur")}
              aria-label={qr ? "Ubah ukuran QR verifikasi" : "Ubah ukuran tanda tangan"}
              data-testid={qr ? "posisi-qr-pegangan" : "posisi-pegangan"}
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 px-0.5">
        <span className="text-[11px] text-muted-foreground whitespace-nowrap">
          {qr ? "Ukuran QR" : "Ukuran TTD"}
        </span>
        <input
          type="range" min={MIN} max={MAKS} step="0.01" value={pos.lebar}
          onChange={(e) => setPos((p) => jepit({ ...p, lebar: parseFloat(e.target.value) }))}
          className={`flex-1 ${warna.accent} min-w-0`}
          data-testid={qr ? "posisi-qr-ukuran" : "posisi-ukuran"}
        />
      </div>
      <p className="text-[11px] text-muted-foreground">
        {qr
          ? "Geser kotak hijau ke tempat kosong (hindari kaki halaman), tarik pegangan untuk mengubah ukuran — jaga cukup besar agar mudah dipindai."
          : "Geser kotak biru ke tempat tanda tangan; tarik pegangan untuk mengubah ukuran."}
      </p>

      <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" className="h-9 text-xs" disabled={mengirim} onClick={onBatal}>
            Kembali
          </Button>
          <Button type="button" variant="outline" size="sm" className="h-9 text-xs" disabled={mengirim}
            onClick={() => onKirim(null)}
            title={qr ? "QR otomatis di pojok kanan-bawah halaman terakhir"
                      : "Tanpa memilih posisi — dibubuhkan otomatis di halaman terakhir"}
            data-testid="posisi-lewati">
            <SkipForward className="w-3.5 h-3.5 mr-1.5" />{labelOtomatis}
          </Button>
        </div>
        <Button type="button" size="sm" className="h-9 text-xs" disabled={mengirim || gagalHal || muatHal}
          onClick={() => onKirim({ halaman, ...pos })} data-testid="posisi-kirim">
          {mengirim ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
          {labelKirim || (qr ? "Simpan & Unduh" : "Bubuhkan di Posisi Ini")}
        </Button>
      </div>
    </div>
  );
}
