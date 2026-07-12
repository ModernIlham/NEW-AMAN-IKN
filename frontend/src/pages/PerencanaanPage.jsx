import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ClipboardList, CheckCircle2, XCircle, Coins,
} from "lucide-react";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_KONDISI = {
  "Baik": "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  "Rusak Ringan": "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  "Rusak Berat": "bg-red-500/15 text-red-600 dark:text-red-400",
};

/**
 * Perencanaan — Fase 4 tahap awal: kandidat usulan RKBMN pemeliharaan
 * (PMK 153/2021). Menyaring aset layak (Baik/RR, dioperasikan) vs tidak
 * (rusak berat/idle/nonaktif) + riwayat biaya pemeliharaan per aset.
 * RKBMN pengadaan + sanding SBSK menyusul sesuai masterplan.
 */
export default function PerencanaanPage({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tahun, setTahun] = useState(new Date().getFullYear());

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/perencanaan/rkbmn-pemeliharaan`, { params: { tahun } })
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat kandidat RKBMN"))
      .finally(() => setLoading(false));
  }, [tahun]);

  const fmtRp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
  const th = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-background" data-testid="perencanaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="perencanaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <ClipboardList className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Perencanaan — Kandidat RKBMN Pemeliharaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Saringan kelayakan usulan (PMK 153/2021) + riwayat biaya per aset
            </p>
          </div>
          <select
            value={tahun}
            onChange={(e) => setTahun(parseInt(e.target.value, 10))}
            className="h-8 px-2 rounded-lg border border-border bg-background text-xs text-foreground flex-shrink-0"
            data-testid="perencanaan-tahun"
            aria-label="Tahun anggaran riwayat biaya"
          >
            {[th, th - 1, th - 2].map((t) => <option key={t} value={t}>TA {t}</option>)}
          </select>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-blue-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="perencanaan-stat-layak">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.layak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Layak diusulkan</p>
              </div>
              <div className="bg-card rounded-xl border border-red-500/40 p-3 text-center" data-testid="perencanaan-stat-tidak">
                <XCircle className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.tidak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Tidak layak (lihat alasan)</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="perencanaan-stat-biaya">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(data.ringkasan.total_biaya_riwayat)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Biaya pemeliharaan TA {data.tahun} (aset layak)</p>
              </div>
            </div>

            {/* ── Daftar layak ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <p className="text-xs font-bold text-foreground">Layak Diusulkan — biaya riwayat terbesar dulu</p>
              </div>
              {data.layak.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">Tidak ada aset layak — lengkapi kondisi aset di modul Inventarisasi.</p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.layak.slice(0, 100).map((a) => (
                    <li key={a.id} className="px-3 py-2 flex items-center justify-between gap-2" data-testid={`perencanaan-layak-${a.id}`}>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-muted-foreground font-mono truncate">
                          {a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_KONDISI[a.condition] || "bg-muted text-muted-foreground"}`}>
                          {a.condition || "-"}
                        </span>
                        <span className="text-xs font-bold text-foreground">
                          {a.riwayat_jumlah > 0 ? `${a.riwayat_jumlah}× · ${fmtRp(a.riwayat_biaya)}` : "belum ada riwayat"}
                        </span>
                      </div>
                    </li>
                  ))}
                  {data.layak.length > 100 && (
                    <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 100 pertama dari {data.ringkasan.layak}.</li>
                  )}
                </ul>
              )}
            </div>

            {/* ── Daftar tidak layak ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-500" />
                <p className="text-xs font-bold text-foreground">Tidak Layak — beserta jalur yang benar</p>
              </div>
              {data.tidak.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">Semua aset layak diusulkan.</p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.tidak.slice(0, 100).map((a) => (
                    <li key={a.id} className="px-3 py-2" data-testid={`perencanaan-tidak-${a.id}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{a.asset_code} · {a.NUP}</span>
                      </div>
                      <p className="text-[11px] text-red-500/90 mt-0.5">{a.alasan}</p>
                    </li>
                  ))}
                  {data.tidak.length > 100 && (
                    <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 100 pertama dari {data.ringkasan.tidak}.</li>
                  )}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>
    </div>
  );
}
