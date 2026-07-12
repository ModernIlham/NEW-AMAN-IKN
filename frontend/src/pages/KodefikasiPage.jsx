import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Upload, Download, Pencil, Trash2, Loader2,
  ListTree, ChevronLeft, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEVEL_FILTERS = [
  { value: 0, label: "Semua" },
  { value: 1, label: "Golongan" },
  { value: 2, label: "Bidang" },
  { value: 3, label: "Kelompok" },
  { value: 4, label: "Sub" },
  { value: 5, label: "Sub-sub" },
];

const LEVEL_BADGE = {
  1: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  2: "bg-teal-500/15 text-teal-600 dark:text-teal-400",
  3: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  4: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  5: "bg-slate-500/15 text-muted-foreground",
};

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

/**
 * Referensi Kodefikasi Barang BMN — fondasi Fase 2.
 *
 * Semua user login bisa mencari/menelusuri 5 level kode; admin dapat
 * menambah, mengubah uraian, menghapus (bila tanpa turunan), dan impor
 * massal CSV/XLSX. Level selalu diturunkan dari panjang kode di server.
 */
export default function KodefikasiPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  // Dialog tambah/edit: {mode:"tambah"} | {mode:"edit", kode, uraian}
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();
  const searchTimer = useRef(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1, s = search, lv = level) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/kodefikasi`, {
        params: { search: s, level: lv || undefined, page: p, page_size: 50 },
      });
      setItems(r.data?.items || []);
      setTotal(r.data?.total || 0);
      setTotalPages(r.data?.total_pages || 1);
      setPage(p);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat kodefikasi"));
    } finally {
      setLoading(false);
    }
  }, [search, level]);

  useEffect(() => { load(1, "", 0); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Cari dengan debounce ringan — tanpa tombol, langsung menyaring.
  const onSearchChange = (v) => {
    setSearch(v);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(1, v, level), 350);
  };
  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  const changeLevel = (lv) => {
    setLevel(lv);
    load(1, search, lv);
  };

  const submitForm = async () => {
    if (!form) return;
    const uraian = (form.uraian || "").trim();
    if (!uraian) { toast.error("Uraian wajib diisi"); return; }
    setSaving(true);
    try {
      if (form.mode === "tambah") {
        const kode = (form.kode || "").trim();
        await axios.post(`${API}/kodefikasi`, { kode, uraian });
        toast.success(`Kode ${kode} ditambahkan`);
      } else {
        await axios.put(`${API}/kodefikasi/${form.kode}`, { uraian });
        toast.success(`Uraian kode ${form.kode} diperbarui`);
      }
      setForm(null);
      load(page, search, level);
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan kodefikasi"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (item) => {
    const ok = await confirm({
      title: `Hapus kode ${item.kode}?`,
      description: `"${item.uraian}" (${item.label_level}) akan dihapus dari referensi. Kode yang masih punya turunan akan ditolak server.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/kodefikasi/${item.kode}`);
      toast.success(`Kode ${item.kode} dihapus`);
      load(page, search, level);
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus kode"));
    }
  };

  const onImportFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // reset supaya file sama bisa dipilih ulang
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/kodefikasi/import`, fd);
      const d = r.data || {};
      toast.success(d.message || "Impor selesai");
      if (d.error_count > 0) {
        toast.warning(`${d.error_count} baris bermasalah — contoh: ${(d.errors || [])[0] || ""}`);
      }
      load(1, search, level);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengimpor file"));
    } finally {
      setImporting(false);
    }
  };

  const downloadTemplate = () => {
    downloadFileWithProgress(`${API}/kodefikasi/template`, "template_kodefikasi.csv", {
      label: "Template Kodefikasi",
    }).catch(() => {});
  };

  return (
    <div className="min-h-screen bg-background" data-testid="kodefikasi-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="kodefikasi-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <ListTree className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Kodefikasi Barang</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {total} kode · 5 level (Golongan → Sub-sub Kelompok) · digit pertama &apos;1&apos; = persediaan
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {/* ── Toolbar: cari + filter level + aksi admin ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Cari kode (prefix) atau uraian…"
                className="pl-9 h-10"
                data-testid="kodefikasi-search"
              />
            </div>
            {isAdmin && (
              <>
                <Button variant="outline" className="h-10 gap-1.5" onClick={() => setForm({ mode: "tambah", kode: "", uraian: "" })} data-testid="kodefikasi-add">
                  <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah</span>
                </Button>
                <Button variant="outline" className="h-10 gap-1.5" disabled={importing} onClick={() => fileRef.current?.click()} data-testid="kodefikasi-import">
                  {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  <span className="hidden sm:inline">Impor</span>
                </Button>
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onImportFile} />
                <Button variant="outline" className="h-10 gap-1.5" onClick={downloadTemplate} data-testid="kodefikasi-template">
                  <Download className="w-4 h-4" /><span className="hidden sm:inline">Template</span>
                </Button>
              </>
            )}
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {LEVEL_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => changeLevel(f.value)}
                className={`h-8 px-3 rounded-full border text-xs font-medium min-w-0 min-h-0 transition-colors ${
                  level === f.value
                    ? "bg-blue-600 border-blue-600 text-white"
                    : "border-border text-muted-foreground hover:bg-muted"
                }`}
                data-testid={`kodefikasi-level-${f.value}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── Tabel ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-blue-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <ListTree className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada kode yang cocok</p>
              <p className="text-xs text-muted-foreground mt-1">
                {isAdmin
                  ? "Impor daftar kodefikasi (CSV/XLSX kolom kode & uraian) atau tambah manual — 8 golongan standar sudah tersedia otomatis."
                  : "Coba kata kunci lain, atau minta admin mengimpor daftar kodefikasi."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Kode</th>
                    <th className="px-3 py-2.5 font-semibold">Uraian</th>
                    <th className="px-3 py-2.5 font-semibold">Level</th>
                    <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Induk</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={it.kode} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`kodefikasi-row-${it.kode}`}>
                      <td className="px-3 py-2 font-mono text-xs font-semibold text-foreground whitespace-nowrap">
                        {it.kode}
                        {it.is_persediaan && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[9px] font-bold align-middle">PERSEDIAAN</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-foreground/90">{it.uraian}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${LEVEL_BADGE[it.level] || LEVEL_BADGE[5]}`}>
                          {it.level} · {it.label_level}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground hidden sm:table-cell">{it.parent_kode || "—"}</td>
                      {isAdmin && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() => setForm({ mode: "edit", kode: it.kode, uraian: it.uraian })}
                            aria-label={`Ubah uraian ${it.kode}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`kodefikasi-edit-${it.kode}`}
                          >
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => remove(it)}
                            aria-label={`Hapus ${it.kode}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`kodefikasi-delete-${it.kode}`}
                          >
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

        {/* ── Paginasi ── */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => load(page - 1, search, level)} className="gap-1">
              <ChevronLeft className="w-4 h-4" />Sebelumnya
            </Button>
            <span className="text-xs text-muted-foreground">Hal. {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => load(page + 1, search, level)} className="gap-1">
              Berikutnya<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </main>

      {/* ── Dialog tambah / edit ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Kode" : `Ubah Uraian — ${form?.kode}`}</DialogTitle>
            <DialogDescription className="text-xs">
              {form?.mode === "tambah"
                ? "Panjang kode menentukan levelnya otomatis: 1 digit golongan, 3 bidang, 5 kelompok, 7 sub, 10 sub-sub."
                : "Hanya uraian yang dapat diubah — kode & level tetap."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {form?.mode === "tambah" && (
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kodefikasi-kode-input">Kode (angka, 1/3/5/7/10 digit)</label>
                <Input
                  id="kodefikasi-kode-input"
                  value={form?.kode || ""}
                  onChange={(e) => setForm((f) => ({ ...f, kode: e.target.value.replace(/\D/g, "").slice(0, 10) }))}
                  placeholder="cth. 3010203001"
                  className="font-mono"
                  data-testid="kodefikasi-form-kode"
                />
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kodefikasi-uraian-input">Uraian</label>
              <Input
                id="kodefikasi-uraian-input"
                value={form?.uraian || ""}
                onChange={(e) => setForm((f) => ({ ...f, uraian: e.target.value }))}
                placeholder="cth. Alat Besar Apung"
                data-testid="kodefikasi-form-uraian"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="kodefikasi-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
