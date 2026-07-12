import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Eye, RefreshCw, ChevronDown, BadgeCheck,
  UserCheck, Handshake, ArrowLeftRight, BookOpen, ShieldCheck, FileText,
} from "lucide-react";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_OBJEK = {
  penggunaan: UserCheck,
  pemanfaatan: Handshake,
  pemindahtanganan: ArrowLeftRight,
  penatausahaan: BookOpen,
  pengamanan_pemeliharaan: ShieldCheck,
};

/**
 * Wasdal — dasbor pemantauan tingkat KPB (PMK 207/2021, pustaka §8).
 * Temuan otomatis dari register yang sudah ada, dikelompokkan per lima
 * objek pemantauan; bahan pra-isi laporan wasdal semesteran (kanal resmi
 * pelaporan tetap Modul Wasdal SIMAN v2). Register penertiban ber-timer
 * 15 hari kerja & BA pemantauan insidentil menyusul sesuai masterplan.
 */
export default function WasdalPage({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [buka, setBuka] = useState(null); // kunci objek yang dibentangkan

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/wasdal/pemantauan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat pemantauan wasdal"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { muat(); }, [muat]);

  // Kelompokkan temuan sebuah objek per jenis → [{jenis, label, items}]
  const perJenis = (objek) => {
    const grup = {};
    (data?.temuan?.[objek] || []).forEach((t) => {
      (grup[t.jenis] = grup[t.jenis] || { jenis: t.jenis, label: t.label, items: [] })
        .items.push(t);
    });
    return Object.values(grup);
  };

  return (
    <div className="min-h-screen bg-background" data-testid="wasdal-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <Eye className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Wasdal — Pemantauan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {data ? `${data.periode?.label} · ${data.total_aset} aset dipantau` : "PMK 207/PMK.06/2021"}
            </p>
          </div>
          <button
            type="button"
            aria-label="Unduh laporan pemantauan (PDF)"
            onClick={() => downloadFileWithProgress(
              `${API}/wasdal/laporan-pdf`,
              `Laporan_Wasdal_${(data?.periode?.label || "periode").replace(/\s/g, "_")}.pdf`,
              { label: "Laporan Hasil Pemantauan Wasdal" },
            ).catch(() => {})}
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-laporan"
          >
            <FileText className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={muat}
            aria-label="Muat ulang"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-reload"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu per objek pemantauan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {Object.entries(data.label_objek || {}).map(([kunci, label]) => {
                const Icon = IKON_OBJEK[kunci] || Eye;
                const n = data.rekap?.per_objek?.[kunci] || 0;
                return (
                  <button
                    key={kunci}
                    type="button"
                    onClick={() => n > 0 && setBuka(buka === kunci ? null : kunci)}
                    disabled={n === 0}
                    className={`bg-card rounded-xl border p-3 text-center transition-colors min-w-0 min-h-0 ${
                      n > 0 ? "border-sky-500/40 hover:bg-sky-500/10" : "border-emerald-500/40 opacity-70"
                    }`}
                    data-testid={`wasdal-objek-${kunci}`}
                  >
                    {n > 0
                      ? <Icon className="w-5 h-5 mx-auto mb-1 text-sky-500" />
                      : <BadgeCheck className="w-5 h-5 mx-auto mb-1 text-emerald-500" />}
                    <p className="text-lg font-bold text-foreground leading-none">{n}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
                  </button>
                );
              })}
            </div>

            <p className="text-[11px] text-muted-foreground text-center">
              {data.rekap?.total || 0} temuan pemantauan — bahan pra-isi laporan wasdal;
              pelaporan resmi tetap melalui Modul Wasdal SIMAN v2.
            </p>

            {/* ── Rincian temuan per objek ── */}
            {Object.entries(data.label_objek || {}).map(([kunci, label]) => {
              const n = data.rekap?.per_objek?.[kunci] || 0;
              if (n === 0) return null;
              const Icon = IKON_OBJEK[kunci] || Eye;
              const terbuka = buka === kunci;
              return (
                <div key={kunci} className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setBuka(terbuka ? null : kunci)}
                    className="w-full px-3 py-2.5 flex items-center gap-2 hover:bg-muted transition-colors"
                    data-testid={`wasdal-seksi-${kunci}`}
                  >
                    <Icon className="w-4 h-4 text-sky-500 flex-shrink-0" />
                    <p className="text-xs font-bold text-foreground flex-1 text-left">{label}</p>
                    <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                      {n}
                    </span>
                    <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${terbuka ? "rotate-180" : ""}`} />
                  </button>
                  {terbuka && (
                    <div className="border-t border-border">
                      {perJenis(kunci).map((g) => (
                        <div key={g.jenis}>
                          <p className="px-3 pt-2.5 pb-1 text-[11px] font-semibold text-sky-600 dark:text-sky-400">
                            {g.label} · {g.items.length}
                          </p>
                          <ul className="divide-y divide-border/60">
                            {g.items.map((t, i) => (
                              <li key={`${g.jenis}-${t.asset_id || t.usulan_id || t.pemanfaatan_id || i}`} className="px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <p className="text-xs font-semibold text-foreground min-w-0 truncate">
                                    {t.asset_name || t.pihak || "-"}
                                  </p>
                                  {t.asset_code && (
                                    <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">
                                      {t.asset_code} · {t.NUP}
                                    </span>
                                  )}
                                </div>
                                {t.detail && (
                                  <p className="text-[11px] text-muted-foreground mt-0.5">{t.detail}</p>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                      {(data.terpotong?.[kunci] || 0) > 0 && (
                        <p className="text-[11px] text-muted-foreground text-center py-2">
                          +{data.terpotong[kunci]} temuan lain tidak ditampilkan (100 pertama per objek).
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              Menyusul: register penertiban (timer 15 hari kerja), BA pemantauan insidentil,
              dan generator laporan formulir PMK 207 — masterplan Fase 6.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
