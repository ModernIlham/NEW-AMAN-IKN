import React from "react";
import { Palette } from "lucide-react";

// Pilih hitam/putih berdasar luminansi sRGB, bukan tema aplikasi.
export function teksKontrasWarna(value) {
  const rgb = value.slice(1).match(/.{2}/g).map(v => parseInt(v, 16) / 255)
    .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const luminansi = rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  return luminansi > 0.179 ? "#000000" : "#ffffff";
}

/** Satu bidang warna: kode dapat diketik, ikon kanan membuka palet native. */
export default function MarkerColorInput({ label, testId, color, value, disabled, invalid, onColorChange, onTextChange, onBlur }) {
  return <div className="marker-style-row text-[11px]">
    <span>{label}</span>
    <div data-testid={`${testId}-field`} className={`marker-color-field flex min-w-0 items-stretch rounded-md ring-1 ring-inset ring-border ${disabled ? "opacity-50" : ""}`}
      style={{ backgroundColor: color, color: teksKontrasWarna(color) }}>
      <input type="text" aria-label={`Kode ${label.toLowerCase()}`} data-testid={`${testId}-hex`}
        className="marker-color-code min-w-0 flex-1 rounded-l-md bg-transparent font-mono"
        style={{ color: "inherit" }} value={value} disabled={disabled} maxLength={7}
        spellCheck={false} autoComplete="off" placeholder="#RRGGBB" pattern="#?[0-9a-fA-F]{6}"
        aria-invalid={invalid} onChange={e => onTextChange(e.target.value)} onBlur={onBlur} />
      <label className={`marker-color-picker relative flex shrink-0 items-center justify-center rounded-r-md ${disabled ? "cursor-not-allowed" : "cursor-pointer hover:bg-black/10"}`} title={`Pilih ${label.toLowerCase()}`}>
        <Palette className="h-4 w-4 pointer-events-none" aria-hidden="true" />
        {/* Input asli menerima ketukan/keyboard langsung, tanpa ketergantungan showPicker. */}
        <input type="color" aria-label={`Pilih ${label.toLowerCase()}`} data-testid={testId}
          className="absolute inset-0 h-full w-full cursor-inherit opacity-0" value={color}
          disabled={disabled} onChange={e => onColorChange(e.target.value)} />
      </label>
    </div>
  </div>;
}
