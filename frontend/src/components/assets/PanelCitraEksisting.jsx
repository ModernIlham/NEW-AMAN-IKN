import React from "react";
import { ChevronDown, Eye, EyeOff, Loader2, LocateFixed, PenLine, RefreshCw, Satellite } from "lucide-react";
import { formatTanggalCitra } from "../../lib/lapisanCitra";

/**
 * Panel lapisan EKSISTING di Peta Aset (kanan bawah, di atas panel denah).
 * Isinya: gambar & citra terdaftar urut dari paling atas (tampil/sembunyi per
 * lapisan, lompat ke areanya) dan pengatur opasitas citra.
 *
 * Kepala panel = tombol lipat, sama dengan panel Lapis Denah: di HP panel
 * bawaannya terlipat agar tak menutup sepertiga peta.
 */
export default function PanelCitraEksisting({ citra, buka, onLipat }) {
  const { lapis, memuat, galat } = citra;
  const persen = Math.round((citra.opasitas || 0.85) * 100);
  return (
    <div
      className="pointer-events-auto w-[11rem] sm:w-56 max-w-full rounded-lg border border-border bg-background/95 backdrop-blur shadow-lg overflow-hidden"
      data-peta-panel="citra"
      data-testid="asset-map-citra-panel"
    >
      <button
        type="button"
        onClick={onLipat}
        aria-expanded={buka}
        className="w-full px-2 py-1.5 flex items-center gap-1.5 text-left min-h-0 hover:bg-muted transition-colors"
        data-testid="citra-panel-lipat"
      >
        <Satellite className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
        <span className="text-[11px] font-bold truncate flex-1">Eksisting</span>
        {!buka && lapis.length > 0 && (
          <span className="text-[9px] text-muted-foreground tabular-nums flex-shrink-0">
            {lapis.length} lapis
          </span>
        )}
        {memuat && <Loader2 className="w-3 h-3 animate-spin text-amber-600 flex-shrink-0" />}
        <ChevronDown className={`w-3 h-3 text-muted-foreground flex-shrink-0 transition-transform ${buka ? "rotate-180" : ""}`} />
      </button>
      {buka && (
        <>
          <div className="border-t border-border max-h-40 overflow-y-auto py-0.5">
            {galat && (
              <div className="px-2 py-2 flex items-start gap-1.5">
                <p className="text-[10px] text-red-600 dark:text-red-400 leading-snug flex-1">{galat}</p>
                <button type="button" onClick={citra.muatUlang}
                  className="min-w-0 min-h-0 w-5 h-5 rounded flex items-center justify-center hover:bg-muted flex-shrink-0"
                  aria-label="Coba muat ulang daftar citra" data-testid="citra-coba-ulang">
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
            )}
            {!galat && !memuat && lapis.length === 0 && (
              <p className="px-2 py-2 text-[10px] text-muted-foreground leading-snug" data-testid="citra-kosong">
                Belum ada lapisan. Admin: Hierarki Spasial → Lapisan Eksisting.
              </p>
            )}
            {lapis.map((l) => (
              <div key={l.id} className={`px-2 py-1 flex items-center gap-1.5 ${l.tampil ? "" : "opacity-50"}`}
                data-testid={`citra-lapis-${l.id}`}>
                <button
                  type="button"
                  onClick={() => citra.menuju(l)}
                  className="min-w-0 min-h-0 flex-1 text-left rounded hover:bg-muted px-0.5"
                  title={`Tuju ${l.nama}`}
                  data-testid={`citra-tuju-${l.id}`}
                >
                  <span className="flex items-center gap-1 text-[10px] font-semibold min-w-0">
                    {l.jenis === "gambar"
                      ? <PenLine className="w-2.5 h-2.5 flex-shrink-0 text-teal-600" aria-hidden="true" />
                      : <Satellite className="w-2.5 h-2.5 flex-shrink-0 text-amber-600" aria-hidden="true" />}
                    <span className="truncate">{l.nama}</span>
                  </span>
                  <span className="block text-[9px] text-muted-foreground truncate">
                    {l.jenis === "gambar" ? `${(l.fitur || []).length} objek` : formatTanggalCitra(l.tanggal_rekam)}
                    {l.diArea ? "" : " · di luar layar"}
                  </span>
                </button>
                {!l.diArea && <LocateFixed className="w-3 h-3 text-muted-foreground flex-shrink-0" aria-hidden="true" />}
                <button
                  type="button"
                  onClick={() => citra.toggleLapisan(l.id)}
                  aria-pressed={l.tampil}
                  aria-label={l.tampil ? `Sembunyikan ${l.nama}` : `Tampilkan ${l.nama}`}
                  className="min-w-0 min-h-0 w-6 h-6 rounded flex items-center justify-center hover:bg-muted flex-shrink-0"
                  data-testid={`citra-saklar-${l.id}`}
                >
                  {l.tampil
                    ? <Eye className="w-3 h-3 text-muted-foreground" />
                    : <EyeOff className="w-3 h-3 text-muted-foreground" />}
                </button>
              </div>
            ))}
          </div>
          {lapis.some((l) => l.jenis === "citra") && (
            <label className="px-2 py-1.5 border-t border-border flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground flex-shrink-0">Citra</span>
              <input
                type="range" min="10" max="100" step="5" value={persen}
                onChange={(e) => citra.setOpasitas(Number(e.target.value) / 100)}
                className="flex-1 min-w-0 min-h-0 h-4 accent-amber-600"
                aria-label="Opasitas citra eksisting"
                data-testid="citra-opasitas"
              />
              <span className="text-[10px] font-semibold tabular-nums w-8 text-right flex-shrink-0">{persen}%</span>
            </label>
          )}
        </>
      )}
    </div>
  );
}
