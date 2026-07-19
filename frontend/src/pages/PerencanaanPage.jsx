import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, ArrowRight, Loader2, ClipboardList, CheckCircle2, XCircle, Coins, FileDown,
  Plus, Scale, Search, Send, Trash2,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useTransitionDialog } from "@/components/ui/TransitionDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_KONDISI = {
  "Baik": "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  "Rusak Ringan": "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  "Rusak Berat": "bg-red-500/15 text-red-600 dark:text-red-400",
};

const WARNA_STATUS_USULAN = {
  draft: "bg-muted text-foreground/70",
  diajukan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  dikembalikan: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  disetujui_pb: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  dikirim_pengelola: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  disetujui_telaah: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak_telaah: "bg-red-500/15 text-red-600 dark:text-red-400",
};

// Transisi "mundur"/negatif — tampil outline merah, bukan solid biru
const TRANSISI_MUNDUR = ["dikembalikan", "ditolak_telaah"];

/**
 * Perencanaan — Kandidat usulan RKBMN pemeliharaan (PMK 153/2021):
 * menyaring aset layak (Baik/RR, dioperasikan) vs tidak (rusak berat/idle/
 * nonaktif) + riwayat biaya pemeliharaan per aset, register usulan RKBMN
 * berstatus, dan sanding SBSK (PMK 138/2022) yang telah tersedia.
 */
