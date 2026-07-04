import React, { useState, useEffect } from "react";
import {
  BookOpen, Loader2, MapPin, User as UserIcon, Briefcase, Ticket,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { getApiError } from "@/lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatTanggal = (iso) => {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleDateString("id-ID", {
      day: "2-digit", month: "long", year: "numeric",
    });
  } catch {
    return iso;
  }
};

const statusBadgeClass = (status) => (
  status === "Ditemukan" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
  : status === "Tidak Ditemukan" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
  : status === "Berlebih" ? "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300"
  : status === "Sengketa" ? "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300"
  : "bg-muted text-muted-foreground"
);

/**
 * Kartu Inventarisasi — riwayat pengesahan sebuah aset LINTAS kegiatan.
 * Query berdasarkan identitas aset (prioritas kode_register; fallback
 * kode barang + NUP), bukan activity_id, sehingga riwayat dari semua
 * kegiatan yang pernah disahkan ikut tampil.
 *
 * Lazy-loaded oleh DashboardPage (pola sama dengan dialog lazy lain).
 */
export default function KartuInventarisasiDialog({ open, identity, onClose }) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!open || !identity) { setData(null); return; }
    const params = {};
    if (identity.kode_register) params.kode_register = identity.kode_register;
    else {
      if (identity.asset_code) params.asset_code = identity.asset_code;
      if (identity.NUP) params.NUP = identity.NUP;
    }
    if (!params.kode_register && !params.asset_code) {
      toast.error("Aset belum memiliki kode register atau kode barang");
      onClose?.();
      return;
    }
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/assets/kartu-inventarisasi`, { params })
      .then(r => { if (!cancelled) setData(r.data); })
      .catch(err => {
        if (!cancelled) {
          toast.error(getApiError(err, "Gagal memuat kartu inventarisasi"));
          onClose?.();
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, identity?.kode_register, identity?.asset_code, identity?.NUP]);

  const asset = data?.asset || identity || {};
  const history = data?.history || [];

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose?.(); }}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto" data-testid="kartu-inventarisasi-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" />
            Kartu Inventarisasi
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Riwayat pengesahan aset ini di seluruh kegiatan inventarisasi.
          </DialogDescription>
        </DialogHeader>

        {/* Identitas aset */}
        <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm font-bold text-foreground">{asset.asset_code || "-"}</span>
            {asset.NUP && (
              <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded font-medium">NUP {asset.NUP}</span>
            )}
          </div>
          <p className="text-sm font-semibold text-foreground">{asset.asset_name || "-"}</p>
          {asset.kode_register && (
            <p className="text-[11px] font-mono text-muted-foreground break-all">Reg: {asset.kode_register}</p>
          )}
        </div>

        {/* Timeline riwayat */}
        {loading ? (
          <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            <span className="text-sm">Memuat riwayat...</span>
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Ticket className="w-10 h-10 mx-auto mb-2 opacity-40" />
            <p className="text-sm">Belum ada riwayat pengesahan untuk aset ini.</p>
            <p className="text-xs mt-1">Riwayat tercatat saat sebuah kegiatan disahkan.</p>
          </div>
        ) : (
          <div className="space-y-0" data-testid="kartu-history-list">
            {history.map((h, i) => (
              <div key={h.id || i} className="relative pl-5 pb-4 last:pb-0">
                {/* Garis timeline */}
                {i < history.length - 1 && (
                  <div className="absolute left-[5px] top-4 bottom-0 w-px bg-border" />
                )}
                <div className="absolute left-0 top-1.5 w-[11px] h-[11px] rounded-full border-2 border-blue-500 bg-card" />
                <div className="rounded-lg border border-border p-2.5 space-y-1.5 bg-card">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <span className="text-[11px] font-mono font-bold bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 px-1.5 py-0.5 rounded">
                      {h.ticket_number || "-"}
                    </span>
                    <span className="text-[11px] text-muted-foreground">{formatTanggal(h.tanggal_pengesahan)}</span>
                  </div>
                  <p className="text-xs font-semibold text-foreground">{h.activity_name || "-"}</p>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${statusBadgeClass(h.inventory_status)}`}>
                      {h.inventory_status || "Belum"}
                    </span>
                    {h.condition && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                        h.condition === "Baik" ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400" : "bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400"
                      }`}>{h.condition}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground flex-wrap">
                    {h.location && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" />{h.location}</span>}
                    {h.user && <span className="flex items-center gap-0.5"><UserIcon className="w-3 h-3" />{h.user}</span>}
                    {h.eselon1 && <span className="flex items-center gap-0.5"><Briefcase className="w-3 h-3" />{h.eselon1}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
