import React, { memo, useState, useRef, useCallback, useEffect } from "react";
import { createPortal } from "react-dom";
import { ScanLine, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useBackGuard } from "@/hooks/useBackGuard";

/**
 * Ekstrak kode yang bisa dicari dari isi QR/barcode stiker.
 * Stiker bisa berisi kode mentah ("3.05.01.05.007"), gabungan
 * ("kode|NUP"), atau URL — ambil bagian yang paling mirip kode aset,
 * lalu biarkan pencarian multi-field backend (asset_code, kode_register,
 * serial_number, dll.) yang menemukan asetnya.
 */
export function extractScannedCode(text) {
  const raw = (text || "").trim();
  if (!raw) return "";
  // Format QR kartu inventaris: "#<kode register>" — sisanya dipakai verbatim
  // sebagai kode_register (hanya '#' yang dibuang, tanpa heuristik token).
  if (raw.startsWith("#")) return raw.slice(1);
  if (/^https?:\/\//i.test(raw)) {
    // URL: pakai segmen path/query terakhir yang mirip kode
    try {
      const u = new URL(raw);
      const segs = [...u.pathname.split("/"), ...u.searchParams.values()].filter(Boolean);
      const match = segs.reverse().find(s => /^[A-Za-z0-9._-]{4,}$/.test(s));
      if (match) return match;
    } catch { /* bukan URL valid — lanjut ke heuristik token */ }
  }
  if (/[\s|;,]/.test(raw)) {
    // Teks multi-bagian (mis. "kode|NUP"): ambil token terpanjang
    const tokens = raw.match(/[A-Za-z0-9._-]{4,}/g) || [];
    if (tokens.length) return tokens.reduce((a, b) => (b.length > a.length ? b : a));
  }
  return raw;
}

/**
 * Tombol scan QR/barcode stiker aset. Memakai BarcodeDetector API bawaan
 * browser — bila tidak didukung, tombol tidak dirender sama sekali.
 * Hasil scan yang sudah diekstrak dikirim lewat onDetected(code).
 */
const QrScanButton = memo(({ onDetected }) => {
  const [scanning, setScanning] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const detectorRef = useRef(null);
  const timerRef = useRef(null);
  const supported = typeof window !== "undefined" && "BarcodeDetector" in window;

  const stopScan = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    setScanning(false);
  }, []);

  // Pastikan kamera mati saat komponen di-unmount
  useEffect(() => stopScan, [stopScan]);

  // Back/Undo browser saat scanner terbuka → tutup scanner (bukan pindah halaman)
  useBackGuard(stopScan, scanning);

  const startScan = useCallback(async () => {
    try {
      let formats = ["qr_code", "code_128", "code_39"];
      try {
        const avail = await window.BarcodeDetector.getSupportedFormats();
        formats = formats.filter(f => avail.includes(f));
      } catch { /* pakai daftar default */ }
      detectorRef.current = new window.BarcodeDetector(formats.length ? { formats } : undefined);
      streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      setScanning(true);
    } catch (err) {
      if (err?.name === "NotAllowedError") toast.error("Akses kamera ditolak. Izinkan di pengaturan browser.");
      else toast.error("Gagal membuka kamera");
    }
  }, []);

  // Setelah overlay dirender: sambungkan stream ke <video> dan scan tiap ~300ms
  useEffect(() => {
    if (!scanning) return;
    const video = videoRef.current;
    if (!video || !streamRef.current) return;
    video.srcObject = streamRef.current;
    video.play().catch(() => {});
    timerRef.current = setInterval(async () => {
      if (!detectorRef.current || video.readyState < 2) return;
      try {
        const codes = await detectorRef.current.detect(video);
        if (codes && codes.length > 0) {
          const code = extractScannedCode(codes[0].rawValue || "");
          stopScan();
          // Jangan tampilkan notifikasi "berhasil" di sini — hasil scan belum
          // tentu ada di kegiatan yang sedang dibuka. Penanganan (verifikasi ke
          // kegiatan + notifikasi sukses/gagal) diserahkan ke onDetected.
          if (code) onDetected?.(code);
          else toast.error("QR tidak berisi kode yang dikenali");
        }
      } catch { /* frame belum siap — coba lagi di tick berikutnya */ }
    }, 300);
    return () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };
  }, [scanning, onDetected, stopScan]);

  if (!supported) return null;

  return (
    <>
      <Button type="button" variant="outline" size="sm" onClick={startScan} className="h-9 w-9 p-0 sm:w-auto sm:px-2.5 lg:h-8 min-h-0 min-w-0 text-xs flex-shrink-0" title="Scan QR/barcode stiker aset" aria-label="Scan QR/barcode stiker aset" data-testid="qr-scan-btn">
        <ScanLine className="w-4 h-4" />
        <span className="hidden sm:inline">Scan</span>
      </Button>
      {scanning && createPortal(
        <div className="fixed inset-0 z-[110] bg-black" data-testid="qr-scan-overlay">
          <video ref={videoRef} className="w-full h-full object-cover" playsInline muted />
          <button type="button" onClick={stopScan} className="absolute top-4 right-4 w-10 h-10 rounded-full bg-black/60 text-white flex items-center justify-center" aria-label="Tutup scanner" data-testid="qr-scan-close">
            <X className="w-5 h-5" />
          </button>
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-56 h-56 border-2 border-white/80 rounded-xl" />
          </div>
          <div className="absolute inset-x-0 bottom-8 text-center text-white text-sm font-medium drop-shadow px-4">
            Arahkan kamera ke QR/barcode stiker aset
          </div>
        </div>,
        document.body
      )}
    </>
  );
});

QrScanButton.displayName = "QrScanButton";
export default QrScanButton;