export default function PerencanaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tahun, setTahun] = useState(new Date().getFullYear());
  // Tanggalan header: tanggal acuan ringkas — TA riwayat biaya mengikuti
  // tahun dari tanggal yang dipilih (menggantikan select TA polos).
  const [tanggalAcuan, setTanggalAcuan] = useState(
    () => new Date().toISOString().slice(0, 10));
  const tanggalanRef = useRef(null);
  const pilihTanggalAcuan = (v) => {
    if (!v) return;
    setTanggalAcuan(v);
    const thBaru = parseInt(v.slice(0, 4), 10);
    if (!Number.isNaN(thBaru)) setTahun(thBaru);
  };
  // Register usulan RKBMN: data GET + dialog usulan baru {data, aset, saving}
  const [usulan, setUsulan] = useState(null);
  const [formUsulan, setFormUsulan] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const refTidak = useRef(null); // jalan pintas dari kartu ringkasan "Tidak layak"
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  const { minta, transitionDialog } = useTransitionDialog();

  const muatUsulan = useCallback(() => {
    axios.get(`${API}/perencanaan/usulan`)
      .then((r) => setUsulan(r.data))
      .catch(() => {});
  }, []);

  // Referensi Master Satker — saran unit/KPB pengusul
  const [satkerList, setSatkerList] = useState([]);
  useEffect(() => {
    axios.get(`${API}/satker`)
      .then((r) => setSatkerList(r.data?.items || []))
      .catch(() => {});
  }, []);

  // ── SBSK (PMK 138/2024) + sanding usulan vs aset eksisting ──
  const [sbsk, setSbsk] = useState(null);
  const [formSbsk, setFormSbsk] = useState(null);
  const [sanding, setSanding] = useState(null);   // {usulan, hasil|null}
  const muatSbsk = useCallback(() => {
    axios.get(`${API}/perencanaan/sbsk`)
      .then((r) => setSbsk(r.data))
      .catch(() => setSbsk({ items: [] }));
  }, []);
  useEffect(() => { muatSbsk(); }, [muatSbsk]);

  const simpanSbsk = async () => {
    if (!formSbsk?.peruntukan?.trim()) { toast.error("Peruntukan wajib diisi"); return; }
    try {
      await axios.post(`${API}/perencanaan/sbsk`, {
        ...formSbsk, standar: Number(formSbsk.standar) || 0 });
      toast.success("Baris standar SBSK tersimpan");
      setFormSbsk(null);
      muatSbsk();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menyimpan standar"); }
  };

  const hapusSbsk = async (s) => {
    const ok = await confirm({
      title: `Hapus standar "${s.peruntukan}"?`, description: s.keterangan || "",
      confirmLabel: "Hapus", variant: "danger" });
    if (!ok) return;
    try {
      await axios.delete(`${API}/perencanaan/sbsk/${s.id}`);
      muatSbsk();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
  };

  const bukaSanding = async (u) => {
    setSanding({ usulan: u, hasil: null });
    try {
      const r = await axios.get(`${API}/perencanaan/usulan/${u.id}/sanding`);
      setSanding({ usulan: u, hasil: r.data });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memuat sanding");
      setSanding(null);
    }
  };

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/perencanaan/rkbmn-pemeliharaan`, { params: { tahun } })
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat kandidat RKBMN"))
      .finally(() => setLoading(false));
  }, [tahun]);

  useEffect(() => { muatUsulan(); }, [muatUsulan]);

  useEffect(() => {
    if (!formUsulan || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, formUsulan]);

  const simpanUsulan = async () => {
    if (!formUsulan) return;
    setFormUsulan((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/perencanaan/usulan`, {
        ...formUsulan.data,
        volume: Number(formUsulan.data.volume || 0),
        asset_id: formUsulan.aset?.id || "",
      });
      toast.success("Usulan RKBMN dicatat (draft)");
      setFormUsulan(null);
      muatUsulan();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat usulan");
      setFormUsulan((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const pindahStatusUsulan = async (u, ke) => {
    const label = usulan?.label_status?.[ke] || ke;
    const wajib = ke === "dikembalikan";
    const v = await minta({
      judul: `Status usulan → ${label}`,
      fields: [{ key: "catatan", label: wajib ? "Catatan perbaikan" : "Catatan", type: "textarea", wajib }],
      confirmLabel: label,
    });
    if (v === null) return;
    const catatan = v.catatan || "";
    try {
      await axios.post(`${API}/perencanaan/usulan/${u.id}/status`, { status: ke, catatan });
      toast.success(`Status usulan: ${label}`);
      muatUsulan();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status usulan");
    }
  };

  const hapusUsulan = async (u) => {
    const ok = await confirm({
      title: "Hapus usulan RKBMN?",
      description: `${u.uraian} — TA ${u.tahun_rkbmn} (${u.unit_pengusul}).`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/perencanaan/usulan/${u.id}`);
      toast.success("Usulan dihapus");
      muatUsulan();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus usulan");
    }
  };

  const fmtRp = (n) => `Rp${Number(n || 0).toLocaleString("id-ID")}`;
  const th = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-background" data-testid="perencanaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="perencanaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <ClipboardList className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Perencanaan — Kandidat RKBMN Pemeliharaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Saringan kelayakan usulan (PMK 153/2021) + riwayat biaya per aset
            </p>
          </div>
          {/* Tanggalan ringkas: persegi seukuran tombol — strip bulan, angka
              tanggal, tahun; klik membuka pemilih tanggal. TA riwayat biaya
              mengikuti tahun tanggal terpilih. */}
          <button
            type="button"
            onClick={() => {
              const el = tanggalanRef.current;
              if (!el) return;
              if (typeof el.showPicker === "function") el.showPicker();
              else el.click();
            }}
            className="h-9 w-10 rounded-lg border border-border bg-background flex flex-col items-stretch overflow-hidden flex-shrink-0 hover:border-blue-500 min-w-0 min-h-0"
            title={`Tanggal acuan ${tanggalAcuan} — TA ${tahun}. Klik untuk mengganti.`}
            aria-label="Pilih tanggal acuan tahun anggaran"
            data-testid="perencanaan-tanggalan"
          >
            <span className="bg-blue-600 text-white text-[7px] font-bold uppercase tracking-wide leading-none py-[2px] text-center">
              {new Date(`${tanggalAcuan}T00:00:00`).toLocaleDateString("id-ID", { month: "short" })}
            </span>
            <span className="text-[13px] font-bold text-foreground leading-none pt-[2px] text-center">
              {tanggalAcuan.slice(8, 10)}
            </span>
            <span className="text-[7px] text-muted-foreground leading-none pb-[2px] text-center">
              {tanggalAcuan.slice(0, 4)}
            </span>
          </button>
          <input
            ref={tanggalanRef} type="date" value={tanggalAcuan}
            onChange={(e) => pilihTanggalAcuan(e.target.value)}
            className="sr-only" tabIndex={-1} aria-hidden="true"
            data-testid="perencanaan-tanggalan-input"
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="h-8 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1.5 hover:bg-muted flex-shrink-0 min-h-0"
                title="Unduhan perencanaan"
                aria-label="Unduhan perencanaan"
                data-testid="perencanaan-unduh-menu"
              >
                <FileDown className="w-3.5 h-3.5" /><span className="hidden sm:inline">Unduh</span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuItem className="min-h-[42px]" data-testid="perencanaan-xlsx"
                onClick={() => downloadFileWithProgress(
                  `${API}/perencanaan/rkbmn-pemeliharaan-xlsx?tahun=${tahun}`,
                  `Usulan_RKBMN_Pemeliharaan_TA${tahun + 1}.xlsx`,
                  { label: "Kertas kerja usulan RKBMN" },
                ).catch(() => {})}>
                <div>
                  <p className="text-xs font-semibold">Kertas Kerja RKBMN (XLSX)</p>
                  <p className="text-[10px] text-muted-foreground">Usulan pemeliharaan TA {tahun + 1}</p>
                </div>
              </DropdownMenuItem>
              <DropdownMenuItem className="min-h-[42px]" data-testid="perencanaan-export"
                onClick={() => downloadFileWithProgress(
                  `${API}/perencanaan/usulan/export`, "register_usulan_rkbmn.csv",
                  { label: "Register usulan RKBMN (CSV)" },
                ).catch(() => {})}>
                <div>
                  <p className="text-xs font-semibold">Register Usulan (CSV)</p>
                  <p className="text-[10px] text-muted-foreground">Seluruh usulan RKBMN tercatat</p>
                </div>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <BookingNomorButton modul="perencanaan" jenisNaskah="Laporan" referensi="RKBMN" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-blue-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="perencanaan-stat-layak">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.layak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Layak diusulkan</p>
              </div>
              <button
                type="button"
                onClick={() => refTidak.current?.scrollIntoView({ behavior: "smooth" })}
                title="Gulir ke daftar tidak layak beserta alasannya"
                className="bg-card rounded-xl border border-red-500/40 p-3 text-center hover:bg-red-500/5"
                data-testid="perencanaan-stat-tidak"
              >
                <XCircle className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.tidak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Tidak layak (lihat alasan)</p>
              </button>
              <div className="bg-card rounded-xl border border-border p-3 text-center col-span-2 sm:col-span-1" data-testid="perencanaan-stat-biaya">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none truncate whitespace-nowrap tabular-nums" title={fmtRp(data.ringkasan.total_biaya_riwayat)}>{fmtRp(data.ringkasan.total_biaya_riwayat)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Biaya pemeliharaan TA {data.tahun} (aset layak)</p>
              </div>
            </div>

            {/* ── Register usulan RKBMN per unit (PMK 153/2021 + KMK 128/2022) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="perencanaan-usulan">
              <div className="px-3 py-2.5 border-b border-border flex flex-wrap items-center gap-2 gap-y-1.5">
                <Send className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Usulan RKBMN per Unit</p>
                  <p className="text-[10px] text-muted-foreground truncate" title="PB = Pengguna Barang; Pengelola = Pengelola Barang (DJKN/Kementerian Keuangan)">
                    Draft → diajukan → disetujui PB → dikirim Pengelola → hasil penelaahan
                  </p>
                </div>
                {(usulan?.ringkasan?.berjalan || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold flex-shrink-0">
                    {usulan.ringkasan.berjalan} berjalan
                  </span>
                )}
                <Button size="sm" className="h-7 text-[11px] min-h-0 flex-shrink-0 bg-blue-600 hover:bg-blue-700 text-white"
                  onClick={() => { setCari(""); setHasilCari([]); setFormUsulan({ data: { tahun_rkbmn: String(th + 2), jenis: "pemeliharaan", unit_pengusul: "", uraian: "", volume: "1", satuan: "unit", keterangan: "" }, aset: null, saving: false }); }}
                  title="Buat usulan RKBMN baru" aria-label="Buat usulan RKBMN baru"
                  data-testid="perencanaan-usulan-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Buat Usulan</span>
                </Button>
              </div>
              {(usulan?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada usulan — buat dari kandidat layak di bawah (usulan resmi tetap via SIMAN V2).
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {usulan.items.map((u) => (
                    <li key={u.id} className="p-3" data-testid={`perencanaan-usulan-${u.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS_USULAN[u.status] || "bg-muted"}`}>
                          {usulan.label_status?.[u.status] || u.status}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-600 dark:text-blue-400 text-[10px] font-semibold">
                          {usulan.label_jenis?.[u.jenis] || u.jenis}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                          RKBMN TA {u.tahun_rkbmn}
                        </span>
                        {u.sptjm && (
                          <span title="Surat Pernyataan Tanggung Jawab Mutlak" className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">SPTJM</span>
                        )}
                        {u.reviu_apip && (
                          <span title="Sudah direviu Aparat Pengawasan Intern Pemerintah" className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">Reviu APIP</span>
                        )}
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{u.uraian}</p>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[u.unit_pengusul, `${u.volume} ${u.satuan}`,
                          u.asset_name && `aset: ${u.asset_name} (${u.asset_code} · ${u.NUP})`,
                          u.keterangan, `oleh ${u.created_by}`].filter(Boolean).join(" · ")}
                      </p>
                      <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                        {(usulan.transisi?.[u.status] || []).map((ke, idx, daftarKe) => {
                          const majuPertama = idx === daftarKe.findIndex((k) => !TRANSISI_MUNDUR.includes(k));
                          return (
                            <Button key={ke} size="sm" variant={majuPertama ? "default" : "outline"}
                              className={`h-7 text-[11px] min-h-0 ${majuPertama
                                ? "bg-blue-600 hover:bg-blue-700 text-white"
                                : TRANSISI_MUNDUR.includes(ke)
                                  ? "border-red-500/40 text-red-600 dark:text-red-400 hover:bg-red-500/10"
                                  : ""}`}
                              onClick={() => pindahStatusUsulan(u, ke)}
                              data-testid={`perencanaan-usulan-${u.id}-ke-${ke}`}>
                              <ArrowRight className="w-3 h-3 mr-1" />{usulan.label_status?.[ke] || ke}
                            </Button>
                          );
                        })}
                        <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                          onClick={() => bukaSanding(u)}
                          title="Sanding usulan vs aset eksisting + standar SBSK (PMK 138/2024)"
                          data-testid={`perencanaan-usulan-${u.id}-sanding`}>
                          <Scale className="w-3.5 h-3.5 mr-1" />Sanding
                        </Button>
                        {isAdmin && (
                          <button type="button" onClick={() => hapusUsulan(u)} aria-label="Hapus usulan"
                            className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── Tabel standar SBSK (PMK 138/2024) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="perencanaan-sbsk">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
                <Scale className="w-4 h-4 text-violet-500" />
                <div className="flex-1 min-w-[160px]">
                  <p className="text-xs font-bold text-foreground">Standar Barang &amp; Standar Kebutuhan — SBSK (PMK 138/2024)</p>
                  <p className="text-[10px] text-muted-foreground">
                    Batas tertinggi perencanaan kebutuhan; angka dirawat admin dari Lampiran PMK. Dipakai tombol &quot;Sanding&quot; per usulan.
                  </p>
                </div>
                {isAdmin && (
                  <Button size="sm" className="h-7 text-[11px] min-h-0 bg-blue-600 hover:bg-blue-700 text-white"
                    onClick={() => setFormSbsk({ kategori: "barang", peruntukan: "", satuan: "unit", standar: "1", keterangan: "" })}
                    data-testid="sbsk-tambah">
                    <Plus className="w-3.5 h-3.5 mr-1" />Tambah Standar
                  </Button>
                )}
              </div>
              {!sbsk ? (
                <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
              ) : (sbsk.items || []).length === 0 ? (
                <div className="text-center py-4 px-3">
                  <p className="text-[11px] text-muted-foreground">
                    Belum ada baris standar — angka batas tertinggi diambil admin dari Lampiran PMK 138/2024 lewat tombol &quot;Tambah Standar&quot;.
                  </p>
                  {isAdmin && (
                    <Button size="sm" className="mt-3 bg-blue-600 hover:bg-blue-700 text-white"
                      onClick={() => setFormSbsk({ kategori: "barang", peruntukan: "", satuan: "unit", standar: "1", keterangan: "" })}
                      data-testid="sbsk-tambah-kosong">
                      <Plus className="w-3.5 h-3.5 mr-1" />Tambah Standar
                    </Button>
                  )}
                </div>
              ) : (
                <div className="divide-y divide-border/60">
                  {(sbsk.items || []).map((s) => (
                    <div key={s.id} className="px-3 py-1.5 flex items-center gap-2.5">
                      <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[9px] font-bold uppercase flex-shrink-0">
                        {s.kategori}
                      </span>
                      <p className="text-[12px] flex-1 min-w-0 truncate">
                        <b>{s.peruntukan}</b> — {s.standar} {s.satuan}
                        <span className="text-muted-foreground"> · {s.keterangan}</span>
                      </p>
                      {isAdmin && (
                        <button type="button" onClick={() => hapusSbsk(s)} aria-label={`Hapus standar ${s.peruntukan}`}
                          className="h-6 w-6 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Daftar layak ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                <p className="text-xs font-bold text-foreground">Layak Diusulkan — biaya riwayat terbesar dulu</p>
              </div>
              {data.layak.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">Tidak ada aset layak — lengkapi kondisi aset di modul Inventarisasi.</p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.layak.slice(0, 100).map((a) => (
                    <li key={a.id} className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 gap-y-1.5" data-testid={`perencanaan-layak-${a.id}`}>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-muted-foreground font-mono truncate">
                          {a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_KONDISI[a.condition] || "bg-muted text-muted-foreground"}`}>
                          {a.condition || "-"}
                        </span>
                        <span className="text-xs font-bold text-foreground whitespace-nowrap">
                          {a.riwayat_jumlah > 0 ? `${a.riwayat_jumlah}× · ${fmtRp(a.riwayat_biaya)}` : "belum ada riwayat"}
                        </span>
                      </div>
                    </li>
                  ))}
                  {data.layak.length > 100 && (
                    <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 100 pertama dari {data.ringkasan.layak}.</li>
                  )}
                </ul>
              )}
            </div>

            {/* ── Daftar tidak layak ── */}
            <div ref={refTidak} className="bg-card rounded-xl border border-border shadow-sm overflow-hidden scroll-mt-16">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-500" />
                <p className="text-xs font-bold text-foreground">Tidak Layak — beserta jalur yang benar</p>
              </div>
              {data.tidak.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">Semua aset layak diusulkan.</p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.tidak.slice(0, 100).map((a) => (
                    <li key={a.id} className="px-3 py-2" data-testid={`perencanaan-tidak-${a.id}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{a.asset_code} · {a.NUP}</span>
                      </div>
                      <p className="text-[11px] text-red-500/90 mt-0.5">{a.alasan}</p>
                    </li>
                  ))}
                  {data.tidak.length > 100 && (
                    <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 100 pertama dari {data.ringkasan.tidak}.</li>
                  )}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog buat usulan RKBMN ── */}
      <Dialog open={!!formUsulan} onOpenChange={(o) => { if (!o) setFormUsulan(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Buat Usulan RKBMN</DialogTitle>
            <DialogDescription className="text-xs">
              Register pendamping (PMK 153/2021 + KMK 128/KM.6/2022) — usulan resmi via SIMAN V2.
            </DialogDescription>
          </DialogHeader>
          {formUsulan && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-tahun">RKBMN untuk TA</label>
                  <Input id="usl-tahun" inputMode="numeric" maxLength={4} value={formUsulan.data.tahun_rkbmn}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, tahun_rkbmn: e.target.value.replace(/\D/g, "") } }))}
                    data-testid="usulan-tahun" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-jenis">Jenis usulan</label>
                  <select id="usl-jenis" value={formUsulan.data.jenis}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="usulan-jenis">
                    {Object.entries(usulan?.label_jenis || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-unit">Unit/KPB pengusul</label>
                  <Input id="usl-unit" placeholder="ketik bebas atau pilih dari Master Satker" value={formUsulan.data.unit_pengusul}
                    list="usulan-satker-list"
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, unit_pengusul: e.target.value } }))}
                    data-testid="usulan-unit" />
                  <datalist id="usulan-satker-list">
                    {satkerList.map((s) => (
                      <option key={s.kode_satker} value={s.nama_satker || s.kode_satker}>{s.kode_satker}</option>
                    ))}
                  </datalist>
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-uraian">Uraian usulan</label>
                  <Input id="usl-uraian" placeholder="cth. Pemeliharaan berat genset kantor" value={formUsulan.data.uraian}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, uraian: e.target.value } }))}
                    data-testid="usulan-uraian" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-volume">Volume</label>
                  <Input id="usl-volume" type="number" min="1" value={formUsulan.data.volume}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, volume: e.target.value } }))}
                    data-testid="usulan-volume" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-satuan">Satuan</label>
                  <Input id="usl-satuan" placeholder="unit / paket / m²" value={formUsulan.data.satuan}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, satuan: e.target.value } }))}
                    data-testid="usulan-satuan" />
                </div>
              </div>
              {!formUsulan.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-cari">Tautkan aset (ops., untuk pemeliharaan/eksisting)</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="usl-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="usulan-cari" />
                  </div>
                  {mencari && <p className="text-[11px] text-muted-foreground mt-1">Mencari…</p>}
                  <ul className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormUsulan((f) => ({ ...f, aset: a }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`usulan-pilih-${a.id}`}>
                          <span className="text-foreground/90">{a.asset_name || "-"}</span>{" "}
                          <span className="font-mono text-[10px] text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="rounded-lg border border-border p-2 text-xs flex items-center justify-between gap-2">
                  <span className="text-foreground/90 min-w-0 truncate">
                    {formUsulan.aset.asset_name || "-"}{" "}
                    <span className="font-mono text-[10px] text-muted-foreground">({formUsulan.aset.asset_code} · {formUsulan.aset.NUP})</span>
                  </span>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormUsulan((f) => ({ ...f, aset: null }))}>
                    Lepas
                  </Button>
                </div>
              )}
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="usl-ket">Keterangan (ops.)</label>
                <Input id="usl-ket" value={formUsulan.data.keterangan}
                  onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                  data-testid="usulan-keterangan" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormUsulan(null)}>Batal</Button>
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white"
                  disabled={formUsulan.saving || !formUsulan.data.unit_pengusul.trim() || !formUsulan.data.uraian.trim() || !formUsulan.data.satuan.trim()}
                  onClick={simpanUsulan} data-testid="usulan-simpan">
                  {formUsulan.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan Draft"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog tambah standar SBSK ── */}
      <Dialog open={!!formSbsk} onOpenChange={(o) => !o && setFormSbsk(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tambah Standar SBSK</DialogTitle>
            <DialogDescription>Angka dari Lampiran PMK 138/2024 (batas tertinggi kebutuhan).</DialogDescription>
          </DialogHeader>
          {formSbsk && (
            <div className="space-y-2">
              <select value={formSbsk.kategori}
                onChange={(e) => setFormSbsk({ ...formSbsk, kategori: e.target.value })}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm" data-testid="sbsk-kategori">
                <option value="ruang_kerja">Ruang kerja (m²)</option>
                <option value="kendaraan">Kendaraan dinas</option>
                <option value="barang">Barang/peralatan</option>
                <option value="tanah_bangunan">Tanah & bangunan</option>
              </select>
              <Input value={formSbsk.peruntukan} placeholder="Peruntukan (mis. Pejabat eselon III)"
                onChange={(e) => setFormSbsk({ ...formSbsk, peruntukan: e.target.value })}
                className="h-9" data-testid="sbsk-peruntukan" />
              <div className="grid grid-cols-2 gap-2">
                <Input value={formSbsk.standar} inputMode="decimal" placeholder="Angka standar"
                  onChange={(e) => setFormSbsk({ ...formSbsk, standar: e.target.value })}
                  className="h-9" data-testid="sbsk-standar" />
                <Input value={formSbsk.satuan} placeholder="Satuan (unit/m²)"
                  onChange={(e) => setFormSbsk({ ...formSbsk, satuan: e.target.value })}
                  className="h-9" />
              </div>
              <Input value={formSbsk.keterangan} placeholder="Keterangan/rujukan lampiran (opsional)"
                onChange={(e) => setFormSbsk({ ...formSbsk, keterangan: e.target.value })}
                className="h-9" />
              <div className="flex justify-end gap-1.5 pt-1">
                <Button variant="outline" size="sm" className="h-9 text-xs" onClick={() => setFormSbsk(null)}>Batal</Button>
                <Button size="sm" className="h-9 text-xs bg-blue-600 hover:bg-blue-700 text-white" onClick={simpanSbsk} data-testid="sbsk-simpan">Simpan</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog hasil sanding usulan ── */}
      <Dialog open={!!sanding} onOpenChange={(o) => !o && setSanding(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Scale className="w-4 h-4 text-violet-500" />Sanding Usulan vs Eksisting &amp; SBSK
            </DialogTitle>
            <DialogDescription className="truncate">{sanding?.usulan?.uraian}</DialogDescription>
          </DialogHeader>
          {!sanding?.hasil ? (
            <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
          ) : (
            <div className="space-y-2.5" data-testid="sanding-hasil">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[["Eksisting sejenis", sanding.hasil.jumlah_eksisting, "unit"],
                  ["Umur rata-rata", sanding.hasil.umur_rata_tahun ?? "—", "tahun"],
                  ["Nilai eksisting", fmtRp(Math.round(sanding.hasil.nilai_eksisting || 0)), ""]].map(([l, v, s], i) => (
                  <div key={l} className={`rounded-lg border border-border p-2 text-center ${i === 2 ? "col-span-2 sm:col-span-1" : ""}`}>
                    <p className="text-sm font-extrabold leading-tight truncate whitespace-nowrap tabular-nums" title={String(v)}>{v}</p>
                    <p className="text-[9px] text-muted-foreground">{l}{s ? ` (${s})` : ""}</p>
                  </div>
                ))}
              </div>
              {Object.keys(sanding.hasil.kondisi || {}).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(sanding.hasil.kondisi).map(([k, n]) => (
                    <span key={k} className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_KONDISI[k] || "bg-muted text-muted-foreground"}`}>
                      {k}: {n}
                    </span>
                  ))}
                </div>
              )}
              <div className="rounded-lg bg-muted/60 p-2.5 space-y-1">
                {(sanding.hasil.catatan || []).map((c, i) => (
                  <p key={i} className="text-[11px] text-foreground/90">• {c}</p>
                ))}
                {(sanding.hasil.catatan || []).length === 0 && (
                  <p className="text-[11px] text-muted-foreground">Tidak ada catatan — lengkapi kode barang usulan agar sanding otomatis bekerja.</p>
                )}
              </div>
              <p className="text-[10px] text-muted-foreground">
                Kode barang sanding: <b className="font-mono">{sanding.hasil.kode_barang || "—"}</b> ·
                Dasar: PMK 153/2021 jo. PMK 138/2024 (SBSK).
              </p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {confirmDialog}
      {transitionDialog}
    </div>
  );
}
