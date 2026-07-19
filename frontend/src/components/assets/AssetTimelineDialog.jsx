import React, { useState, useEffect, useMemo } from "react";
import { History, Loader2, Landmark } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatTanggal = (iso) => {
  if (!iso) return "tanpa tanggal";
  try {
    return new Date(iso).toLocaleDateString("id-ID", {
      day: "2-digit", month: "long", year: "numeric",
    });
  } catch {
    return iso;
  }
};

// Warna badge per modul — konsisten light/dark lewat pasangan kelas.
const MODUL_BADGE = {
  inventarisasi: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  penggunaan: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  pemanfaatan: "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300",
  pemeliharaan: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  pengamanan: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
  penilaian: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  penghapusan: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  pemindahtanganan: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  pemusnahan: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  wasdal: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-900/40 dark:text-fuchsia-300",
  bast: "bg-lime-100 text-lime-700 dark:bg-lime-900/40 dark:text-lime-300",
  pembukuan: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
  siman: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
  aset: "bg-muted text-muted-foreground",
};

/**
 * Timeline Aset — riwayat perlakuan SATU aset fisik lintas modul.
 * Arsitektur W5: induk data = identitas aset (kode_register / kode+NUP),
 * bukan dokumen aset per kegiatan inventarisasi. Endpoint backend
 * menggabungkan pencatatan & pengesahan lintas kegiatan, Buku Barang,
 * PSP/idle/proses Penggunaan, Pemanfaatan, Pemeliharaan, Pengamanan,
 * Penilaian, Penghapusan, Pemindahtanganan, Pemusnahan, Wasdal, BAST,
 * audit, dan referensi resmi SIMAN V2 (PSP dll.).
 *
 * Lazy-loaded oleh DashboardPage (pola sama dengan dialog lazy lain).
 */
export default function AssetTimelineDialog({ open, assetId, onClose }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [filterModul, setFilterModul] = useState("");

  useEffect(() => {
    if (!open || !assetId) { setData(null); setFilterModul(""); return undefined; }
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/assets/${assetId}/timeline`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch((err) => {
        if (!cancelled) {
          toast.error(getApiError(err, "Gagal memuat timeline aset"));
          onClose?.();
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, assetId]);

  const aset = data?.aset || {};
  const labelModul = data?.label_modul || {};
  const ringkasan = data?.ringkasan || {};
  const psp = data?.psp_siman || {};
  const events = useMemo(() => {
    const semua = data?.events || [];
    return filterModul ? semua.filter((e) => e.modul === filterModul) : semua;
  }, [data, filterModul]);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose?.(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col overflow-hidden p-0"
        data-testid="asset-timeline-dialog">
        <DialogHeader className="px-4 pt-4 pb-2 border-b border-border flex-shrink-0">
          <DialogTitle className="flex items-center gap-2 text-sm break-words">
            <History className="w-4 h-4 text-primary flex-shrink-0" />
            Timeline Aset — {aset.asset_name || "…"}
          </DialogTitle>
          <DialogDescription className="text-[11px] break-words">
            {[aset.asset_code && `${aset.asset_code} · NUP ${aset.NUP || "-"}`,
              aset.kode_register && `Register ${aset.kode_register}`]
              .filter(Boolean).join(" · ") || "Riwayat perlakuan aset lintas modul"}
          </DialogDescription>
          {data && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                {data.jumlah_kegiatan || 0} kegiatan inventarisasi
              </span>
              {aset.condition && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  Kondisi: {aset.condition}
                </span>
              )}
              {aset.dihapus && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300">
                  Sudah dihapus dari daftar BMN
                </span>
              )}
            </div>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {loading && (
            <div className="flex items-center justify-center py-10 text-muted-foreground text-xs gap-2">
              <Loader2 className="w-4 h-4 animate-spin" /> Memuat timeline…
            </div>
          )}

          {!loading && data && (
            <>
              {/* Info PSP resmi dari SIMAN V2 — data impor yang kini dimanfaatkan */}
              {psp.no_psp && (
                <div className="mb-3 rounded-lg border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 px-3 py-2"
                  data-testid="timeline-psp-siman">
                  <p className="text-[11px] font-semibold text-sky-800 dark:text-sky-300 flex items-center gap-1.5">
                    <Landmark className="w-3.5 h-3.5" /> PSP resmi menurut SIMAN V2
                  </p>
                  <p className="text-[11px] text-sky-700 dark:text-sky-400 break-words">
                    No. {psp.no_psp}
                    {psp.tanggal_psp && ` — ${formatTanggal(psp.tanggal_psp)}`}
                    {psp.status_penggunaan && ` · ${psp.status_penggunaan}`}
                  </p>
                </div>
              )}

              {/* Chip filter per modul */}
              <div className="flex flex-wrap gap-1 mb-3">
                <button type="button" onClick={() => setFilterModul("")}
                  className={`min-w-0 min-h-0 text-[10px] px-2 py-1 rounded-full border ${!filterModul ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border"}`}
                  data-testid="timeline-filter-semua">
                  Semua ({(data.events || []).length})
                </button>
                {Object.entries(ringkasan).map(([m, n]) => (
                  <button key={m} type="button"
                    onClick={() => setFilterModul(filterModul === m ? "" : m)}
                    className={`min-w-0 min-h-0 text-[10px] px-2 py-1 rounded-full border ${filterModul === m ? "bg-primary text-primary-foreground border-primary" : "bg-background text-muted-foreground border-border"}`}
                    data-testid={`timeline-filter-${m}`}>
                    {labelModul[m] || m} ({n})
                  </button>
                ))}
              </div>

              {/* Garis waktu */}
              {events.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-8">
                  Belum ada event untuk filter ini.
                </p>
              ) : (
                <ol className="relative border-l-2 border-dashed border-border ml-2 space-y-3"
                  data-testid="timeline-events">
                  {events.map((e, i) => (
                    <li key={`${e.modul}-${e.jenis}-${i}`} className="ml-4 relative">
                      <span className="absolute -left-[23px] top-1 w-3 h-3 rounded-full bg-background border-2 border-primary" />
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={`text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded ${MODUL_BADGE[e.modul] || MODUL_BADGE.aset}`}>
                          {labelModul[e.modul] || e.modul}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {formatTanggal(e.tanggal)}
                        </span>
                      </div>
                      <p className="text-xs font-medium text-foreground break-words mt-0.5">{e.judul}</p>
                      {e.detail && (
                        <p className="text-[11px] text-muted-foreground break-words">{e.detail}</p>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </>
          )}
        </div>

        {/* Catatan arsitektur untuk pengguna */}
        <div className="px-4 py-2 border-t border-border flex-shrink-0">
          <p className="text-[10px] text-muted-foreground break-words">
            Induk data = identitas aset (register/kode+NUP). Kegiatan
            inventarisasi adalah pemutakhir berkala — aset yang sama di
            beberapa kegiatan otomatis dikenali satu.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
