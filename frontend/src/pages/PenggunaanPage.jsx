import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, UserCheck, ChevronLeft, ChevronRight,
  BadgeCheck, FileWarning, FileText,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Penggunaan — Fase 3 tahap awal: rekap aset per PEMEGANG lintas kegiatan,
 * dibangun dari data pengguna + NIP + BAST yang sudah dicatat modul
 * inventarisasi. PSP/alih status/BMN idle menyusul (PMK 40 & 120/2024).
 */
export default function PenggunaanPage({ onBack }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalLengkap, setTotalLengkap] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  // Dialog daftar aset: {pemegang, rows, loading}
  const [detail, setDetail] = useState(null);
  const searchTimer = useRef(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1, s = search) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/penggunaan/pemegang`, {
        params: { search: s, page: p, page_size: 50 },
      });
      setItems(r.data?.items || []);
      setTotal(r.data?.total_pemegang || 0);
      setTotalLengkap(r.data?.total_lengkap || 0);
      setTotalPages(r.data?.total_pages || 1);
      setPage(p);
    } catch {
      toast.error("Gagal memuat daftar pemegang");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { load(1, ""); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSearchChange = (v) => {
    setSearch(v);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => load(1, v), 350);
  };
  useEffect(() => () => { if (searchTimer.current) clearTimeout(searchTimer.current); }, []);

  const openDetail = async (p) => {
    setDetail({ pemegang: p, rows: [], loading: true });
    try {
      const r = await axios.get(`${API}/penggunaan/pemegang/aset`, {
        params: { nama: p.nama, nip: p.nip || "" },
      });
      setDetail({ pemegang: p, rows: r.data?.items || [], loading: false });
    } catch {
      toast.error("Gagal memuat aset pemegang");
      setDetail(null);
    }
  };

  return (
    <div className="min-h-screen bg-background" data-testid="penggunaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="penggunaan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <UserCheck className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Aset per Pemegang</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {total} pemegang · {totalLengkap} berkas lengkap (NIP + semua BAST) · lintas kegiatan
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Cari nama, NIP, atau jabatan…"
            className="pl-9 h-10"
            data-testid="penggunaan-search"
          />
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <UserCheck className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada pemegang tercatat</p>
              <p className="text-xs text-muted-foreground mt-1">
                Isi kolom Pengguna (+NIP & BAST) pada aset di modul Inventarisasi — rekap ini terbangun otomatis.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-border/60">
              {items.map((p) => (
                <li key={`${p.nama}|${p.nip}`}>
                  <button
                    type="button"
                    onClick={() => openDetail(p)}
                    className="w-full text-left p-3 flex items-center gap-3 hover:bg-muted/40"
                    data-testid={`penggunaan-row-${p.nama}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground leading-tight">{p.nama}</p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[p.nip && `NIP ${p.nip}`, p.jabatan, p.melekat_ke,
                          `${p.jumlah_kegiatan} kegiatan`].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    <span className="text-xs font-bold text-foreground flex-shrink-0">{p.jumlah_aset} aset</span>
                    {p.lengkap ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-[10px] font-semibold flex-shrink-0">
                        <BadgeCheck className="w-3 h-3" />Lengkap
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 text-[10px] font-semibold flex-shrink-0">
                        <FileWarning className="w-3 h-3" />BAST {p.jumlah_bast}/{p.jumlah_aset}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => load(page - 1, search)} className="gap-1">
              <ChevronLeft className="w-4 h-4" />Sebelumnya
            </Button>
            <span className="text-xs text-muted-foreground">Hal. {page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => load(page + 1, search)} className="gap-1">
              Berikutnya<ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          PSP, alih status, dan pemantauan BMN idle (PMK 40 & 120/2024) menyusul — masterplan Fase 3.
        </p>
      </main>

      {/* ── Dialog daftar aset pemegang ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Aset — {detail?.pemegang?.nama}</DialogTitle>
            <DialogDescription className="text-xs">
              {[detail?.pemegang?.nip && `NIP ${detail.pemegang.nip}`, detail?.pemegang?.jabatan]
                .filter(Boolean).join(" · ") || "Daftar aset yang melekat pada pemegang ini"}
            </DialogDescription>
          </DialogHeader>
          {detail?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-sky-600" /></div>
          ) : (
            <>
            <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
              onClick={() => downloadFileWithProgress(
                `${API}/penggunaan/pemegang/daftar-pdf?nama=${encodeURIComponent(detail?.pemegang?.nama || "")}&nip=${encodeURIComponent(detail?.pemegang?.nip || "")}`,
                `Daftar_Barang_${(detail?.pemegang?.nama || "pemegang").replace(/\s/g, "_")}.pdf`,
                { label: `Daftar Barang ${detail?.pemegang?.nama}` },
              ).catch(() => {})}
              data-testid="penggunaan-unduh-daftar">
              <FileText className="w-3.5 h-3.5 mr-1.5" />Unduh Daftar (PDF Lampiran BAST)
            </Button>
            <ul className="space-y-2">
              {(detail?.rows || []).map((a) => (
                <li key={a.id} className="rounded-lg border border-border p-2.5 text-xs" data-testid={`penggunaan-aset-${a.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-foreground">{a.asset_name || "-"}</p>
                    {a.ada_bast ? (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">BAST ✓</span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">Tanpa BAST</span>
                    )}
                  </div>
                  <p className="text-muted-foreground mt-1 font-mono">{a.asset_code} · NUP {a.NUP}</p>
                  <p className="text-muted-foreground mt-0.5">
                    {[a.location, a.condition, a.inventory_status].filter(Boolean).join(" · ") || "—"}
                  </p>
                </li>
              ))}
            </ul>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
