import React from "react";
import { PencilLine } from "lucide-react";
import { useAdaDraf } from "../../lib/drafAset";

// Chip "Draf" pada baris/kartu aset: ada perubahan (isian/foto) yang tersimpan
// di perangkat ini tetapi BELUM dikirim ke server. Pembeda dari chip antrean
// (queued/saving/failed) yang berarti data SUDAH disimpan & menunggu sinkron.
export default function BadgeDraf({ assetId, className = "" }) {
  const ada = useAdaDraf(assetId);
  if (!ada) return null;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1 py-px text-[9px] font-semibold leading-none bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-700 ${className}`}
      title="Ada perubahan yang belum disimpan di perangkat ini — buka aset untuk melanjutkan atau membuangnya"
      data-testid={`badge-draf-${assetId}`}
    >
      <PencilLine className="w-2.5 h-2.5" />Draf
    </span>
  );
}
