import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, DoorOpen,
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

const EMPTY = {
  mode: "tambah", kode_ruangan: "", nama_ruangan: "", gedung: "", lantai: "",
  penanggung_jawab_id: "", penanggung_jawab_nama: "", unit_kerja: "",
  keterangan: "", aktif: true,
};

/**
 * Master Referensi Ruangan (PMK 181/2016, #294) — fondasi KIR/DBR.
 *
 * Semua user login melihat daftar ruangan; admin mengelola. Tiap ruangan bisa
 * menunjuk Penanggung Jawab Ruangan dari registry pejabat.
 */
export default function RuanganPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [pjList, setPjList] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/ruangan`);
      setItems(r.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat daftar ruangan"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Kandidat penanggung jawab: pejabat berperan penanggung_jawab_ruangan
    // yang masih berlaku hari ini (cermin pejabat_utils._berlaku_pada — aktif
    // dan rentang berlaku_mulai/selesai mencakup tanggal ini).
    axios.get(`${API}/pejabat`).then((r) => {
      const all = r.data?.items || [];
      const now = new Date();
      const hariIni = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
      setPjList(all.filter((p) => {
        if (!(p.peran || []).includes("penanggung_jawab_ruangan")) return false;
        if (p.aktif === false) return false;
        const mulai = String(p.berlaku_mulai || "").slice(0, 10);
        const selesai = String(p.berlaku_selesai || "").slice(0, 10);
        if (mulai && hariIni < mulai) return false;
        if (selesai && hariIni > selesai) return false;
        return true;
      }));
    }).catch(() => {});
  }, [load]);

  const onPickPj = (id) => setForm((f) => {
    const pj = pjList.find((p) => p.id === id);
    return { ...f, penanggung_jawab_id: id, penanggung_jawab_nama: pj?.nama || "" };
  });

  const submitForm = async () => {
    if (!form) return;
    if (!(form.kode_ruangan || "").trim()) { toast.error("Kode ruangan wajib diisi"); return; }
    if (!(form.nama_ruangan || "").trim()) { toast.error("Nama ruangan wajib diisi"); return; }
    setSaving(true);
    const body = {
      kode_ruangan: form.kode_ruangan, nama_ruangan: form.nama_ruangan,
      gedung: form.gedung, lantai: form.lantai,
      penanggung_jawab_id: form.penanggung_jawab_id,
      penanggung_jawab_nama: form.penanggung_jawab_nama,
      unit_kerja: form.unit_kerja, keterangan: form.keterangan, aktif: form.aktif,
    };
    try {
      if (form.mode === "tambah") {
        await axios.post(`${API}/ruangan`, body);
        toast.success(`Ruangan ${form.kode_ruangan} ditambahkan`);
      } else {
        await axios.put(`${API}/ruangan/${form.id}`, body);
        toast.success(`Ruangan ${form.kode_ruangan} diperbarui`);
      }
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan ruangan"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it) => {
    const ok = await confirm({
      title: `Hapus ruangan ${it.kode_ruangan}?`,
      description: `"${it.nama_ruangan}" akan dihapus dari referensi ruangan.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/ruangan/${it.id}`);
      toast.success(`Ruangan ${it.kode_ruangan} dihapus`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus ruangan"));
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = !q ? items : items.filter((it) =>
    [it.kode_ruangan, it.nama_ruangan, it.gedung, it.penanggung_jawab_nama]
      .some((v) => String(v || "").toLowerCase().includes(q)));

  return (
    <div className="min-h-screen bg-background" data-testid="ruangan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="ruangan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
            <DoorOpen className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Ruangan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {items.length} ruangan · fondasi KIR/DBR & lokasi terstruktur (PMK 181/2016)
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari kode / nama / gedung / penanggung jawab…" className="pl-9 h-10" data-testid="ruangan-search" />
            </div>
            {isAdmin && (
              <Button variant="outline" className="h-10 gap-1.5"
                onClick={() => setForm({ ...EMPTY })} data-testid="ruangan-add">
                <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah</span>
              </Button>
            )}
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-teal-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <DoorOpen className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada ruangan</p>
              <p className="text-xs text-muted-foreground mt-1">
                {isAdmin ? "Tambah ruangan untuk menata lokasi BMN (dasar KIR/DBR)."
                  : "Minta admin menambah data ruangan."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Kode / Nama</th>
                    <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Gedung / Lantai</th>
                    <th className="px-3 py-2.5 font-semibold">Penanggung Jawab</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`ruangan-row-${it.id}`}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-foreground font-mono text-xs">{it.kode_ruangan}</p>
                        <p className="text-[12px] text-foreground/90">{it.nama_ruangan}</p>
                      </td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground whitespace-nowrap hidden sm:table-cell">
                        {[it.gedung, it.lantai ? `Lt. ${it.lantai}` : ""].filter(Boolean).join(" · ") || "—"}
                      </td>
                      <td className="px-3 py-2 text-[12px] text-foreground/90">{it.penanggung_jawab_nama || "—"}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          it.aktif === false
                            ? "bg-slate-500/15 text-muted-foreground"
                            : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"}`}>
                          {it.aktif === false ? "Nonaktif" : "Aktif"}
                        </span>
                      </td>
                      {isAdmin && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button type="button" onClick={() => setForm({ ...EMPTY, ...it, mode: "edit" })}
                            aria-label={`Ubah ${it.kode_ruangan}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`ruangan-edit-${it.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            aria-label={`Hapus ${it.kode_ruangan}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`ruangan-delete-${it.id}`}>
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
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Ruangan" : `Ubah Ruangan — ${form?.kode_ruangan}`}</DialogTitle>
            <DialogDescription className="text-xs">
              Lokasi terstruktur per ruangan — dasar Kartu Inventaris Ruangan (KIR) & Daftar Barang Ruangan (DBR).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Kode Ruangan *"><Input value={form.kode_ruangan} onChange={(e) => setForm((f) => ({ ...f, kode_ruangan: e.target.value }))} className="font-mono" placeholder="cth. R.101" data-testid="ruangan-form-kode" /></Field>
                <Field label="Nama Ruangan *"><Input value={form.nama_ruangan} onChange={(e) => setForm((f) => ({ ...f, nama_ruangan: e.target.value }))} placeholder="cth. Ruang Kepala" data-testid="ruangan-form-nama" /></Field>
                <Field label="Gedung"><Input value={form.gedung} onChange={(e) => setForm((f) => ({ ...f, gedung: e.target.value }))} /></Field>
                <Field label="Lantai"><Input value={form.lantai} onChange={(e) => setForm((f) => ({ ...f, lantai: e.target.value }))} /></Field>
                <Field label="Penanggung Jawab Ruangan">
                  <select value={form.penanggung_jawab_id} onChange={(e) => onPickPj(e.target.value)}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" data-testid="ruangan-form-pj">
                    <option value="">— pilih dari pejabat —</option>
                    {form.penanggung_jawab_id && !pjList.some((p) => p.id === form.penanggung_jawab_id) && (
                      <option value={form.penanggung_jawab_id}>
                        {form.penanggung_jawab_nama || "Pejabat lama"} (kedaluwarsa)
                      </option>
                    )}
                    {pjList.map((p) => <option key={p.id} value={p.id}>{p.nama}{p.jabatan ? ` (${p.jabatan})` : ""}</option>)}
                  </select>
                </Field>
                <Field label="Unit Kerja"><Input value={form.unit_kerja} onChange={(e) => setForm((f) => ({ ...f, unit_kerja: e.target.value }))} /></Field>
              </div>
              <Field label="Status">
                <label className="flex items-center gap-2 h-8">
                  <input type="checkbox" checked={form.aktif !== false}
                    onChange={(e) => setForm((f) => ({ ...f, aktif: e.target.checked }))}
                    className="w-4 h-4" data-testid="ruangan-form-aktif" />
                  <span className="text-sm text-foreground">Aktif</span>
                </label>
              </Field>
              <Field label="Keterangan"><Input value={form.keterangan} onChange={(e) => setForm((f) => ({ ...f, keterangan: e.target.value }))} /></Field>
              {pjList.length === 0 && (
                <p className="text-[11px] text-muted-foreground">
                  Belum ada pejabat berperan &quot;Penanggung Jawab Ruangan&quot; — tambahkan di Referensi Pejabat agar bisa dipilih.
                </p>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="ruangan-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
      {children}
    </div>
  );
}
