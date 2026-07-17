import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ClipboardList, CheckCircle2, XCircle, Coins, FileDown,
  Plus, Search, Send, Trash2,
} from "lucide-react";
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

/**
 * Perencanaan — Fase 4 tahap awal: kandidat usulan RKBMN pemeliharaan
 * (PMK 153/2021). Menyaring aset layak (Baik/RR, dioperasikan) vs tidak
 * (rusak berat/idle/nonaktif) + riwayat biaya pemeliharaan per aset,
 * plus register usulan RKBMN berstatus. Sanding SBSK menyusul.
 */
export default function PerencanaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tahun, setTahun] = useState(new Date().getFullYear());
  // Register usulan RKBMN: data GET + dialog usulan baru {data, aset, saving}
  const [usulan, setUsulan] = useState(null);
  const [formUsulan, setFormUsulan] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  const { minta, transitionDialog } = useTransitionDialog();

  const muatUsulan = useCallback(() => {
    axios.get(`${API}/perencanaan/usulan`)
      .then((r) => setUsulan(r.data))
      .catch(() => {});
  }, []);

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
        <div className="max-w-5xl mx-auto flex items-center gap-3">
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
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Perencanaan — Kandidat RKBMN Pemeliharaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Saringan kelayakan usulan (PMK 153/2021) + riwayat biaya per aset
            </p>
          </div>
          <select
            value={tahun}
            onChange={(e) => setTahun(parseInt(e.target.value, 10))}
            className="h-8 px-2 rounded-lg border border-border bg-background text-xs text-foreground flex-shrink-0"
            data-testid="perencanaan-tahun"
            aria-label="Tahun anggaran riwayat biaya"
          >
            {[th, th - 1, th - 2].map((t) => <option key={t} value={t}>TA {t}</option>)}
          </select>
          <button
            type="button"
            onClick={() => downloadFileWithProgress(
              `${API}/perencanaan/rkbmn-pemeliharaan-xlsx?tahun=${tahun}`,
              `Usulan_RKBMN_Pemeliharaan_TA${tahun + 1}.xlsx`,
              { label: "Kertas kerja usulan RKBMN" },
            ).catch(() => {})}
            className="h-8 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1.5 hover:bg-muted flex-shrink-0 min-h-0"
            data-testid="perencanaan-xlsx"
          >
            <FileDown className="w-3.5 h-3.5" /><span className="hidden sm:inline">Kertas Kerja</span>
          </button>
          <button
            type="button"
            onClick={() => downloadFileWithProgress(
              `${API}/perencanaan/usulan/export`, "register_usulan_rkbmn.csv",
              { label: "Register usulan RKBMN (CSV)" },
            ).catch(() => {})}
            className="h-8 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1.5 hover:bg-muted flex-shrink-0 min-h-0"
            data-testid="perencanaan-export"
          >
            <FileDown className="w-3.5 h-3.5" /><span className="hidden sm:inline">CSV</span>
          </button>
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
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="perencanaan-stat-layak">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.layak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Layak diusulkan</p>
              </div>
              <div className="bg-card rounded-xl border border-red-500/40 p-3 text-center" data-testid="perencanaan-stat-tidak">
                <XCircle className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{data.ringkasan.tidak}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Tidak layak (lihat alasan)</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="perencanaan-stat-biaya">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(data.ringkasan.total_biaya_riwayat)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Biaya pemeliharaan TA {data.tahun} (aset layak)</p>
              </div>
            </div>

            {/* ── Register usulan RKBMN per unit (PMK 153/2021 + KMK 128/2022) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="perencanaan-usulan">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <Send className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Usulan RKBMN per Unit</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Draft → diajukan → disetujui PB → dikirim Pengelola → hasil penelaahan
                  </p>
                </div>
                {(usulan?.ringkasan?.berjalan || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold flex-shrink-0">
                    {usulan.ringkasan.berjalan} berjalan
                  </span>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => { setCari(""); setHasilCari([]); setFormUsulan({ data: { tahun_rkbmn: String(th + 2), jenis: "pemeliharaan", unit_pengusul: "", uraian: "", volume: "1", satuan: "unit", keterangan: "" }, aset: null, saving: false }); }}
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
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">SPTJM</span>
                        )}
                        {u.reviu_apip && (
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold">Reviu APIP</span>
                        )}
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{u.uraian}</p>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[u.unit_pengusul, `${u.volume} ${u.satuan}`,
                          u.asset_name && `aset: ${u.asset_name} (${u.asset_code} · ${u.NUP})`,
                          u.keterangan, `oleh ${u.created_by}`].filter(Boolean).join(" · ")}
                      </p>
                      <div className="flex gap-1.5 mt-1.5 flex-wrap items-center">
                        {(usulan.transisi?.[u.status] || []).map((ke) => (
                          <Button key={ke} size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => pindahStatusUsulan(u, ke)}
                            data-testid={`perencanaan-usulan-${u.id}-ke-${ke}`}>
                            {usulan.label_status?.[ke] || ke}
                          </Button>
                        ))}
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
                    <li key={a.id} className="px-3 py-2 flex items-center justify-between gap-2" data-testid={`perencanaan-layak-${a.id}`}>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-muted-foreground font-mono truncate">
                          {a.asset_code} · {a.NUP}{a.location ? ` · ${a.location}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_KONDISI[a.condition] || "bg-muted text-muted-foreground"}`}>
                          {a.condition || "-"}
                        </span>
                        <span className="text-xs font-bold text-foreground">
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
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
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
                  <Input id="usl-unit" placeholder="cth. Satker Balai X" value={formUsulan.data.unit_pengusul}
                    onChange={(e) => setFormUsulan((f) => ({ ...f, data: { ...f.data, unit_pengusul: e.target.value } }))}
                    data-testid="usulan-unit" />
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

      {confirmDialog}
      {transitionDialog}
    </div>
  );
}
