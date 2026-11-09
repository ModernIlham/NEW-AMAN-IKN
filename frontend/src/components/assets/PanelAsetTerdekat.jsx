import React, { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { ArrowUp, ChevronDown, LocateFixed, PencilLine } from "lucide-react";
import { cariTerdekat, jumlahDalamRadius, mataAngin } from "../../lib/asetTerdekat";
import { formatJarak } from "../../lib/ukurPeta";
import { STATUS_COLORS } from "../../lib/warnaAset";

// Toko posisi kecil: lokasiSayaPeta menulis (±1×/detik), panel ini membaca.
// Sengaja DI LUAR state AssetMapFullView — komponen peta itu besar, dan
// me-render ulangnya tiap fix GPS akan membuat HP kelas bawah tersendat.
export function buatTokoPosisi() {
  let posisi = null;
  const pendengar = new Set();
  return {
    get: () => posisi,
    set(p) { posisi = p; pendengar.forEach((fn) => fn()); },
    subscribe(fn) { pendengar.add(fn); return () => pendengar.delete(fn); },
  };
}

const RADIUS_RINGKAS = 50; // meter — "N aset di sekitar Anda"
const KUNCI_FILTER = "aman_peta_terdekat_belum";

function bacaFilter() {
  try { return localStorage.getItem(KUNCI_FILTER) === "1"; } catch { return false; }
}

/**
 * Panel "Aset terdekat" — muncul hanya saat Lokasi Anda aktif. Membantu
 * petugas lapangan menjawab "aset mana di dekat saya yang belum didata?":
 * jarak + arah mata angin (peta selalu menghadap utara), ketuk untuk
 * membawa peta ke pin dan membuka popup-nya.
 */
export default function PanelAsetTerdekat({ toko, titik, onFokus, onEdit }) {
  const posisi = useSyncExternalStore(toko.subscribe, toko.get, () => null);
  const [buka, setBuka] = useState(false);
  const [hanyaBelum, setHanyaBelum] = useState(bacaFilter);
  useEffect(() => {
    try { localStorage.setItem(KUNCI_FILTER, hanyaBelum ? "1" : "0"); } catch { /* diam */ }
  }, [hanyaBelum]);

  const daftar = useMemo(() => cariTerdekat(titik, posisi, { n: 5, hanyaBelum }), [titik, posisi, hanyaBelum]);
  const dekat = useMemo(() => jumlahDalamRadius(titik, posisi, RADIUS_RINGKAS, { hanyaBelum }), [titik, posisi, hanyaBelum]);

  if (!posisi || !titik.length) return null;
  const pertama = daftar[0];
  // Akurasi GPS lebih kasar dari jarak → angka jarak menyesatkan; beri tanda.
  const kasar = posisi.accuracy > 30;

  return (
    <div className="absolute left-1/2 -translate-x-1/2 top-2 z-[600] w-[min(20rem,calc(100%-7.5rem))] pointer-events-none" data-peta-panel="terdekat" data-testid="panel-aset-terdekat">
      <div className="pointer-events-auto rounded-lg border border-blue-300 dark:border-blue-700 bg-background/95 backdrop-blur shadow-lg">
        <button type="button" onClick={() => setBuka((b) => !b)} aria-expanded={buka}
          className="w-full flex items-center gap-1.5 px-2 py-1 text-left hover:bg-muted rounded-lg"
          data-testid="panel-aset-terdekat-toggle">
          <LocateFixed className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
          <span className="flex-1 min-w-0 truncate text-[11px]">
            <b className="tabular-nums">{dekat}</b> aset{hanyaBelum ? " belum didata" : ""} ≤ {RADIUS_RINGKAS} m
            {pertama && <span className="text-muted-foreground"> · terdekat {formatJarak(pertama.jarak)}</span>}
          </span>
          <ChevronDown className={`w-3.5 h-3.5 shrink-0 text-muted-foreground transition-transform ${buka ? "rotate-180" : ""}`} />
        </button>
        {buka && (
          <div className="px-2 pb-2" data-testid="panel-aset-terdekat-isi">
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground py-1 cursor-pointer">
              <input type="checkbox" checked={hanyaBelum} onChange={(e) => setHanyaBelum(e.target.checked)}
                className="min-w-0 min-h-0" data-testid="panel-aset-terdekat-belum" />
              Hanya yang belum diinventarisasi
            </label>
            {daftar.length === 0 ? (
              <p className="text-[10px] text-muted-foreground py-1">Tidak ada aset {hanyaBelum ? "belum didata " : ""}dalam 5 km.</p>
            ) : (
              <ul className="space-y-0.5">
                {daftar.map((t) => (
                  <li key={t.row.id} className="flex items-center gap-1">
                    <button type="button" onClick={() => onFokus(t.row)}
                      className="flex-1 min-w-0 flex items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-muted min-h-0"
                      title={`Tampilkan di peta — ${mataAngin(t.arah)} dari Anda`}
                      data-testid={`terdekat-${t.row.id}`}>
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: STATUS_COLORS[t.row.inventory_status] || STATUS_COLORS["Belum Diinventarisasi"] }} />
                      <span className="flex-1 min-w-0">
                        <span className="block truncate text-[11px] font-medium">{t.row.asset_name || "-"}</span>
                        <span className="block truncate text-[9.5px] text-muted-foreground">{t.row.asset_code || "-"}{t.row.NUP ? ` · NUP ${t.row.NUP}` : ""}</span>
                      </span>
                      <span className="shrink-0 flex items-center gap-0.5 text-[10px] tabular-nums">
                        <ArrowUp className="w-3 h-3 text-blue-600 dark:text-blue-400" style={{ transform: `rotate(${Math.round(t.arah)}deg)` }} aria-label={mataAngin(t.arah)} />
                        {formatJarak(t.jarak)}
                      </span>
                    </button>
                    {onEdit && (
                      <button type="button" onClick={() => onEdit(t.row)} aria-label={`Edit ${t.row.asset_name || "aset"}`}
                        className="shrink-0 w-7 h-7 min-w-0 min-h-0 rounded flex items-center justify-center text-amber-700 hover:bg-amber-100 hover:text-amber-800 dark:text-amber-400 dark:hover:bg-amber-900/40 dark:hover:text-amber-300"
                        data-testid={`terdekat-edit-${t.row.id}`}>
                        <PencilLine className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {kasar && (
              <p className="text-[9.5px] text-amber-700 dark:text-amber-400 mt-1">Akurasi GPS ±{Math.round(posisi.accuracy)} m — jarak bisa meleset sebesar itu.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
