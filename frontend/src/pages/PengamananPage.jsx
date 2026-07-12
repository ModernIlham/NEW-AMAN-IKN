import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ShieldCheck, Scale, BadgeCheck, Camera,
  QrCode, MapPin, UserCheck, FileText,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_KEKURANGAN = {
  foto: Camera,
  register: QrCode,
  lokasi: MapPin,
  pengguna: UserCheck,
  bast: FileText,
};

/**
 * Pengamanan — Fase 3 tahap awal: dasbor tertib administrasi data aset
 * (penangkal temuan "barang tanpa foto/label/dokumen") + daftar pantau
 * sengketa dari data inventarisasi. Arsip dokumen kepemilikan & jadwal
 * pemeliharaan menyusul sesuai masterplan.
 */
export default function PengamananPage({ onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog daftar aset kurang: {jenis, label, rows, loading}
  const [detail, setDetail] = useState(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    axios.get(`${API}/pengamanan/ringkasan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat ringkasan pengamanan"))
      .finally(() => setLoading(false));
  }, []);

  const openDetail = async (jenis, label) => {
    setDetail({ jenis, label, rows: [], loading: true });
    try {
      const r = await axios.get(`${API}/pengamanan/aset-kurang`, {
        params: { jenis, page_size: 200 },
      });
      setDetail({ jenis, label, rows: r.data?.items || [], total: r.data?.total || 0, loading: false });
    } catch {
      toast.error("Gagal memuat daftar aset");
      setDetail(null);
    }
  };

  const pct = (n) => (data?.total_aset ? Math.round((n / data.total_aset) * 100) : 0);

  return (
    <div className="min-h-screen bg-background" data-testid="pengamanan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengamanan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pengamanan — Tertib Administrasi</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Kesehatan data {data?.total_aset ?? "…"} aset + daftar pantau sengketa
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-amber-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="pengamanan-stat-lengkap">
                <BadgeCheck className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.lengkap}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Data lengkap ({pct(data.lengkap)}%)</p>
              </div>
              {Object.entries(data.label_kekurangan || {}).map(([jenis, label]) => {
                const Icon = IKON_KEKURANGAN[jenis] || FileText;
                const n = data.kekurangan?.[jenis] || 0;
                return (
                  <button
                    key={jenis}
                    type="button"
                    onClick={() => n > 0 && openDetail(jenis, label)}
                    disabled={n === 0}
                    className={`bg-card rounded-xl border p-3 text-center transition-colors min-w-0 min-h-0 ${
                      n > 0 ? "border-amber-500/40 hover:bg-amber-500/10" : "border-border opacity-60"
                    }`}
                    data-testid={`pengamanan-stat-${jenis}`}
                  >
                    <Icon className={`w-5 h-5 mx-auto mb-1 ${n > 0 ? "text-amber-500" : "text-muted-foreground"}`} />
                    <p className="text-lg font-bold text-foreground leading-none">{n}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
                  </button>
                );
              })}
            </div>

            {/* ── Daftar pantau sengketa ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <Scale className="w-4 h-4 text-violet-500" />
                <p className="text-xs font-bold text-foreground">Daftar Pantau Sengketa</p>
                <span className="px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                  {data.jumlah_sengketa}
                </span>
              </div>
              {data.jumlah_sengketa === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Tidak ada aset berstatus sengketa — data dari klasifikasi inventarisasi.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.sengketa.map((s) => (
                    <li key={s.id} className="p-3" data-testid={`pengamanan-sengketa-${s.id}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-foreground">{s.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground">{s.asset_code} · {s.NUP}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[s.nomor_perkara && `Perkara ${s.nomor_perkara}`,
                          s.pihak_bersengketa && `vs ${s.pihak_bersengketa}`,
                          s.keterangan].filter(Boolean).join(" · ") || "—"}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              Arsip dokumen kepemilikan (sertifikat/BPKB) & jadwal pemeliharaan menyusul — masterplan Fase 3.
            </p>
          </>
        )}
      </main>

      {/* ── Dialog daftar aset kurang ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{detail?.label}</DialogTitle>
            <DialogDescription className="text-xs">
              {detail?.total ?? 0} aset — lengkapi lewat modul Inventarisasi (edit aset / mode lapangan).
            </DialogDescription>
          </DialogHeader>
          {detail?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-amber-600" /></div>
          ) : (
            <ul className="space-y-1.5">
              {(detail?.rows || []).map((a) => (
                <li key={a.id} className="rounded-lg border border-border p-2 text-xs flex items-center justify-between gap-2">
                  <span className="text-foreground/90 min-w-0 truncate">{a.asset_name || "-"}</span>
                  <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{a.asset_code} · {a.NUP}</span>
                </li>
              ))}
              {(detail?.rows || []).length === 200 && (
                <li className="text-[11px] text-muted-foreground text-center pt-1">Menampilkan 200 pertama.</li>
              )}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
