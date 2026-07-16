import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Pencil, RotateCcw, Loader2, Landmark, Info,
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

// Nama golongan BMN (kodefikasi PMK 29/2010) — label stabil (uraian bisa disunting admin).
const GOL_NAMA = {
  "1": "Persediaan", "2": "Tanah", "3": "Peralatan dan Mesin",
  "4": "Gedung dan Bangunan", "5": "Jalan, Irigasi, dan Jaringan",
  "6": "Aset Tetap Lainnya", "7": "Konstruksi Dalam Pengerjaan",
  "8": "Aset Tak Berwujud",
};

/**
 * Referensi Akun Neraca (Bagan Akun Standar) per golongan BMN (#300).
 *
 * Semua user login melihat pemetaan golongan → akun neraca; admin menimpa per
 * golongan dari Lampiran BAS (default riset ditandai perlu-verifikasi) atau
 * mengembalikannya ke default. Dasar kolom "Akun Neraca" di Laporan Posisi BMN
 * di Neraca (#301) & DBKP per Golongan (#302).
 */
export default function AkunBasPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/akun-bas`);
      setItems(r.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat referensi akun neraca"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const submitForm = async () => {
    if (!form) return;
    if (!/^\d{3,6}$/.test((form.akun || "").trim())) {
      toast.error("Kode akun harus 3–6 digit angka (mis. 132111)");
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/akun-bas`, {
        golongan: form.golongan, akun: form.akun.trim(), uraian: form.uraian || "",
      });
      toast.success(`Akun golongan ${form.golongan} disimpan`);
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan akun neraca"));
    } finally {
      setSaving(false);
    }
  };

  const revert = async (it) => {
    const ok = await confirm({
      title: `Kembalikan golongan ${it.golongan} ke default?`,
      description: "Entri satker akan dihapus dan pemetaan kembali ke akun default hasil riset (perlu verifikasi Lampiran BAS).",
      confirmLabel: "Kembalikan", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/akun-bas/${it.golongan}`);
      toast.success(`Golongan ${it.golongan} kembali ke default`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengembalikan ke default"));
    }
  };

  const jumlahSatker = items.filter((it) => (it.sumber || "").startsWith("input satker")).length;

  return (
    <div className="min-h-screen bg-background" data-testid="akun-bas-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="akun-bas-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center flex-shrink-0">
            <Landmark className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Akun Neraca</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Golongan BMN → akun neraca (BAS) · dasar kolom Akun di Neraca &amp; DBKP
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-2.5 flex gap-2.5">
          <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-[11px] sm:text-xs text-foreground/90 leading-relaxed">
            Akun default adalah <strong>akun representatif</strong> per golongan hasil riset (Neraca Percobaan/Posisi BMN)
            &mdash; <strong>wajib diverifikasi ke Lampiran Bagan Akun Standar</strong> (KEP-211/PB/2018 dst.).
            {isAdmin ? " Sunting akun agar sesuai BAS satker; entri satker menimpa default." : " Hubungi admin untuk menyesuaikan."}
          </p>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-amber-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Landmark className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Referensi belum termuat</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Gol.</th>
                    <th className="px-3 py-2.5 font-semibold">Akun Neraca</th>
                    <th className="px-3 py-2.5 font-semibold">Uraian</th>
                    <th className="px-3 py-2.5 font-semibold">Sumber</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => {
                    const satker = (it.sumber || "").startsWith("input satker");
                    return (
                      <tr key={it.golongan} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`akun-bas-row-${it.golongan}`}>
                        <td className="px-3 py-2.5">
                          <p className="font-bold text-foreground font-mono">{it.golongan}</p>
                          <p className="text-[10px] text-muted-foreground leading-tight">{GOL_NAMA[it.golongan] || ""}</p>
                        </td>
                        <td className="px-3 py-2.5 font-mono font-semibold text-foreground whitespace-nowrap">{it.akun || "—"}</td>
                        <td className="px-3 py-2.5 text-[12px] text-foreground/90">{it.uraian || "—"}</td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            satker
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                            {satker ? "Input satker" : "Default riset"}
                          </span>
                        </td>
                        {isAdmin && (
                          <td className="px-3 py-2.5 text-right whitespace-nowrap">
                            <button type="button" onClick={() => setForm({ ...it })}
                              aria-label={`Ubah akun golongan ${it.golongan}`}
                              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                              data-testid={`akun-bas-edit-${it.golongan}`}>
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            {satker && (
                              <button type="button" onClick={() => revert(it)}
                                aria-label={`Kembalikan golongan ${it.golongan} ke default`}
                                title="Kembalikan ke default"
                                className="p-1.5 rounded-md text-muted-foreground hover:text-amber-600 hover:bg-amber-500/10 min-w-0 min-h-0"
                                data-testid={`akun-bas-revert-${it.golongan}`}>
                                <RotateCcw className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {!loading && items.length > 0 && (
          <p className="text-[11px] text-muted-foreground px-1">
            {items.length} golongan · {jumlahSatker} disunting satker · {items.length - jumlahSatker} default riset.
          </p>
        )}
      </main>

      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Ubah Akun Neraca — Golongan {form?.golongan}</DialogTitle>
            <DialogDescription className="text-xs">
              {form ? `${GOL_NAMA[form.golongan] || ""} — sesuaikan kode akun neraca dengan Lampiran Bagan Akun Standar satker.` : ""}
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="akun-bas-akun">Kode Akun Neraca *</label>
                <Input id="akun-bas-akun" value={form.akun}
                  onChange={(e) => setForm((f) => ({ ...f, akun: e.target.value.replace(/[^\d]/g, "").slice(0, 6) }))}
                  className="font-mono" inputMode="numeric" placeholder="cth. 132111" data-testid="akun-bas-form-akun" />
                <p className="text-[10px] text-muted-foreground mt-1">3–6 digit angka (akun sub-kelompok neraca).</p>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="akun-bas-uraian">Uraian</label>
                <Input id="akun-bas-uraian" value={form.uraian}
                  onChange={(e) => setForm((f) => ({ ...f, uraian: e.target.value }))}
                  placeholder="cth. Peralatan dan Mesin" data-testid="akun-bas-form-uraian" />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="akun-bas-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
