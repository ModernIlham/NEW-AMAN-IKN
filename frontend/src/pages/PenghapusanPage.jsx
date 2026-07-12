import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, FileX, SearchX, Flame, Coins, TicketCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_JALUR = { tidak_ditemukan: SearchX, rusak_berat: Flame };
const WARNA_JALUR = {
  tidak_ditemukan: "text-amber-500 border-amber-500/40",
  rusak_berat: "text-red-500 border-red-500/40",
};
const WARNA_STATUS = {
  diusulkan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  diproses: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  sk_terbit: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak: "bg-muted text-muted-foreground",
};

/**
 * Penghapusan — Fase 6: kandidat usul hapus dari inventarisasi + tiket
 * usulan berstatus (PMK 83/2016): diusulkan → diproses → SK terbit/tolak.
 * Transisi status = gerbang persetujuan (admin); riwayat tercatat.
 */
export default function PenghapusanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [usulan, setUsulan] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog buat usulan: {aset, keterangan, saving}
  const [formUsul, setFormUsul] = useState(null);
  // Dialog SK terbit: {usulan, nomor_sk, tanggal_sk, catatan, saving}
  const [formSk, setFormSk] = useState(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    Promise.all([
      axios.get(`${API}/penghapusan/kandidat`),
      axios.get(`${API}/penghapusan/usulan`),
    ])
      .then(([k, u]) => { setData(k.data); setUsulan(u.data); })
      .catch(() => toast.error("Gagal memuat data penghapusan"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;

  const simpanUsulan = async () => {
    if (!formUsul) return;
    setFormUsul((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penghapusan/usulan`, {
        asset_id: formUsul.aset.id, keterangan: formUsul.keterangan,
      });
      toast.success("Usulan penghapusan dibuat");
      setFormUsul(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat usulan");
      setFormUsul((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const transisi = async (u, status, ekstra = {}) => {
    try {
      await axios.post(`${API}/penghapusan/usulan/${u.id}/status`, { status, ...ekstra });
      toast.success(`Status usulan: ${usulan?.label_status?.[status] || status}`);
      muat();
      return true;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
      return false;
    }
  };

  const tolak = async (u) => {
    const ok = await confirm({
      title: "Tolak/batalkan usulan?",
      description: `${u.asset_name || "-"} (${u.asset_code} · ${u.NUP}). Usulan berhenti di sini; aset bisa diusulkan ulang nanti.`,
      confirmLabel: "Tolak",
      variant: "danger",
    });
    if (ok) transisi(u, "ditolak");
  };

  const simpanSk = async () => {
    if (!formSk) return;
    if (!formSk.nomor_sk.trim()) { toast.error("Nomor SK wajib diisi"); return; }
    setFormSk((f) => ({ ...f, saving: true }));
    const ok = await transisi(formSk.usulan, "sk_terbit", {
      nomor_sk: formSk.nomor_sk, tanggal_sk: formSk.tanggal_sk, catatan: formSk.catatan,
    });
    if (ok) setFormSk(null);
    else setFormSk((f) => (f ? { ...f, saving: false } : f));
  };

  const labelStatus = usulan?.label_status || {};
  const labelJalur = usulan?.label_jalur || {};

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
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Penghapusan — Kandidat & Usulan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Usul → proses → SK terbit · PMK 83/PMK.06/2016
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
            <div className="grid grid-cols-3 gap-2">
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
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penghapusan-stat-usulan">
                <TicketCheck className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{usulan?.jumlah ?? 0}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Tiket usulan</p>
              </div>
            </div>

            {/* ── Usulan berjalan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <TicketCheck className="w-4 h-4 text-emerald-500" />
                <p className="text-xs font-bold text-foreground">Usulan Penghapusan</p>
              </div>
              {(usulan?.items || []).length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4 px-3">
                  Belum ada usulan — gunakan tombol Usulkan pada kandidat di bawah.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {usulan.items.map((u) => (
                    <li key={u.id} className="px-3 py-2" data-testid={`penghapusan-usulan-${u.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS[u.status] || "bg-muted"}`}>
                          {labelStatus[u.status] || u.status}
                        </span>
                        <p className="text-xs font-semibold text-foreground truncate flex-1 min-w-[120px]">{u.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground">{u.asset_code} · {u.NUP}</span>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        {labelJalur[u.jalur] || u.jalur}
                        {u.nomor_sk && ` · SK: ${u.nomor_sk}${u.tanggal_sk ? ` (${u.tanggal_sk})` : ""}`}
                        {u.keterangan && ` · ${u.keterangan}`}
                        {` · oleh ${u.created_by}`}
                      </p>
                      {isAdmin && (u.status === "diusulkan" || u.status === "diproses") && (
                        <div className="flex gap-1.5 mt-1.5">
                          {u.status === "diusulkan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => transisi(u, "diproses")}
                              data-testid={`penghapusan-proses-${u.id}`}>
                              Proses
                            </Button>
                          )}
                          {u.status === "diproses" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setFormSk({ usulan: u, nomor_sk: "", tanggal_sk: new Date().toISOString().slice(0, 10), catatan: "", saving: false })}
                              data-testid={`penghapusan-sk-${u.id}`}>
                              SK Terbit
                            </Button>
                          )}
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 text-red-500 hover:text-red-600"
                            onClick={() => tolak(u)}>
                            Tolak
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── Kandidat per jalur ── */}
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
                        <li key={a.id} className="px-3 py-2 flex items-center gap-2" data-testid={`penghapusan-row-${a.id}`}>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                            <p className="text-[10px] text-muted-foreground font-mono truncate">
                              {a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}
                              {a.keterangan ? ` · ${a.keterangan}` : ""}
                            </p>
                          </div>
                          <span className="text-xs font-bold text-foreground flex-shrink-0">{fmtRp(a.harga)}</span>
                          {a.usulan ? (
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${WARNA_STATUS[a.usulan.status] || "bg-muted"}`}>
                              {labelStatus[a.usulan.status] || a.usulan.status}
                            </span>
                          ) : (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                              onClick={() => setFormUsul({ aset: a, keterangan: "", saving: false })}
                              data-testid={`penghapusan-usulkan-${a.id}`}>
                              Usulkan
                            </Button>
                          )}
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

      {/* ── Dialog buat usulan ── */}
      <Dialog open={!!formUsul} onOpenChange={(o) => { if (!o) setFormUsul(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Usulkan Penghapusan</DialogTitle>
            <DialogDescription className="text-xs">
              {formUsul?.aset?.asset_name} ({formUsul?.aset?.asset_code} · {formUsul?.aset?.NUP}).
              Tiket berjalan: diusulkan → diproses → SK terbit.
            </DialogDescription>
          </DialogHeader>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="phx-ket">Keterangan</label>
            <Input id="phx-ket" placeholder="cth. hasil inventarisasi 2026, kronologis terlampir"
              value={formUsul?.keterangan || ""}
              onChange={(e) => setFormUsul((f) => ({ ...f, keterangan: e.target.value }))}
              data-testid="penghapusan-usul-keterangan" />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormUsul(null)}>Batal</Button>
            <Button onClick={simpanUsulan} disabled={formUsul?.saving}
              className="bg-red-700 hover:bg-red-800 text-white" data-testid="penghapusan-usul-simpan">
              {formUsul?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <FileX className="w-4 h-4 mr-1.5" />}Buat Usulan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog SK terbit ── */}
      <Dialog open={!!formSk} onOpenChange={(o) => { if (!o) setFormSk(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>SK Penghapusan Terbit</DialogTitle>
            <DialogDescription className="text-xs">
              {formSk?.usulan?.asset_name} ({formSk?.usulan?.asset_code} · {formSk?.usulan?.NUP}) — status menjadi final.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="phx-sk">Nomor SK</label>
              <Input id="phx-sk" placeholder="cth. KEP-12/MK.6/2026"
                value={formSk?.nomor_sk || ""}
                onChange={(e) => setFormSk((f) => ({ ...f, nomor_sk: e.target.value }))}
                data-testid="penghapusan-sk-nomor" />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="phx-tgl">Tanggal SK</label>
              <Input id="phx-tgl" type="date" value={formSk?.tanggal_sk || ""}
                onChange={(e) => setFormSk((f) => ({ ...f, tanggal_sk: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="phx-cat">Catatan</label>
              <Input id="phx-cat" value={formSk?.catatan || ""}
                onChange={(e) => setFormSk((f) => ({ ...f, catatan: e.target.value }))} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormSk(null)}>Batal</Button>
            <Button onClick={simpanSk} disabled={formSk?.saving}
              className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="penghapusan-sk-simpan">
              {formSk?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <TicketCheck className="w-4 h-4 mr-1.5" />}Terbitkan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
