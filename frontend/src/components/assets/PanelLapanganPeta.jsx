import React, { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { ArrowUp, ChevronDown, CircleCheck, Compass, ExternalLink, LocateFixed, MapPinned, PencilLine, Plus, X } from "lucide-react";
import {
  AKURASI_TITIK_M, cariTerdekat, cukupPresisi, jumlahDalamRadius, mataAngin, statusPandu, urlGoogleMaps,
} from "../../lib/asetTerdekat";
import { parseKoordinat } from "../../lib/koordinatAset";
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
const JARAK_GOOGLE_MAPS = 300; // lebih jauh dari ini → tawarkan navigasi jalan
const KUNCI_FILTER = "aman_peta_terdekat_belum";

function bacaFilter() {
  try { return localStorage.getItem(KUNCI_FILTER) === "1"; } catch { return false; }
}

/** Pil akurasi GPS: hijau = cukup untuk titik aset, kuning = kasar, merah = sangat kasar. */
function PilAkurasi({ akurasi }) {
  const a = Math.round(akurasi);
  const kelas = akurasi <= AKURASI_TITIK_M
    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
    : akurasi <= 30
      ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
      : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200";
  return <span className={`shrink-0 rounded-full px-1.5 text-[10px] font-semibold tabular-nums ${kelas}`} data-testid="panel-lapangan-akurasi">GPS ±{a} m</span>;
}

function namaAset(row) {
  return row?.asset_name || row?.asset_code || "aset";
}

/**
 * Panel lapangan di Peta Aset — muncul hanya saat Lokasi Anda aktif. Menjawab
 * tiga pertanyaan petugas di lapangan:
 *   1. "Aset apa di dekat saya (yang belum didata)?" → daftar terdekat
 *   2. "Di mana aset X?" → Pandu: garis + jarak + arah, kabar saat tiba
 *   3. "Titik aset ini salah / belum ada" → set titik = lokasi saya,
 *      tambah aset di lokasi saya (keduanya bergerbang akurasi ≤ 8 m)
 */
export default function PanelLapanganPeta({ toko, titik, tujuan, onPandu, onFokus, onEdit, onSetTitik, onTambahDiSini }) {
  const posisi = useSyncExternalStore(toko.subscribe, toko.get, () => null);
  const [buka, setBuka] = useState(false);
  const [hanyaBelum, setHanyaBelum] = useState(bacaFilter);
  const [yakinTitik, setYakinTitik] = useState(false);
  useEffect(() => {
    try { localStorage.setItem(KUNCI_FILTER, hanyaBelum ? "1" : "0"); } catch { /* diam */ }
  }, [hanyaBelum]);

  const daftar = useMemo(() => cariTerdekat(titik, posisi, { n: 5, hanyaBelum }), [titik, posisi, hanyaBelum]);
  const dekat = useMemo(() => jumlahDalamRadius(titik, posisi, RADIUS_RINGKAS, { hanyaBelum }), [titik, posisi, hanyaBelum]);

  const titikTujuan = useMemo(() => {
    if (!tujuan) return null;
    const lat = parseKoordinat(tujuan.koordinat_latitude);
    const lng = parseKoordinat(tujuan.koordinat_longitude);
    return lat === null || lng === null ? null : { lat, lng };
  }, [tujuan]);
  const pandu = statusPandu(posisi, titikTujuan);

  // Getar sekali saat tiba (bila perangkat mendukung) — petugas sering
  // berjalan sambil melihat sekeliling, bukan layar.
  const sudahTibaRef = useRef(false);
  useEffect(() => {
    if (pandu?.tiba && !sudahTibaRef.current) {
      sudahTibaRef.current = true;
      try { navigator.vibrate?.(200); } catch { /* diam */ }
    }
    if (!pandu?.tiba) sudahTibaRef.current = false;
  }, [pandu?.tiba]);
  useEffect(() => { setYakinTitik(false); sudahTibaRef.current = false; }, [tujuan?.id]);
  // Lokasi dimatikan → pemandu berhenti juga.
  useEffect(() => { if (!posisi && tujuan) onPandu(null); }, [posisi, tujuan, onPandu]);

  if (!posisi) return null;
  const presisi = cukupPresisi(posisi);
  const alasanPresisi = `Tunggu GPS ≤ ${AKURASI_TITIK_M} m (kini ±${Math.round(posisi.accuracy)} m) — coba di area terbuka`;

  const kartu = "pointer-events-auto rounded-lg border bg-background/95 backdrop-blur shadow-lg";

  // ── Mode PANDU: menuju satu aset ──
  if (tujuan && pandu) {
    const tiba = pandu.tiba;
    return (
      <div className="absolute left-1/2 -translate-x-1/2 top-2 z-[600] w-[min(21rem,calc(100%-6rem))] pointer-events-none" data-peta-panel="lapangan" data-testid="panel-lapangan-pandu">
        <div className={`${kartu} ${tiba ? "border-emerald-400 dark:border-emerald-600" : "border-violet-400 dark:border-violet-600"} px-2 py-1.5`}>
          <div className="flex items-center gap-1.5">
            {tiba
              ? <CircleCheck className="w-4 h-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              : <Compass className="w-4 h-4 shrink-0 text-violet-600 dark:text-violet-400" />}
            <div className="flex-1 min-w-0">
              <p className="text-[11px] font-semibold truncate" data-testid="panel-lapangan-pandu-judul">
                {tiba ? `Anda di lokasi ${namaAset(tujuan)}` : `Menuju ${namaAset(tujuan)}`}
              </p>
              <p className="text-[10px] text-muted-foreground flex items-center gap-1 tabular-nums">
                {!tiba && <ArrowUp className="w-3 h-3 text-violet-600 dark:text-violet-400" style={{ transform: `rotate(${Math.round(pandu.arah)}deg)` }} />}
                <span data-testid="panel-lapangan-pandu-jarak">{tiba ? `± ${formatJarak(pandu.jarak)} dari titik tercatat` : `${formatJarak(pandu.jarak)} · ${mataAngin(pandu.arah)}`}</span>
                <PilAkurasi akurasi={posisi.accuracy} />
              </p>
            </div>
            <button type="button" onClick={() => onPandu(null)} aria-label="Selesai memandu"
              className="shrink-0 w-7 h-7 rounded flex items-center justify-center hover:bg-muted" data-testid="panel-lapangan-pandu-selesai">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {onEdit && (
              <button type="button" onClick={() => onEdit(tujuan)} data-testid="panel-lapangan-pandu-edit"
                className="flex-1 min-w-[6.5rem] h-8 rounded-md bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-semibold flex items-center justify-center gap-1">
                <PencilLine className="w-3.5 h-3.5" />Edit / foto aset
              </button>
            )}
            {tiba && onSetTitik && (
              <button type="button" disabled={!presisi} data-testid="panel-lapangan-pandu-set-titik"
                title={presisi ? "" : alasanPresisi}
                onClick={() => {
                  if (!yakinTitik) { setYakinTitik(true); return; }
                  if (onSetTitik(tujuan)) setYakinTitik(false);
                }}
                className="flex-1 min-w-[6.5rem] h-8 rounded-md border border-emerald-500 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-900/30 dark:hover:text-emerald-200 disabled:opacity-50 text-[11px] font-semibold flex items-center justify-center gap-1">
                <MapPinned className="w-3.5 h-3.5" />{yakinTitik ? "Ketuk lagi: pindahkan titik" : "Titik = lokasi saya"}
              </button>
            )}
            {!tiba && pandu.jarak > JARAK_GOOGLE_MAPS && (
              <a href={urlGoogleMaps(titikTujuan.lat, titikTujuan.lng)} target="_blank" rel="noopener noreferrer"
                data-testid="panel-lapangan-pandu-gmaps"
                className="flex-1 min-w-[6.5rem] h-8 rounded-md border border-border hover:bg-muted text-[11px] font-semibold flex items-center justify-center gap-1">
                <ExternalLink className="w-3.5 h-3.5" />Rute Google Maps
              </a>
            )}
          </div>
          {tiba && onSetTitik && !presisi && (
            <p className="text-[9.5px] text-amber-700 dark:text-amber-400 mt-1">{alasanPresisi}.</p>
          )}
        </div>
      </div>
    );
  }

  // ── Mode RINGKAS / DAFTAR ──
  const pertama = daftar[0];
  return (
    <div className="absolute left-1/2 -translate-x-1/2 top-2 z-[600] w-[min(21rem,calc(100%-6rem))] pointer-events-none" data-peta-panel="lapangan" data-testid="panel-lapangan">
      <div className={`${kartu} border-blue-300 dark:border-blue-700`}>
        <button type="button" onClick={() => setBuka((b) => !b)} aria-expanded={buka}
          className="w-full flex items-center gap-1.5 px-2 py-1 text-left hover:bg-muted rounded-lg"
          data-testid="panel-lapangan-toggle">
          <LocateFixed className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400 shrink-0" />
          <span className="flex-1 min-w-0 truncate text-[11px]">
            <b className="tabular-nums">{dekat}</b> aset{hanyaBelum ? " belum didata" : ""} ≤ {RADIUS_RINGKAS} m
            {pertama && <span className="text-muted-foreground"> · terdekat {formatJarak(pertama.jarak)}</span>}
          </span>
          <PilAkurasi akurasi={posisi.accuracy} />
          <ChevronDown className={`w-3.5 h-3.5 shrink-0 text-muted-foreground transition-transform ${buka ? "rotate-180" : ""}`} />
        </button>
        {buka && (
          <div className="px-2 pb-2" data-testid="panel-lapangan-isi">
            {onTambahDiSini && (
              <>
                <button type="button" onClick={() => { setBuka(false); onTambahDiSini(); }} disabled={!presisi} data-testid="panel-lapangan-tambah"
                  className="w-full h-8 mt-0.5 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-[11px] font-semibold flex items-center justify-center gap-1">
                  <Plus className="w-3.5 h-3.5" />Tambah aset di lokasi saya
                </button>
                {!presisi && <p className="text-[9.5px] text-amber-700 dark:text-amber-400 mt-0.5">{alasanPresisi}.</p>}
              </>
            )}
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground py-1 cursor-pointer">
              <input type="checkbox" checked={hanyaBelum} onChange={(e) => setHanyaBelum(e.target.checked)}
                className="min-w-0 min-h-0" data-testid="panel-lapangan-belum" />
              Hanya yang belum diinventarisasi
            </label>
            {daftar.length === 0 ? (
              <p className="text-[10px] text-muted-foreground py-1">Tidak ada aset {hanyaBelum ? "belum didata " : ""}dalam 5 km.</p>
            ) : (
              <ul className="space-y-0.5">
                {daftar.map((t) => (
                  <li key={t.row.id} className="flex items-center gap-0.5">
                    {/* Daftar dilipat dulu: popup pin dibuka di bawah panel ini dan
                        tombol-tombolnya harus bisa diketuk. */}
                    <button type="button" onClick={() => { setBuka(false); onFokus(t.row); }}
                      className="flex-1 min-w-0 flex items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-muted min-h-0"
                      title="Tampilkan di peta" data-testid={`terdekat-${t.row.id}`}>
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
                    <button type="button" onClick={() => onPandu(t.row)} aria-label={`Pandu ke ${namaAset(t.row)}`} title="Pandu ke aset ini"
                      className="shrink-0 w-7 h-7 min-w-0 min-h-0 rounded flex items-center justify-center text-violet-700 hover:bg-violet-100 hover:text-violet-800 dark:text-violet-300 dark:hover:bg-violet-900/40 dark:hover:text-violet-200"
                      data-testid={`terdekat-pandu-${t.row.id}`}>
                      <Compass className="w-3.5 h-3.5" />
                    </button>
                    {onEdit && (
                      <button type="button" onClick={() => onEdit(t.row)} aria-label={`Edit ${namaAset(t.row)}`} title="Edit aset"
                        className="shrink-0 w-7 h-7 min-w-0 min-h-0 rounded flex items-center justify-center text-amber-700 hover:bg-amber-100 hover:text-amber-800 dark:text-amber-400 dark:hover:bg-amber-900/40 dark:hover:text-amber-300"
                        data-testid={`terdekat-edit-${t.row.id}`}>
                        <PencilLine className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[9.5px] text-muted-foreground mt-1 leading-snug">
              ◎ ketuk = kembali ke lokasi Anda · 🧭 = pandu ke aset (garis ungu). Ketuk pin untuk mengatur titiknya ke lokasi Anda.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
