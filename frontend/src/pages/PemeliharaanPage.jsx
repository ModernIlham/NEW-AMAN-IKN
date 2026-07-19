import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Wrench, Plus, Search, Trash2, X,
  CalendarDays, Coins, Boxes, ClipboardList, Download, FileText,
  CalendarClock, Pencil, ChevronLeft, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import StatKartu from "@/components/ui/StatKartu";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KONDISI_SETELAH = ["", "Baik", "Rusak Ringan", "Rusak Berat"];
// Klasifikasi baku DJKN: ringan (harian) / sedang (berkala) / berat (ahli)
const WARNA_JENIS = {
  ringan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  sedang: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  berat: "bg-red-500/15 text-red-600 dark:text-red-400",
};
const WARNA_JENIS_DEFAULT = "bg-muted text-muted-foreground";

const BADGE_JADWAL = {
  terlambat: "bg-red-500/15 text-red-600 dark:text-red-400",
  segera: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  terjadwal: "bg-muted text-muted-foreground",
};
const LABEL_JADWAL = { terlambat: "Terlambat", segera: "Segera", terjadwal: "Terjadwal" };

const FORM_KOSONG = {
  tanggal: new Date().toISOString().slice(0, 10),
  jenis: "sedang",
  uraian: "",
  biaya: "",
  pelaksana: "",
  no_bukti: "",
  kondisi_setelah: "",
  keterangan: "",
};

/**
 * Pemeliharaan — Fase 3 tahap awal: catatan riwayat + biaya pemeliharaan
 * per aset (bahan Daftar Hasil Pemeliharaan Barang, PP 27/2014 Ps. 46-47),
 * jadwal pemeliharaan berkala, dan unduhan DHPB PDF.
 */
