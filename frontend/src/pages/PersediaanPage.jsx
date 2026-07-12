import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, Boxes,
  ChevronLeft, ChevronRight, PackagePlus, History,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_FILTERS = [
  { value: "", label: "Semua" },
  { value: "aman", label: "Aman" },
  { value: "kritis", label: "Kritis" },
  { value: "habis", label: "Habis" },
];

const STATUS_BADGE = {
  aman: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  kritis: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  habis: "bg-red-500/15 text-red-600 dark:text-red-400",
};

const emptyForm = {
  kode_barang: "", nup: "", nama_barang: "", merk: "", tipe: "",
  satuan: "Buah", lokasi: "", batas_kritis: 0, expired_default: "",
  tahun_anggaran: "", keterangan: "",
};

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

/**
 * Master Persediaan — langkah UI modul Inventarisasi Persediaan (§7.4).
 *
 * Barang lahir dengan stok 0; stok & nilai bertambah lewat transaksi
 * masuk FIFO (iterasi berikutnya). Edit master ber-OCC (If-Match versi).
 */
export default function PersediaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [satuanList, setSatuanList] = useState([]);
  // Dialog: {mode:"tambah", data} | {mode:"edit", id, version, data}
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  // Transaksi masuk: {item, data:{jenis,jumlah,...}}; riwayat: {item, rows, loading}
  const [masuk, setMasuk] = useState(null);
  const [riwayat, setRiwayat] = useState(null);
  const [jenisMasuk, setJenisMasuk] = useState([]);
  const { confirm, confirmDialog } = useConfirm();
  const searchTimer = useRef(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1, s = search, st = status) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/persediaan`, {
        params: { search: s, status: st || undefined, page: p, page_size: 50 },
      });
      setItems(r.data?.items || []);
      setTotal(r.data?.total || 0);
      setTotalPages(r.data?.total_pages || 1);
      setPage(p);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat persediaan"));
    } finally {
      setLoading(false);
    }
  }, [search, status]);

  useEffect(() => {
    load(1, "", "");
    axios.get(`${API}/persediaan/satuan-baku`)
      .then((r) => setSatuanList(Array.isArray(r.data) ? r.data : []))
      .catch(() => setSatuanList([]));
    axios.get(`${API}/persediaan/jenis-transaksi`)
      .then((r) => setJenisMasuk(r.data?.masuk || []))
      .catch(() => setJenisMasuk([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSearchChange = (v) => {
    setSearch(v);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(1, v, status), 350);
  };
  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  const changeStatus = (st) => {
    setStatus(st);
    load(1, search, st);
  };

  const setField = (k, v) => setForm((f) => ({ ...f, data: { ...f.data, [k]: v } }));

  const submitForm = async () => {
    if (!form) return;
    const d = form.data;
    if (!String(d.nama_barang || "").trim()) { toast.error("Nama barang wajib diisi"); return; }
    setSaving(true);
    try {
      if (form.mode === "tambah") {
        if (!String(d.kode_barang || "").trim()) { toast.error("Kode barang wajib diisi"); setSaving(false); return; }
        const r = await axios.post(`${API}/persediaan`, { ...d, batas_kritis: Number(d.batas_kritis) || 0 });
        toast.success(`Barang ${r.data?.kode_barang} NUP ${r.data?.nup} ditambahkan`);
      } else {
        const payload = { ...d, batas_kritis: Number(d.batas_kritis) || 0 };
        delete payload.kode_barang; delete payload.nup;
        await axios.put(`${API}/persediaan/${form.id}`, payload, {
          headers: { "If-Match": String(form.version) },
        });
        toast.success("Barang persediaan diperbarui");
      }
      setForm(null);
      load(page, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan barang persediaan"));
      if (err?.response?.status === 409) load(page, search, status);
    } finally {
      setSaving(false);
    }
  };

  const submitMasuk = async () => {
    if (!masuk) return;
    const d = masuk.data;
    const jumlah = parseInt(d.jumlah, 10);
    if (!jumlah || jumlah <= 0) { toast.error("Jumlah harus lebih dari 0"); return; }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/persediaan/${masuk.item.id}/masuk`, {
        ...d, jumlah, harga_satuan: Number(d.harga_satuan) || 0,
      });
      toast.success(`${r.data?.message} — stok kini ${r.data?.stok}`);
      setMasuk(null);
      load(page, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mencatat transaksi masuk"));
    } finally {
      setSaving(false);
    }
  };

  const openRiwayat = async (item) => {
    setRiwayat({ item, rows: [], loading: true });
    try {
      const r = await axios.get(`${API}/persediaan/${item.id}/riwayat`, { params: { page_size: 50 } });
      setRiwayat({ item, rows: r.data?.items || [], loading: false });
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat riwayat"));
      setRiwayat(null);
    }
  };

  const fmtRp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;

  const remove = async (item) => {
    const ok = await confirm({
      title: `Hapus ${item.nama_barang}?`,
      description: `Kode ${item.kode_barang} NUP ${item.nup}. Hanya barang berstok 0 tanpa layer yang bisa dihapus — jejak transaksi tetap aman.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/persediaan/${item.id}`);
      toast.success("Barang persediaan dihapus");
      load(page, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus barang"));
    }
  };

  return (
    <div className="min-h-screen bg-background" data-testid="persediaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="persediaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center flex-shrink-0">
            <Boxes className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Master Persediaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {total} barang · stok & nilai mengikuti layer FIFO · transaksi masuk/keluar menyusul
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {/* ── Toolbar ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Cari kode, nama, atau merk…"
                className="pl-9 h-10"
                data-testid="persediaan-search"
              />
            </div>
            <Button className="h-10 gap-1.5" onClick={() => setForm({ mode: "tambah", data: { ...emptyForm } })} data-testid="persediaan-add">
              <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah Barang</span>
            </Button>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                type="button"
                onClick={() => changeStatus(f.value)}
                className={`h-8 px-3 rounded-full border text-xs font-medium min-w-0 min-h-0 transition-colors ${
                  status === f.value
                    ? "bg-emerald-600 border-emerald-600 text-white"
                    : "border-border text-muted-foreground hover:bg-muted"
                }`}
                data-testid={`persediaan-status-${f.value || "semua"}`}
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
              <Loader2 className="w-7 h-7 animate-spin text-emerald-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Boxes className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada barang persediaan</p>
              <p className="text-xs text-muted-foreground mt-1">
                Tambahkan barang (kode berawalan &apos;1&apos;; 10 digit → nomor urut otomatis).
                Stok terisi lewat transaksi masuk pada tahap berikutnya.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Kode · NUP</th>
                    <th className="px-3 py-2.5 font-semibold">Nama Barang</th>
                    <th className="px-3 py-2.5 font-semibold">Satuan</th>
                    <th className="px-3 py-2.5 font-semibold">Stok</th>
                    <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Lokasi</th>
                    <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((it) => (
                    <tr key={it.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`persediaan-row-${it.kode_barang}-${it.nup}`}>
                      <td className="px-3 py-2 font-mono text-xs text-foreground whitespace-nowrap">
                        {it.kode_barang}
                        <span className="text-muted-foreground"> · {it.nup}</span>
                      </td>
                      <td className="px-3 py-2 text-foreground/90">
                        {it.nama_barang}
                        {(it.merk || it.tipe) && (
                          <span className="block text-[11px] text-muted-foreground">
                            {[it.merk, it.tipe].filter(Boolean).join(" — ")}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{it.satuan || "-"}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className="font-semibold text-foreground">{it.stok}</span>
                        <span className={`ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATUS_BADGE[it.status_stok] || ""}`}>
                          {it.status_stok}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground hidden sm:table-cell">{it.lokasi || "—"}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setMasuk({
                            item: it,
                            data: {
                              jenis: "pembelian", jumlah: "", harga_satuan: "",
                              expired: "", no_bukti: "", jenis_dokumen: "",
                              tgl_dokumen: "", no_kontrak: "", penyedia: "", keterangan: "",
                            },
                          })}
                          aria-label={`Transaksi masuk ${it.nama_barang}`}
                          title="Transaksi masuk (stok bertambah)"
                          className="p-1.5 rounded-md text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 min-w-0 min-h-0"
                          data-testid={`persediaan-masuk-${it.kode_barang}-${it.nup}`}
                        >
                          <PackagePlus className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => openRiwayat(it)}
                          aria-label={`Riwayat ${it.nama_barang}`}
                          title="Riwayat transaksi"
                          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                          data-testid={`persediaan-riwayat-${it.kode_barang}-${it.nup}`}
                        >
                          <History className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setForm({
                            mode: "edit", id: it.id, version: it.version,
                            data: {
                              nama_barang: it.nama_barang || "", merk: it.merk || "",
                              tipe: it.tipe || "", satuan: it.satuan || "Buah",
                              lokasi: it.lokasi || "", batas_kritis: it.batas_kritis || 0,
                              expired_default: it.expired_default || "",
                              tahun_anggaran: it.tahun_anggaran || "",
                              keterangan: it.keterangan || "",
                              kode_barang: it.kode_barang, nup: it.nup,
                            },
                          })}
                          aria-label={`Ubah ${it.nama_barang}`}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                          data-testid={`persediaan-edit-${it.kode_barang}-${it.nup}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        {isAdmin && (
                          <button
                            type="button"
                            onClick={() => remove(it)}
                            aria-label={`Hapus ${it.nama_barang}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`persediaan-delete-${it.kode_barang}-${it.nup}`}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
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
            <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => load(page - 1, search, status)} className="gap-1">
              <ChevronLeft className="w-4 h-4" />Sebelumnya
            </Button>
            <span className="text-xs text-muted-foreground">Hal. {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => load(page + 1, search, status)} className="gap-1">
              Berikutnya<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </main>

      {/* ── Dialog tambah / edit ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {form?.mode === "tambah" ? "Tambah Barang Persediaan" : `Ubah — ${form?.data?.kode_barang} · NUP ${form?.data?.nup}`}
            </DialogTitle>
            <DialogDescription className="text-xs">
              {form?.mode === "tambah"
                ? "Kode wajib berawalan '1'. Isi 10 digit — nomor urut 6 digit dibuat otomatis; NUP kosong = otomatis."
                : "Kode & NUP tidak dapat diubah. Stok dikelola lewat transaksi."}
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              {form.mode === "tambah" && (
                <>
                  <div className="col-span-2 sm:col-span-1">
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-kode">Kode Barang (10/16 digit)</label>
                    <Input id="psd-kode" className="font-mono" placeholder="cth. 1010101001"
                      value={form.data.kode_barang}
                      onChange={(e) => setField("kode_barang", e.target.value.replace(/\D/g, "").slice(0, 16))}
                      data-testid="persediaan-form-kode" />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-nup">NUP (kosong = otomatis)</label>
                    <Input id="psd-nup" className="font-mono" placeholder="otomatis"
                      value={form.data.nup}
                      onChange={(e) => setField("nup", e.target.value.replace(/\D/g, "").slice(0, 6))} />
                  </div>
                </>
              )}
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-nama">Nama Barang</label>
                <Input id="psd-nama" placeholder="cth. Kertas HVS A4 80gr"
                  value={form.data.nama_barang}
                  onChange={(e) => setField("nama_barang", e.target.value)}
                  data-testid="persediaan-form-nama" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-merk">Merk</label>
                <Input id="psd-merk" value={form.data.merk} onChange={(e) => setField("merk", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-tipe">Tipe</label>
                <Input id="psd-tipe" value={form.data.tipe} onChange={(e) => setField("tipe", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-satuan">Satuan</label>
                <select
                  id="psd-satuan"
                  value={form.data.satuan}
                  onChange={(e) => setField("satuan", e.target.value)}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                >
                  {(satuanList.length ? satuanList : ["Buah"]).map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-batas">Batas Kritis</label>
                <Input id="psd-batas" type="number" min="0"
                  value={form.data.batas_kritis}
                  onChange={(e) => setField("batas_kritis", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-lokasi">Lokasi/Gudang</label>
                <Input id="psd-lokasi" value={form.data.lokasi} onChange={(e) => setField("lokasi", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-expired">Kedaluwarsa Bawaan</label>
                <Input id="psd-expired" type="date"
                  value={form.data.expired_default}
                  onChange={(e) => setField("expired_default", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-tahun">Tahun Anggaran</label>
                <Input id="psd-tahun" placeholder="cth. 2026"
                  value={form.data.tahun_anggaran}
                  onChange={(e) => setField("tahun_anggaran", e.target.value.replace(/\D/g, "").slice(0, 4))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-ket">Keterangan</label>
                <Input id="psd-ket" value={form.data.keterangan} onChange={(e) => setField("keterangan", e.target.value)} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="persediaan-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog transaksi masuk ── */}
      <Dialog open={!!masuk} onOpenChange={(o) => { if (!o) setMasuk(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Transaksi Masuk — {masuk?.item?.nama_barang}</DialogTitle>
            <DialogDescription className="text-xs">
              Membuat layer FIFO baru (harga melekat di layer) dan menambah stok.
              Kode {masuk?.item?.kode_barang} · NUP {masuk?.item?.nup} · stok saat ini {masuk?.item?.stok}.
            </DialogDescription>
          </DialogHeader>
          {masuk && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-jenis">Jenis</label>
                <select
                  id="psd-in-jenis"
                  value={masuk.data.jenis}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="persediaan-masuk-jenis"
                >
                  {(jenisMasuk.length ? jenisMasuk : [{ key: "pembelian", label: "Pembelian", kode: "M02" }]).map((j) => (
                    <option key={j.key} value={j.key}>{j.label} ({j.kode})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-jumlah">Jumlah</label>
                <Input id="psd-in-jumlah" type="number" min="1" placeholder="0"
                  value={masuk.data.jumlah}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, jumlah: e.target.value } }))}
                  data-testid="persediaan-masuk-jumlah" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-harga">Harga Satuan (Rp)</label>
                <Input id="psd-in-harga" type="number" min="0" placeholder="0"
                  value={masuk.data.harga_satuan}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, harga_satuan: e.target.value } }))}
                  data-testid="persediaan-masuk-harga" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-expired">Kedaluwarsa Batch</label>
                <Input id="psd-in-expired" type="date"
                  value={masuk.data.expired}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, expired: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-bukti">No. Bukti/BAST</label>
                <Input id="psd-in-bukti" placeholder="cth. BAST-12/2026"
                  value={masuk.data.no_bukti}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, no_bukti: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-jdok">Jenis Dokumen</label>
                <Input id="psd-in-jdok" placeholder="BAST / Kuitansi / Kontrak"
                  value={masuk.data.jenis_dokumen}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, jenis_dokumen: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-penyedia">Penyedia</label>
                <Input id="psd-in-penyedia"
                  value={masuk.data.penyedia}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, penyedia: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-in-ket">Keterangan</label>
                <Input id="psd-in-ket"
                  value={masuk.data.keterangan}
                  onChange={(e) => setMasuk((m) => ({ ...m, data: { ...m.data, keterangan: e.target.value } }))} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setMasuk(null)}>Batal</Button>
            <Button onClick={submitMasuk} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700" data-testid="persediaan-masuk-simpan">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <PackagePlus className="w-4 h-4 mr-1.5" />}Catat Masuk
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog riwayat transaksi ── */}
      <Dialog open={!!riwayat} onOpenChange={(o) => { if (!o) setRiwayat(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Riwayat — {riwayat?.item?.nama_barang}</DialogTitle>
            <DialogDescription className="text-xs">
              Jurnal transaksi (terbaru dulu) · kode {riwayat?.item?.kode_barang} · NUP {riwayat?.item?.nup}
            </DialogDescription>
          </DialogHeader>
          {riwayat?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-emerald-600" /></div>
          ) : (riwayat?.rows?.length || 0) === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">Belum ada transaksi — catat transaksi masuk untuk mengisi stok.</p>
          ) : (
            <div className="space-y-2">
              {riwayat.rows.map((t) => (
                <div key={t.id} className="rounded-lg border border-border p-2.5 text-xs" data-testid={`riwayat-item-${t.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className={`px-2 py-0.5 rounded-full font-semibold ${t.arah === "masuk" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-red-500/15 text-red-600 dark:text-red-400"}`}>
                      {t.jenis_label} ({t.kode_sakti})
                    </span>
                    <span className="text-muted-foreground">{(t.timestamp || "").slice(0, 16).replace("T", " ")}</span>
                  </div>
                  <p className="mt-1.5 text-foreground">
                    {t.arah === "masuk" ? "+" : "−"}{t.jumlah} × {fmtRp(t.harga_satuan)} = <b>{fmtRp(t.total)}</b>
                    <span className="text-muted-foreground"> · stok {t.stok_sebelum} → {t.stok_sesudah}</span>
                  </p>
                  {(t.no_bukti || t.penyedia || t.keterangan) && (
                    <p className="mt-1 text-muted-foreground">
                      {[t.no_bukti && `Bukti: ${t.no_bukti}`, t.penyedia && `Penyedia: ${t.penyedia}`, t.keterangan]
                        .filter(Boolean).join(" · ")}
                    </p>
                  )}
                  <p className="mt-0.5 text-muted-foreground">Petugas: {t.petugas}</p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
