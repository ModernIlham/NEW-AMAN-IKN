import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2, X } from "lucide-react";
import { muatPhotoLightbox } from "../../lib/muatPhotoLightbox";
import { useBackGuard } from "../../hooks/useBackGuard";

function StatusPemuatan({ asset, gagal, onClose, onRetry }) {
  useBackGuard(onClose);
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const key = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", key); };
  }, [onClose]);
  return createPortal(
    <div role="dialog" aria-modal="true" aria-label="Penampil foto aset"
      className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-md flex items-center justify-center p-4"
      data-testid="lightbox-loading-dialog">
      <div className="w-full max-w-sm rounded-xl bg-card text-foreground shadow-xl p-4">
        <div className="flex items-center gap-2 justify-between mb-3">
          <p className="font-semibold">Foto aset</p>
          <button type="button" onClick={onClose} aria-label="Tutup penampil foto"
            data-testid="lightbox-loader-close" className="min-h-11 min-w-11 rounded-lg hover:bg-muted flex items-center justify-center">
            <X className="w-5 h-5" />
          </button>
        </div>
        {asset?.thumbnail && <img src={asset.thumbnail} alt={asset.asset_name || "Pratinjau aset"}
          className="max-h-60 w-full object-contain rounded-lg mb-3" />}
        <p role={gagal ? "alert" : "status"} className="text-sm text-muted-foreground flex items-start gap-2">
          {!gagal && <Loader2 className="w-4 h-4 shrink-0 animate-spin mt-0.5" />}
          {gagal ? "Penampil foto belum dapat dimuat. Sambungkan internet lalu coba lagi. Data dan antrean simpan Anda tetap aman."
            : "Memuat penampil foto…"}
        </p>
        {gagal && <button type="button" onClick={onRetry} data-testid="lightbox-loader-retry"
          className="mt-4 min-h-11 w-full rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2">Coba lagi</button>}
      </div>
    </div>, document.body);
}

export default function PhotoLightboxLoader(props) {
  const [Penampil, setPenampil] = useState(null);
  const [gagal, setGagal] = useState(false);
  const [percobaan, setPercobaan] = useState(0);
  useEffect(() => {
    let aktif = true;
    setGagal(false);
    muatPhotoLightbox().then(module => {
      if (aktif) setPenampil(() => module.default);
    }).catch(() => { if (aktif) setGagal(true); });
    return () => { aktif = false; };
  }, [percobaan]);
  if (Penampil) return <Penampil {...props} />;
  return <StatusPemuatan asset={props.asset} gagal={gagal} onClose={props.onClose}
    onRetry={() => setPercobaan(n => n + 1)} />;
}
