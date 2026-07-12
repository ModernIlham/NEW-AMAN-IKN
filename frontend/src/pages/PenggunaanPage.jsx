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
 * inventarisasi — plus daftar pantau BMN IDLE (PMK 120/2024): kandidat
 * otomatis dari status Nonaktif / tanpa pengguna, tiket klarifikasi →
 * digunakan kembali / usul serah → diserahkan ke Pengelola.
 * PSP/alih status menyusul (PMK 40/2024).
 */
export default function PenggunaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalLengkap, setTotalLengkap] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  // Dialog daftar aset: {pemegang, rows, loading}
  const [detail, setDetail] = useState(null);
  // Data BMN idle: {kandidat, tiket, ringkasan, label_status, catatan}
  const [idle, setIdle] = useState(null);
  // Dialog transisi idle: {tiket, ke, fields{}, saving}
  const [trxIdle, setTrxIdle] = useState(null);
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

  const loadIdle = useCallback(() => {
    axios.get(`${API}/penggunaan/idle`)
      .then((r) => setIdle(r.data))
      .catch(() => toast.error("Gagal memuat daftar BMN idle"));
  }, []);

  useEffect(() => { load(1, ""); loadIdle(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

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

  const bukaKlarifikasi = async (k) => {
    try {
      await axios.post(`${API}/penggunaan/idle`, { asset_id: k.asset_id });
      toast.success("Tiket klarifikasi dibuka");
      loadIdle();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka tiket");
    }
  };

  const kirimTransisiIdle = async (tiket, ke, fields = {}) => {
    try {
      await axios.post(`${API}/penggunaan/idle/${tiket.id}/status`, { status: ke, ...fields });
      toast.success(`Status: ${idle?.label_status?.[ke] || ke}`);
      setTrxIdle(null);
      loadIdle();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
      setTrxIdle((t) => (t ? { ...t, saving: false } : t));
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

        {/* ── BMN Idle (PMK 120/2024) ── */}
        {idle && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penggunaan-idle">
            <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
              <FileWarning className="w-4 h-4 text-amber-500" />
              <p className="text-xs font-bold text-foreground flex-1">BMN Idle — Daftar Pantau (PMK 120/2024)</p>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                {idle.ringkasan?.kandidat || 0} kandidat
              </span>
            </div>
            {(idle.kandidat || []).length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-5 px-4">
                Tidak ada indikasi idle — seluruh aset berstatus aktif dan berpengguna.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {idle.kandidat.slice(0, 50).map((k) => (
                  <li key={k.asset_id} className="p-3 flex flex-wrap items-center gap-2" data-testid={`penggunaan-idle-${k.asset_id}`}>
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-semibold text-foreground truncate">
                        {k.asset_name || "-"} <span className="font-mono font-normal text-muted-foreground">({k.asset_code} · {k.NUP})</span>
                      </span>
                      <span className="block text-[11px] text-muted-foreground truncate">{k.alasan}{k.location && ` · ${k.location}`}</span>
                    </span>
                    {k.tiket ? (
                      <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                        {idle.label_status?.[k.tiket.status] || k.tiket.status}
                      </span>
                    ) : (
                      <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                        onClick={() => bukaKlarifikasi(k)} data-testid={`penggunaan-idle-klarifikasi-${k.asset_id}`}>
                        Klarifikasi
                      </Button>
                    )}
                  </li>
                ))}
                {(idle.kandidat || []).length > 50 && (
                  <li className="text-[11px] text-muted-foreground text-center py-2">Menampilkan 50 kandidat pertama.</li>
                )}
              </ul>
            )}
            {(idle.tiket || []).length > 0 && (
              <div className="border-t border-border">
                <p className="px-3 pt-2.5 pb-1 text-[11px] font-semibold text-foreground/80">Tiket penanganan</p>
                <ul className="divide-y divide-border/60">
                  {idle.tiket.map((t) => (
                    <li key={t.id} className="p-3" data-testid={`penggunaan-tiket-${t.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                          {idle.label_status?.[t.status] || t.status}
                        </span>
                        <p className="text-xs font-semibold text-foreground flex-1 min-w-[120px] truncate">
                          {t.asset_name} <span className="font-mono font-normal text-muted-foreground">({t.asset_code} · {t.NUP})</span>
                        </p>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {t.alasan}
                        {t.nomor_usulan && ` · Usulan ${t.nomor_usulan}`}
                        {t.nomor_bast_serah && ` · BAST ${t.nomor_bast_serah}`}
                        {t.keterangan && ` · ${t.keterangan}`}
                        {` · oleh ${t.created_by}`}
                      </p>
                      {isAdmin && ["klarifikasi", "usul_serah"].includes(t.status) && (
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          {t.status === "klarifikasi" && (
                            <>
                              <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                                onClick={() => kirimTransisiIdle(t, "digunakan_kembali")}>
                                Digunakan Kembali
                              </Button>
                              <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                                onClick={() => setTrxIdle({ tiket: t, ke: "usul_serah", saving: false, fields: { nomor_usulan: "" } })}
                                data-testid={`penggunaan-idle-usul-${t.id}`}>
                                Usul Serah
                              </Button>
                            </>
                          )}
                          {t.status === "usul_serah" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setTrxIdle({ tiket: t, ke: "diserahkan", saving: false, fields: { nomor_bast_serah: "" } })}
                              data-testid={`penggunaan-idle-serah-${t.id}`}>
                              Diserahkan (BAST)
                            </Button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{idle.catatan}</p>
          </div>
        )}

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          PSP dan alih status penggunaan (PMK 40/2024) menyusul — masterplan Fase 3.
        </p>
      </main>

      {/* ── Dialog transisi tiket idle ── */}
      <Dialog open={!!trxIdle} onOpenChange={(o) => { if (!o) setTrxIdle(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{idle?.label_status?.[trxIdle?.ke] || trxIdle?.ke}</DialogTitle>
            <DialogDescription className="text-xs">
              {trxIdle?.tiket && `${trxIdle.tiket.asset_name} (${trxIdle.tiket.asset_code} · ${trxIdle.tiket.NUP})`}
            </DialogDescription>
          </DialogHeader>
          {trxIdle?.ke === "usul_serah" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="idle-usulan">No. Surat Usulan Penyerahan</label>
              <Input id="idle-usulan" placeholder="S-12/SATKER/2026" value={trxIdle.fields.nomor_usulan}
                onChange={(e) => setTrxIdle((t) => ({ ...t, fields: { ...t.fields, nomor_usulan: e.target.value } }))}
                data-testid="penggunaan-idle-nomor-usulan" />
            </div>
          )}
          {trxIdle?.ke === "diserahkan" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="idle-bast">No. BAST Penyerahan ke Pengelola</label>
              <Input id="idle-bast" placeholder="BAST-01/KNL.05/2026" value={trxIdle.fields.nomor_bast_serah}
                onChange={(e) => setTrxIdle((t) => ({ ...t, fields: { ...t.fields, nomor_bast_serah: e.target.value } }))}
                data-testid="penggunaan-idle-nomor-bast" />
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setTrxIdle(null)}>Batal</Button>
            <Button disabled={trxIdle?.saving}
              onClick={() => { setTrxIdle((t) => ({ ...t, saving: true })); kirimTransisiIdle(trxIdle.tiket, trxIdle.ke, trxIdle.fields); }}
              className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-idle-simpan">
              Simpan
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
