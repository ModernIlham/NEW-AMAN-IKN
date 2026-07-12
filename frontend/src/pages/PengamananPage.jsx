import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ShieldCheck, Scale, BadgeCheck, Camera,
  Gavel, Plus, QrCode, MapPin, Search, Trash2, UserCheck, FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_KEKURANGAN = {
  foto: Camera,
  register: QrCode,
  lokasi: MapPin,
  pengguna: UserCheck,
  bast: FileText,
};

/**
 * Pengamanan — Fase 3 tahap awal: dasbor tertib administrasi data aset
 * (penangkal temuan "barang tanpa foto/label/dokumen") + daftar pantau
 * sengketa dari data inventarisasi. Arsip dokumen kepemilikan & jadwal
 * pemeliharaan menyusul sesuai masterplan.
 */
const WARNA_STATUS_KASUS = {
  identifikasi: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  mediasi: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  blokir: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  litigasi: "bg-red-500/15 text-red-600 dark:text-red-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
};

export default function PengamananPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog daftar aset kurang: {jenis, label, rows, loading}
  const [detail, setDetail] = useState(null);
  // Register kasus: data GET + dialog kasus baru {data, aset, saving}
  const [kasus, setKasus] = useState(null);
  const [formKasus, setFormKasus] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muatKasus = useCallback(() => {
    axios.get(`${API}/pengamanan/kasus`)
      .then((r) => setKasus(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    axios.get(`${API}/pengamanan/ringkasan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat ringkasan pengamanan"))
      .finally(() => setLoading(false));
    muatKasus();
  }, [muatKasus]);

  useEffect(() => {
    if (!formKasus || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, formKasus]);

  const simpanKasus = async () => {
    if (!formKasus?.aset) return;
    setFormKasus((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengamanan/kasus`, {
        ...formKasus.data, asset_id: formKasus.aset.id,
      });
      toast.success("Kasus dibuka");
      setFormKasus(null);
      muatKasus();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuka kasus");
      setFormKasus((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const pindahStatusKasus = async (k, ke) => {
    const label = kasus?.label_status?.[ke] || ke;
    const catatan = window.prompt(`Catatan transisi ke "${label}" (opsional):`, "");
    if (catatan === null) return;
    try {
      await axios.post(`${API}/pengamanan/kasus/${k.id}/status`, { status: ke, catatan });
      toast.success(`Status kasus: ${label}`);
      muatKasus();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status kasus");
    }
  };

  const hapusKasus = async (k) => {
    const ok = await confirm({
      title: "Hapus kasus?",
      description: `${k.asset_name || k.asset_id} — ${k.uraian}`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengamanan/kasus/${k.id}`);
      toast.success("Kasus dihapus");
      muatKasus();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus kasus");
    }
  };

  const openDetail = async (jenis, label) => {
    setDetail({ jenis, label, rows: [], loading: true });
    try {
      const r = await axios.get(`${API}/pengamanan/aset-kurang`, {
        params: { jenis, page_size: 200 },
      });
      setDetail({ jenis, label, rows: r.data?.items || [], total: r.data?.total || 0, loading: false });
    } catch {
      toast.error("Gagal memuat daftar aset");
      setDetail(null);
    }
  };

  const pct = (n) => (data?.total_aset ? Math.round((n / data.total_aset) * 100) : 0);

  return (
    <div className="min-h-screen bg-background" data-testid="pengamanan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengamanan-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center flex-shrink-0">
            <ShieldCheck className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pengamanan — Tertib Administrasi</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Kesehatan data {data?.total_aset ?? "…"} aset + daftar pantau sengketa
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-amber-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="pengamanan-stat-lengkap">
                <BadgeCheck className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.lengkap}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Data lengkap ({pct(data.lengkap)}%)</p>
              </div>
              {Object.entries(data.label_kekurangan || {}).map(([jenis, label]) => {
                const Icon = IKON_KEKURANGAN[jenis] || FileText;
                const n = data.kekurangan?.[jenis] || 0;
                return (
                  <button
                    key={jenis}
                    type="button"
                    onClick={() => n > 0 && openDetail(jenis, label)}
                    disabled={n === 0}
                    className={`bg-card rounded-xl border p-3 text-center transition-colors min-w-0 min-h-0 ${
                      n > 0 ? "border-amber-500/40 hover:bg-amber-500/10" : "border-border opacity-60"
                    }`}
                    data-testid={`pengamanan-stat-${jenis}`}
                  >
                    <Icon className={`w-5 h-5 mx-auto mb-1 ${n > 0 ? "text-amber-500" : "text-muted-foreground"}`} />
                    <p className="text-lg font-bold text-foreground leading-none">{n}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
                  </button>
                );
              })}
            </div>

            {/* ── Daftar pantau sengketa ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <Scale className="w-4 h-4 text-violet-500" />
                <p className="text-xs font-bold text-foreground">Daftar Pantau Sengketa</p>
                <span className="px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                  {data.jumlah_sengketa}
                </span>
              </div>
              {data.jumlah_sengketa === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Tidak ada aset berstatus sengketa — data dari klasifikasi inventarisasi.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.sengketa.map((s) => (
                    <li key={s.id} className="p-3" data-testid={`pengamanan-sengketa-${s.id}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-foreground">{s.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground">{s.asset_code} · {s.NUP}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[s.nomor_perkara && `Perkara ${s.nomor_perkara}`,
                          s.pihak_bersengketa && `vs ${s.pihak_bersengketa}`,
                          s.keterangan].filter(Boolean).join(" · ") || "—"}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── Register BMN bermasalah/sengketa (pustaka §11) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pengamanan-kasus">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <Gavel className="w-4 h-4 text-red-500 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Register BMN Bermasalah</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Identifikasi → mediasi → blokir → litigasi → selesai (PP 27/2014 Ps. 42)
                  </p>
                </div>
                {(kasus?.ringkasan?.aktif || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold flex-shrink-0">
                    {kasus.ringkasan.aktif} aktif
                  </span>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => { setCari(""); setHasilCari([]); setFormKasus({ data: { kategori: "dikuasai_pihak_lain", uraian: "", pihak_lawan: "", nomor_perkara: "", pendamping: "" }, aset: null, saving: false }); }}
                  data-testid="pengamanan-kasus-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Buka Kasus</span>
                </Button>
              </div>
              {(kasus?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada kasus — buka kasus bila ada BMN dikuasai pihak lain, tumpang tindih sertipikat, atau berperkara.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {kasus.items.map((k) => (
                    <li key={k.id} className="p-3" data-testid={`pengamanan-kasus-${k.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS_KASUS[k.status] || "bg-muted"}`}>
                          {kasus.label_status?.[k.status] || k.status}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                          {kasus.label_kategori?.[k.kategori] || k.kategori}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{k.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{k.asset_code} · {k.NUP}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[k.uraian, `vs ${k.pihak_lawan}`,
                          k.nomor_perkara && `Perkara ${k.nomor_perkara}`,
                          k.pendamping && `Pendamping ${k.pendamping}`,
                          `oleh ${k.created_by}`].filter(Boolean).join(" · ")}
                      </p>
                      <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                        {(kasus.transisi?.[k.status] || []).map((ke) => (
                          <Button key={ke} size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => pindahStatusKasus(k, ke)}
                            data-testid={`pengamanan-kasus-${k.id}-ke-${ke}`}>
                            {kasus.label_status?.[ke] || ke}
                          </Button>
                        ))}
                        {isAdmin && (
                          <button type="button" onClick={() => hapusKasus(k)} aria-label="Hapus kasus"
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

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              {kasus?.catatan || "Arsip dokumen kepemilikan (sertifikat/BPKB) menyusul — masterplan Fase 3."}
            </p>
          </>
        )}
      </main>

      {/* ── Dialog buka kasus ── */}
      <Dialog open={!!formKasus} onOpenChange={(o) => { if (!o) setFormKasus(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Buka Kasus BMN Bermasalah</DialogTitle>
            <DialogDescription className="text-xs">
              Register pendamping (pustaka §11) — bahan laporan wasdal; bukan kanal resmi.
            </DialogDescription>
          </DialogHeader>
          {formKasus && (
            <div className="space-y-3">
              {!formKasus.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-cari">Cari aset</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="kss-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="kasus-cari" />
                  </div>
                  {mencari && <p className="text-[11px] text-muted-foreground mt-1">Mencari…</p>}
                  <ul className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormKasus((f) => ({ ...f, aset: a }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`kasus-pilih-${a.id}`}>
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
                    {formKasus.aset.asset_name || "-"}{" "}
                    <span className="font-mono text-[10px] text-muted-foreground">({formKasus.aset.asset_code} · {formKasus.aset.NUP})</span>
                  </span>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormKasus((f) => ({ ...f, aset: null }))}>
                    Ganti
                  </Button>
                </div>
              )}
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-kategori">Kategori kasus</label>
                <select id="kss-kategori" value={formKasus.data.kategori}
                  onChange={(e) => setFormKasus((f) => ({ ...f, data: { ...f.data, kategori: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="kasus-kategori">
                  {Object.entries(kasus?.label_kategori || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-uraian">Uraian kasus</label>
                <Input id="kss-uraian" placeholder="cth. Tanah kantor diokupasi warga sejak 2024"
                  value={formKasus.data.uraian}
                  onChange={(e) => setFormKasus((f) => ({ ...f, data: { ...f.data, uraian: e.target.value } }))}
                  data-testid="kasus-uraian" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-lawan">Pihak lawan</label>
                  <Input id="kss-lawan" value={formKasus.data.pihak_lawan}
                    onChange={(e) => setFormKasus((f) => ({ ...f, data: { ...f.data, pihak_lawan: e.target.value } }))}
                    data-testid="kasus-lawan" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-perkara">No. perkara (ops.)</label>
                  <Input id="kss-perkara" value={formKasus.data.nomor_perkara}
                    onChange={(e) => setFormKasus((f) => ({ ...f, data: { ...f.data, nomor_perkara: e.target.value } }))}
                    data-testid="kasus-perkara" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kss-pendamping">Pendamping (ops., mis. JPN Kejari)</label>
                <Input id="kss-pendamping" value={formKasus.data.pendamping}
                  onChange={(e) => setFormKasus((f) => ({ ...f, data: { ...f.data, pendamping: e.target.value } }))}
                  data-testid="kasus-pendamping" />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormKasus(null)}>Batal</Button>
                <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white"
                  disabled={formKasus.saving || !formKasus.aset || !formKasus.data.uraian.trim() || !formKasus.data.pihak_lawan.trim()}
                  onClick={simpanKasus} data-testid="kasus-simpan">
                  {formKasus.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Buka Kasus"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {confirmDialog}

      {/* ── Dialog daftar aset kurang ── */}
      <Dialog open={!!detail} onOpenChange={(o) => { if (!o) setDetail(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{detail?.label}</DialogTitle>
            <DialogDescription className="text-xs">
              {detail?.total ?? 0} aset — lengkapi lewat modul Inventarisasi (edit aset / mode lapangan).
            </DialogDescription>
          </DialogHeader>
          {detail?.loading ? (
            <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-amber-600" /></div>
          ) : (
            <ul className="space-y-1.5">
              {(detail?.rows || []).map((a) => (
                <li key={a.id} className="rounded-lg border border-border p-2 text-xs flex items-center justify-between gap-2">
                  <span className="text-foreground/90 min-w-0 truncate">{a.asset_name || "-"}</span>
                  <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{a.asset_code} · {a.NUP}</span>
                </li>
              ))}
              {(detail?.rows || []).length === 200 && (
                <li className="text-[11px] text-muted-foreground text-center pt-1">Menampilkan 200 pertama.</li>
              )}
            </ul>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
