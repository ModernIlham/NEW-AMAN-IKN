import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Flame, Plus, Search, Trash2, X, Coins, FileText,
  Paperclip, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FORM_KOSONG = {
  nomor_ba: "", tanggal_ba: new Date().toISOString().slice(0, 10),
  cara: "dihancurkan", nomor_persetujuan: "", keterangan: "",
};

/**
 * Pemusnahan — Fase 6 tahap awal: register Berita Acara Pemusnahan
 * (PMK 83/2016). BA dicatat setelah persetujuan + pelaksanaan; objek
 * dibatasi aset Rusak Berat (divalidasi backend). Tindak lanjut usulan
 * penghapusan lewat modul Penghapusan.
 */
export default function PemusnahanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog: {data, aset: [], saving}
  const [form, setForm] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  // Dialog lampiran bukti: {ba, uploading}
  const [lamp, setLamp] = useState(null);
  const lampInputRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    axios.get(`${API}/pemusnahan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register pemusnahan"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  // Cari aset Rusak Berat untuk daftar BA
  useEffect(() => {
    if (!form || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, {
          params: { search: cari.trim(), condition: "Rusak Berat", page_size: 8 },
        });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, form]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;
  const setField = (k, v) => setForm((f) => ({ ...f, data: { ...f.data, [k]: v } }));
  const tambahAset = (a) => setForm((f) => (
    f.aset.some((x) => x.id === a.id) ? { ...f } : { ...f, aset: [...f.aset, a] }
  ));

  const simpan = async () => {
    if (!form) return;
    if (form.aset.length === 0) { toast.error("Tambahkan minimal satu aset"); return; }
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pemusnahan`, {
        ...form.data, asset_ids: form.aset.map((a) => a.id),
      });
      toast.success("BA Pemusnahan tercatat");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat BA");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapus = async (r) => {
    const ok = await confirm({
      title: `Hapus BA ${r.nomor_ba}?`,
      description: "Hanya untuk salah input — jejak pemusnahan resmi ada di arsip dokumen.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pemusnahan/${r.id}`);
      toast.success("BA dihapus");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus BA");
    }
  };

  const unggahLampiran = async (fileObj) => {
    if (!lamp || !fileObj) return;
    setLamp((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const res = await axios.post(`${API}/pemusnahan/${lamp.ba.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLamp((l) => (l ? { ...l, uploading: false,
        ba: { ...l.ba, lampiran: res.data?.lampiran || [] } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLamp((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiran = async (fileId) => {
    if (!lamp) return;
    try {
      await axios.delete(`${API}/pemusnahan/${lamp.ba.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLamp((l) => (l ? { ...l,
        ba: { ...l.ba, lampiran: (l.ba.lampiran || []).filter((x) => x.file_id !== fileId) } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  const usulkanHapus = async (r) => {
    const ok = await confirm({
      title: `Usulkan penghapusan aset BA ${r.nomor_ba}?`,
      description: "Tindak lanjut PMK 83/2016 — usulan dibuat di register Penghapusan untuk tiap aset yang belum diusulkan.",
      confirmLabel: "Usulkan",
    });
    if (!ok) return;
    try {
      const res = await axios.post(`${API}/pemusnahan/${r.id}/usulkan-penghapusan`);
      const { dibuat, terlewati } = res.data || {};
      toast.success(`${dibuat} usulan dibuat${terlewati ? `, ${terlewati} dilewati (sudah ada usulan aktif)` : ""}`);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat usulan penghapusan");
    }
  };

  const labelCara = data?.label_cara || {};

  return (
    <div className="min-h-screen bg-background" data-testid="pemusnahan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pemusnahan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-orange-700 flex items-center justify-center flex-shrink-0">
            <Flame className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pemusnahan — Register BA</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Setelah persetujuan + pelaksanaan · PMK 83/PMK.06/2016
            </p>
          </div>
          <Button size="sm" onClick={() => { setCari(""); setHasilCari([]); setForm({ data: { ...FORM_KOSONG }, aset: [], saving: false }); }}
            className="bg-orange-700 hover:bg-orange-800 text-white flex-shrink-0" data-testid="pemusnahan-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Catat BA</span>
          </Button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-orange-700" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemusnahan-stat-ba">
                <FileText className="w-5 h-5 text-orange-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.jumlah_ba}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Berita Acara</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemusnahan-stat-aset">
                <Flame className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.jumlah_aset}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Aset dimusnahkan</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemusnahan-stat-nilai">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(data.ringkasan.nilai)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan</p>
              </div>
            </div>

            {/* ── Daftar BA ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <Flame className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Belum ada BA pemusnahan tercatat.</p>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((r) => (
                    <li key={r.id} className="p-3" data-testid={`pemusnahan-row-${r.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-foreground">{r.nomor_ba}</p>
                        <span className="px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-600 dark:text-orange-400 text-[10px] font-semibold">
                          {labelCara[r.cara] || r.cara}
                        </span>
                        <span className="text-[11px] text-muted-foreground">{r.tanggal_ba}</span>
                        <span className="text-[11px] text-muted-foreground ml-auto">{(r.aset || []).length} aset</span>
                        {(r.aset_diusulkan || 0) >= (r.aset || []).length ? (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
                            ✓ Diusulkan hapus
                          </span>
                        ) : (
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => usulkanHapus(r)}
                            data-testid={`pemusnahan-usulkan-${r.id}`}>
                            Usulkan Hapus{(r.aset_diusulkan || 0) > 0 && ` (${r.aset_diusulkan}/${(r.aset || []).length})`}
                          </Button>
                        )}
                        <button type="button" aria-label="Lampiran bukti"
                          onClick={() => setLamp({ ba: r, uploading: false })}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                          data-testid={`pemusnahan-lampiran-${r.id}`}>
                          <Paperclip className="w-3 h-3" />
                        </button>
                        <button type="button" aria-label="Unduh BA (PDF)"
                          onClick={() => downloadFileWithProgress(
                            `${API}/pemusnahan/${r.id}/ba-pdf`,
                            `BA_Pemusnahan_${(r.nomor_ba || "BA").replace(/[/\s]/g, "-")}.pdf`,
                            { label: `BA Pemusnahan ${r.nomor_ba}` },
                          ).catch(() => {})}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                          data-testid={`pemusnahan-unduh-${r.id}`}>
                          <FileText className="w-3 h-3" />
                        </button>
                        {isAdmin && (
                          <button type="button" onClick={() => hapus(r)} aria-label="Hapus BA"
                            className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Persetujuan: {r.nomor_persetujuan}{r.keterangan && ` · ${r.keterangan}`} · oleh {r.created_by}
                      </p>
                      <ul className="mt-1 space-y-0.5">
                        {(r.aset || []).map((a) => (
                          <li key={a.asset_id} className="text-[11px] text-foreground/80 flex justify-between gap-2">
                            <span className="truncate">{a.asset_name} <span className="font-mono text-muted-foreground">({a.asset_code} · {a.NUP})</span></span>
                            <span className="flex-shrink-0">{fmtRp(a.harga)}</span>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog catat BA ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat BA Pemusnahan</DialogTitle>
            <DialogDescription className="text-xs">
              Hanya aset Rusak Berat; nomor persetujuan wajib (pemusnahan
              tanpa persetujuan = temuan).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-ba">Nomor BA</label>
                <Input id="pms-ba" placeholder="BA-01/VII/2026" value={form.data.nomor_ba}
                  onChange={(e) => setField("nomor_ba", e.target.value)} data-testid="pemusnahan-nomor" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-tgl">Tanggal BA</label>
                <Input id="pms-tgl" type="date" max={new Date().toISOString().slice(0, 10)}
                  value={form.data.tanggal_ba} onChange={(e) => setField("tanggal_ba", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-cara">Cara</label>
                <select id="pms-cara" value={form.data.cara} onChange={(e) => setField("cara", e.target.value)}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pemusnahan-cara">
                  {Object.entries(labelCara).length
                    ? Object.entries(labelCara).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                    : <option value="dihancurkan">Dihancurkan</option>}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-setuju">No. Persetujuan</label>
                <Input id="pms-setuju" placeholder="S-9/KNL.05/2026" value={form.data.nomor_persetujuan}
                  onChange={(e) => setField("nomor_persetujuan", e.target.value)} data-testid="pemusnahan-persetujuan" />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-ket">Keterangan</label>
                <Input id="pms-ket" value={form.data.keterangan}
                  onChange={(e) => setField("keterangan", e.target.value)} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pms-cari">Tambah aset (Rusak Berat)</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="pms-cari" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                    value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pemusnahan-cari" />
                  {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {mencari ? (
                        <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-orange-700" /></div>
                      ) : hasilCari.map((a) => (
                        <button key={a.id} type="button"
                          onClick={() => { tambahAset(a); setCari(""); setHasilCari([]); }}
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
            <Button onClick={simpan} disabled={form?.saving || (form?.aset?.length || 0) === 0}
              className="bg-orange-700 hover:bg-orange-800 text-white" data-testid="pemusnahan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Flame className="w-4 h-4 mr-1.5" />}Catat BA
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran bukti pelaksanaan ── */}
      <Dialog open={!!lamp} onOpenChange={(o) => { if (!o) setLamp(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Lampiran Bukti Pemusnahan</DialogTitle>
            <DialogDescription className="text-xs">
              {lamp && `BA ${lamp.ba.nomor_ba}. Foto pelaksanaan / scan BA bertanda tangan (PDF/JPG/PNG, maks 10MB, 10 berkas).`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiran(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lamp?.uploading || (lamp?.ba?.lampiran || []).length >= 10}
            onClick={() => lampInputRef.current?.click()} data-testid="pemusnahan-lampiran-unggah">
            {lamp?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lamp?.ba?.lampiran || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran bukti.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lamp?.ba?.lampiran || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/pemusnahan/${lamp.ba.id}/lampiran/${f.file_id}`), "_blank", "noopener")}
                    className="min-w-0 flex-1 text-left hover:underline">
                    <span className="block text-xs font-semibold text-foreground truncate">{f.filename}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {String(f.tanggal || "").slice(0, 10)} · oleh {f.oleh}
                    </span>
                  </button>
                  {isAdmin && (
                    <button type="button" aria-label="Hapus lampiran" onClick={() => hapusLampiran(f.file_id)}
                      className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
