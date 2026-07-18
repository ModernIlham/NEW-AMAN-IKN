import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, FileText, FileDown, ChevronDown,
  ShieldCheck, Boxes, Scale, Lock, LockOpen, Plus, Trash2, CalendarCheck,
  Settings,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useTransitionDialog } from "@/components/ui/TransitionDialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import SimanSyncCard from "@/components/pelaporan/SimanSyncCard";
import ReportSettingsEditor from "@/components/assets/ReportSettingsEditor";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Laporan resmi per kegiatan — endpoint yang SUDAH berjalan di modul
// Inventarisasi Aset; hub ini menyatukannya lintas kegiatan.
const LAPORAN_KEGIATAN = [
  { key: "lhi-pdf", label: "LHI Lengkap", nama: "LHI" },
  { key: "rhi-pdf", label: "RHI (Rekapitulasi)", nama: "RHI" },
  { key: "bahi-pdf", label: "BAHI (Berita Acara)", nama: "BAHI" },
  { key: "dbkp-pdf", label: "DBKP per Golongan", nama: "DBKP" },
  { key: "sp-hasil-pdf", label: "SP Hasil", nama: "SP_Hasil" },
  { key: "sp-pelaksanaan-pdf", label: "SP Pelaksanaan", nama: "SP_Pelaksanaan" },
  { key: "executive-summary-pdf", label: "Laporan Eksekutif", nama: "Eksekutif" },
];

function fmtPeriode(a) {
  const d = (v) => (v ? String(v).slice(0, 10) : "");
  const dari = d(a.tanggal_mulai);
  const sampai = d(a.tanggal_selesai);
  if (!dari && !sampai) return "—";
  return `${dari || "…"} s.d. ${sampai || "…"}`;
}

/**
 * Hub Pelaporan — arsip laporan lintas kegiatan (sub-modul Penatausahaan ›
 * Pelaporan, status Sebagian Aktif). Menyatukan 13+ laporan inventarisasi
 * per kegiatan + laporan persediaan pada satu pintu — bekal LBKP/rekonsiliasi
 * pada tahap berikutnya.
 */
