import React, { useEffect, useState } from "react";
import AssetForm from "./AssetForm";

// Jalankan `fn` saat peramban senggang (paling lambat `batasMs`); kembalikan
// fungsi pembatal. Cadangan setTimeout untuk peramban tanpa requestIdleCallback.
function jadwalSenggang(fn, batasMs = 3000) {
  if (typeof window !== "undefined" && typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(fn, { timeout: batasMs });
    return () => window.cancelIdleCallback?.(id);
  }
  const t = setTimeout(fn, 1500);
  return () => clearTimeout(t);
}

// Satu pemilik draf/tab untuk kedua ukuran layar. Perubahan breakpoint hanya
// mengubah posisi/ukuran, tidak mengganti instance form yang sedang diketik.
//
// Mount PERTAMA form yang sedang tertutup ditunda ke waktu senggang. Form ini
// (±2.400 baris, puluhan Select) dulu dirender penuh walau tersembunyi di luar
// layar — terukur ±250 ms dari ±600 ms render saat dashboard HP dibuka (CPU
// 4× lebih lambat). Begitu form dibuka ia langsung ter-mount, dan sekali
// ter-mount TIDAK pernah dilepas, sehingga draf, tab, dan fokus tetap milik
// satu instance seperti sebelumnya.
export default function AssetFormSidebar({ isDesktop, panelVisible, isOpen, ...formProps }) {
  const terlihat = isDesktop ? isOpen || panelVisible : isOpen;
  const [dipasang, setDipasang] = useState(terlihat);
  useEffect(() => {
    if (dipasang) return undefined;
    if (terlihat) { setDipasang(true); return undefined; }
    return jadwalSenggang(() => setDipasang(true));
  }, [dipasang, terlihat]);

  return <div data-testid="asset-form-sidebar"
    className={`shrink-0 ${isDesktop ? (panelVisible ? "w-[320px] min-w-[320px]" : "w-0 min-w-0 overflow-hidden") : "w-0"}`}
    style={isDesktop ? { transition: "width 0.3s ease, min-width 0.3s ease", willChange: "width", contain: "layout style" } : undefined}>
    {(dipasang || terlihat) && (
      <AssetForm {...formProps} isOpen={terlihat} alwaysExpanded={isDesktop && panelVisible} />
    )}
  </div>;
}
