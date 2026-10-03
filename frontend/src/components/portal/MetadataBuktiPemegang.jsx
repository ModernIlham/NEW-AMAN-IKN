import React from "react";
import { ringkasPengambilan } from "../../lib/kameraPemegang";

export default function MetadataBuktiPemegang({ bukti = [] }) {
  return bukti.some(p => p.pengambilan) ? <ul className="space-y-1 text-xs text-muted-foreground" aria-label="Waktu dan koordinat bukti">
    {bukti.map((p, i) => p.pengambilan && <li key={i}>Foto {i + 1}: {ringkasPengambilan(p)}</li>)}
  </ul> : null;
}
