import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Scale, Coins, TrendingDown, Wallet, AlertTriangle,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Penilaian — Fase 5 tahap awal: posisi penyusutan aset tetap
 * (PMK 65/2017: garis lurus tanpa residu, semesteran, konvensi semester
 * penuh; masa manfaat KMK 295/2019 jo. 266/2023 per kelompok). Revaluasi
 * dan referensi masa manfaat yang dapat dikelola menyusul.
 */
export default function PenilaianPage({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [perTanggal, setPerTanggal] = useState(new Date().toISOString().slice(0, 10));

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/penilaian/penyusutan`, { params: { per_tanggal: perTanggal } })
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat posisi penyusutan"))
      .finally(() => setLoading(false));
  }, [perTanggal]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;

  return (
    <div className="min-h-screen bg-background" data-testid="penilaian-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="penilaian-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-violet-600 flex items-center justify-center flex-shrink-0">
            <Scale className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Penilaian — Posisi Penyusutan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Garis lurus semesteran (PMK 65/2017) · masa manfaat KMK 295/2019 jo. 266/2023
            </p>
          </div>
          <Input
            type="date"
            value={perTanggal}
            onChange={(e) => e.target.value && setPerTanggal(e.target.value)}
            className="h-8 w-36 text-xs flex-shrink-0"
            data-testid="penilaian-tanggal"
            aria-label="Posisi per tanggal"
          />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-violet-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-perolehan">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.nilai_perolehan)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan ({data.total.jumlah} aset disusutkan)</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-akumulasi">
                <TrendingDown className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.akumulasi)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Akumulasi penyusutan</p>
              </div>
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="penilaian-stat-buku">
                <Wallet className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.nilai_buku)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai buku</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-habis">
                <AlertTriangle className="w-5 h-5 text-amber-500 mx-auto mb-1" />
                <p className="text-base font-bold text-foreground leading-none">{data.jumlah_habis}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Habis masa manfaat (nilai buku 0, tetap tersaji)</p>
              </div>
            </div>

            {/* ── Per golongan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border">
                <p className="text-xs font-bold text-foreground">Per Golongan — posisi per {data.per_tanggal}</p>
              </div>
              {data.per_golongan.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Belum ada aset yang dapat dihitung — lengkapi tanggal perolehan & referensi masa manfaat.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.per_golongan.map((g) => (
                    <li key={g.golongan} className="px-3 py-2" data-testid={`penilaian-gol-${g.golongan}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-foreground truncate">
                          {g.golongan} — {g.uraian} <span className="text-muted-foreground font-normal">({g.jumlah} aset)</span>
                        </p>
                        <p className="text-xs font-bold text-foreground flex-shrink-0">{fmtRp(g.nilai_buku)}</p>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Perolehan {fmtRp(g.nilai_perolehan)} − akumulasi {fmtRp(g.akumulasi)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── Daftar telaah ── */}
            {(data.henti.length > 0 || data.tanpa_referensi.length > 0) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="bg-card rounded-xl border border-red-500/40 shadow-sm overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-xs font-bold text-foreground">Telaah Henti Susut ({data.henti.length})</p>
                  </div>
                  <ul className="divide-y divide-border/60 max-h-64 overflow-y-auto">
                    {data.henti.map((a) => (
                      <li key={a.id} className="px-3 py-1.5">
                        <p className="text-[11px] font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-red-500/90">{a.alasan}</p>
                      </li>
                    ))}
                    {data.henti.length === 0 && <li className="text-[11px] text-muted-foreground text-center py-3">Tidak ada.</li>}
                  </ul>
                </div>
                <div className="bg-card rounded-xl border border-amber-500/40 shadow-sm overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-xs font-bold text-foreground">Perlu Referensi/Data ({data.tanpa_referensi.length})</p>
                  </div>
                  <ul className="divide-y divide-border/60 max-h-64 overflow-y-auto">
                    {data.tanpa_referensi.map((a) => (
                      <li key={a.id} className="px-3 py-1.5">
                        <p className="text-[11px] font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-amber-600 dark:text-amber-400">{a.alasan}</p>
                      </li>
                    ))}
                    {data.tanpa_referensi.length === 0 && <li className="text-[11px] text-muted-foreground text-center py-3">Tidak ada.</li>}
                  </ul>
                </div>
              </div>
            )}

            {Object.keys(data.tidak || {}).length > 0 && (
              <div className="bg-card rounded-xl border border-border p-3">
                <p className="text-xs font-bold text-foreground mb-1">Bukan objek penyusutan</p>
                {Object.entries(data.tidak).map(([alasan, n]) => (
                  <p key={alasan} className="text-[11px] text-muted-foreground">{n} aset — {alasan}</p>
                ))}
              </div>
            )}

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>
    </div>
  );
}
