import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Plus, Pencil, Trash2, Loader2, Boxes, Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

/**
 * Referensi Akun Persediaan (sub-kelompok → akun neraca 1171xx) — evaluasi #3.
 *
 * Semua user login melihat katalog akun 1171xx + pemetaan override satker;
 * admin menambah/mengubah/menghapus override per sub-kelompok (5 digit).
 * Default (tanpa override) = 117111 (Barang Konsumsi). Dipakai laporan Posisi
 * Persediaan per akun.
 */
export default function PersediaanAkunPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [overrides, setOverrides] = useState([]);
  const [katalog, setKatalog] = useState([]);
  const [defaultAkun, setDefaultAkun] = useState("117111");
  const [defaultUraian, setDefaultUraian] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/persediaan-akun`);
      setOverrides(r.data?.overrides || []);
      setKatalog(r.data?.katalog || []);
      setDefaultAkun(r.data?.default_akun || "117111");
      setDefaultUraian(r.data?.default_uraian || "");
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat referensi akun persediaan"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const uraianAkun = (akun) => katalog.find((k) => k.akun === akun)?.uraian || "";

  const submitForm = async () => {
    if (!form) return;
    if (!/^1\d{4}$/.test((form.sub_kelompok || "").trim())) {
      toast.error("Sub-kelompok harus 5 digit angka diawali '1' (mis. 10101)");
      return;
    }
    if (!/^1171\d{2}$/.test((form.akun || "").trim())) {
      toast.error("Pilih akun neraca 1171xx");
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/persediaan-akun`, {
        sub_kelompok: form.sub_kelompok.trim(), akun: form.akun.trim(),
        uraian: form.uraian || uraianAkun(form.akun.trim()),
      });
      toast.success(`Pemetaan ${form.sub_kelompok} → ${form.akun} disimpan`);
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan pemetaan"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it) => {
    const ok = await confirm({
      title: `Hapus pemetaan ${it.sub_kelompok}?`,
      description: `Sub-kelompok ${it.sub_kelompok} akan kembali ke akun default (${defaultAkun}).`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/persediaan-akun/${it.sub_kelompok}`);
      toast.success(`Pemetaan ${it.sub_kelompok} dihapus`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus pemetaan"));
    }
  };

  return (
    <div className="min-h-screen bg-background" data-testid="persediaan-akun-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="persediaan-akun-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center flex-shrink-0">
            <Boxes className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Akun Persediaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Sub-kelompok → akun neraca 1171xx · default {defaultAkun} · dasar Laporan Posisi per akun
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2.5 flex gap-2.5">
          <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-[11px] sm:text-xs text-foreground/90 leading-relaxed">
            Default semua persediaan = <strong>{defaultAkun}{defaultUraian ? ` (${defaultUraian})` : ""}</strong>.
            Sub-akun 1171xx lain <strong>perlu verifikasi Lampiran Bagan Akun Standar</strong> (KEP-211/PB/2018).
            {isAdmin ? " Tambah pemetaan per sub-kelompok agar akun sesuai jenis persediaan." : " Hubungi admin untuk menyesuaikan."}
          </p>
        </div>

        {/* Katalog akun 1171xx (referensi) */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground mb-2">Katalog Akun 1171xx (referensi)</p>
          <div className="flex flex-wrap gap-1.5">
            {katalog.map((k) => (
              <span key={k.akun} className="px-2 py-1 rounded-md bg-muted text-[11px]" title={k.uraian}>
                <span className="font-mono font-semibold">{k.akun}</span> <span className="text-muted-foreground">{k.uraian}</span>
              </span>
            ))}
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">{overrides.length} pemetaan sub-kelompok (selain default {defaultAkun})</p>
          {isAdmin && (
            <Button variant="outline" className="h-9 gap-1.5"
              onClick={() => setForm({ mode: "tambah", sub_kelompok: "", akun: defaultAkun, uraian: "" })}
              data-testid="persediaan-akun-add">
              <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah Pemetaan</span>
            </Button>
          )}
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-orange-600" />
            </div>
          ) : overrides.length === 0 ? (
            <div className="text-center py-14 px-4">
              <Boxes className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada pemetaan khusus</p>
              <p className="text-xs text-muted-foreground mt-1">Seluruh persediaan memakai akun default {defaultAkun}. {isAdmin ? "Tambah pemetaan bila ada sub-kelompok dengan akun berbeda." : ""}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Sub-Kelompok</th>
                    <th className="px-3 py-2.5 font-semibold">Akun Neraca</th>
                    <th className="px-3 py-2.5 font-semibold">Uraian</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {overrides.map((it) => (
                    <tr key={it.sub_kelompok} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`persediaan-akun-row-${it.sub_kelompok}`}>
                      <td className="px-3 py-2.5 font-mono font-semibold text-foreground">{it.sub_kelompok}</td>
                      <td className="px-3 py-2.5 font-mono font-semibold text-foreground">{it.akun}</td>
                      <td className="px-3 py-2.5 text-[12px] text-foreground/90">{it.uraian || "—"}</td>
                      {isAdmin && (
                        <td className="px-3 py-2.5 text-right whitespace-nowrap">
                          <button type="button" onClick={() => setForm({ mode: "edit", sub_kelompok: it.sub_kelompok, akun: it.akun, uraian: it.uraian })}
                            aria-label={`Ubah ${it.sub_kelompok}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`persediaan-akun-edit-${it.sub_kelompok}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            aria-label={`Hapus ${it.sub_kelompok}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`persediaan-akun-delete-${it.sub_kelompok}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Pemetaan Akun" : `Ubah Pemetaan — ${form?.sub_kelompok}`}</DialogTitle>
            <DialogDescription className="text-xs">
              Petakan sub-kelompok persediaan (5 digit) ke akun neraca 1171xx yang sesuai Lampiran BAS satker.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pa-sub">Sub-Kelompok (5 digit)</label>
                <Input id="pa-sub" value={form.sub_kelompok}
                  onChange={(e) => setForm((f) => ({ ...f, sub_kelompok: e.target.value.replace(/[^\d]/g, "").slice(0, 5) }))}
                  className="font-mono" inputMode="numeric" placeholder="cth. 10101" disabled={form.mode === "edit"}
                  data-testid="persediaan-akun-form-sub" />
                <p className="text-[10px] text-muted-foreground mt-1">Diawali &apos;1&apos; (domain persediaan).</p>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pa-akun">Akun Neraca</label>
                <select id="pa-akun" value={form.akun}
                  onChange={(e) => setForm((f) => ({ ...f, akun: e.target.value, uraian: uraianAkun(e.target.value) }))}
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm font-mono" data-testid="persediaan-akun-form-akun">
                  {katalog.map((k) => <option key={k.akun} value={k.akun}>{k.akun} — {k.uraian}</option>)}
                </select>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="persediaan-akun-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
