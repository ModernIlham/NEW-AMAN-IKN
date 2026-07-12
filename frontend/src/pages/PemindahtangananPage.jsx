import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ArrowLeftRight, Plus, Search, Trash2, X, Coins,
  TicketCheck, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_STATUS = {
  diusulkan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  disetujui: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  dilaksanakan: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak: "bg-muted text-muted-foreground",
};

/**
 * Pemindahtanganan — Fase 6 tahap awal: register usulan berstatus
 * (PMK 111/2016 jo. 165/2021): diusulkan → disetujui → dilaksanakan →
 * selesai (SK Penghapusan). Dokumen wajib per tahap mengunci transisi;
 * peringatan tenggat lelang 6 bulan.
 */
export default function PemindahtangananPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog usulan baru: {data, aset: [], saving}
  const [form, setForm] = useState(null);
  // Dialog transisi: {usulan, ke, fields{}, saving}
  const [trx, setTrx] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    axios.get(`${API}/pemindahtanganan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register pemindahtanganan"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  useEffect(() => {
    if (!form || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, form]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;
  const labelStatus = data?.label_status || {};
  const labelBentuk = data?.label_bentuk || {};
  const labelDokumen = data?.label_dokumen || {};

  const simpanUsulan = async () => {
    if (!form) return;
    if (form.aset.length === 0) { toast.error("Tambahkan minimal satu aset"); return; }
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pemindahtanganan`, {
        ...form.data, asset_ids: form.aset.map((a) => a.id),
      });
      toast.success("Usulan pemindahtanganan dibuat");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat usulan");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const kirimTransisi = async () => {
    if (!trx) return;
    setTrx((t) => ({ ...t, saving: true }));
    try {
      await axios.post(`${API}/pemindahtanganan/${trx.usulan.id}/status`, {
        status: trx.ke, ...trx.fields,
      });
      toast.success(`Status: ${labelStatus[trx.ke] || trx.ke}`);
      setTrx(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
      setTrx((t) => (t ? { ...t, saving: false } : t));
    }
  };

  const tolak = async (u) => {
    const ok = await confirm({
      title: "Tolak/batalkan usulan?",
      description: `${labelBentuk[u.bentuk] || u.bentuk} — ${u.pihak}.`,
      confirmLabel: "Tolak", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.post(`${API}/pemindahtanganan/${u.id}/status`, { status: "ditolak" });
      toast.success("Usulan ditolak/dibatalkan");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
    }
  };

  const setTrxField = (k, v) => setTrx((t) => ({ ...t, fields: { ...t.fields, [k]: v } }));
  const r = data?.ringkasan;

  return (
    <div className="min-h-screen bg-background" data-testid="pemindahtanganan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pemindahtanganan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <ArrowLeftRight className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pemindahtanganan — Register Usulan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Penjualan · Tukar Menukar · Hibah · PMPP (PMK 111/2016 jo. 165/2021)
            </p>
          </div>
          <Button size="sm" onClick={() => { setCari(""); setHasilCari([]); setForm({ data: { bentuk: "hibah", pihak: "", keterangan: "" }, aset: [], saving: false }); }}
            className="bg-indigo-600 hover:bg-indigo-700 text-white flex-shrink-0" data-testid="pemindahtanganan-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Usulkan</span>
          </Button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-indigo-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemindahtanganan-stat-proses">
                <TicketCheck className="w-5 h-5 text-sky-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">
                  {r.per_status.diusulkan + r.per_status.disetujui + r.per_status.dilaksanakan}
                </p>
                <p className="text-[10px] text-muted-foreground mt-1">Usulan berjalan</p>
              </div>
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="pemindahtanganan-stat-selesai">
                <ArrowLeftRight className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.per_status.selesai}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Selesai (SK terbit)</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemindahtanganan-stat-nilai">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(r.nilai)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan ({r.jumlah_aset} aset)</p>
              </div>
            </div>

            {/* ── Daftar usulan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <ArrowLeftRight className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Belum ada usulan pemindahtanganan.</p>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((u) => (
                    <li key={u.id} className="p-3" data-testid={`pemindahtanganan-row-${u.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS[u.status] || "bg-muted"}`}>
                          {labelStatus[u.status] || u.status}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 text-[10px] font-semibold">
                          {labelBentuk[u.bentuk] || u.bentuk}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{u.pihak}</p>
                        <span className="text-[11px] text-muted-foreground">{(u.aset || []).length} aset</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {u.nomor_persetujuan && `Persetujuan ${u.nomor_persetujuan}`}
                        {u.nomor_dokumen && ` · ${labelDokumen[u.bentuk] || "Dokumen"} ${u.nomor_dokumen}`}
                        {u.ntpn && ` · NTPN ${u.ntpn}`}
                        {u.nomor_sk_penghapusan && ` · SK Hapus ${u.nomor_sk_penghapusan}`}
                        {u.keterangan && ` · ${u.keterangan}`}
                        {` · oleh ${u.created_by}`}
                      </p>
                      {(u.peringatan || []).map((w) => (
                        <p key={w} className="text-[11px] text-red-500/90 mt-0.5 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 flex-shrink-0" />{w}
                        </p>
                      ))}
                      <ul className="mt-1 space-y-0.5">
                        {(u.aset || []).slice(0, 5).map((a) => (
                          <li key={a.asset_id} className="text-[11px] text-foreground/80 truncate">
                            {a.asset_name} <span className="font-mono text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                          </li>
                        ))}
                        {(u.aset || []).length > 5 && (
                          <li className="text-[11px] text-muted-foreground">+{u.aset.length - 5} aset lainnya</li>
                        )}
                      </ul>
                      {isAdmin && ["diusulkan", "disetujui", "dilaksanakan"].includes(u.status) && (
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          {u.status === "diusulkan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => setTrx({ usulan: u, ke: "disetujui", saving: false, fields: { nomor_persetujuan: "", tanggal_persetujuan: new Date().toISOString().slice(0, 10) } })}
                              data-testid={`pemindahtanganan-setujui-${u.id}`}>
                              Setujui
                            </Button>
                          )}
                          {u.status === "disetujui" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => setTrx({ usulan: u, ke: "dilaksanakan", saving: false, fields: { nomor_dokumen: "", ntpn: "" } })}
                              data-testid={`pemindahtanganan-laksanakan-${u.id}`}>
                              Laksanakan
                            </Button>
                          )}
                          {u.status === "dilaksanakan" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setTrx({ usulan: u, ke: "selesai", saving: false, fields: { nomor_sk_penghapusan: "" } })}
                              data-testid={`pemindahtanganan-selesai-${u.id}`}>
                              Selesai (SK)
                            </Button>
                          )}
                          {u.status !== "dilaksanakan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 text-red-500 hover:text-red-600"
                              onClick={() => tolak(u)}>
                              Tolak
                            </Button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog usulan baru ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Usulan Pemindahtanganan</DialogTitle>
            <DialogDescription className="text-xs">
              Alur: diusulkan → disetujui → dilaksanakan → selesai (SK Penghapusan).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-bentuk">Bentuk</label>
                <select id="ptg-bentuk" value={form.data.bentuk}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, bentuk: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pemindahtanganan-bentuk">
                  {Object.entries(labelBentuk).length
                    ? Object.entries(labelBentuk).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                    : <option value="hibah">Hibah</option>}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-pihak">Pihak (penerima/pembeli/mitra)</label>
                <Input id="ptg-pihak" placeholder="cth. Pemerintah Desa Sukamaju"
                  value={form.data.pihak}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, pihak: e.target.value } }))}
                  data-testid="pemindahtanganan-pihak" />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-ket">Keterangan</label>
                <Input id="ptg-ket" value={form.data.keterangan}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-cari">Tambah aset</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="ptg-cari" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                    value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pemindahtanganan-cari" />
                  {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {mencari ? (
                        <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-indigo-600" /></div>
                      ) : hasilCari.map((a) => (
                        <button key={a.id} type="button"
                          onClick={() => { setForm((f) => (f.aset.some((x) => x.id === a.id) ? f : { ...f, aset: [...f.aset, a] })); setCari(""); setHasilCari([]); }}
                          className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                          <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                          <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP} · {a.condition}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {form.aset.length > 0 && (
                <ul className="col-span-2 space-y-1">
                  {form.aset.map((a) => (
                    <li key={a.id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                        <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                      </span>
                      <button type="button" aria-label="Keluarkan aset"
                        onClick={() => setForm((f) => ({ ...f, aset: f.aset.filter((x) => x.id !== a.id) }))}
                        className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpanUsulan} disabled={form?.saving || (form?.aset?.length || 0) === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="pemindahtanganan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ArrowLeftRight className="w-4 h-4 mr-1.5" />}Buat Usulan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog transisi status ── */}
      <Dialog open={!!trx} onOpenChange={(o) => { if (!o) setTrx(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{labelStatus[trx?.ke] || trx?.ke}</DialogTitle>
            <DialogDescription className="text-xs">
              {trx?.usulan && `${labelBentuk[trx.usulan.bentuk] || trx.usulan.bentuk} — ${trx.usulan.pihak}`}
            </DialogDescription>
          </DialogHeader>
          {trx?.ke === "disetujui" && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-setuju">No. Surat Persetujuan</label>
                <Input id="ptg-setuju" placeholder="S-12/KNL.05/2026" value={trx.fields.nomor_persetujuan}
                  onChange={(e) => setTrxField("nomor_persetujuan", e.target.value)} data-testid="pemindahtanganan-nomor-setuju" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-tgl-setuju">Tanggal</label>
                <Input id="ptg-tgl-setuju" type="date" value={trx.fields.tanggal_persetujuan}
                  onChange={(e) => setTrxField("tanggal_persetujuan", e.target.value)} />
              </div>
            </div>
          )}
          {trx?.ke === "dilaksanakan" && (
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-dok">
                  No. {labelDokumen[trx.usulan.bentuk] || "Dokumen Pelaksanaan"}
                </label>
                <Input id="ptg-dok" value={trx.fields.nomor_dokumen}
                  onChange={(e) => setTrxField("nomor_dokumen", e.target.value)} data-testid="pemindahtanganan-nomor-dokumen" />
              </div>
              {String(trx.usulan.bentuk).startsWith("penjualan") && (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-ntpn">NTPN Setor Hasil Penjualan</label>
                  <Input id="ptg-ntpn" className="font-mono" value={trx.fields.ntpn}
                    onChange={(e) => setTrxField("ntpn", e.target.value)} data-testid="pemindahtanganan-ntpn" />
                </div>
              )}
            </div>
          )}
          {trx?.ke === "selesai" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="ptg-sk">No. SK Penghapusan</label>
              <Input id="ptg-sk" placeholder="KEP-12/MK.6/2026" value={trx.fields.nomor_sk_penghapusan}
                onChange={(e) => setTrxField("nomor_sk_penghapusan", e.target.value)} data-testid="pemindahtanganan-nomor-sk" />
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setTrx(null)}>Batal</Button>
            <Button onClick={kirimTransisi} disabled={trx?.saving}
              className="bg-indigo-600 hover:bg-indigo-700 text-white" data-testid="pemindahtanganan-trx-simpan">
              {trx?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <TicketCheck className="w-4 h-4 mr-1.5" />}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