export default function PemeliharaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [rekap, setRekap] = useState(null);
  const [daftar, setDaftar] = useState(null);
  const [loadingDaftar, setLoadingDaftar] = useState(true);
  const [page, setPage] = useState(1);
  const [tahun, setTahun] = useState("");        // "" = semua tahun
  const [jenisFilter, setJenisFilter] = useState("");
  const [asetFilter, setAsetFilter] = useState(null); // {id, nama}
  const [jenisList, setJenisList] = useState([]);
  // Referensi Master Pegawai — saran pelaksana internal (penyedia jasa tetap ketik bebas)
  const [pegawaiList, setPegawaiList] = useState([]);
  // Jadwal berkala: {items, jumlah, terlambat, segera} | null
  const [jadwal, setJadwal] = useState(null);
  // Dialog catat: {data, aset, saving} | null
  const [form, setForm] = useState(null);
  // Dialog jadwal: {id?, data, aset, saving} | null — id terisi saat edit
  const [formJadwal, setFormJadwal] = useState(null);
  // Pemilih aset di dialog
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const fmtRp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
  // Nominal ringkas utk kartu sempit (mis. "Rp1,2 jt"); nilai penuh via title
  const fmtRpCompact = (n) => `Rp${new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 }).format(Number(n || 0))}`;
  const fmtTgl = (iso) => {
    if (!iso) return "-";
    const d = new Date(`${iso}T00:00:00`);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
  };

  const muatRekap = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/pemeliharaan/rekap`, {
        params: tahun ? { tahun } : {},
      });
      setRekap(r.data);
    } catch {
      toast.error("Gagal memuat rekap pemeliharaan");
    }
  }, [tahun]);

  const muatDaftar = useCallback(async () => {
    setLoadingDaftar(true);
    try {
      const params = { page, page_size: 20 };
      if (tahun) params.tahun = tahun;
      if (jenisFilter) params.jenis = jenisFilter;
      if (asetFilter) params.asset_id = asetFilter.id;
      const r = await axios.get(`${API}/pemeliharaan`, { params });
      setDaftar(r.data);
    } catch {
      toast.error("Gagal memuat daftar pemeliharaan");
    } finally {
      setLoadingDaftar(false);
    }
  }, [page, tahun, jenisFilter, asetFilter]);

  const muatJadwal = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/pemeliharaan/jadwal`);
      setJadwal(r.data);
    } catch {
      toast.error("Gagal memuat jadwal berkala");
    }
  }, []);

  useEffect(() => { muatRekap(); }, [muatRekap]);
  useEffect(() => { muatDaftar(); }, [muatDaftar]);
  useEffect(() => { muatJadwal(); }, [muatJadwal]);
  useEffect(() => {
    axios.get(`${API}/pemeliharaan/jenis`)
      .then((r) => setJenisList(r.data?.items || []))
      .catch(() => {});
    axios.get(`${API}/pegawai`)
      .then((r) => setPegawaiList((r.data?.items || []).map((p) => ({
        nama: p.nama || "", jabatan: p.jabatan || "", unit: p.unit_kerja || "",
      })).filter((p) => p.nama)))
      .catch(() => {});
  }, []);

  // Pencarian aset (debounce) — dipakai form catat & form jadwal baru
  useEffect(() => {
    const butuhAset = (form && !form.aset)
      || (formJadwal && !formJadwal.id && !formJadwal.aset);
    if (!butuhAset) return undefined;
    if (cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 10 } });
        setHasilCari(r.data?.items || []);
      } catch {
        setHasilCari([]);
      } finally {
        setMencari(false);
      }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, form, formJadwal]);

  const bukaForm = (aset = null) => {
    setCari("");
    setHasilCari([]);
    setForm({ data: { ...FORM_KOSONG, tanggal: new Date().toISOString().slice(0, 10) }, aset, saving: false });
  };
  const setField = (k, v) => setForm((f) => ({ ...f, data: { ...f.data, [k]: v } }));

  const bukaFormJadwal = (j = null) => {
    setCari("");
    setHasilCari([]);
    setFormJadwal(j ? {
      id: j.id,
      aset: { id: j.asset_id, asset_name: j.asset_name, asset_code: j.asset_code, NUP: j.NUP },
      data: { interval_bulan: j.interval_bulan, mulai: j.mulai, keterangan: j.keterangan || "" },
      saving: false,
    } : {
      id: null, aset: null, saving: false,
      data: { interval_bulan: 6, mulai: new Date().toISOString().slice(0, 10), keterangan: "" },
    });
  };
  const setFieldJadwal = (k, v) => setFormJadwal((f) => ({ ...f, data: { ...f.data, [k]: v } }));

  const simpanJadwal = async () => {
    if (!formJadwal) return;
    if (!formJadwal.id && !formJadwal.aset) { toast.error("Pilih aset terlebih dahulu"); return; }
    setFormJadwal((f) => ({ ...f, saving: true }));
    try {
      if (formJadwal.id) {
        await axios.put(`${API}/pemeliharaan/jadwal/${formJadwal.id}`, formJadwal.data);
      } else {
        await axios.post(`${API}/pemeliharaan/jadwal`, { ...formJadwal.data, asset_id: formJadwal.aset.id });
      }
      toast.success("Jadwal berkala tersimpan");
      setFormJadwal(null);
      muatJadwal();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan jadwal");
      setFormJadwal((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusJadwal = async (j) => {
    const ok = await confirm({
      title: "Hapus jadwal berkala?",
      description: `${j.asset_name || "-"} — tiap ${j.interval_bulan} bulan${j.keterangan ? ` (${j.keterangan})` : ""}.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pemeliharaan/jadwal/${j.id}`);
      toast.success("Jadwal dihapus");
      muatJadwal();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus jadwal");
    }
  };

  const simpan = async () => {
    if (!form?.aset) { toast.error("Pilih aset terlebih dahulu"); return; }
    if (!form.data.uraian.trim()) { toast.error("Uraian pekerjaan wajib diisi"); return; }
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pemeliharaan`, { ...form.data, asset_id: form.aset.id });
      toast.success("Catatan pemeliharaan tersimpan");
      setForm(null);
      setPage(1);
      muatRekap();
      muatDaftar();
      muatJadwal(); // pelaksanaan terbaru menggeser jatuh tempo jadwal
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan catatan");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  // Integrasi Pemeliharaan → Pembukuan: posting pengembangan nilai (jurnal
  // 202) — keputusan kualitatif admin; nilai perolehan aset bertambah.
  const postingKapitalisasi = async (row) => {
    const ok = await confirm({
      title: "Posting pengembangan nilai aset (jurnal 202)?",
      description:
        `${row.uraian} — ${row.asset_name || "-"} (${fmtRp(row.biaya)}). ` +
        "Nilai perolehan aset BERTAMBAH sebesar biaya ini (DBKP/Neraca ikut " +
        "naik) dan jurnal 202 tercatat di Buku Barang. Lakukan hanya bila " +
        "pemeliharaan ini menambah masa manfaat/kapasitas (belanja modal, " +
        "PMK 181). Tidak dapat dibatalkan dari sini.",
      confirmLabel: "Posting 202",
    });
    if (!ok) return;
    try {
      const r = await axios.post(`${API}/pemeliharaan/${row.id}/kapitalisasi`);
      toast.success(`Nilai aset bertambah ${fmtRp(r.data?.nilai_ditambahkan)} (jurnal 202)`);
      muatRekap();
      muatDaftar();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal posting pengembangan nilai");
    }
  };

  const hapus = async (row) => {
    const ok = await confirm({
      title: "Hapus catatan pemeliharaan?",
      description: `${row.uraian} — ${row.asset_name || "-"} (${fmtTgl(row.tanggal)}, ${fmtRp(row.biaya)}). Tindakan ini tidak dapat dibatalkan.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pemeliharaan/${row.id}`);
      toast.success("Catatan dihapus");
      muatRekap();
      muatDaftar();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus catatan");
    }
  };

  const labelJenis = daftar?.label_jenis || rekap?.label_jenis || {};
  const tahunTersedia = Object.keys(rekap?.per_tahun || {}).filter((t) => t !== "0").sort().reverse();
  // DHPB mengikuti filter tahun; tanpa filter = tahun berjalan
  const tahunDhpb = tahun || new Date().getFullYear();

  return (
    <div className="min-h-screen bg-background" data-testid="pemeliharaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pemeliharaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center flex-shrink-0">
            <Wrench className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Pemeliharaan BMN</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Riwayat & biaya per aset — bahan Daftar Hasil Pemeliharaan (PP 27/2014)
            </p>
          </div>
          <Button size="sm" onClick={bukaForm}
            className="h-9 w-9 p-0 bg-orange-600 hover:bg-orange-700 text-white flex-shrink-0"
            title="Catat pemeliharaan" aria-label="Catat pemeliharaan"
            data-testid="pemeliharaan-tambah">
            <Plus className="w-4 h-4" />
          </Button>
          <BookingNomorButton modul="pemeliharaan" jenisNaskah="Laporan" referensi="DHPB" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {/* ── Kartu rekap ── */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          <StatKartu
            icon={ClipboardList}
            value={rekap?.jumlah ?? "…"}
            label={`Kegiatan${tahun ? ` (${tahun})` : ""}`}
            warna="text-orange-500"
            tint="bg-orange-500/10"
            testid="pemeliharaan-stat-kegiatan"
          />
          <StatKartu
            icon={Coins}
            value={rekap ? fmtRpCompact(rekap.total_biaya) : "…"}
            title={rekap ? fmtRp(rekap.total_biaya) : undefined}
            label={`Total biaya${tahun ? ` (${tahun})` : ""}`}
            warna="text-emerald-500"
            tint="bg-emerald-500/10"
            testid="pemeliharaan-stat-biaya"
            className="col-span-2 sm:col-span-1 order-last sm:order-none"
          />
          <StatKartu
            icon={Boxes}
            value={rekap?.jumlah_aset ?? "…"}
            label="Aset terpelihara"
            warna="text-sky-500"
            tint="bg-sky-500/10"
            testid="pemeliharaan-stat-aset"
          />
        </div>

        {/* ── Jadwal berkala (pedoman DKPB Ps. 46(2) PP 27/2014) ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <div className="px-3 py-2 border-b border-border flex flex-wrap items-center gap-2 gap-y-1.5">
            <CalendarClock className="w-4 h-4 text-orange-500" />
            <p className="text-xs font-bold text-foreground">Jadwal Berkala</p>
            {(jadwal?.terlambat || 0) > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${BADGE_JADWAL.terlambat}`}>
                {jadwal.terlambat} terlambat
              </span>
            )}
            {(jadwal?.segera || 0) > 0 && (
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${BADGE_JADWAL.segera}`}>
                {jadwal.segera} segera
              </span>
            )}
            <div className="ml-auto flex gap-1.5">
              {(jadwal?.items || []).length > 0 && (
                <button
                  type="button"
                  onClick={() => downloadFileWithProgress(`${API}/pemeliharaan/jadwal/export`, "jadwal_pemeliharaan.csv", { label: "Ekspor Jadwal Pemeliharaan (CSV)" }).catch(() => {})}
                  className="h-7 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1 hover:bg-muted min-h-0"
                  data-testid="pemeliharaan-jadwal-export"
                >
                  <Download className="w-3.5 h-3.5" />CSV
                </button>
              )}
              <button
                type="button"
                onClick={() => bukaFormJadwal()}
                className="h-7 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1 hover:bg-muted min-h-0"
                data-testid="pemeliharaan-jadwal-tambah"
              >
                <Plus className="w-3.5 h-3.5" />Tambah
              </button>
            </div>
          </div>
          {(jadwal?.items || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4 px-3">
              Belum ada jadwal — tambahkan pemeliharaan berkala (mis. servis AC tiap 6 bulan) agar jatuh tempo terpantau.
            </p>
          ) : (
            <ul className="divide-y divide-border/60">
              {jadwal.items.map((j) => (
                <li key={j.id} className="px-3 py-2 flex items-center gap-2" data-testid={`pemeliharaan-jadwal-${j.id}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      <p className="text-xs font-semibold text-foreground truncate">{j.asset_name || "-"}</p>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${BADGE_JADWAL[j.status] || BADGE_JADWAL.terjadwal}`}>
                        {LABEL_JADWAL[j.status] || j.status} · {fmtTgl(j.jatuh_tempo)}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground truncate">
                      <span className="font-mono">{j.asset_code} · {j.NUP}</span> · tiap {j.interval_bulan} bln
                      {j.keterangan && ` · ${j.keterangan}`}
                      {j.terakhir && ` · terakhir ${fmtTgl(j.terakhir)}`}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => bukaForm({ id: j.asset_id, asset_name: j.asset_name, asset_code: j.asset_code, NUP: j.NUP })}
                    className="h-7 px-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-[11px] font-semibold flex-shrink-0 min-h-0 min-w-0"
                    data-testid={`pemeliharaan-jadwal-catat-${j.id}`}
                  >
                    Catat
                  </button>
                  <button
                    type="button"
                    onClick={() => bukaFormJadwal(j)}
                    aria-label="Ubah jadwal"
                    className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted flex-shrink-0 min-h-0 min-w-0"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  {isAdmin && (
                    <button
                      type="button"
                      onClick={() => hapusJadwal(j)}
                      aria-label="Hapus jadwal"
                      className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ── Aset dengan biaya terbesar ── */}
        {(rekap?.per_aset || []).length > 0 && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <Coins className="w-4 h-4 text-emerald-500" />
              <p className="text-xs font-bold text-foreground">Aset dengan biaya pemeliharaan terbesar</p>
            </div>
            <ul className="divide-y divide-border/60">
              {rekap.per_aset.slice(0, 5).map((a) => (
                <li key={a.asset_id}>
                  <button
                    type="button"
                    onClick={() => { setAsetFilter({ id: a.asset_id, nama: a.asset_name }); setPage(1); }}
                    className="w-full px-3 py-2 flex items-center justify-between gap-2 text-left hover:bg-muted"
                    data-testid={`pemeliharaan-topaset-${a.asset_id}`}
                  >
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</span>
                      <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP} · {a.jumlah}× · terakhir {fmtTgl(a.terakhir)}</span>
                    </span>
                    <span className="text-xs font-bold text-foreground flex-shrink-0">{fmtRp(a.total_biaya)}</span>
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ── Filter ── */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={tahun}
            onChange={(e) => { setTahun(e.target.value); setPage(1); }}
            className="h-8 px-2 rounded-lg border border-border bg-background text-xs text-foreground"
            data-testid="pemeliharaan-filter-tahun"
          >
            <option value="">Semua tahun</option>
            {tahunTersedia.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select
            value={jenisFilter}
            onChange={(e) => { setJenisFilter(e.target.value); setPage(1); }}
            className="h-8 px-2 rounded-lg border border-border bg-background text-xs text-foreground"
            data-testid="pemeliharaan-filter-jenis"
          >
            <option value="">Semua jenis</option>
            {Object.entries(labelJenis).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs" title="Daftar Hasil Pemeliharaan Barang" data-testid="pemeliharaan-dhpb">
                <FileText className="w-3.5 h-3.5 mr-1.5" />DHPB (PDF)
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
              <p className="px-2 py-1 text-[10px] text-muted-foreground">DHPB — Daftar Hasil Pemeliharaan Barang</p>
              {[
                { label: `Tahun penuh ${tahunDhpb}`, q: "" },
                { label: `Semester I ${tahunDhpb} (Jan–Jun)`, q: "&semester=1" },
                { label: `Semester II ${tahunDhpb} (Jul–Des)`, q: "&semester=2" },
              ].map((o) => (
                <DropdownMenuItem
                  key={o.label}
                  className="min-h-[42px]"
                  onClick={() =>
                    downloadFileWithProgress(
                      `${API}/pemeliharaan/dhpb-pdf?tahun=${tahunDhpb}${o.q}`,
                      `DHPB_${tahunDhpb}${o.q ? `_S${o.q.slice(-1)}` : ""}.pdf`,
                      { label: `DHPB ${o.label}` },
                    ).catch(() => {})}
                >
                  {o.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <Button variant="outline" size="sm" className="h-8 text-xs" title="Ekspor Riwayat Pemeliharaan (CSV)"
            onClick={() => downloadFileWithProgress(`${API}/pemeliharaan/export`, "riwayat_pemeliharaan.csv", { label: "Ekspor Riwayat Pemeliharaan (CSV)" }).catch(() => {})}
            data-testid="pemeliharaan-export">
            <Download className="w-3.5 h-3.5 mr-1.5" />CSV
          </Button>
          {asetFilter && (
            <button
              type="button"
              onClick={() => { setAsetFilter(null); setPage(1); }}
              className="h-8 px-2.5 rounded-lg bg-orange-500/15 text-orange-600 dark:text-orange-400 text-xs font-semibold flex items-center gap-1.5 hover:bg-orange-500/25"
              data-testid="pemeliharaan-filter-aset"
            >
              <span className="max-w-[180px] truncate">{asetFilter.nama || "Aset terpilih"}</span>
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* ── Daftar catatan ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-orange-500" />
            <p className="text-xs font-bold text-foreground flex-1">Riwayat Pemeliharaan</p>
            <span className="px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-600 dark:text-orange-400 text-[10px] font-semibold">
              {daftar?.total ?? 0} catatan
            </span>
          </div>
          {loadingDaftar ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-orange-600" />
            </div>
          ) : (daftar?.items || []).length === 0 ? (
            <div className="text-center py-10 px-4">
              <Wrench className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">Belum ada catatan pemeliharaan{tahun || jenisFilter || asetFilter ? " untuk filter ini" : ""}.</p>
              <p className="text-[11px] text-muted-foreground mt-1">Gunakan tombol Catat untuk merekam servis/perbaikan aset.</p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {daftar.items.map((r) => (
                <li key={r.id} className="p-3" data-testid={`pemeliharaan-row-${r.id}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                          <CalendarDays className="w-3 h-3" />{fmtTgl(r.tanggal)}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_JENIS[r.jenis] || WARNA_JENIS_DEFAULT}`}>
                          {labelJenis[r.jenis] || r.jenis}
                        </span>
                        {r.kondisi_setelah && (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">
                            Kondisi → {r.kondisi_setelah}
                          </span>
                        )}
                        {r.indikasi_kapitalisasi && !r.kapitalisasi_diposting && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-400 text-[10px] font-semibold"
                            title="Biaya ≥ ambang kapitalisasi PMK 181/2016 — telaah apakah menambah masa manfaat/kapasitas (belanja modal, bukan 523)"
                          >
                            Telaah kapitalisasi
                          </span>
                        )}
                        {r.kapitalisasi_diposting && (
                          <span
                            className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold"
                            title={`Sudah diposting sebagai pengembangan nilai (jurnal 202) oleh ${r.kapitalisasi_oleh || "-"}`}
                          >
                            Nilai dikapitalisasi ✓
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-semibold text-foreground mt-1">{r.uraian}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {r.asset_name || "-"} <span className="font-mono">({r.asset_code} · {r.NUP})</span>
                        {r.pelaksana && ` · ${r.pelaksana}`}
                        {r.no_bukti && ` · Bukti: ${r.no_bukti}`}
                      </p>
                      {r.keterangan && <p className="text-[11px] text-muted-foreground/80 mt-0.5">{r.keterangan}</p>}
                    </div>
                    <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                      <span className="text-sm font-bold text-foreground">{fmtRp(r.biaya)}</span>
                      {isAdmin && r.indikasi_kapitalisasi && !r.kapitalisasi_diposting && (
                        <button
                          type="button"
                          onClick={() => postingKapitalisasi(r)}
                          title="Posting pengembangan nilai aset (jurnal 202) — nilai perolehan bertambah"
                          className="h-7 px-2 rounded-lg border border-fuchsia-500/40 text-fuchsia-600 dark:text-fuchsia-400 text-[10px] font-semibold flex items-center gap-1 hover:bg-fuchsia-500/10 min-h-0 min-w-0 whitespace-nowrap"
                          data-testid={`pemeliharaan-kapitalisasi-${r.id}`}
                        >
                          Posting 202
                        </button>
                      )}
                      {isAdmin && (
                        <button
                          type="button"
                          onClick={() => hapus(r)}
                          aria-label="Hapus catatan"
                          className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0"
                          data-testid={`pemeliharaan-hapus-${r.id}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ── Navigasi halaman ── */}
        {(daftar?.total_pages || 1) > 1 && (
          <div className="flex items-center justify-center gap-2 pb-4">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="gap-1">
              <ChevronLeft className="w-4 h-4" />Sebelumnya
            </Button>
            <span className="text-xs text-muted-foreground">Hal. {page} / {daftar.total_pages}</span>
            <Button variant="outline" size="sm" disabled={page >= daftar.total_pages} onClick={() => setPage((p) => p + 1)} className="gap-1">
              Berikutnya<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </main>

      {/* ── Dialog catat pemeliharaan ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Pemeliharaan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu catatan per kejadian servis/perbaikan — menjadi riwayat aset dan bahan rekap biaya per tahun anggaran.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-aset">Aset</label>
                {form.aset ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-border p-2">
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-foreground truncate">{form.aset.asset_name}</span>
                      <span className="block text-[10px] text-muted-foreground font-mono">{form.aset.asset_code} · {form.aset.NUP}</span>
                    </span>
                    <button type="button" onClick={() => setForm((f) => ({ ...f, aset: null }))} aria-label="Ganti aset"
                      className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted flex-shrink-0 min-h-0 min-w-0">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <Input id="pml-aset" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pemeliharaan-cari-aset" />
                    {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                      <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                        {mencari ? (
                          <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-orange-600" /></div>
                        ) : hasilCari.map((a) => (
                          <button key={a.id} type="button"
                            onClick={() => { setForm((f) => ({ ...f, aset: a })); setCari(""); setHasilCari([]); }}
                            className="w-full px-2.5 py-1.5 text-left hover:bg-muted"
                            data-testid={`pemeliharaan-pilih-aset-${a.id}`}>
                            <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                            <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-tanggal">Tanggal</label>
                <Input id="pml-tanggal" type="date" max={new Date().toISOString().slice(0, 10)}
                  value={form.data.tanggal} onChange={(e) => setField("tanggal", e.target.value)}
                  data-testid="pemeliharaan-tanggal" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-jenis">Jenis</label>
                <select id="pml-jenis" value={form.data.jenis} onChange={(e) => setField("jenis", e.target.value)}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pemeliharaan-jenis">
                  {(jenisList.length ? jenisList : [{ key: "sedang", label: "Pemeliharaan sedang (berkala)" }]).map((j) => (
                    <option key={j.key} value={j.key}>{j.label}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-uraian">Uraian pekerjaan</label>
                <Input id="pml-uraian" placeholder="cth. Servis rutin + ganti filter AC"
                  value={form.data.uraian} onChange={(e) => setField("uraian", e.target.value)}
                  data-testid="pemeliharaan-uraian" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-biaya">Biaya (Rp)</label>
                <Input id="pml-biaya" type="number" min="0" placeholder="0"
                  value={form.data.biaya} onChange={(e) => setField("biaya", e.target.value)}
                  data-testid="pemeliharaan-biaya" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-pelaksana">Pelaksana</label>
                <Input id="pml-pelaksana" placeholder="petugas / penyedia jasa" list="pml-pegawai-list"
                  value={form.data.pelaksana} onChange={(e) => setField("pelaksana", e.target.value)} />
                <datalist id="pml-pegawai-list">
                  {pegawaiList.map((p, i) => (
                    <option key={`${p.nama}-${i}`} value={p.nama}>
                      {[p.jabatan, p.unit].filter(Boolean).join(" · ")}
                    </option>
                  ))}
                </datalist>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-bukti">No. Bukti</label>
                <Input id="pml-bukti" placeholder="SPM / kuitansi / BAST"
                  value={form.data.no_bukti} onChange={(e) => setField("no_bukti", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-kondisi">Kondisi setelah</label>
                <select id="pml-kondisi" value={form.data.kondisi_setelah}
                  onChange={(e) => setField("kondisi_setelah", e.target.value)}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pemeliharaan-kondisi">
                  {KONDISI_SETELAH.map((k) => (
                    <option key={k || "tetap"} value={k}>{k || "Tidak berubah"}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pml-ket">Keterangan</label>
                <Input id="pml-ket" value={form.data.keterangan}
                  onChange={(e) => setField("keterangan", e.target.value)} />
              </div>
              {form.data.kondisi_setelah && (
                <p className="col-span-2 text-[11px] text-muted-foreground -mt-1">
                  Kondisi aset pada modul Inventarisasi akan diperbarui menjadi “{form.data.kondisi_setelah}”.
                </p>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpan} disabled={form?.saving} className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="pemeliharaan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Wrench className="w-4 h-4 mr-1.5" />}Simpan Catatan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog jadwal berkala ── */}
      <Dialog open={!!formJadwal} onOpenChange={(o) => { if (!o) setFormJadwal(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{formJadwal?.id ? "Ubah Jadwal Berkala" : "Tambah Jadwal Berkala"}</DialogTitle>
            <DialogDescription className="text-xs">
              Jatuh tempo berikutnya dihitung dari pelaksanaan terakhir + interval;
              mencatat pemeliharaan aset ini otomatis menggeser jadwalnya.
            </DialogDescription>
          </DialogHeader>
          {formJadwal && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmlj-aset">Aset</label>
                {formJadwal.aset ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-border p-2">
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-foreground truncate">{formJadwal.aset.asset_name}</span>
                      <span className="block text-[10px] text-muted-foreground font-mono">{formJadwal.aset.asset_code} · {formJadwal.aset.NUP}</span>
                    </span>
                    {!formJadwal.id && (
                      <button type="button" onClick={() => setFormJadwal((f) => ({ ...f, aset: null }))} aria-label="Ganti aset"
                        className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted flex-shrink-0 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <Input id="pmlj-aset" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pemeliharaan-jadwal-cari" />
                    {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                      <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                        {mencari ? (
                          <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-orange-600" /></div>
                        ) : hasilCari.map((a) => (
                          <button key={a.id} type="button"
                            onClick={() => { setFormJadwal((f) => ({ ...f, aset: a })); setCari(""); setHasilCari([]); }}
                            className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                            <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                            <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmlj-interval">Interval (bulan)</label>
                <Input id="pmlj-interval" type="number" min="1" max="60"
                  value={formJadwal.data.interval_bulan}
                  onChange={(e) => setFieldJadwal("interval_bulan", e.target.value)}
                  data-testid="pemeliharaan-jadwal-interval" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmlj-mulai">Jatuh tempo pertama</label>
                <Input id="pmlj-mulai" type="date"
                  value={formJadwal.data.mulai}
                  onChange={(e) => setFieldJadwal("mulai", e.target.value)} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmlj-ket">Keterangan</label>
                <Input id="pmlj-ket" placeholder="cth. servis rutin AC / ganti oli genset"
                  value={formJadwal.data.keterangan}
                  onChange={(e) => setFieldJadwal("keterangan", e.target.value)} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormJadwal(null)}>Batal</Button>
            <Button onClick={simpanJadwal} disabled={formJadwal?.saving} className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="pemeliharaan-jadwal-simpan">
              {formJadwal?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <CalendarClock className="w-4 h-4 mr-1.5" />}Simpan Jadwal
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
