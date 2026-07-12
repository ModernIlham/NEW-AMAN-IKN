import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, UserCheck, ChevronLeft, ChevronRight,
  BadgeCheck, FileWarning, FileText, Plus, X, Trash2, ScrollText,
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
  // Data register PSP: {items, ringkasan, label_jenis, catatan}
  const [psp, setPsp] = useState(null);
  // Dialog catat SK PSP: {data, aset: [], saving}
  const [formPsp, setFormPsp] = useState(null);
  const [cariPsp, setCariPsp] = useState("");
  const [hasilCariPsp, setHasilCariPsp] = useState([]);
  const cariPspTimer = useRef(null);
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

  const loadPsp = useCallback(() => {
    axios.get(`${API}/penggunaan/psp`)
      .then((r) => setPsp(r.data))
      .catch(() => toast.error("Gagal memuat register PSP"));
  }, []);

  useEffect(() => { load(1, ""); loadIdle(); loadPsp(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Pencarian aset (debounce) untuk dialog catat SK PSP
  useEffect(() => {
    if (!formPsp || cariPsp.trim().length < 2) { setHasilCariPsp([]); return undefined; }
    clearTimeout(cariPspTimer.current);
    cariPspTimer.current = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cariPsp.trim(), page_size: 8 } });
        setHasilCariPsp(r.data?.items || []);
      } catch { setHasilCariPsp([]); }
    }, 300);
    return () => clearTimeout(cariPspTimer.current);
  }, [cariPsp, formPsp]);

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

  const simpanPsp = async () => {
    if (!formPsp) return;
    if (formPsp.aset.length === 0) { toast.error("Tambahkan minimal satu aset"); return; }
    setFormPsp((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penggunaan/psp`, {
        ...formPsp.data, asset_ids: formPsp.aset.map((a) => a.id),
      });
      toast.success("SK penetapan tercatat");
      setFormPsp(null);
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat SK");
      setFormPsp((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusPsp = async (sk) => {
    try {
      await axios.delete(`${API}/penggunaan/psp/${sk.id}`);
      toast.success("Catatan SK dihapus");
      loadPsp();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus SK");
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

        {/* ── Register SK Penetapan Penggunaan (PSP) ── */}
        {psp && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penggunaan-psp">
            <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-sky-500" />
              <p className="text-xs font-bold text-foreground flex-1">Penetapan Status Penggunaan (PMK 40/2024)</p>
              <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                {psp.ringkasan?.aset_tercakup || 0}/{psp.ringkasan?.total_aset || 0} aset tercakup
              </span>
              <Button size="sm" onClick={() => { setCariPsp(""); setHasilCariPsp([]); setFormPsp({ data: { nomor_sk: "", tanggal_sk: new Date().toISOString().slice(0, 10), jenis: "psp", penetap: "", keterangan: "" }, aset: [], saving: false }); }}
                className="h-7 text-[11px] min-h-0 bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-psp-tambah">
                <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat SK</span>
              </Button>
            </div>
            {(psp.items || []).length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-5 px-4">
                Belum ada SK penetapan tercatat — mulai dari SK PSP terbaru satker.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {psp.items.map((sk) => (
                  <li key={sk.id} className="p-3" data-testid={`penggunaan-psp-${sk.id}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                        {psp.label_jenis?.[sk.jenis] || sk.jenis}
                      </span>
                      <p className="text-xs font-semibold text-foreground flex-1 min-w-[120px] truncate">{sk.nomor_sk}</p>
                      <span className="text-[11px] text-muted-foreground">{sk.tanggal_sk} · {(sk.aset || []).length} aset</span>
                      {isAdmin && (
                        <button type="button" aria-label="Hapus SK" onClick={() => hapusPsp(sk)}
                          className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                      {[sk.penetap && `Penetap: ${sk.penetap}`, sk.keterangan,
                        `oleh ${sk.created_by}`].filter(Boolean).join(" · ")}
                    </p>
                    <ul className="mt-1 space-y-0.5">
                      {(sk.aset || []).slice(0, 4).map((a) => (
                        <li key={a.asset_id} className="text-[11px] text-foreground/80 truncate">
                          {a.asset_name} <span className="font-mono text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                        </li>
                      ))}
                      {(sk.aset || []).length > 4 && (
                        <li className="text-[11px] text-muted-foreground">+{sk.aset.length - 4} aset lainnya</li>
                      )}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
            <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{psp.catatan}</p>
          </div>
        )}

        <p className="text-center text-[11px] text-muted-foreground pb-4">
          Alih status antar Pengguna & BAST digital penetapan (PMK 40/2024) menyusul — masterplan Fase 3.
        </p>
      </main>

      {/* ── Dialog catat SK PSP ── */}
      <Dialog open={!!formPsp} onOpenChange={(o) => { if (!o) setFormPsp(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat SK Penetapan Penggunaan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu catatan per SK — cakupan aset dipetakan agar terlihat aset yang belum ter-PSP.
            </DialogDescription>
          </DialogHeader>
          {formPsp && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-nomor">Nomor SK</label>
                <Input id="psp-nomor" placeholder="KEP-1/MK.6/2026" value={formPsp.data.nomor_sk}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, nomor_sk: e.target.value } }))}
                  data-testid="penggunaan-psp-nomor" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-tgl">Tanggal SK</label>
                <Input id="psp-tgl" type="date" value={formPsp.data.tanggal_sk}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, tanggal_sk: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-jenis">Jenis</label>
                <select id="psp-jenis" value={formPsp.data.jenis}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="penggunaan-psp-jenis">
                  {Object.entries(psp?.label_jenis || { psp: "PSP" }).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-penetap">Penetap</label>
                <Input id="psp-penetap" placeholder="Pengelola/Pengguna Barang" value={formPsp.data.penetap}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, penetap: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-ket">Keterangan</label>
                <Input id="psp-ket" value={formPsp.data.keterangan}
                  onChange={(e) => setFormPsp((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="psp-cari">Tambah aset</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="psp-cari" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                    value={cariPsp} onChange={(e) => setCariPsp(e.target.value)} data-testid="penggunaan-psp-cari" />
                  {hasilCariPsp.length > 0 && cariPsp.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {hasilCariPsp.map((a) => (
                        <button key={a.id} type="button"
                          onClick={() => { setFormPsp((f) => (f.aset.some((x) => x.id === a.id) ? f : { ...f, aset: [...f.aset, a] })); setCariPsp(""); setHasilCariPsp([]); }}
                          className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                          <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                          <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {formPsp.aset.length > 0 && (
                <ul className="col-span-2 space-y-1">
                  {formPsp.aset.map((a) => (
                    <li key={a.id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                        <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                      </span>
                      <button type="button" aria-label="Keluarkan aset"
                        onClick={() => setFormPsp((f) => ({ ...f, aset: f.aset.filter((x) => x.id !== a.id) }))}
                        className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setFormPsp(null)}>Batal</Button>
            <Button onClick={simpanPsp} disabled={formPsp?.saving || (formPsp?.aset?.length || 0) === 0}
              className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="penggunaan-psp-simpan">
              {formPsp?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ScrollText className="w-4 h-4 mr-1.5" />}Catat SK
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
