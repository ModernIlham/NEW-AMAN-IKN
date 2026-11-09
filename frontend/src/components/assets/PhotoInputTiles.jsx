import React from "react";
import { Camera, Images, ScanLine, Clock } from "lucide-react";

// Semua pemicu foto sejajar thumbnail, dengan sasaran sentuh yang sama besar.
export default function PhotoInputTiles({ full = false, disabled = false, onCamera, onGallery, onTimemark, onScan, prefix = "photo" }) {
  const options = [
    ...(!full ? [["full-camera", "Timemark", "Kamera Timemark (jam dan GPS)", Clock, onTimemark],
      ["camera", "Kamera", "Kamera perangkat", Camera, onCamera],
      ["gallery", "Galeri", "Pilih foto dari galeri", Images, onGallery]] : []),
    ...(typeof window !== "undefined" && "BarcodeDetector" in window ? [["full-camera-scan", "Scan", "Kamera dan scan QR aset", ScanLine, onScan]] : []),
  ];
  return options.filter(o => o[4]).map(([key, label, title, Icon, onClick]) => <button key={key} type="button" disabled={disabled} onClick={onClick}
    title={title} aria-label={title} data-testid={prefix === "photo" && key === "camera" ? "camera-capture-btn" : `${prefix}-${key}-btn`}
    className="w-14 h-14 min-w-0 min-h-0 shrink-0 rounded-lg border border-dashed border-teal-600/50 bg-teal-50/50 dark:bg-teal-900/15 text-teal-700 dark:text-teal-300 flex flex-col items-center justify-center gap-1 disabled:opacity-50">
    <Icon className="w-4 h-4" /><span className="text-[9px] leading-tight">{label}</span>
  </button>);
}
