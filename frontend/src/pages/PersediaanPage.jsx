import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, Boxes,
  ChevronLeft, ChevronRight, PackagePlus, PackageMinus, History,
  AlertTriangle, FileDown, ClipboardCheck, ChevronDown, Upload, Download,
  Layers, X,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

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
  const [gudang, setGudang] = useState("");
  const [daftarGudang, setDaftarGudang] = useState([]);
  const [loading, setLoading] = useState(false);
  const [satuanList, setSatuanList] = useState([]);
  // Dialog: {mode:"tambah", data} | {mode:"edit", id, version, data}
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  // Transaksi masuk/keluar: {item, data:{jenis,jumlah,...}}; riwayat: {item, rows, loading}
  const [masuk, setMasuk] = useState(null);
  const [keluar, setKeluar] = useState(null);
  const [riwayat, setRiwayat] = useState(null);
  const [jenisMasuk, setJenisMasuk] = useState([]);
  const [jenisKeluar, setJenisKeluar] = useState([]);
  const [peringatan, setPeringatan] = useState(null);
  // Status opname semester berjalan: {sudah, label, terakhir, pesan}
  const [opnameStatus, setOpnameStatus] = useState(null);
  // Dialog laporan mutasi: {dari, sampai} default bulan berjalan
  const [mutasi, setMutasi] = useState(null);
  // Dialog opname: {item, stok_fisik, alasan}; BAOF: {tanggal}
  const [opname, setOpname] = useState(null);
  const [baof, setBaof] = useState(null);
  // Impor master
  const [importing, setImporting] = useState(false);
  const fileImporRef = useRef(null);
  // Transaksi massal per dokumen: {arah, jenis, ..., items[], cari, hasil, laporan}
  const [massal, setMassal] = useState(null);
  const massalTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();
  const searchTimer = useRef(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1, s = search, st = status, g = gudang) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/persediaan`, {
        params: { search: s, status: st || undefined,
                  gudang: g || undefined, page: p, page_size: 50 },
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
  }, [search, status, gudang]);

  useEffect(() => {
    load(1, "", "");
    axios.get(`${API}/persediaan/satuan-baku`)
      .then((r) => setSatuanList(Array.isArray(r.data) ? r.data : []))
      .catch(() => setSatuanList([]));
    axios.get(`${API}/persediaan/jenis-transaksi`)
      .then((r) => { setJenisMasuk(r.data?.masuk || []); setJenisKeluar(r.data?.keluar || []); })
      .catch(() => { setJenisMasuk([]); setJenisKeluar([]); });
    axios.get(`${API}/persediaan/peringatan`)
      .then((r) => setPeringatan(r.data))
      .catch(() => setPeringatan(null));
    axios.get(`${API}/persediaan/opname/status`)
      .then((r) => setOpnameStatus(r.data))
      .catch(() => setOpnameStatus(null));
    axios.get(`${API}/persediaan/gudang/daftar`)
      .then((r) => setDaftarGudang(r.data?.items || []))
      .catch(() => setDaftarGudang([]));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSearchChange = (v) => {
    setSearch(v);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(1, v, status), 350);
  };
  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  // Pencarian barang untuk dialog transaksi massal (debounce)
  const massalCari = massal?.cari || "";
  useEffect(() => {
    if (!massal || massalCari.trim().length < 2) return undefined;
    clearTimeout(massalTimer.current);
    massalTimer.current = setTimeout(async () => {
      setMassal((m) => (m ? { ...m, mencari: true } : m));
      try {
        const r = await axios.get(`${API}/persediaan`, {
          params: { search: massalCari.trim(), page_size: 8 },
        });
        setMassal((m) => (m ? { ...m, hasil: r.data?.items || [], mencari: false } : m));
      } catch {
        setMassal((m) => (m ? { ...m, hasil: [], mencari: false } : m));
      }
    }, 300);
    return () => clearTimeout(massalTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [massalCari]);

  const changeStatus = (st) => {
    setStatus(st);
    load(1, search, st);
  };

  const changeGudang = (g) => {
    setGudang(g);
    load(1, search, status, g);
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

  const submitKeluar = async () => {
    if (!keluar) return;
    const d = keluar.data;
    const jumlah = parseInt(d.jumlah, 10);
    if (!jumlah || jumlah <= 0) { toast.error("Jumlah harus lebih dari 0"); return; }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/persediaan/${keluar.item.id}/keluar`, { ...d, jumlah });
      toast.success(`${r.data?.message} — nilai keluar ${fmtRp(r.data?.nilai_keluar)}, stok kini ${r.data?.stok}`);
      setKeluar(null);
      load(page, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mencatat transaksi keluar"));
    } finally {
      setSaving(false);
    }
  };

  const onImportFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/persediaan/import`, fd);
      const d = r.data || {};
      toast.success(d.message || "Impor selesai");
      if (d.error_count > 0) {
        toast.warning(`${d.error_count} baris bermasalah — contoh: ${(d.errors || [])[0] || ""}`);
      }
      load(1, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengimpor file"));
    } finally {
      setImporting(false);
    }
  };

  const submitOpname = async () => {
    if (!opname) return;
    const fisik = parseInt(opname.stok_fisik, 10);
    if (Number.isNaN(fisik) || fisik < 0) { toast.error("Stok fisik tidak valid"); return; }
    if ((opname.alasan || "").trim().length < 3) { toast.error("Alasan selisih wajib diisi (bahan CaLK)"); return; }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/persediaan/${opname.item.id}/opname`, {
        stok_fisik: fisik, alasan: opname.alasan.trim(),
      });
      toast.success(r.data?.message || "Opname tercatat");
      setOpname(null);
      load(page, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal merekam opname"));
    } finally {
      setSaving(false);
    }
  };

  const bukaMassal = () => setMassal({
    arah: "masuk", jenis: "pembelian", no_bukti: "", jenis_dokumen: "",
    penyedia: "", unit_penerima: "", keterangan: "",
    items: [], cari: "", hasil: [], mencari: false, saving: false, laporan: null,
  });
  const setMField = (k, v) => setMassal((m) => ({ ...m, [k]: v }));

  const tambahItemMassal = (it) => setMassal((m) => {
    if (m.items.some((x) => x.id === it.id)) return { ...m, cari: "", hasil: [] };
    return {
      ...m, cari: "", hasil: [],
      items: [...m.items, {
        id: it.id, kode_barang: it.kode_barang, nup: it.nup,
        nama_barang: it.nama_barang, stok: it.stok, satuan: it.satuan,
        jumlah: "", harga_satuan: "", expired: "",
      }],
    };
  });
  const setItemMassal = (id, k, v) => setMassal((m) => ({
    ...m, items: m.items.map((x) => (x.id === id ? { ...x, [k]: v } : x)),
  }));
  const hapusItemMassal = (id) => setMassal((m) => ({
    ...m, items: m.items.filter((x) => x.id !== id),
  }));

  const submitMassal = async () => {
    if (!massal || massal.items.length === 0) { toast.error("Tambahkan minimal satu barang"); return; }
    for (const it of massal.items) {
      const n = parseInt(it.jumlah, 10);
      if (Number.isNaN(n) || n <= 0) { toast.error(`Jumlah tidak valid: ${it.nama_barang}`); return; }
      if (massal.arah === "masuk") {
        const h = parseFloat(it.harga_satuan);
        if (Number.isNaN(h) || h < 0) { toast.error(`Harga tidak valid: ${it.nama_barang}`); return; }
      }
    }
    setMassal((m) => ({ ...m, saving: true }));
    try {
      const r = await axios.post(`${API}/persediaan/transaksi-massal`, {
        arah: massal.arah, jenis: massal.jenis, no_bukti: massal.no_bukti,
        jenis_dokumen: massal.jenis_dokumen, penyedia: massal.penyedia,
        unit_penerima: massal.unit_penerima, keterangan: massal.keterangan,
        items: massal.items.map((it) => ({
          persediaan_id: it.id, jumlah: parseInt(it.jumlah, 10),
          harga_satuan: massal.arah === "masuk" ? parseFloat(it.harga_satuan) : 0,
          expired: it.expired || "",
        })),
      });
      const d = r.data || {};
      if ((d.gagal || 0) > 0) {
        // Jangan tutup dialog: operator harus tahu persis barang mana yang gagal
        toast.warning(`${d.sukses}/${d.total} barang tercatat — ${d.gagal} gagal (lihat rincian)`);
        setMassal((m) => ({ ...m, saving: false, laporan: d }));
      } else {
        toast.success(`Transaksi massal tercatat: ${d.sukses} barang, satu dokumen`);
        setMassal(null);
      }
      load(1, search, status);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memproses transaksi massal"));
      setMassal((m) => (m ? { ...m, saving: false } : m));
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
        {/* ── Banner pengingat opname semesteran ── */}
        {opnameStatus && !opnameStatus.sudah && opnameStatus.pesan && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-xl p-2.5 sm:p-3 flex items-center gap-2" data-testid="persediaan-opname-banner">
            <ClipboardCheck className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <p className="text-xs text-amber-800 dark:text-amber-200 flex-1 min-w-0">{opnameStatus.pesan}</p>
          </div>
        )}

        {/* ── Banner peringatan (kritis/habis/kedaluwarsa) + nota dinas ── */}
        {peringatan && peringatan.total_masalah > 0 && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-xl p-2.5 sm:p-3 flex items-center gap-2 flex-wrap" data-testid="persediaan-peringatan">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <p className="text-xs text-amber-800 dark:text-amber-300 flex-1 min-w-[180px]">
              {[
                peringatan.habis.length > 0 && `${peringatan.habis.length} habis`,
                peringatan.kritis.length > 0 && `${peringatan.kritis.length} kritis`,
                peringatan.kedaluwarsa.length > 0 && `${peringatan.kedaluwarsa.length} kedaluwarsa`,
                peringatan.segera_kedaluwarsa.length > 0 && `${peringatan.segera_kedaluwarsa.length} segera kedaluwarsa (≤${peringatan.horizon_hari} hari)`,
              ].filter(Boolean).join(" · ")}
            </p>
            {(peringatan.habis.length > 0 || peringatan.kritis.length > 0) && (
              <button
                type="button"
                onClick={() => downloadFileWithProgress(`${API}/persediaan/nota-dinas?jenis=kritis`, "Nota_Dinas_Stok_Kritis.pdf", { label: "Nota Dinas Stok Kritis" }).catch(() => {})}
                className="h-8 px-2.5 rounded-lg border border-amber-400 dark:border-amber-600 text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1 hover:bg-amber-100 dark:hover:bg-amber-900/40 min-w-0 min-h-0"
                data-testid="persediaan-nota-kritis"
              >
                <FileDown className="w-3.5 h-3.5" />Nota Dinas Kritis
              </button>
            )}
            {(peringatan.kedaluwarsa.length > 0 || peringatan.segera_kedaluwarsa.length > 0) && (
              <button
                type="button"
                onClick={() => downloadFileWithProgress(`${API}/persediaan/nota-dinas?jenis=kedaluwarsa`, "Nota_Dinas_Kedaluwarsa.pdf", { label: "Nota Dinas Kedaluwarsa" }).catch(() => {})}
                className="h-8 px-2.5 rounded-lg border border-amber-400 dark:border-amber-600 text-[11px] font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1 hover:bg-amber-100 dark:hover:bg-amber-900/40 min-w-0 min-h-0"
                data-testid="persediaan-nota-kedaluwarsa"
              >
                <FileDown className="w-3.5 h-3.5" />Nota Dinas Kedaluwarsa
              </button>
            )}
          </div>
        )}

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
            <Button variant="outline" className="h-10 gap-1.5" onClick={bukaMassal} data-testid="persediaan-massal">
              <Layers className="w-4 h-4" /><span className="hidden sm:inline">Massal</span>
            </Button>
            {/* Menu Dokumen: laporan & berita acara dalam satu tombol */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="h-10 gap-1.5" data-testid="persediaan-menu-dokumen">
                  <FileDown className="w-4 h-4" /><span className="hidden sm:inline">Dokumen</span>
                  <ChevronDown className="w-3.5 h-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-64">
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-laporan-posisi"
                  onClick={() => downloadFileWithProgress(
                    `${API}/persediaan/laporan/posisi-pdf${gudang ? `?gudang=${encodeURIComponent(gudang)}` : ""}`,
                    gudang ? `Laporan_Posisi_Persediaan_${gudang.replace(/[^\w-]/g, "_")}.pdf` : "Laporan_Posisi_Persediaan.pdf",
                    { label: gudang ? `Laporan Posisi Persediaan — ${gudang}` : "Laporan Posisi Persediaan" }).catch(() => {})}>
                  <FileDown className="w-4 h-4 mr-2" />Laporan Posisi (PDF)
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-laporan-mutasi"
                  onClick={() => {
                    const now = new Date();
                    const awal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
                    setMutasi({ dari: awal, sampai: now.toISOString().slice(0, 10) });
                  }}>
                  <FileDown className="w-4 h-4 mr-2" />Laporan Mutasi (pilih periode)
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-kertas-kerja"
                  onClick={() => downloadFileWithProgress(`${API}/persediaan/opname/kertas-kerja-pdf`, "Kertas_Kerja_Opname.pdf", { label: "Kertas Kerja Opname" }).catch(() => {})}>
                  <ClipboardCheck className="w-4 h-4 mr-2" />Kertas Kerja Opname
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-baof"
                  onClick={() => setBaof({ tanggal: new Date().toISOString().slice(0, 10) })}>
                  <ClipboardCheck className="w-4 h-4 mr-2" />BAOF (pilih tanggal)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            {/* Menu Data: impor / template / ekspor master */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="h-10 gap-1.5" data-testid="persediaan-menu-data">
                  <Upload className="w-4 h-4" /><span className="hidden sm:inline">Data</span>
                  <ChevronDown className="w-3.5 h-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuItem className="min-h-[42px]" disabled={importing} data-testid="persediaan-import"
                  onClick={() => fileImporRef.current?.click()}>
                  {importing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}Impor CSV/XLSX
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-template"
                  onClick={() => downloadFileWithProgress(`${API}/persediaan/template`, "template_persediaan.csv", { label: "Template Persediaan" }).catch(() => {})}>
                  <Download className="w-4 h-4 mr-2" />Unduh Template
                </DropdownMenuItem>
                <DropdownMenuItem className="min-h-[42px]" data-testid="persediaan-export"
                  onClick={() => downloadFileWithProgress(`${API}/persediaan/export`, "master_persediaan.csv", { label: "Ekspor Master Persediaan" }).catch(() => {})}>
                  <Download className="w-4 h-4 mr-2" />Ekspor CSV (+stok & nilai)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <input ref={fileImporRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={onImportFile} />
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
            {daftarGudang.length > 0 && (
              <select
                value={gudang}
                onChange={(e) => changeGudang(e.target.value)}
                className="h-8 px-2 rounded-full border border-border bg-background text-xs text-foreground min-w-0 min-h-0"
                aria-label="Filter Lokasi/Gudang"
                data-testid="persediaan-filter-gudang"
              >
                <option value="">Semua gudang</option>
                {daftarGudang.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            )}
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
                          onClick={() => setKeluar({
                            item: it,
                            data: { jenis: "habis_pakai", jumlah: "", unit_penerima: "", no_bukti: "", keterangan: "" },
                          })}
                          disabled={!it.stok}
                          aria-label={`Transaksi keluar ${it.nama_barang}`}
                          title={it.stok ? "Transaksi keluar (FIFO)" : "Stok kosong"}
                          className="p-1.5 rounded-md text-red-600 dark:text-red-400 hover:bg-red-500/10 disabled:opacity-30 min-w-0 min-h-0"
                          data-testid={`persediaan-keluar-${it.kode_barang}-${it.nup}`}
                        >
                          <PackageMinus className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setOpname({ item: it, stok_fisik: String(it.stok), alasan: "" })}
                          aria-label={`Opname ${it.nama_barang}`}
                          title="Rekam hasil opname fisik"
                          className="p-1.5 rounded-md text-violet-600 dark:text-violet-400 hover:bg-violet-500/10 min-w-0 min-h-0"
                          data-testid={`persediaan-opname-${it.kode_barang}-${it.nup}`}
                        >
                          <ClipboardCheck className="w-3.5 h-3.5" />
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

      {/* ── Dialog transaksi keluar ── */}
      <Dialog open={!!keluar} onOpenChange={(o) => { if (!o) setKeluar(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Transaksi Keluar — {keluar?.item?.nama_barang}</DialogTitle>
            <DialogDescription className="text-xs">
              Mengonsumsi layer FIFO tertua dulu; nilai keluar dihitung dari harga
              layer terpakai. Stok tersedia: {keluar?.item?.stok}.
            </DialogDescription>
          </DialogHeader>
          {keluar && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-out-jenis">Jenis</label>
                <select
                  id="psd-out-jenis"
                  value={keluar.data.jenis}
                  onChange={(e) => setKeluar((m) => ({ ...m, data: { ...m.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="persediaan-keluar-jenis"
                >
                  {(jenisKeluar.length ? jenisKeluar : [{ key: "habis_pakai", label: "Habis Pakai/Pemakaian", kode: "K01" }]).map((j) => (
                    <option key={j.key} value={j.key}>{j.label} ({j.kode})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-out-jumlah">Jumlah (maks {keluar.item.stok})</label>
                <Input id="psd-out-jumlah" type="number" min="1" max={keluar.item.stok} placeholder="0"
                  value={keluar.data.jumlah}
                  onChange={(e) => setKeluar((m) => ({ ...m, data: { ...m.data, jumlah: e.target.value } }))}
                  data-testid="persediaan-keluar-jumlah" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-out-unit">Unit Penerima</label>
                <Input id="psd-out-unit" placeholder="cth. Bagian Umum"
                  value={keluar.data.unit_penerima}
                  onChange={(e) => setKeluar((m) => ({ ...m, data: { ...m.data, unit_penerima: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-out-bukti">No. Bukti</label>
                <Input id="psd-out-bukti"
                  value={keluar.data.no_bukti}
                  onChange={(e) => setKeluar((m) => ({ ...m, data: { ...m.data, no_bukti: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-out-ket">Keterangan</label>
                <Input id="psd-out-ket"
                  value={keluar.data.keterangan}
                  onChange={(e) => setKeluar((m) => ({ ...m, data: { ...m.data, keterangan: e.target.value } }))} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setKeluar(null)}>Batal</Button>
            <Button onClick={submitKeluar} disabled={saving} className="bg-red-600 hover:bg-red-700" data-testid="persediaan-keluar-simpan">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <PackageMinus className="w-4 h-4 mr-1.5" />}Catat Keluar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog opname per barang ── */}
      <Dialog open={!!opname} onOpenChange={(o) => { if (!o) setOpname(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Opname Fisik — {opname?.item?.nama_barang}</DialogTitle>
            <DialogDescription className="text-xs">
              Stok buku saat ini: <b>{opname?.item?.stok}</b>. Selisih akan dibukukan
              otomatis (kurang = konsumsi FIFO; lebih = layer penyesuaian) + jurnal opname.
            </DialogDescription>
          </DialogHeader>
          {opname && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-op-fisik">Stok Fisik Hasil Hitung</label>
                <Input id="psd-op-fisik" type="number" min="0"
                  value={opname.stok_fisik}
                  onChange={(e) => setOpname((m) => ({ ...m, stok_fisik: e.target.value }))}
                  data-testid="persediaan-opname-fisik" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-op-alasan">Alasan Selisih (wajib — bahan CaLK)</label>
                <Input id="psd-op-alasan" placeholder="cth. susut pemakaian tidak tercatat"
                  value={opname.alasan}
                  onChange={(e) => setOpname((m) => ({ ...m, alasan: e.target.value }))}
                  data-testid="persediaan-opname-alasan" />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpname(null)}>Batal</Button>
            <Button onClick={submitOpname} disabled={saving} className="bg-violet-600 hover:bg-violet-700" data-testid="persediaan-opname-simpan">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ClipboardCheck className="w-4 h-4 mr-1.5" />}Rekam Opname
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog BAOF ── */}
      <Dialog open={!!baof} onOpenChange={(o) => { if (!o) setBaof(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Berita Acara Opname Fisik (BAOF)</DialogTitle>
            <DialogDescription className="text-xs">
              Berisi seluruh penyesuaian opname pada tanggal terpilih + 3 penandatangan.
            </DialogDescription>
          </DialogHeader>
          {baof && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-baof-tgl">Tanggal Opname</label>
              <Input id="psd-baof-tgl" type="date" value={baof.tanggal}
                onChange={(e) => setBaof((m) => ({ ...m, tanggal: e.target.value }))} />
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setBaof(null)}>Batal</Button>
            <Button
              onClick={() => {
                if (!baof?.tanggal) { toast.error("Pilih tanggal"); return; }
                downloadFileWithProgress(
                  `${API}/persediaan/opname/baof-pdf?tanggal=${baof.tanggal}`,
                  `BAOF_${baof.tanggal}.pdf`,
                  { label: "Berita Acara Opname Fisik" },
                ).catch(() => {});
                setBaof(null);
              }}
              data-testid="persediaan-baof-unduh"
            >
              <FileDown className="w-4 h-4 mr-1.5" />Unduh PDF
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog rentang laporan mutasi ── */}
      <Dialog open={!!mutasi} onOpenChange={(o) => { if (!o) setMutasi(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Laporan Mutasi Persediaan</DialogTitle>
            <DialogDescription className="text-xs">
              Saldo awal → masuk → keluar → saldo akhir per barang, dihitung dari jurnal transaksi.
            </DialogDescription>
          </DialogHeader>
          {mutasi && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-mut-dari">Dari</label>
                <Input id="psd-mut-dari" type="date" value={mutasi.dari}
                  onChange={(e) => setMutasi((m) => ({ ...m, dari: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-mut-sampai">Sampai</label>
                <Input id="psd-mut-sampai" type="date" value={mutasi.sampai}
                  onChange={(e) => setMutasi((m) => ({ ...m, sampai: e.target.value }))} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setMutasi(null)}>Batal</Button>
            <Button
              onClick={() => {
                if (!mutasi?.dari || !mutasi?.sampai) { toast.error("Isi rentang tanggal"); return; }
                downloadFileWithProgress(
                  `${API}/persediaan/laporan/mutasi-pdf?dari=${mutasi.dari}&sampai=${mutasi.sampai}`,
                  `Laporan_Mutasi_Persediaan_${mutasi.dari}_${mutasi.sampai}.pdf`,
                  { label: "Laporan Mutasi Persediaan" },
                ).catch(() => {});
                setMutasi(null);
              }}
              data-testid="persediaan-mutasi-unduh"
            >
              <FileDown className="w-4 h-4 mr-1.5" />Unduh PDF
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
          {(riwayat?.rows?.length || 0) > 0 && (
            <Button variant="outline" size="sm" className="gap-1.5 self-start"
              onClick={() => downloadFileWithProgress(
                `${API}/persediaan/${riwayat.item.id}/kartu-barang-pdf`,
                `Kartu_Barang_${riwayat.item.kode_barang || riwayat.item.id}.pdf`,
                { label: `Kartu Barang ${riwayat.item.nama_barang}` },
              ).catch(() => {})}
              data-testid="persediaan-kartu-barang">
              <FileDown className="w-3.5 h-3.5" />Kartu Barang (PDF)
            </Button>
          )}
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

      {/* ── Dialog transaksi massal per dokumen ── */}
      <Dialog open={!!massal} onOpenChange={(o) => { if (!o) setMassal(null); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Transaksi Massal — Satu Dokumen</DialogTitle>
            <DialogDescription className="text-xs">
              Satu bukti (BAST/kuitansi/nota dinas) untuk banyak barang sekaligus.
              Tiap barang tetap tercatat sebagai transaksi berjurnal FIFO tersendiri.
            </DialogDescription>
          </DialogHeader>
          {massal && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-arah">Arah</label>
                  <select id="psd-m-arah" value={massal.arah}
                    onChange={(e) => setMassal((m) => ({
                      ...m, arah: e.target.value,
                      jenis: e.target.value === "masuk" ? "pembelian" : "habis_pakai",
                    }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="persediaan-massal-arah">
                    <option value="masuk">Masuk</option>
                    <option value="keluar">Keluar</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-jenis">Jenis</label>
                  <select id="psd-m-jenis" value={massal.jenis}
                    onChange={(e) => setMField("jenis", e.target.value)}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="persediaan-massal-jenis">
                    {(massal.arah === "masuk" ? jenisMasuk : jenisKeluar).map((j) => (
                      <option key={j.key} value={j.key}>{j.label} ({j.kode})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-bukti">No. Bukti</label>
                  <Input id="psd-m-bukti" placeholder="cth. BAST-15/VII/2026"
                    value={massal.no_bukti} onChange={(e) => setMField("no_bukti", e.target.value)}
                    data-testid="persediaan-massal-bukti" />
                </div>
                {massal.arah === "masuk" ? (
                  <>
                    <div>
                      <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-jdok">Jenis Dokumen</label>
                      <Input id="psd-m-jdok" placeholder="BAST / Kuitansi / Kontrak"
                        value={massal.jenis_dokumen} onChange={(e) => setMField("jenis_dokumen", e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-penyedia">Penyedia</label>
                      <Input id="psd-m-penyedia" value={massal.penyedia}
                        onChange={(e) => setMField("penyedia", e.target.value)} />
                    </div>
                  </>
                ) : (
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-unit">Unit Penerima</label>
                    <Input id="psd-m-unit" placeholder="cth. Bagian Umum"
                      value={massal.unit_penerima} onChange={(e) => setMField("unit_penerima", e.target.value)} />
                  </div>
                )}
                <div className={massal.arah === "masuk" ? "" : "col-span-1"}>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-ket">Keterangan</label>
                  <Input id="psd-m-ket" value={massal.keterangan}
                    onChange={(e) => setMField("keterangan", e.target.value)} />
                </div>
              </div>

              {/* Pencarian & daftar barang dokumen */}
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psd-m-cari">Tambah barang</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="psd-m-cari" className="pl-8" placeholder="Cari kode/nama barang (min. 2 huruf)"
                    value={massal.cari} onChange={(e) => setMField("cari", e.target.value)}
                    data-testid="persediaan-massal-cari" />
                  {(massal.mencari || massal.hasil.length > 0) && massal.cari.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {massal.mencari ? (
                        <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-emerald-600" /></div>
                      ) : massal.hasil.map((it) => (
                        <button key={it.id} type="button" onClick={() => tambahItemMassal(it)}
                          className="w-full px-2.5 py-1.5 text-left hover:bg-muted"
                          data-testid={`persediaan-massal-pilih-${it.kode_barang}-${it.nup}`}>
                          <span className="block text-xs font-semibold text-foreground truncate">{it.nama_barang}</span>
                          <span className="block text-[10px] text-muted-foreground font-mono">{it.kode_barang} · NUP {it.nup} · stok {it.stok}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {massal.items.length > 0 && (
                <ul className="space-y-1.5">
                  {massal.items.map((it) => {
                    const gagal = massal.laporan?.hasil?.find((h) => h.persediaan_id === it.id && !h.ok);
                    return (
                      <li key={it.id} className={`rounded-lg border p-2 ${gagal ? "border-red-500/60 bg-red-500/5" : "border-border"}`}>
                        <div className="flex items-center gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-foreground truncate">{it.nama_barang}</p>
                            <p className="text-[10px] text-muted-foreground font-mono">{it.kode_barang} · NUP {it.nup} · stok {it.stok} {it.satuan || ""}</p>
                          </div>
                          <Input type="number" min="1" placeholder="Jml" className="w-20 h-8 text-xs"
                            value={it.jumlah} onChange={(e) => setItemMassal(it.id, "jumlah", e.target.value)}
                            data-testid={`persediaan-massal-jumlah-${it.kode_barang}-${it.nup}`} />
                          {massal.arah === "masuk" && (
                            <Input type="number" min="0" placeholder="Harga" className="w-28 h-8 text-xs"
                              value={it.harga_satuan} onChange={(e) => setItemMassal(it.id, "harga_satuan", e.target.value)} />
                          )}
                          <button type="button" onClick={() => hapusItemMassal(it.id)} aria-label="Hapus barang"
                            className="h-8 w-8 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                        {gagal && <p className="mt-1 text-[11px] text-red-500">Gagal: {gagal.error}</p>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setMassal(null)}>Batal</Button>
            <Button onClick={submitMassal} disabled={massal?.saving || (massal?.items?.length || 0) === 0}
              className="bg-emerald-600 hover:bg-emerald-700" data-testid="persediaan-massal-simpan">
              {massal?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Layers className="w-4 h-4 mr-1.5" />}
              Catat {massal?.items?.length || 0} Barang
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
