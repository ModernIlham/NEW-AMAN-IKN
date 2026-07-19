import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Upload, Download, Pencil, Trash2, Loader2,
  ListTree, ChevronLeft, ChevronRight, Info, FileDown, Table2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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

// Label ramah metadata SIMAN (disajikan hanya di panel Detail, bukan tabel utama).
const META_LABELS = {
  satuan: "Satuan",
  dasar: "Dasar",
  jenis_bmn: "Jenis BMN",
  tb_stb: "TB/STB",
  bukti_kepemilikan: "Bukti Kepemilikan",
};
const META_ORDER = ["satuan", "dasar", "jenis_bmn", "tb_stb", "bukti_kepemilikan"];

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
  // Panel Detail: {item, jenjang:[{level,label,kode,uraian}], loading}
  const [detail, setDetail] = useState(null);
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

  // Impor satu ATAU banyak file sekaligus (mis. 5 file SIMAN per level) —
  // tiap file di-POST berurutan, hasilnya diringkas jadi satu notifikasi.
  const onImportFile = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = ""; // reset supaya file sama bisa dipilih ulang
    if (!files.length) return;
    setImporting(true);
    const agg = { inserted: 0, updated: 0, meta: 0, errors: 0, gagal: 0 };
    let contohError = "";
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        const r = await axios.post(`${API}/kodefikasi/import`, fd);
        const d = r.data || {};
        agg.inserted += d.inserted || 0;
        agg.updated += d.updated || 0;
        agg.meta += d.dengan_metadata || 0;
        agg.errors += d.error_count || 0;
        if (!contohError && (d.errors || [])[0]) contohError = d.errors[0];
      } catch (err) {
        agg.gagal += 1;
        if (!contohError) contohError = getApiError(err, `Gagal: ${file.name}`);
      }
    }
    const nfile = files.length > 1 ? `${files.length} file — ` : "";
    toast.success(`${nfile}Impor selesai: ${agg.inserted} baru, ${agg.updated} diperbarui`
      + (agg.meta ? `, ${agg.meta} berinfo SIMAN` : ""));
    if (agg.errors > 0 || agg.gagal > 0) {
      toast.warning(`${agg.errors} baris bermasalah${agg.gagal ? `, ${agg.gagal} file gagal` : ""}`
        + (contohError ? ` — contoh: ${contohError}` : ""));
    }
    load(1, search, level);
    setImporting(false);
  };

  const openDetail = async (item) => {
    setDetail({ item, jenjang: [], loading: true });
    try {
      const r = await axios.get(`${API}/kodefikasi/lookup/${item.kode}`);
      setDetail({ item, jenjang: r.data?.jenjang || [], loading: false });
    } catch (err) {
      setDetail({ item, jenjang: [], loading: false });
    }
  };

  const downloadTemplate = () => {
    downloadFileWithProgress(`${API}/kodefikasi/template`, "template_kodefikasi.csv", {
      label: "Template Kodefikasi",
    }).catch(() => {});
  };

  // Dua pendekatan ekspor: datar (seperti tabel) & hierarki berkolom + info SIMAN.
  const exportKodefikasi = (bentuk) => {
    const nama = bentuk === "hierarki" ? "kodefikasi_hierarki.xlsx" : "kodefikasi_datar.xlsx";
    downloadFileWithProgress(`${API}/kodefikasi/export?bentuk=${bentuk}`, nama, {
      label: bentuk === "hierarki" ? "Ekspor Kodefikasi (hierarki + info SIMAN)" : "Ekspor Kodefikasi (datar)",
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
        {/* ── Toolbar padat: cari + aksi ikon (1 baris) + segmented filter level ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 space-y-2">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 min-w-0">
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
                <Button variant="outline" className="h-10 w-10 p-0 flex-shrink-0" title="Tambah kode kodefikasi baru secara manual"
                  aria-label="Tambah kode" onClick={() => setForm({ mode: "tambah", kode: "", uraian: "" })} data-testid="kodefikasi-add">
                  <Plus className="w-4 h-4" />
                </Button>
                <Button variant="outline" className="h-10 w-10 p-0 flex-shrink-0" disabled={importing} title="Impor kodefikasi massal dari file CSV/Excel"
                  aria-label="Impor kodefikasi" onClick={() => fileRef.current?.click()} data-testid="kodefikasi-import">
                  {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                </Button>
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" multiple className="hidden" onChange={onImportFile} />
              </>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="h-10 w-10 p-0 flex-shrink-0" data-testid="kodefikasi-unduh"
                  aria-label="Unduh / ekspor kodefikasi" title="Unduh template impor atau ekspor daftar kodefikasi">
                  <FileDown className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                {isAdmin && (
                  <DropdownMenuItem className="min-h-[42px] gap-2" onClick={downloadTemplate} data-testid="kodefikasi-template">
                    <Download className="w-4 h-4" />Template Impor (CSV)
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem className="min-h-[42px] gap-2" onClick={() => exportKodefikasi("datar")} data-testid="kodefikasi-export-datar">
                  <FileDown className="w-4 h-4" />Ekspor Datar — Kode, Uraian, Level, Induk
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px] gap-2" onClick={() => exportKodefikasi("hierarki")} data-testid="kodefikasi-export-hierarki">
                  <Table2 className="w-4 h-4" />Ekspor Hierarki — Golongan s.d. Sub-Sub + SIMAN
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          {/* Segmented control: satu bagian utuh, keenam segmen MUAT dalam 1
              baris — font & padding mengecil di layar kecil agar tak terpotong */}
          <div className="flex w-full items-stretch rounded-lg border border-border overflow-hidden">
            {LEVEL_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => changeLevel(f.value)}
                className={`flex-1 h-9 px-0.5 sm:px-2 text-[10px] sm:text-xs font-medium leading-none whitespace-nowrap border-l first:border-l-0 border-border min-w-0 min-h-0 transition-colors ${
                  level === f.value
                    ? "bg-blue-600 text-white"
                    : "text-muted-foreground hover:bg-muted"
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
                  ? "Impor daftar kodefikasi (CSV/XLSX kolom kode & uraian, atau 5 file keluaran SIMAN V2 per level sekaligus) — 8 golongan standar sudah tersedia otomatis."
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
                    <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>
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
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => openDetail(it)}
                          aria-label={`Detail ${it.kode}`}
                          title="Detail (hierarki & info SIMAN)"
                          className="p-1.5 rounded-md text-blue-600 dark:text-blue-400 hover:bg-blue-500/10 min-w-0 min-h-0"
                          data-testid={`kodefikasi-detail-${it.kode}`}
                        >
                          <Info className="w-3.5 h-3.5" />
                        </button>
                        {isAdmin && (
                          <>
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
                          </>
                        )}
                      </td>
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

      {/* ── Dialog Detail: hierarki + metadata SIMAN (tak tampil di tabel utama) ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-mono text-base">{detail?.item?.kode}</DialogTitle>
            <DialogDescription className="text-xs">
              {detail?.item?.uraian}
              {detail?.item?.label_level ? ` · ${detail.item.level} ${detail.item.label_level}` : ""}
            </DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-4">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground mb-1.5">Hierarki Kode</p>
                {detail.loading ? (
                  <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-blue-600" /></div>
                ) : (detail.jenjang || []).length === 0 ? (
                  <p className="text-xs text-muted-foreground">Tidak dapat memuat hierarki.</p>
                ) : (
                  <ol className="space-y-1">
                    {detail.jenjang.map((j) => (
                      <li key={j.kode} className="flex items-baseline gap-2 text-sm" data-testid={`detail-jenjang-${j.level}`}>
                        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold shrink-0 ${LEVEL_BADGE[j.level] || LEVEL_BADGE[5]}`}>{j.label}</span>
                        <span className="font-mono text-xs text-muted-foreground shrink-0">{j.kode}</span>
                        <span className="text-foreground/90">{j.uraian || <span className="text-muted-foreground italic">(belum terdaftar)</span>}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>

              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground mb-1.5">Informasi Tambahan (SIMAN)</p>
                {META_ORDER.some((k) => (detail.item?.meta?.[k] || "").trim()) ? (
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                    {META_ORDER.map((k) => (
                      <React.Fragment key={k}>
                        <dt className="text-muted-foreground whitespace-nowrap">{META_LABELS[k]}</dt>
                        <dd className="text-foreground/90 text-right">{(detail.item?.meta?.[k] || "").trim() || "—"}</dd>
                      </React.Fragment>
                    ))}
                  </dl>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Belum ada info tambahan untuk kode ini (biasanya melekat di kode barang 10 digit hasil impor SIMAN).
                  </p>
                )}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
