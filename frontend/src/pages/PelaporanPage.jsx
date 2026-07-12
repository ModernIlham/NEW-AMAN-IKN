import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, FileText, FileDown, ChevronDown,
  ShieldCheck, Boxes, Scale,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

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
export default function PelaporanPage({ onBack }) {
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  useEffect(() => {
    axios.get(`${API}/inventory-activities`)
      .then((r) => setActivities(Array.isArray(r.data) ? r.data : (r.data?.items || [])))
      .catch(() => toast.error("Gagal memuat daftar kegiatan"))
      .finally(() => setLoading(false));
  }, []);

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
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
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
                  { label: `Semester I ${th} (Jan–Jun)`, q: `tahun=${th}&semester=1`, f: `LBKP_${th}_S1.pdf` },
                  { label: `Semester II ${th} (Jul–Des)`, q: `tahun=${th}&semester=2`, f: `LBKP_${th}_S2.pdf` },
                  { label: `Tahunan ${th}`, q: `tahun=${th}`, f: `LBKP_${th}.pdf` },
                  { label: `Tahunan ${th - 1}`, q: `tahun=${th - 1}`, f: `LBKP_${th - 1}.pdf` },
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
                  { label: `Semester I ${th} (Jan–Jun)`, q: `tahun=${th}&semester=1`, f: `CaLBMN_${th}_S1.pdf` },
                  { label: `Semester II ${th} (Jul–Des)`, q: `tahun=${th}&semester=2`, f: `CaLBMN_${th}_S2.pdf` },
                  { label: `Tahunan ${th}`, q: `tahun=${th}`, f: `CaLBMN_${th}.pdf` },
                  { label: `Tahunan ${th - 1}`, q: `tahun=${th - 1}`, f: `CaLBMN_${th - 1}.pdf` },
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
          LBKP semesteran/tahunan & ekspor rekonsiliasi SIMAK/SAKTI menyusul pada tahap berikutnya (masterplan Fase 2 › Pelaporan).
        </p>
      </main>
    </div>
  );
}
