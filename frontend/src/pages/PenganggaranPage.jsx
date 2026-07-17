import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, CalendarClock, Loader2, Wallet, Plus, Search, X, Coins,
  Download, TicketCheck, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WARNA_STATUS = {
  diusulkan: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  disetujui_telaah: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  masuk_dipa: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  terealisasi: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  ditolak: "bg-muted text-muted-foreground",
};

/**
 * Penganggaran — Fase 4 tahap awal: register usulan berstatus
 * (PMK 62/2023 + PMK 153/2021, pustaka §9): diusulkan → disetujui telaah
 * → masuk DIPA → terealisasi; nilai tercatat per tahap. Kanal resmi tetap
 * SIMAN V2/SAKTI — AMAN mencatat jejak per usulan/aset, bukan memutus.
 */
export default function PenganggaranPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog usulan baru: {data, aset: [], saving}
  const [form, setForm] = useState(null);
  // Dialog transisi: {usulan, ke, fields{}, saving}
  const [trx, setTrx] = useState(null);
  // Kalender penganggaran: data GET + dialog tahapan baru {data, saving}
  const [kalender, setKalender] = useState(null);
  const [formTahapan, setFormTahapan] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    axios.get(`${API}/penganggaran`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register penganggaran"))
      .finally(() => setLoading(false));
    axios.get(`${API}/penganggaran/kalender`)
      .then((r) => setKalender(r.data))
      .catch(() => {});
  }, []);
  useEffect(() => { muat(); }, [muat]);

  useEffect(() => {
    if (!form || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, form]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;
  const labelStatus = data?.label_status || {};
  // Usulan RKBMN (Perencanaan) utk dropdown tautan — FK rkbmn_id backend
  // sudah lengkap; ini mengaktifkannya di UI (audit G4 #1).
  const [rkbmnList, setRkbmnList] = React.useState([]);
  React.useEffect(() => {
    axios.get(`${API}/perencanaan/usulan`)
      .then((r) => setRkbmnList(r.data?.items || []))
      .catch(() => {});
  }, []);
  const labelJenis = data?.label_jenis || {};
  const labelAkun = data?.label_akun || {};

  const simpanUsulan = async () => {
    if (!form) return;
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penganggaran`, {
        ...form.data,
        rkbmn_id: form.data.rkbmn_id || "",
        nilai_usulan: Number(form.data.nilai_usulan || 0),
        asset_ids: form.aset.map((a) => a.id),
      });
      toast.success("Usulan penganggaran dicatat");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat usulan");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const kirimTransisi = async () => {
    if (!trx) return;
    setTrx((t) => ({ ...t, saving: true }));
    try {
      await axios.post(`${API}/penganggaran/${trx.usulan.id}/status`, {
        status: trx.ke,
        ...trx.fields,
        nilai_disetujui: Number(trx.fields.nilai_disetujui || 0),
        nilai_dipa: Number(trx.fields.nilai_dipa || 0),
        nilai_realisasi: Number(trx.fields.nilai_realisasi || 0),
      });
      toast.success(`Status: ${labelStatus[trx.ke] || trx.ke}`);
      setTrx(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
      setTrx((t) => (t ? { ...t, saving: false } : t));
    }
  };

  const tolak = async (u) => {
    const ok = await confirm({
      title: "Tolak usulan?",
      description: `${u.uraian} (TA ${u.tahun_anggaran}).`,
      confirmLabel: "Tolak", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.post(`${API}/penganggaran/${u.id}/status`, { status: "ditolak" });
      toast.success("Usulan ditolak");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah status");
    }
  };

  const simpanTahapan = async () => {
    if (!formTahapan) return;
    setFormTahapan((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penganggaran/kalender`, formTahapan.data);
      toast.success("Tahapan kalender dicatat");
      setFormTahapan(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat tahapan");
      setFormTahapan((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusTahapan = async (t) => {
    const ok = await confirm({
      title: "Hapus tahapan kalender?",
      description: `${t.nama} — tenggat ${t.tanggal} (TA ${t.tahun_anggaran}).`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/penganggaran/kalender/${t.id}`);
      toast.success("Tahapan dihapus");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus tahapan");
    }
  };

  const setTrxField = (k, v) => setTrx((t) => ({ ...t, fields: { ...t.fields, [k]: v } }));
  const r = data?.ringkasan;

  return (
    <div className="min-h-screen bg-background" data-testid="penganggaran-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="penganggaran-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
            <Wallet className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Penganggaran — Register Usulan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              RKBMN → RKA-K/L → DIPA → realisasi (PMK 62/2023 + 153/2021)
            </p>
          </div>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            onClick={() => downloadFileWithProgress(`${API}/penganggaran/export`, "register_penganggaran.csv", { label: "Ekspor Register Penganggaran (CSV)" }).catch(() => {})}
            data-testid="penganggaran-export">
            <Download className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">CSV</span>
          </Button>
          <Button size="sm"
            onClick={() => { setCari(""); setHasilCari([]); setForm({ data: { jenis: "pemeliharaan", uraian: "", tahun_anggaran: String(new Date().getFullYear() + 2), nilai_usulan: "", akun: "523", sumber: "", keterangan: "" }, aset: [], saving: false }); }}
            className="bg-teal-600 hover:bg-teal-700 text-white flex-shrink-0" data-testid="penganggaran-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Catat Usulan</span>
          </Button>
          <BookingNomorButton modul="penganggaran" jenisNaskah="Laporan" referensi="Usulan Anggaran" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-teal-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penganggaran-stat-berjalan">
                <TicketCheck className="w-5 h-5 text-sky-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">
                  {r.per_status.diusulkan + r.per_status.disetujui_telaah + r.per_status.masuk_dipa}
                </p>
                <p className="text-[10px] text-muted-foreground mt-1">Usulan berjalan</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penganggaran-stat-usulan">
                <Coins className="w-5 h-5 text-teal-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(r.nilai.usulan)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai usulan</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penganggaran-stat-dipa">
                <Coins className="w-5 h-5 text-violet-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(r.nilai.dipa)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai DIPA</p>
              </div>
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="penganggaran-stat-serapan">
                <p className="text-lg font-bold text-foreground leading-none mt-1.5">{r.serapan_persen}%</p>
                <p className="text-[10px] text-muted-foreground mt-1">Serapan ({fmtRp(r.nilai.realisasi)})</p>
                {(data.total_realisasi_pengadaan || 0) > 0 && (
                  <p className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5" title="Total nilai perolehan Pengadaan yang tertaut usulan">
                    Realisasi Pengadaan tertaut: {fmtRp(data.total_realisasi_pengadaan)}
                  </p>
                )}
              </div>
            </div>

            {/* ── Sanding per akun BAS ── */}
            {(data.per_akun || []).length > 0 && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                <div className="px-3 py-2.5 border-b border-border">
                  <p className="text-xs font-bold text-foreground">Sanding Rencana vs Realisasi per Akun BAS</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs" data-testid="penganggaran-sanding">
                    <thead>
                      <tr className="text-muted-foreground border-b border-border/60">
                        <th className="text-left px-3 py-1.5 font-semibold">Akun</th>
                        <th className="text-right px-2 py-1.5 font-semibold">Usulan</th>
                        <th className="text-right px-2 py-1.5 font-semibold">Disetujui</th>
                        <th className="text-right px-2 py-1.5 font-semibold">DIPA</th>
                        <th className="text-right px-2 py-1.5 font-semibold">Realisasi</th>
                        <th className="text-right px-3 py-1.5 font-semibold">Serapan</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {data.per_akun.map((a) => (
                        <tr key={a.akun}>
                          <td className="px-3 py-1.5 text-foreground whitespace-nowrap">
                            <span className="font-mono font-semibold">{a.akun !== "lainnya" ? a.akun : "—"}</span>
                            <span className="text-muted-foreground"> {a.label} · {a.jumlah} usulan</span>
                          </td>
                          <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(a.usulan)}</td>
                          <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(a.disetujui)}</td>
                          <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(a.dipa)}</td>
                          <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(a.realisasi)}</td>
                          <td className="px-3 py-1.5 text-right font-semibold whitespace-nowrap">
                            <span className={a.serapan_persen >= 90 ? "text-emerald-600 dark:text-emerald-400" : a.dipa > 0 ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}>
                              {a.serapan_persen}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── Sanding realisasi per triwulan (pustaka §9) ── */}
            {(data.per_triwulan || []).length > 0 && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penganggaran-triwulan">
                <div className="px-3 py-2.5 border-b border-border">
                  <p className="text-xs font-bold text-foreground">Sanding Realisasi per Triwulan</p>
                  <p className="text-[10px] text-muted-foreground">
                    Triwulan mengikuti tanggal usulan ditandai terealisasi; serapan kumulatif dibanding total DIPA tahun tsb.
                  </p>
                </div>
                <div className="divide-y divide-border/60">
                  {data.per_triwulan.map((g) => (
                    <div key={g.tahun_anggaran}>
                      <div className="px-3 pt-2 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
                        <span className="font-bold text-foreground">TA {g.tahun_anggaran}</span>
                        <span className="text-muted-foreground">DIPA {fmtRp(g.dipa)} · Realisasi {fmtRp(g.realisasi)}</span>
                        <span className={`font-semibold ${g.serapan_persen >= 90 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                          {g.serapan_persen}%
                        </span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-muted-foreground border-b border-border/60">
                              <th className="text-left px-3 py-1.5 font-semibold">Triwulan</th>
                              <th className="text-right px-2 py-1.5 font-semibold">Usulan cair</th>
                              <th className="text-right px-2 py-1.5 font-semibold">Realisasi</th>
                              <th className="text-right px-2 py-1.5 font-semibold">Kumulatif</th>
                              <th className="text-right px-3 py-1.5 font-semibold">Serapan kum.</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border/60">
                            {g.per_triwulan.map((tw) => (
                              <tr key={tw.triwulan}>
                                <td className="px-3 py-1.5 text-foreground whitespace-nowrap font-semibold">{tw.nama}</td>
                                <td className="px-2 py-1.5 text-right text-foreground/90">{tw.jumlah}</td>
                                <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(tw.realisasi)}</td>
                                <td className="px-2 py-1.5 text-right text-foreground/90 whitespace-nowrap">{fmtRp(tw.kumulatif)}</td>
                                <td className="px-3 py-1.5 text-right font-semibold whitespace-nowrap">
                                  <span className={tw.serapan_kumulatif_persen >= 90 ? "text-emerald-600 dark:text-emerald-400" : tw.serapan_kumulatif_persen > 0 ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}>
                                    {tw.serapan_kumulatif_persen}%
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {g.tanpa_triwulan > 0 && (
                        <p className="px-3 pb-2 text-[10px] text-muted-foreground">
                          {g.tanpa_triwulan} usulan terealisasi tanpa tanggal riwayat — masuk total, tidak terpetakan ke triwulan.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Kalender penganggaran (tenggat konfigurabel, pustaka §9.4) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penganggaran-kalender">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <CalendarClock className="w-4 h-4 text-teal-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Kalender Penganggaran</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Tenggat internal K/L — tanggal diisi sendiri sesuai surat edaran unit
                  </p>
                </div>
                {kalender?.ringkasan?.lewat > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold flex-shrink-0">
                    {kalender.ringkasan.lewat} lewat tenggat
                  </span>
                )}
                {isAdmin && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormTahapan({ data: { nama: "", tanggal: "", tahun_anggaran: String(new Date().getFullYear() + 2), keterangan: "" }, saving: false })}
                    data-testid="penganggaran-kalender-tambah">
                    <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Tahapan</span>
                  </Button>
                )}
              </div>
              {(kalender?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada tahapan — contoh: penyampaian RKBMN ke Biro/Sekretariat, batas revisi DIPA.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {kalender.items.map((t) => {
                    const info = t.info_tenggat || {};
                    const warna = info.lewat
                      ? "bg-red-500/15 text-red-600 dark:text-red-400"
                      : (info.sisa_hari ?? 999) <= 30
                        ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                        : "bg-muted text-foreground/70";
                    const label = info.lewat ? "Lewat tenggat"
                      : (info.sisa_hari ?? 999) <= 30 ? `${info.sisa_hari} hari lagi` : t.tanggal;
                    return (
                      <li key={t.id} className="px-3 py-2 flex items-center gap-2" data-testid={`penganggaran-tahapan-${t.id}`}>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${warna}`}>{label}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-foreground truncate">{t.nama}</p>
                          <p className="text-[10px] text-muted-foreground truncate">
                            {t.tanggal} · TA {t.tahun_anggaran}{t.keterangan && ` · ${t.keterangan}`}
                          </p>
                        </div>
                        {isAdmin && (
                          <button type="button" onClick={() => hapusTahapan(t)} aria-label={`Hapus ${t.nama}`}
                            className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10 flex-shrink-0">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* ── Daftar usulan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <Wallet className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Belum ada usulan — mulai dari kertas kerja RKBMN di modul Perencanaan.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((u) => (
                    <li key={u.id} className="p-3" data-testid={`penganggaran-row-${u.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS[u.status] || "bg-muted"}`}>
                          {labelStatus[u.status] || u.status}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-600 dark:text-teal-400 text-[10px] font-semibold">
                          {labelJenis[u.jenis] || u.jenis}{u.akun && ` · ${u.akun}`}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                          TA {u.tahun_anggaran}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{u.uraian}</p>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {`Usulan ${fmtRp(u.nilai_usulan)}`}
                        {Number(u.nilai_disetujui) > 0 && ` · Disetujui ${fmtRp(u.nilai_disetujui)}`}
                        {u.nomor_dipa && ` · DIPA ${u.nomor_dipa} (${fmtRp(u.nilai_dipa)})`}
                        {Number(u.nilai_realisasi) > 0 && ` · Realisasi ${fmtRp(u.nilai_realisasi)}`}
                        {u.sumber && ` · ${u.sumber}`}
                        {` · oleh ${u.created_by}`}
                      </p>
                      {(u.aset || []).length > 0 && (
                        <ul className="mt-1 space-y-0.5">
                          {(u.aset || []).slice(0, 4).map((a) => (
                            <li key={a.asset_id} className="text-[11px] text-foreground/80 truncate">
                              {a.asset_name} <span className="font-mono text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                            </li>
                          ))}
                          {(u.aset || []).length > 4 && (
                            <li className="text-[11px] text-muted-foreground">+{u.aset.length - 4} aset lainnya</li>
                          )}
                        </ul>
                      )}
                      {isAdmin && ["diusulkan", "disetujui_telaah", "masuk_dipa"].includes(u.status) && (
                        <div className="flex gap-1.5 mt-1.5 flex-wrap">
                          {u.status === "diusulkan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => setTrx({ usulan: u, ke: "disetujui_telaah", saving: false, fields: { nomor_hasil_penelaahan: "", nilai_disetujui: u.nilai_usulan } })}
                              data-testid={`penganggaran-telaah-${u.id}`}>
                              Disetujui Telaah
                            </Button>
                          )}
                          {u.status === "disetujui_telaah" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => setTrx({ usulan: u, ke: "masuk_dipa", saving: false, fields: { nomor_dipa: "", nilai_dipa: u.nilai_disetujui || u.nilai_usulan } })}
                              data-testid={`penganggaran-dipa-${u.id}`}>
                              Masuk DIPA
                            </Button>
                          )}
                          {u.status === "masuk_dipa" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setTrx({ usulan: u, ke: "terealisasi", saving: false, fields: { nilai_realisasi: u.nilai_dipa } })}
                              data-testid={`penganggaran-realisasi-${u.id}`}>
                              Terealisasi
                            </Button>
                          )}
                          {u.status === "diusulkan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 text-red-500 hover:text-red-600"
                              onClick={() => tolak(u)}>
                              Tolak
                            </Button>
                          )}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog tahapan kalender baru ── */}
      <Dialog open={!!formTahapan} onOpenChange={(o) => { if (!o) setFormTahapan(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Catat Tahapan Kalender</DialogTitle>
            <DialogDescription className="text-xs">
              Tanggal tenggat internal unit Anda (surat edaran K/L) — bukan dari regulasi pusat.
            </DialogDescription>
          </DialogHeader>
          {formTahapan && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kal-nama">Nama tahapan</label>
                <Input id="kal-nama" placeholder="cth. Penyampaian RKBMN ke Biro"
                  value={formTahapan.data.nama}
                  onChange={(e) => setFormTahapan((f) => ({ ...f, data: { ...f.data, nama: e.target.value } }))}
                  data-testid="kalender-nama" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kal-tanggal">Tanggal tenggat</label>
                <Input id="kal-tanggal" type="date" value={formTahapan.data.tanggal}
                  onChange={(e) => setFormTahapan((f) => ({ ...f, data: { ...f.data, tanggal: e.target.value } }))}
                  data-testid="kalender-tanggal" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kal-ta">TA sasaran</label>
                <Input id="kal-ta" inputMode="numeric" maxLength={4} value={formTahapan.data.tahun_anggaran}
                  onChange={(e) => setFormTahapan((f) => ({ ...f, data: { ...f.data, tahun_anggaran: e.target.value.replace(/\D/g, "") } }))}
                  data-testid="kalender-ta" />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kal-ket">Keterangan (opsional)</label>
                <Input id="kal-ket" placeholder="cth. lampirkan kertas kerja SBSK"
                  value={formTahapan.data.keterangan}
                  onChange={(e) => setFormTahapan((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                  data-testid="kalender-keterangan" />
              </div>
              <div className="col-span-2 flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormTahapan(null)}>Batal</Button>
                <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-white"
                  disabled={formTahapan.saving || !formTahapan.data.nama.trim() || !formTahapan.data.tanggal}
                  onClick={simpanTahapan} data-testid="kalender-simpan">
                  {formTahapan.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog usulan baru ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Usulan Penganggaran</DialogTitle>
            <DialogDescription className="text-xs">
              Alur: diusulkan → disetujui telaah → masuk DIPA → terealisasi (siklus RKBMN t-2).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-jenis">Jenis</label>
                <select id="agr-jenis" value={form.data.jenis}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, jenis: e.target.value, akun: e.target.value === "pengadaan" ? "532" : "523" } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="penganggaran-jenis">
                  {Object.entries(labelJenis).length
                    ? Object.entries(labelJenis).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                    : <option value="pemeliharaan">Pemeliharaan</option>}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-akun">Akun BAS</label>
                <select id="agr-akun" value={form.data.akun}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, akun: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="penganggaran-akun">
                  {Object.entries(labelAkun)
                    .filter(([k]) => (form.data.jenis === "pengadaan" ? k.startsWith("53") : k === "523"))
                    .map(([k, v]) => <option key={k} value={k}>{k} — {v}</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-rkbmn">Usulan RKBMN terkait (opsional — dari modul Perencanaan)</label>
                <select id="agr-rkbmn" value={form.data.rkbmn_id || ""}
                  className="w-full h-10 rounded-md border border-input bg-background px-2 text-sm"
                  data-testid="penganggaran-rkbmn"
                  onChange={(e) => {
                    const u = rkbmnList.find((x) => x.id === e.target.value);
                    setForm((f) => ({ ...f, data: { ...f.data,
                      rkbmn_id: e.target.value,
                      uraian: u ? (u.uraian || f.data.uraian) : f.data.uraian,
                      jenis: u ? (u.jenis === "pengadaan" ? "pengadaan" : "pemeliharaan") : f.data.jenis,
                      tahun_anggaran: u?.tahun_rkbmn || f.data.tahun_anggaran,
                    } }));
                  }}>
                  <option value="">— tanpa tautan RKBMN —</option>
                  {rkbmnList.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.tahun_rkbmn} · {u.uraian?.slice(0, 60)} ({u.unit_pengusul || "unit ?"})
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-uraian">Uraian usulan</label>
                <Input id="agr-uraian" placeholder="cth. Servis besar genset kantor"
                  value={form.data.uraian}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, uraian: e.target.value } }))}
                  data-testid="penganggaran-uraian" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-ta">TA sasaran</label>
                <Input id="agr-ta" inputMode="numeric" maxLength={4} value={form.data.tahun_anggaran}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, tahun_anggaran: e.target.value.replace(/\D/g, "") } }))}
                  data-testid="penganggaran-ta" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-nilai">Nilai usulan (Rp)</label>
                <Input id="agr-nilai" type="number" min="1" value={form.data.nilai_usulan}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, nilai_usulan: e.target.value } }))}
                  data-testid="penganggaran-nilai" />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-sumber">Sumber (opsional)</label>
                <Input id="agr-sumber" placeholder="cth. Kertas kerja RKBMN pemeliharaan 2027"
                  value={form.data.sumber}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, sumber: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-cari">Tautkan aset (opsional)</label>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <Input id="agr-cari" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                    value={cari} onChange={(e) => setCari(e.target.value)} data-testid="penganggaran-cari" />
                  {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                    <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                      {mencari ? (
                        <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-teal-600" /></div>
                      ) : hasilCari.map((a) => (
                        <button key={a.id} type="button"
                          onClick={() => { setForm((f) => (f.aset.some((x) => x.id === a.id) ? f : { ...f, aset: [...f.aset, a] })); setCari(""); setHasilCari([]); }}
                          className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                          <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                          <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP} · {a.condition}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              {form.aset.length > 0 && (
                <ul className="col-span-2 space-y-1">
                  {form.aset.map((a) => (
                    <li key={a.id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                      <span className="min-w-0 flex-1">
                        <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                        <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                      </span>
                      <button type="button" aria-label="Keluarkan aset"
                        onClick={() => setForm((f) => ({ ...f, aset: f.aset.filter((x) => x.id !== a.id) }))}
                        className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpanUsulan} disabled={form?.saving}
              className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="penganggaran-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Wallet className="w-4 h-4 mr-1.5" />}Catat Usulan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog transisi status ── */}
      <Dialog open={!!trx} onOpenChange={(o) => { if (!o) setTrx(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{labelStatus[trx?.ke] || trx?.ke}</DialogTitle>
            <DialogDescription className="text-xs">
              {trx?.usulan && `${trx.usulan.uraian} — TA ${trx.usulan.tahun_anggaran}`}
            </DialogDescription>
          </DialogHeader>
          {trx?.ke === "disetujui_telaah" && (
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-telaah">No. RKBMN Hasil Penelaahan (opsional)</label>
                <Input id="agr-telaah" value={trx.fields.nomor_hasil_penelaahan}
                  onChange={(e) => setTrxField("nomor_hasil_penelaahan", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-nilai-setuju">Nilai disetujui (Rp)</label>
                <Input id="agr-nilai-setuju" type="number" min="1" value={trx.fields.nilai_disetujui}
                  onChange={(e) => setTrxField("nilai_disetujui", e.target.value)} data-testid="penganggaran-nilai-setuju" />
              </div>
            </div>
          )}
          {trx?.ke === "masuk_dipa" && (
            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-dipa">No. DIPA petikan</label>
                <Input id="agr-dipa" placeholder="DIPA-xxx.xx.x.xxxxxx/2027" value={trx.fields.nomor_dipa}
                  onChange={(e) => setTrxField("nomor_dipa", e.target.value)} data-testid="penganggaran-nomor-dipa" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-nilai-dipa">Nilai pada DIPA (Rp)</label>
                <Input id="agr-nilai-dipa" type="number" min="1" value={trx.fields.nilai_dipa}
                  onChange={(e) => setTrxField("nilai_dipa", e.target.value)} data-testid="penganggaran-nilai-dipa" />
              </div>
            </div>
          )}
          {trx?.ke === "terealisasi" && (
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="agr-realisasi">Nilai realisasi (Rp)</label>
              <Input id="agr-realisasi" type="number" min="1" value={trx.fields.nilai_realisasi}
                onChange={(e) => setTrxField("nilai_realisasi", e.target.value)} data-testid="penganggaran-nilai-realisasi" />
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setTrx(null)}>Batal</Button>
            <Button onClick={kirimTransisi} disabled={trx?.saving}
              className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="penganggaran-trx-simpan">
              {trx?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <TicketCheck className="w-4 h-4 mr-1.5" />}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