export default function PelaporanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  // Register periode pelaporan: {items, ringkasan, label_status, catatan}
  const [periode, setPeriode] = useState(null);
  const [bukaSampul, setBukaSampul] = useState(false);
  // Dialog reklasifikasi kodefikasi (G7): {cari, hasil, aset, kode_baru, alasan, saving}
  const [reklas, setReklas] = useState(null);
  // Arsip laporan lintas kegiatan (surat ber-nomor + kegiatan disahkan + periode FINAL)
  const [arsip, setArsip] = useState(null);
  const [qArsip, setQArsip] = useState("");

  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  const { minta, transitionDialog } = useTransitionDialog();
  const { confirm, confirmDialog } = useConfirm();

  const muatPeriode = useCallback(() => {
    axios.get(`${API}/pelaporan/periode`)
      .then((r) => setPeriode(r.data))
      .catch(() => toast.error("Gagal memuat periode pelaporan"));
  }, []);

  useEffect(() => {
    axios.get(`${API}/inventory-activities`)
      .then((r) => setActivities(Array.isArray(r.data) ? r.data : (r.data?.items || [])))
      .catch(() => toast.error("Gagal memuat daftar kegiatan"))
      .finally(() => setLoading(false));
    axios.get(`${API}/pelaporan/arsip`)
      .then((r) => setArsip(r.data))
      .catch(() => setArsip({ items: [], ringkas: {} }));
    muatPeriode();
  }, [muatPeriode]);

  const buatPeriode = async (semester, tahun) => {
    const th = tahun || new Date().getFullYear();
    try {
      await axios.post(`${API}/pelaporan/periode`, { tahun: th, semester });
      toast.success("Periode terdaftar");
      muatPeriode();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mendaftarkan periode");
    }
  };

  const kunciPeriode = async (p) => {
    try {
      await axios.post(`${API}/pelaporan/periode/${p.id}/kunci`);
      toast.success(`${p.label} terkunci — laporan periode ini FINAL`);
      muatPeriode();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunci periode");
    }
  };

  const bukaPeriode = async (p) => {
    const v = await minta({
      judul: `Buka kunci ${p.label}`,
      deskripsi: "Alasan tercatat pada riwayat periode.",
      fields: [{ key: "alasan", label: "Alasan", type: "textarea", wajib: true }],
      confirmLabel: "Buka Kunci",
    });
    if (v === null) return;
    const alasan = v.alasan;
    try {
      await axios.post(`${API}/pelaporan/periode/${p.id}/buka`, { alasan });
      toast.success("Kunci periode dibuka");
      muatPeriode();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka kunci");
    }
  };

  const hapusPeriode = async (p) => {
    const ok = await confirm({
      title: `Hapus periode ${p.label}?`,
      description: "Periode beserta status kunci & tenggatnya dihapus dari daftar (tidak menghapus data laporan).",
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pelaporan/periode/${p.id}`);
      toast.success("Periode dihapus");
      muatPeriode();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus periode");
    }
  };

  const aturTenggat = async (p) => {
    const v = await minta({
      judul: `Tenggat penyampaian ${p.label}`,
      deskripsi: "Kosongkan untuk menghapus tenggat.",
      fields: [{ key: "tenggat", label: "Tenggat", type: "date", default: p.tenggat || "" }],
      confirmLabel: "Simpan",
    });
    if (v === null) return;
    const tenggat = v.tenggat || "";
    try {
      await axios.post(`${API}/pelaporan/periode/${p.id}/tenggat`, { tenggat: tenggat.trim() });
      toast.success(tenggat.trim() ? "Tenggat tersimpan" : "Tenggat dihapus");
      muatPeriode();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengatur tenggat");
    }
  };

  // Suffix status periode pada opsi unduh: FINAL (terkunci) / belum final.
  const sufiksPeriode = useCallback((tahun, semester) => {
    const it = (periode?.items || []).find(
      (p) => p.tahun === tahun && (p.semester || null) === (semester || null));
    if (!it) return "";
    return it.status === "terkunci" ? " · FINAL" : " · belum final";
  }, [periode]);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    const rows = !s ? activities : activities.filter((a) =>
      [a.nama_kegiatan, a.ticket_number, a.nama_satker]
        .some((v) => String(v || "").toLowerCase().includes(s)));
    return [...rows].sort((a, b) => String(b.tanggal_mulai || "").localeCompare(String(a.tanggal_mulai || "")));
  }, [activities, search]);

  const unduh = (activity, item) => {
    downloadFileWithProgress(
      `${API}/inventory-activities/${activity.id}/${item.key}`,
      `${item.nama}_${(activity.ticket_number || activity.id.slice(0, 8)).replace(/[^\w-]/g, "_")}.pdf`,
      { label: `${item.nama} — ${activity.nama_kegiatan || ""}` },
    ).catch(() => {});
  };

  const tampilArsip = useMemo(() => {
    const s = qArsip.trim().toLowerCase();
    const items = arsip?.items || [];
    if (!s) return items;
    return items.filter((i) =>
      `${i.judul} ${i.nomor} ${i.sub}`.toLowerCase().includes(s));
  }, [arsip, qArsip]);

  return (
    <div className="min-h-screen bg-background" data-testid="pelaporan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pelaporan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <FileText className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Arsip Pelaporan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Laporan resmi lintas kegiatan + laporan persediaan — satu pintu
            </p>
          </div>
          {isAdmin && (
            <Button variant="outline" size="sm" className="gap-1.5" data-testid="pelaporan-kop"
              onClick={() => setBukaSampul((v) => !v)}>
              <Settings className="w-3.5 h-3.5" />Kop/Sampul
            </Button>
          )}
          {isAdmin && (
            <Button variant="outline" size="sm" className="gap-1.5" data-testid="pelaporan-reklas"
              title="Reklasifikasi kodefikasi aset (SAKTI 304/107) — kode+NUP diperbarui ber-riwayat"
              onClick={() => setReklas({ cari: "", hasil: [], aset: null, kode_baru: "", alasan: "", saving: false })}>
              <Boxes className="w-3.5 h-3.5" />Reklasifikasi
            </Button>
          )}
          <BookingNomorButton modul="pelaporan" jenisNaskah="Laporan" referensi="LHI/LBKP" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {bukaSampul && <ReportSettingsEditor onClose={() => setBukaSampul(false)} />}
        {/* ── Pembukuan satker-wide: Posisi BMN di Neraca (komponen LBKP) ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2.5 sm:p-3 flex items-center gap-2 flex-wrap">
          <span className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Scale className="w-4 h-4 text-white" />
          </span>
          <div className="flex-1 min-w-[140px]">
            <p className="text-xs font-semibold text-foreground">Posisi BMN di Neraca</p>
            <p className="text-[10px] text-muted-foreground">Seluruh aset per golongan (intra/ekstra, PMK 181) + persediaan FIFO</p>
          </div>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/pembukuan/posisi-bmn-pdf`, "Posisi_BMN_Neraca.pdf", { label: "Laporan Posisi BMN di Neraca" }).catch(() => {})}
            data-testid="pelaporan-posisi-bmn">
            <FileDown className="w-3.5 h-3.5" />Unduh PDF
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/pembukuan/rekonsiliasi-xlsx`, "Rekonsiliasi_Posisi_BMN.xlsx", { label: "Ekspor Rekonsiliasi (XLSX)" }).catch(() => {})}
            data-testid="pelaporan-rekonsiliasi">
            <FileDown className="w-3.5 h-3.5" />Rekonsiliasi XLSX
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/pembukuan/lkb-pdf`, "Laporan_Kondisi_Barang.pdf", { label: "Laporan Kondisi Barang (LKB)" }).catch(() => {})}
            data-testid="pelaporan-lkb-kondisi">
            <FileDown className="w-3.5 h-3.5" />LKB
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/pembukuan/dbr-pdf`, "Daftar_Barang_Ruangan.pdf", { label: "Daftar Barang Ruangan (DBR)" }).catch(() => {})}
            data-testid="pelaporan-dbr">
            <FileDown className="w-3.5 h-3.5" />DBR
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/pembukuan/kir-pdf`, "Kartu_Inventaris_Ruangan.pdf", { label: "Kartu Inventaris Ruangan (KIR)" }).catch(() => {})}
            data-testid="pelaporan-kir">
            <FileDown className="w-3.5 h-3.5" />KIR
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5" data-testid="pelaporan-lbkp">
                <FileDown className="w-3.5 h-3.5" />LBKP<ChevronDown className="w-3 h-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              {(() => {
                const th = new Date().getFullYear();
                return [
                  { label: `Semester I ${th} (Jan–Jun)${sufiksPeriode(th, 1)}`, q: `tahun=${th}&semester=1`, f: `LBKP_${th}_S1.pdf` },
                  { label: `Semester II ${th} (Jul–Des)${sufiksPeriode(th, 2)}`, q: `tahun=${th}&semester=2`, f: `LBKP_${th}_S2.pdf` },
                  { label: `Tahunan ${th}${sufiksPeriode(th, null)}`, q: `tahun=${th}`, f: `LBKP_${th}.pdf` },
                  { label: `Semester I ${th - 1}${sufiksPeriode(th - 1, 1)}`, q: `tahun=${th - 1}&semester=1`, f: `LBKP_${th - 1}_S1.pdf` },
                  { label: `Semester II ${th - 1}${sufiksPeriode(th - 1, 2)}`, q: `tahun=${th - 1}&semester=2`, f: `LBKP_${th - 1}_S2.pdf` },
                  { label: `Tahunan ${th - 1}${sufiksPeriode(th - 1, null)}`, q: `tahun=${th - 1}`, f: `LBKP_${th - 1}.pdf` },
                ].map((o) => (
                  <DropdownMenuItem key={o.label} className="min-h-[42px]"
                    onClick={() => downloadFileWithProgress(`${API}/pembukuan/lbkp-pdf?${o.q}`, o.f, { label: `LBKP ${o.label}` }).catch(() => {})}>
                    {o.label}
                  </DropdownMenuItem>
                ));
              })()}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5" data-testid="pelaporan-calbmn">
                <FileDown className="w-3.5 h-3.5" />CaLBMN<ChevronDown className="w-3 h-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              {(() => {
                const th = new Date().getFullYear();
                return [
                  { label: `Semester I ${th} (Jan–Jun)${sufiksPeriode(th, 1)}`, q: `tahun=${th}&semester=1`, f: `CaLBMN_${th}_S1.pdf` },
                  { label: `Semester II ${th} (Jul–Des)${sufiksPeriode(th, 2)}`, q: `tahun=${th}&semester=2`, f: `CaLBMN_${th}_S2.pdf` },
                  { label: `Tahunan ${th}${sufiksPeriode(th, null)}`, q: `tahun=${th}`, f: `CaLBMN_${th}.pdf` },
                  { label: `Semester I ${th - 1}${sufiksPeriode(th - 1, 1)}`, q: `tahun=${th - 1}&semester=1`, f: `CaLBMN_${th - 1}_S1.pdf` },
                  { label: `Semester II ${th - 1}${sufiksPeriode(th - 1, 2)}`, q: `tahun=${th - 1}&semester=2`, f: `CaLBMN_${th - 1}_S2.pdf` },
                  { label: `Tahunan ${th - 1}${sufiksPeriode(th - 1, null)}`, q: `tahun=${th - 1}`, f: `CaLBMN_${th - 1}.pdf` },
                ].map((o) => (
                  <DropdownMenuItem key={o.label} className="min-h-[42px]"
                    onClick={() => downloadFileWithProgress(`${API}/pembukuan/calbmn-pdf?${o.q}`, o.f, { label: `CaLBMN ${o.label}` }).catch(() => {})}>
                    {o.label}
                  </DropdownMenuItem>
                ));
              })()}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* ── ARSIP LAPORAN lintas kegiatan & periode (satu daftar) ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pelaporan-arsip">
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
            <span className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center flex-shrink-0">
              <FileText className="w-4 h-4 text-white" />
            </span>
            <div className="flex-1 min-w-[140px]">
              <p className="text-xs font-semibold text-foreground">Arsip Laporan Lintas Kegiatan</p>
              <p className="text-[10px] text-muted-foreground">
                Naskah ber-nomor (Persuratan) + kegiatan disahkan + periode FINAL — satu daftar riwayat
              </p>
            </div>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input value={qArsip} onChange={(e) => setQArsip(e.target.value)}
                placeholder="Cari nomor/judul…" className="pl-8 h-8 w-44 text-xs" data-testid="arsip-cari" />
            </div>
          </div>
          {!arsip ? (
            <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-muted-foreground" /></div>
          ) : tampilArsip.length === 0 ? (
            <p className="text-center text-[11px] text-muted-foreground py-6">
              Belum ada arsip — booking nomor laporan, sahkan kegiatan, atau kunci periode akan muncul di sini.
            </p>
          ) : (
            <div className="divide-y divide-border/60 max-h-72 overflow-y-auto">
              {tampilArsip.slice(0, 60).map((it) => (
                <div key={`${it.tipe}-${it.id}`} className="px-3 py-2 flex items-center gap-2.5">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase flex-shrink-0 ${
                    it.tipe === "kegiatan" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : it.tipe === "periode" ? "bg-slate-500/15 text-slate-600 dark:text-slate-400"
                        : "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400"}`}>
                    {it.tipe}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-semibold truncate">{it.judul}</p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {it.nomor ? `${it.nomor} · ` : ""}{it.sub}{it.tanggal ? ` · ${it.tanggal}` : ""}
                    </p>
                  </div>
                  <span className="px-1.5 py-0.5 rounded-full bg-muted text-[9px] font-bold text-muted-foreground flex-shrink-0 uppercase">
                    {it.status || "-"}
                  </span>
                </div>
              ))}
            </div>
          )}
          {arsip && (
            <p className="px-3 py-1.5 text-[10px] text-muted-foreground border-t border-border">
              {arsip.ringkas?.surat || 0} naskah ber-nomor · {arsip.ringkas?.kegiatan || 0} kegiatan disahkan · {arsip.ringkas?.periode || 0} periode FINAL
            </p>
          )}
        </div>

        {/* ── Sinkronisasi berkala dengan SIMAN V2 (impor manual ekspor) ── */}
        <SimanSyncCard isAdmin={isAdmin} />

        {/* ── Periode pelaporan ber-kunci ── */}
        {periode && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pelaporan-periode">
            <div className="px-3 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
              <span className="w-8 h-8 rounded-lg bg-slate-600 flex items-center justify-center flex-shrink-0">
                <CalendarCheck className="w-4 h-4 text-white" />
              </span>
              <div className="flex-1 min-w-[140px]">
                <p className="text-xs font-semibold text-foreground">Periode Pelaporan</p>
                <p className="text-[10px] text-muted-foreground">Periode terkunci = LBKP & CaLBMN periode itu berpenanda FINAL</p>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-slate-500/15 text-slate-600 dark:text-slate-400 text-[10px] font-semibold">
                {periode.ringkasan?.terkunci || 0} terkunci
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5" data-testid="pelaporan-periode-tambah">
                    <Plus className="w-3.5 h-3.5" />Daftarkan<ChevronDown className="w-3 h-3" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-60">
                  {(() => {
                    const th = new Date().getFullYear();
                    return [
                      { label: `Semester I ${th}`, semester: 1, tahun: th },
                      { label: `Semester II ${th}`, semester: 2, tahun: th },
                      { label: `Tahunan ${th}`, semester: null, tahun: th },
                      { label: `Semester II ${th - 1}`, semester: 2, tahun: th - 1 },
                      { label: `Tahunan ${th - 1}`, semester: null, tahun: th - 1 },
                    ].map((o) => (
                      <DropdownMenuItem key={o.label} className="min-h-[42px]"
                        onClick={() => buatPeriode(o.semester, o.tahun)}>
                        {o.label}
                      </DropdownMenuItem>
                    ));
                  })()}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
            {(periode.items || []).length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4 px-3">
                Belum ada periode terdaftar — daftarkan periode berjalan lalu kunci saat laporan final.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {periode.items.map((p) => (
                  <li key={p.id} className="px-3 py-2 flex items-center gap-2 flex-wrap" data-testid={`pelaporan-periode-${p.id}`}>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex items-center gap-1 ${
                      p.status === "terkunci"
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                        : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                      {p.status === "terkunci" ? <Lock className="w-3 h-3" /> : <LockOpen className="w-3 h-3" />}
                      {periode.label_status?.[p.status] || p.status}
                    </span>
                    <p className="text-xs font-semibold text-foreground flex-1 min-w-[120px]">{p.label}</p>
                    {p.status === "terkunci" && (
                      <span className="text-[10px] text-muted-foreground">
                        terkunci {String(p.tanggal_kunci || "").slice(0, 10)} oleh {p.dikunci_oleh}
                      </span>
                    )}
                    {p.info_tenggat?.tenggat && p.info_tenggat.lewat && (
                      <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold">
                        Lewat tenggat {p.info_tenggat.tenggat}
                      </span>
                    )}
                    {p.info_tenggat?.tenggat && !p.info_tenggat.lewat && (
                      <span className="text-[10px] text-muted-foreground">
                        tenggat {p.info_tenggat.tenggat} (sisa {p.info_tenggat.sisa_hari} hari)
                      </span>
                    )}
                    {isAdmin && p.status === "terbuka" && (
                      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                        onClick={() => aturTenggat(p)} data-testid={`pelaporan-periode-tenggat-${p.id}`}>
                        <CalendarCheck className="w-3 h-3 mr-1" />Tenggat
                      </Button>
                    )}
                    {isAdmin && p.status === "terbuka" && (
                      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                        onClick={() => kunciPeriode(p)} data-testid={`pelaporan-periode-kunci-${p.id}`}>
                        <Lock className="w-3 h-3 mr-1" />Kunci
                      </Button>
                    )}
                    {isAdmin && p.status === "terkunci" && (
                      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                        onClick={() => bukaPeriode(p)} data-testid={`pelaporan-periode-buka-${p.id}`}>
                        <LockOpen className="w-3 h-3 mr-1" />Buka
                      </Button>
                    )}
                    {isAdmin && p.status === "terbuka" && (
                      <button type="button" aria-label="Hapus periode" onClick={() => hapusPeriode(p)}
                        className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{periode.catatan}</p>
          </div>
        )}

        {/* ── Laporan persediaan (satker-wide) ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm p-2.5 sm:p-3 flex items-center gap-2 flex-wrap">
          <span className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center flex-shrink-0">
            <Boxes className="w-4 h-4 text-white" />
          </span>
          <p className="text-xs font-semibold text-foreground flex-1 min-w-[140px]">Laporan Persediaan</p>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/persediaan/laporan/posisi-pdf`, "Laporan_Posisi_Persediaan.pdf", { label: "Laporan Posisi Persediaan" }).catch(() => {})}
            data-testid="pelaporan-persediaan-posisi">
            <FileDown className="w-3.5 h-3.5" />Posisi
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5"
            onClick={() => {
              const now = new Date();
              const awal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
              const akhir = now.toISOString().slice(0, 10);
              downloadFileWithProgress(`${API}/persediaan/laporan/mutasi-pdf?dari=${awal}&sampai=${akhir}`,
                `Laporan_Mutasi_Persediaan_${awal}_${akhir}.pdf`, { label: "Laporan Mutasi Persediaan (bulan berjalan)" }).catch(() => {});
            }}
            data-testid="pelaporan-persediaan-mutasi">
            <FileDown className="w-3.5 h-3.5" />Mutasi Bulan Ini
          </Button>
        </div>

        {/* ── Pencarian kegiatan ── */}
        <div className="relative">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari kegiatan, tiket, atau satker…"
            className="pl-9 h-10"
            data-testid="pelaporan-search"
          />
        </div>

        {/* ── Daftar kegiatan ── */}
        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-indigo-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <FileText className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Tidak ada kegiatan yang cocok</p>
              <p className="text-xs text-muted-foreground mt-1">Laporan dihasilkan per kegiatan inventarisasi.</p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {filtered.map((a) => {
                const disahkan = a.status_pengesahan === "disahkan";
                return (
                  <li key={a.id} className="p-3 flex items-center gap-3 flex-wrap hover:bg-muted/40" data-testid={`pelaporan-row-${a.id}`}>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground leading-tight">
                        {a.nama_kegiatan || "(tanpa nama)"}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[a.ticket_number, a.nama_satker, fmtPeriode(a)].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {disahkan && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold flex-shrink-0">
                        <ShieldCheck className="w-3 h-3" />Disahkan
                      </span>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm" className="gap-1.5 flex-shrink-0" data-testid={`pelaporan-unduh-${a.id}`}>
                          <FileDown className="w-3.5 h-3.5" />Unduh<ChevronDown className="w-3 h-3" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-60">
                        <DropdownMenuLabel className="text-[11px]">Laporan Resmi — {a.ticket_number || ""}</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        {LAPORAN_KEGIATAN.map((item) => (
                          <DropdownMenuItem key={item.key} className="min-h-[42px]" onClick={() => unduh(a, item)}>
                            <FileDown className="w-4 h-4 mr-2" />{item.label}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          Angka LBKP/rekonsiliasi bersumber dari data aset & persediaan AMAN — pencatatan resmi tetap di SAKTI/SIMAN.
        </p>
      </main>
      {/* ── Dialog Reklasifikasi Kodefikasi (G7 — SAKTI 304/107) ── */}
      <Dialog open={!!reklas} onOpenChange={(o) => { if (!o) setReklas(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reklasifikasi Kodefikasi Aset</DialogTitle>
            <DialogDescription className="text-xs">
              Kode & NUP diperbarui pada aset yang sama (riwayat + jurnal 304/107 tercatat;
              nilai & tanggal perolehan tidak berubah). Kode tujuan = kode barang 10 digit.
            </DialogDescription>
          </DialogHeader>
          {reklas && (
            <div className="space-y-2.5 text-sm">
              {!reklas.aset ? (
                <div>
                  <Input placeholder="Cari kode/nama aset (min. 2 huruf)" value={reklas.cari}
                    data-testid="reklas-cari"
                    onChange={async (e) => {
                      const v = e.target.value;
                      setReklas((r) => ({ ...r, cari: v }));
                      if (v.trim().length >= 2) {
                        try {
                          const rr = await axios.get(`${API}/assets`, { params: { search: v.trim(), page_size: 8 } });
                          setReklas((r) => (r ? { ...r, hasil: rr.data?.items || [] } : r));
                        } catch { /* biarkan */ }
                      }
                    }} />
                  <div className="mt-1.5 max-h-40 overflow-y-auto divide-y divide-border/60 border border-border rounded-lg">
                    {(reklas.hasil || []).map((a) => (
                      <button key={a.id} type="button" className="w-full px-2.5 py-1.5 text-left hover:bg-muted"
                        onClick={() => setReklas((r) => ({ ...r, aset: a }))}>
                        <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                        <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · NUP {a.NUP}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  <div className="rounded-lg border border-border p-2 text-xs">
                    <p className="font-semibold text-foreground">{reklas.aset.asset_name}</p>
                    <p className="font-mono text-muted-foreground">{reklas.aset.asset_code} · NUP {reklas.aset.NUP}</p>
                    <button type="button" className="text-[10px] text-blue-600 hover:underline min-w-0 min-h-0 mt-0.5"
                      onClick={() => setReklas((r) => ({ ...r, aset: null }))}>Ganti aset</button>
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Kode barang tujuan (10 digit) *</label>
                    <Input value={reklas.kode_baru} inputMode="numeric" className="font-mono" data-testid="reklas-kode"
                      onChange={(e) => setReklas((r) => ({ ...r, kode_baru: e.target.value.replace(/\D/g, "").slice(0, 10) }))} />
                  </div>
                  <div>
                    <label className="text-xs font-medium block mb-1">Alasan</label>
                    <Input value={reklas.alasan} placeholder="cth. salah penggolongan saat perekaman"
                      onChange={(e) => setReklas((r) => ({ ...r, alasan: e.target.value }))} />
                  </div>
                  <div className="flex justify-end gap-2 pt-1">
                    <Button variant="outline" onClick={() => setReklas(null)}>Batal</Button>
                    <Button disabled={reklas.saving || reklas.kode_baru.length !== 10} data-testid="reklas-simpan"
                      onClick={async () => {
                        setReklas((r) => ({ ...r, saving: true }));
                        try {
                          const rr = await axios.post(`${API}/pembukuan/reklasifikasi`, {
                            asset_id: reklas.aset.id, kode_baru: reklas.kode_baru, alasan: reklas.alasan });
                          toast.success(`Reklasifikasi tercatat — kode baru ${rr.data.kode_baru} · NUP ${rr.data.nup_baru}`);
                          setReklas(null);
                        } catch (e2) {
                          toast.error(e2?.response?.data?.detail || "Gagal reklasifikasi");
                          setReklas((r) => (r ? { ...r, saving: false } : r));
                        }
                      }}>
                      Reklasifikasi
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
      {confirmDialog}
      {transitionDialog}
    </div>
  );
}
