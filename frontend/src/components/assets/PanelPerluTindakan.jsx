import React, { useState } from "react";
import { AlertTriangle, GitCompareArrows, Lock, Ban, Eye, RotateCcw, Trash2, Loader2, ImageIcon } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { INFO_JENIS, labelAset } from "@/lib/perluTindakan";

const IKON_JENIS = { konflik: GitCompareArrows, terkunci: Lock, ditolak: Ban };
const WARNA_JENIS = {
  konflik: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  terkunci: "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200",
  ditolak: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300",
};

function fmtWaktu(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

// Diangkat ke level modul (bukan di dalam panel) agar tidak remount tiap render.
function KartuTindakan({ entri, onLihat, onUlang, onAbaikan }) {
  const [sibuk, setSibuk] = useState(null);
  const info = INFO_JENIS[entri.jenis];
  const Ikon = IKON_JENIS[entri.jenis] || AlertTriangle;
  const { nama, kode } = labelAset(entri);
  const lain = entri.kegiatanLain === true;
  const jalankan = (aksi, fn) => async () => {
    if (sibuk) return;
    setSibuk(aksi);
    try { await fn(entri); } finally { setSibuk(null); }
  };
  return (
    <li className="rounded-lg border border-border bg-card p-3 space-y-2" data-testid={`tindakan-item-${entri.statusKey}`}>
      <div className="flex items-start gap-2 min-w-0">
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold flex-shrink-0 ${WARNA_JENIS[entri.jenis]}`}>
          <Ikon className="w-3 h-3" /> {info.judul}
        </span>
        {entri.queuedAt && (
          <span className="ml-auto text-[11px] text-muted-foreground flex-shrink-0">{fmtWaktu(entri.queuedAt)}</span>
        )}
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-sm text-foreground truncate">{nama}</p>
        {kode && <p className="text-xs text-muted-foreground font-mono truncate">{kode}</p>}
        {lain && (
          <p className="text-xs text-amber-700 dark:text-amber-400 mt-0.5">
            Milik kegiatan lain{entri.namaKegiatan ? `: ${entri.namaKegiatan}` : ""} — buka kegiatan itu untuk meninjau barisnya.
          </p>
        )}
      </div>
      {entri.pesan && (
        <p className="text-xs rounded-md bg-muted px-2 py-1.5 text-foreground break-words" data-testid={`tindakan-pesan-${entri.statusKey}`}>
          {entri.pesan}
        </p>
      )}
      <p className="text-xs text-muted-foreground">{info.sebab} {info.saran}</p>
      {entri.jenis === "konflik" && entri.adaMedia && (
        <p className="text-xs text-orange-700 dark:text-orange-400 flex items-start gap-1">
          <ImageIcon className="w-3.5 h-3.5 mt-px flex-shrink-0" />
          Simpanan ini berisi foto/dokumen sehingga tidak bisa dikirim ulang otomatis — unduh cadangan saat diminta, abaikan, lalu tambahkan ulang fotonya.
        </p>
      )}
      <div className="flex flex-wrap gap-2 pt-1">
        {entri.bisaDibuka && !lain && (
          <Button size="sm" variant="outline" className="h-8 gap-1 text-xs hover:bg-muted hover:text-foreground"
            onClick={jalankan("lihat", onLihat)} disabled={!!sibuk} data-testid={`tindakan-lihat-${entri.statusKey}`}>
            {sibuk === "lihat" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />} Lihat aset
          </Button>
        )}
        <Button size="sm" className="h-8 gap-1 text-xs bg-teal-700 text-white hover:bg-teal-800 hover:text-white"
          onClick={jalankan("ulang", onUlang)} disabled={!!sibuk} data-testid={`tindakan-ulang-${entri.statusKey}`}>
          {sibuk === "ulang" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />} {info.labelUlang}
        </Button>
        <Button size="sm" variant="ghost" className="h-8 gap-1 text-xs text-rose-700 dark:text-rose-400 hover:bg-rose-50 hover:text-rose-800 dark:hover:bg-rose-900/30 dark:hover:text-rose-300"
          onClick={jalankan("abaikan", onAbaikan)} disabled={!!sibuk} data-testid={`tindakan-abaikan-${entri.statusKey}`}>
          <Trash2 className="w-3.5 h-3.5" /> Abaikan
        </Button>
      </div>
    </li>
  );
}

/**
 * Panel daftar simpanan yang perlu tindakan manual (konflik versi, kegiatan
 * terkunci, ditolak server). Dibuka dari lencana oranye di header — tiap item
 * bisa langsung dibuka barisnya, dikirim ulang, atau diabaikan.
 */
export default function PanelPerluTindakan({ open, onOpenChange, daftar, onLihat, onUlang, onAbaikan }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="panel-perlu-tindakan">
        <DialogHeader className="text-left">
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-600 dark:text-orange-400" />
            Perlu Tindakan ({daftar.length})
          </DialogTitle>
          <DialogDescription>
            Simpanan di bawah tertahan dan tidak bisa diselesaikan tombol Sinkronkan. Perubahan berikutnya pada aset yang sama ikut menunggu sampai item ini diselesaikan.
          </DialogDescription>
        </DialogHeader>
        {daftar.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center" data-testid="panel-perlu-tindakan-kosong">
            Semua simpanan sudah beres. Tidak ada yang perlu ditinjau.
          </p>
        ) : (
          <ul className="space-y-2">
            {daftar.map(entri => (
              <KartuTindakan key={entri.statusKey} entri={entri} onLihat={onLihat} onUlang={onUlang} onAbaikan={onAbaikan} />
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
