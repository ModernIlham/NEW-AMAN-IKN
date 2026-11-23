import React, { useEffect } from "react";
import { createPortal } from "react-dom";
import { Loader2 } from "lucide-react";

/**
 * Layar buram pemblokir selama proses berat berjalan di server (hapus
 * kegiatan, hapus semua aset).
 *
 * Permintaan pemilik: saat hapus berlangsung, data lama masih tampil dan bisa
 * diotak-atik sehingga pengguna mengira perintahnya belum direspons. Overlay
 * ini menutup SELURUH layar (buram + pesan + spinner) sampai proses DAN muat
 * ulang daftarnya selesai.
 *
 * - Dipasang lewat portal ke <body> dengan z di atas dialog Radix (z-50).
 * - `pointer-events-auto` WAJIB: dialog modal Radix menyetel
 *   `pointer-events: none` pada <body>; tanpa ini klik menembus overlay ke
 *   dialog di bawahnya.
 * - Tombol Esc dan klik diserap; pengguna diberi tahu agar tidak menutup
 *   halaman (beforeunload) karena prosesnya tetap berjalan di server.
 */
export default function OverlayProses({ aktif, judul = "Memproses…", keterangan = "", testId = "overlay-proses" }) {
  useEffect(() => {
    if (!aktif) return undefined;
    const tahanEsc = (e) => { if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); } };
    const tahanTutup = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("keydown", tahanEsc, true);
    window.addEventListener("beforeunload", tahanTutup);
    return () => {
      window.removeEventListener("keydown", tahanEsc, true);
      window.removeEventListener("beforeunload", tahanTutup);
    };
  }, [aktif]);

  if (!aktif || typeof document === "undefined") return null;
  return createPortal(
    <div
      className="fixed inset-0 z-[300] pointer-events-auto flex items-center justify-center bg-background/60 backdrop-blur-sm px-4"
      role="alertdialog"
      aria-modal="true"
      aria-busy="true"
      aria-live="assertive"
      aria-label={judul}
      data-testid={testId}
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div className="flex max-w-sm flex-col items-center gap-3 rounded-xl border border-border bg-card px-6 py-5 text-center shadow-xl">
        <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm font-semibold text-foreground">{judul}</p>
        {keterangan && <p className="text-xs text-muted-foreground">{keterangan}</p>}
      </div>
    </div>,
    document.body,
  );
}
