import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Share2, Copy, Clock, Plus, Loader2, Link2, MessageSquare, MapPin,
  Trash2, RefreshCcw, Check, RotateCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { getApiError } from "../../lib/utils";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PRESET = [
  { label: "1 hari", jam: 24 }, { label: "3 hari", jam: 72 },
  { label: "7 hari", jam: 168 }, { label: "30 hari", jam: 720 },
];

function sisa(iso) {
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms) || ms <= 0) return "berakhir";
  const jam = Math.floor(ms / 3600000), hari = Math.floor(jam / 24);
  return hari >= 1 ? `${hari} hari lagi` : `${Math.max(1, jam)} jam lagi`;
}

/**
 * Bagikan peta kegiatan sebagai link kolaboratif ber-masa-tayang. Selama aktif,
 * siapa pun berlink dapat melihat titik aset, berkomentar, & menambah titik.
 * Dikelola operator/admin satker kegiatan; dapat diperpanjang & dibatalkan.
 */
export default function BagikanPetaDialog({ open, onClose, activity }) {
  const [shares, setShares] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [durasiJam, setDurasiJam] = useState(72);
  const [judul, setJudul] = useState("");
  const [izinTitik, setIzinTitik] = useState(true);
  const [izinKomentar, setIzinKomentar] = useState(true);
  const [tersalin, setTersalin] = useState("");
  const { confirm, confirmDialog } = useConfirm();

  const muat = useCallback(() => {
    if (!activity?.id) return;
    setLoading(true);
    axios.get(`${API}/peta/share`, { params: { activity_id: activity.id } })
      .then((r) => setShares(r.data?.items || []))
      .catch(() => setShares([]))
      .finally(() => setLoading(false));
  }, [activity?.id]);

  useEffect(() => { if (open) { muat(); setTersalin(""); } }, [open, muat]);

  const buat = async () => {
    setCreating(true);
    try {
      const r = await axios.post(`${API}/peta/share`, {
        activity_id: activity.id, judul: judul.trim(), durasi_jam: durasiJam,
        izinkan_titik_publik: izinTitik, izinkan_komentar_publik: izinKomentar,
      });
      toast.success("Link peta kolaboratif dibuat");
      setJudul("");
      muat();
      if (r.data?.link) salin(r.data.link, r.data.id);
    } catch (e) { toast.error(getApiError(e, "Gagal membuat link")); }
    finally { setCreating(false); }
  };

  const salin = async (link, sid) => {
    try {
      await navigator.clipboard.writeText(link);
      setTersalin(sid); setTimeout(() => setTersalin(""), 2000);
      toast.success("Link disalin");
    } catch { toast.error("Tak bisa menyalin — salin manual dari kotak link"); }
  };

  const bagikanWA = (link, judulShare) => {
    const teks = `${judulShare || "Peta Kolaboratif"} — bantu tandai & beri komentar:\n${link}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(teks)}`, "_blank", "noopener");
  };

  const bagikanNatif = async (link, judulShare) => {
    if (navigator.share) {
      try { await navigator.share({ title: judulShare || "Peta Kolaboratif", url: link }); } catch { /* dibatalkan */ }
    } else { salin(link); }
  };

  const perpanjang = async (sid, jam) => {
    try {
      await axios.put(`${API}/peta/share/${sid}/perpanjang`, { durasi_jam: jam });
      toast.success(`Diperpanjang ${jam >= 24 ? `${Math.round(jam / 24)} hari` : `${jam} jam`}`);
      muat();
    } catch (e) { toast.error(getApiError(e, "Gagal memperpanjang")); }
  };

  const batal = async (sid) => {
    const ok = await confirm({
      title: "Batalkan link peta?",
      description: "Link akan mati permanen untuk publik. Kontribusi yang sudah masuk tetap tersimpan. Untuk berbagi lagi, gunakan Terbitkan ulang.",
      confirmLabel: "Batalkan", variant: "danger",
    });
    if (!ok) return;
    try { await axios.post(`${API}/peta/share/${sid}/batal`); toast.success("Link dibatalkan"); muat(); }
    catch (e) { toast.error(getApiError(e, "Gagal membatalkan")); }
  };

  const terbitkanUlang = async (sid, jam, { revive = false } = {}) => {
    const ok = await confirm({
      title: revive ? "Terbitkan ulang link ini?" : "Ganti tautan (terbitkan ulang)?",
      description: revive
        ? "Link baru dibuat & diaktifkan kembali. Kontribusi lama tetap tersimpan."
        : "Tautan LAMA yang sudah tersebar akan langsung mati; tautan baru dibuat. Pakai ini bila link bocor.",
      confirmLabel: "Terbitkan ulang",
    });
    if (!ok) return;
    try {
      const r = await axios.post(`${API}/peta/share/${sid}/terbitkan-ulang`, { durasi_jam: jam });
      toast.success("Link diterbitkan ulang — tautan baru aktif");
      muat();
      if (r.data?.link) salin(r.data.link, sid);
    } catch (e) { toast.error(getApiError(e, "Gagal menerbitkan ulang")); }
  };

  const aktif = shares.filter((s) => s.status !== "batal");
  const dibatalkan = shares.filter((s) => s.status === "batal");

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Share2 className="w-5 h-5 text-blue-600" />Bagikan Peta Kolaboratif</DialogTitle>
          <DialogDescription className="text-xs">
            Bagikan peta kegiatan ini via link. Selama masa tayang, siapa pun berlink dapat melihat titik aset,
            berkomentar, dan menambah titik. Setelah kedaluwarsa hanya operator/admin satker ini yang bisa membuka.
          </DialogDescription>
        </DialogHeader>

        {/* Buat link baru */}
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-3 space-y-2.5">
          <p className="text-xs font-semibold text-blue-700 dark:text-blue-300">Buat link baru</p>
          <Input value={judul} onChange={(e) => setJudul(e.target.value)} maxLength={140}
            placeholder="Judul peta (opsional, mis. Verifikasi Lapangan Blok A)" className="h-9 text-sm" data-testid="bagikan-judul" />
          <div>
            <p className="text-[11px] text-muted-foreground mb-1">Masa tayang</p>
            <div className="flex flex-wrap gap-1.5">
              {PRESET.map((p) => (
                <button key={p.jam} type="button" onClick={() => setDurasiJam(p.jam)}
                  className={`px-2.5 h-8 rounded-full text-[11px] font-semibold border min-w-0 min-h-0 ${durasiJam === p.jam ? "bg-blue-600 border-blue-600 text-white" : "border-border text-muted-foreground hover:bg-muted"}`}
                  data-testid={`bagikan-durasi-${p.jam}`}>{p.label}</button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
              <input type="checkbox" checked={izinTitik} onChange={(e) => setIzinTitik(e.target.checked)} className="w-3.5 h-3.5" />
              <MapPin className="w-3 h-3 text-emerald-600" />Tamu boleh menambah titik
            </label>
            <label className="flex items-center gap-1.5 text-[11px] cursor-pointer">
              <input type="checkbox" checked={izinKomentar} onChange={(e) => setIzinKomentar(e.target.checked)} className="w-3.5 h-3.5" />
              <MessageSquare className="w-3 h-3 text-blue-600" />Tamu boleh berkomentar
            </label>
          </div>
          <Button onClick={buat} disabled={creating} size="sm" className="w-full h-9 gap-1.5 bg-blue-600 hover:bg-blue-700 text-white" data-testid="bagikan-buat">
            {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}Buat & salin link
          </Button>
        </div>

        {/* Daftar link aktif */}
        <div className="space-y-2">
          <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide">Link aktif</p>
          {loading ? (
            <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
          ) : aktif.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada link. Buat di atas.</p>
          ) : aktif.map((s) => (
            <div key={s.id} className="rounded-lg border border-border bg-card p-2.5 space-y-2" data-testid={`bagikan-item-${s.id}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-semibold text-foreground truncate">{s.judul || "Peta Kolaboratif"}</p>
                <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 ${s.kedaluwarsa ? "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-400" : "bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400"}`}>
                  <Clock className="w-2.5 h-2.5 inline mr-0.5" />{s.kedaluwarsa ? "Kedaluwarsa" : sisa(s.berlaku_sampai)}
                </span>
              </div>
              {s.link && (
                <div className="flex items-center gap-1.5">
                  <div className="flex-1 min-w-0 bg-muted rounded-md px-2 py-1.5 text-[10px] font-mono text-muted-foreground truncate flex items-center gap-1">
                    <Link2 className="w-3 h-3 flex-shrink-0" /><span className="truncate">{s.link}</span>
                  </div>
                  <button onClick={() => salin(s.link, s.id)} title="Salin" className="h-8 w-8 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:bg-muted min-w-0 min-h-0" data-testid={`bagikan-salin-${s.id}`}>
                    {tersalin === s.id ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-1.5">
                {s.link && <button onClick={() => bagikanWA(s.link, s.judul)} className="h-7 px-2 rounded-md bg-green-600 text-white text-[11px] font-semibold min-w-0 min-h-0">WhatsApp</button>}
                {s.link && <button onClick={() => bagikanNatif(s.link, s.judul)} className="h-7 px-2 rounded-md border border-border text-[11px] text-muted-foreground min-w-0 min-h-0">Bagikan…</button>}
                <span className="text-[10px] text-muted-foreground flex-1 text-right">{s.jumlah_kontribusi || 0} kontribusi</span>
                <button onClick={() => perpanjang(s.id, 168)} title="Perpanjang 7 hari" className="h-7 px-2 rounded-md border border-blue-300 dark:border-blue-800 text-blue-600 dark:text-blue-400 text-[11px] font-semibold flex items-center gap-1 min-w-0 min-h-0" data-testid={`bagikan-perpanjang-${s.id}`}>
                  <RefreshCcw className="w-3 h-3" />Perpanjang
                </button>
                <button onClick={() => terbitkanUlang(s.id, 168)} title="Ganti tautan — matikan link lama yang bocor, buat link baru" className="h-7 w-7 rounded-md border border-amber-300 dark:border-amber-800 text-amber-600 dark:text-amber-400 flex items-center justify-center min-w-0 min-h-0" data-testid={`bagikan-ganti-${s.id}`}>
                  <RotateCw className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => batal(s.id)} title="Batalkan" className="h-7 w-7 rounded-md border border-red-200 dark:border-red-800 text-red-500 flex items-center justify-center min-w-0 min-h-0" data-testid={`bagikan-batal-${s.id}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Link dibatalkan — bisa diterbitkan ulang (tautan baru, yang lama tetap mati) */}
        {dibatalkan.length > 0 && (
          <div className="space-y-2">
            <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide">Dibatalkan</p>
            {dibatalkan.map((s) => (
              <div key={s.id} className="rounded-lg border border-dashed border-border bg-muted/40 p-2.5 flex items-center justify-between gap-2" data-testid={`bagikan-batal-item-${s.id}`}>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-muted-foreground truncate line-through">{s.judul || "Peta Kolaboratif"}</p>
                  <p className="text-[10px] text-muted-foreground">{s.jumlah_kontribusi || 0} kontribusi tersimpan</p>
                </div>
                <button onClick={() => terbitkanUlang(s.id, 168, { revive: true })} className="h-7 px-2 rounded-md border border-emerald-300 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 text-[11px] font-semibold flex items-center gap-1 flex-shrink-0 min-w-0 min-h-0" data-testid={`bagikan-terbitkan-ulang-${s.id}`}>
                  <RotateCw className="w-3 h-3" />Terbitkan ulang
                </button>
              </div>
            ))}
          </div>
        )}
        {confirmDialog}
      </DialogContent>
    </Dialog>
  );
}
