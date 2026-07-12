import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, FileX, SearchX, Flame, Coins,
} from "lucide-react";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_JALUR = { tidak_ditemukan: SearchX, rusak_berat: Flame };
const WARNA_JALUR = {
  tidak_ditemukan: "text-amber-500 border-amber-500/40",
  rusak_berat: "text-red-500 border-red-500/40",
};

/**
 * Penghapusan — Fase 6 tahap awal: kandidat usul hapus dijaring otomatis
 * dari hasil inventarisasi (PMK 83/2016): Tidak Ditemukan → penelusuran +
 * telaah TGR; Rusak Berat → pemusnahan/pemindahtanganan. Tiket usulan
 * formal + arsip SK menyusul sesuai masterplan.
 */
export default function PenghapusanPage({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    axios.get(`${API}/penghapusan/kandidat`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat kandidat penghapusan"))
      .finally(() => setLoading(false));
  }, []);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;

  return (
    <div className="min-h-screen bg-background" data-testid="penghapusan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="penghapusan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-red-700 flex items-center justify-center flex-shrink-0">
            <FileX className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Penghapusan — Kandidat Usul Hapus</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Dijaring dari hasil inventarisasi · PMK 83/PMK.06/2016
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-red-700" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penghapusan-stat-jumlah">
                <FileX className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.jumlah}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Kandidat usul hapus</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penghapusan-stat-nilai">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(data.ringkasan.nilai)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan kandidat</p>
              </div>
            </div>

            {/* ── Per jalur ── */}
            {Object.entries(data.jalur).map(([key, b]) => {
              const Icon = IKON_JALUR[key] || FileX;
              const warna = WARNA_JALUR[key] || "text-red-500 border-border";
              return (
                <div key={key} className={`bg-card rounded-xl border shadow-sm overflow-hidden ${warna.split(" ")[1]}`}>
                  <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                    <Icon className={`w-4 h-4 ${warna.split(" ")[0]}`} />
                    <p className="text-xs font-bold text-foreground flex-1">{b.label} ({b.jumlah})</p>
                    <span className="text-xs font-bold text-foreground">{fmtRp(b.nilai)}</span>
                  </div>
                  <p className="px-3 pt-2 text-[11px] text-muted-foreground">{b.alasan}</p>
                  {b.rows.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-4">Tidak ada kandidat — data inventarisasi sehat.</p>
                  ) : (
                    <ul className="divide-y divide-border/60 mt-2">
                      {b.rows.map((a) => (
                        <li key={a.id} className="px-3 py-2 flex items-center justify-between gap-2" data-testid={`penghapusan-row-${a.id}`}>
                          <div className="min-w-0">
                            <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                            <p className="text-[10px] text-muted-foreground font-mono truncate">
                              {a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}
                              {a.keterangan ? ` · ${a.keterangan}` : ""}
                            </p>
                          </div>
                          <span className="text-xs font-bold text-foreground flex-shrink-0">{fmtRp(a.harga)}</span>
                        </li>
                      ))}
                      {b.dipangkas && (
                        <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 500 pertama.</li>
                      )}
                    </ul>
                  )}
                </div>
              );
            })}

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>
    </div>
  );
}
