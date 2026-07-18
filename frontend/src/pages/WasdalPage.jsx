import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Eye, RefreshCw, ChevronDown, BadgeCheck,
  UserCheck, Handshake, ArrowLeftRight, BookOpen, ShieldCheck, FileText,
  Gavel, Plus, Trash2, AlertTriangle, Siren, FileDown, Paperclip, Upload,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IKON_OBJEK = {
  penggunaan: UserCheck,
  pemanfaatan: Handshake,
  pemindahtanganan: ArrowLeftRight,
  penatausahaan: BookOpen,
  pengamanan_pemeliharaan: ShieldCheck,
};

/**
 * Wasdal — dasbor pemantauan tingkat KPB (PMK 207/2021, pustaka §8).
 * Temuan otomatis dari register yang sudah ada, dikelompokkan per lima
 * objek pemantauan + register penertiban ber-tenggat 15 hari kerja;
 * bahan pra-isi laporan wasdal semesteran (kanal resmi pelaporan tetap
 * Modul Wasdal SIMAN v2), plus register pemantauan insidentil ber-BA
 * (isi BA + PDF + lampiran).
 */
export default function WasdalPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [buka, setBuka] = useState(null); // kunci objek yang dibentangkan
  // Register penertiban: {items, ringkasan, label_sumber, label_status, ...}
  const [pen, setPen] = useState(null);
  // Dialog catat penertiban: {data, saving}
  const [formPen, setFormPen] = useState(null);
  // Dialog selesai penertiban: {tiket, tindak_lanjut, tanggal_selesai, saving}
  const [selesaiPen, setSelesaiPen] = useState(null);
  // Register pemantauan insidentil: {items, ringkasan, label_pemicu, ...}
  const [insi, setInsi] = useState(null);
  // Dialog catat insidentil: {data, saving}
  const [formInsi, setFormInsi] = useState(null);
  // Dialog BA insidentil: {tiket, nomor_ba, tanggal_ba, hasil, saving}
  const [baInsi, setBaInsi] = useState(null);
  // Dialog lapor insidentil: {tiket, tanggal_lapor, keterangan, saving}
  const [laporInsi, setLaporInsi] = useState(null);
  // Dialog lampiran insidentil: {tiket, uploading}
  const [lampInsi, setLampInsi] = useState(null);
  const lampInsiInputRef = useRef(null);
  // Portofolio BMN + indikator tertib + standar SBSK (PMK 138/2024)
  const [porto, setPorto] = useState(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  const { confirm, confirmDialog } = useConfirm();

  const muat = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/wasdal/pemantauan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat pemantauan wasdal"))
      .finally(() => setLoading(false));
  }, []);

  const muatPen = useCallback(() => {
    axios.get(`${API}/wasdal/penertiban`)
      .then((r) => setPen(r.data))
      .catch(() => toast.error("Gagal memuat register penertiban"));
  }, []);

  const muatInsi = useCallback(() => {
    axios.get(`${API}/wasdal/insidentil`)
      .then((r) => setInsi(r.data))
      .catch(() => toast.error("Gagal memuat pemantauan insidentil"));
  }, []);

  useEffect(() => { muat(); muatPen(); muatInsi(); }, [muat, muatPen, muatInsi]);

  useEffect(() => {
    axios.get(`${API}/wasdal/portofolio`)
      .then((r) => setPorto(r.data))
      .catch(() => {});
  }, []);

  const simpanInsi = async () => {
    if (!formInsi) return;
    setFormInsi((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/wasdal/insidentil`, formInsi.data);
      toast.success("Pemantauan insidentil dibuka");
      setFormInsi(null);
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat pemantauan");
      setFormInsi((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const kirimBaInsi = async () => {
    if (!baInsi) return;
    setBaInsi((s) => ({ ...s, saving: true }));
    try {
      await axios.post(`${API}/wasdal/insidentil/${baInsi.tiket.id}/ba`, {
        nomor_ba: baInsi.nomor_ba, tanggal_ba: baInsi.tanggal_ba, hasil: baInsi.hasil,
      });
      toast.success("BA pemantauan tercatat");
      setBaInsi(null);
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat BA");
      setBaInsi((s) => (s ? { ...s, saving: false } : s));
    }
  };

  const kirimLaporInsi = async () => {
    if (!laporInsi) return;
    setLaporInsi((s) => ({ ...s, saving: true }));
    try {
      await axios.post(`${API}/wasdal/insidentil/${laporInsi.tiket.id}/lapor`, {
        tanggal_lapor: laporInsi.tanggal_lapor, keterangan: laporInsi.keterangan,
      });
      toast.success("Pelaporan tercatat");
      setLaporInsi(null);
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat pelaporan");
      setLaporInsi((s) => (s ? { ...s, saving: false } : s));
    }
  };

  const hapusInsi = async (tiket) => {
    const ok = await confirm({
      title: "Hapus tiket insidentil?",
      description: `Tiket "${(tiket.uraian_pemicu || "").slice(0, 80) || tiket.id}" beserta lampirannya akan dihapus permanen.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/wasdal/insidentil/${tiket.id}`);
      toast.success("Tiket dihapus");
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus tiket");
    }
  };

  const unggahLampiranInsi = async (fileObj) => {
    if (!lampInsi || !fileObj) return;
    setLampInsi((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const r = await axios.post(`${API}/wasdal/insidentil/${lampInsi.tiket.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLampInsi((l) => (l ? { ...l, uploading: false,
        tiket: { ...l.tiket, lampiran: r.data?.lampiran || [] } } : l));
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLampInsi((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiranInsi = async (fileId) => {
    if (!lampInsi) return;
    try {
      await axios.delete(`${API}/wasdal/insidentil/${lampInsi.tiket.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLampInsi((l) => (l ? { ...l,
        tiket: { ...l.tiket,
          lampiran: (l.tiket.lampiran || []).filter((x) => x.file_id !== fileId) } } : l));
      muatInsi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  const simpanPen = async () => {
    if (!formPen) return;
    setFormPen((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/wasdal/penertiban`, formPen.data);
      toast.success("Tiket penertiban dibuka");
      setFormPen(null);
      muatPen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat penertiban");
      setFormPen((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const kirimSelesaiPen = async () => {
    if (!selesaiPen) return;
    setSelesaiPen((s) => ({ ...s, saving: true }));
    try {
      await axios.post(`${API}/wasdal/penertiban/${selesaiPen.tiket.id}/selesai`, {
        tindak_lanjut: selesaiPen.tindak_lanjut,
        tanggal_selesai: selesaiPen.tanggal_selesai,
      });
      toast.success("Penertiban selesai");
      setSelesaiPen(null);
      muatPen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyelesaikan tiket");
      setSelesaiPen((s) => (s ? { ...s, saving: false } : s));
    }
  };

  const hapusPen = async (tiket) => {
    const ok = await confirm({
      title: "Hapus tiket penertiban?",
      description: `Tiket penertiban "${(tiket.uraian || "").slice(0, 80) || tiket.id}" ber-tenggat 15 hari kerja akan dihapus permanen.`,
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/wasdal/penertiban/${tiket.id}`);
      toast.success("Tiket dihapus");
      muatPen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus tiket");
    }
  };

  // Kelompokkan temuan sebuah objek per jenis → [{jenis, label, items}]
  const perJenis = (objek) => {
    const grup = {};
    (data?.temuan?.[objek] || []).forEach((t) => {
      (grup[t.jenis] = grup[t.jenis] || { jenis: t.jenis, label: t.label, items: [] })
        .items.push(t);
    });
    return Object.values(grup);
  };

  return (
    <div className="min-h-screen bg-background" data-testid="wasdal-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            title="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <Eye className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Wasdal — Pemantauan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {data ? `${data.periode?.label} · ${data.total_aset} aset dipantau` : "PMK 207/PMK.06/2021"}
            </p>
          </div>
          <button
            type="button"
            aria-label="Unduh laporan pemantauan periode berjalan (PDF)"
            title="Unduh laporan pemantauan periode berjalan (PDF)"
            onClick={() => downloadFileWithProgress(
              `${API}/wasdal/laporan-pdf`,
              `Laporan_Wasdal_${(data?.periode?.label || "periode").replace(/\s/g, "_")}.pdf`,
              { label: "Laporan Hasil Pemantauan Wasdal" },
            ).catch(() => {})}
            className="h-9 px-2.5 rounded-lg border border-border text-foreground/80 flex items-center justify-center gap-1 hover:bg-muted flex-shrink-0 text-[10px] font-bold min-w-0 min-h-0"
            data-testid="wasdal-laporan"
          >
            <FileText className="w-4 h-4" /><span className="hidden sm:inline">Periode</span>
          </button>
          <button
            type="button"
            aria-label="Unduh Laporan Tahunan Wasdal (Lampiran PMK 207)"
            title="Laporan Tahunan Wasdal — formulir Lampiran PMK 207/2021"
            onClick={() => downloadFileWithProgress(
              `${API}/wasdal/laporan-tahunan-pdf`,
              `Laporan_Tahunan_Wasdal_${new Date().getFullYear()}.pdf`,
              { label: "Laporan Tahunan Wasdal (Lampiran PMK 207)" },
            ).catch(() => {})}
            className="h-9 px-2.5 rounded-lg border border-border text-foreground/80 flex items-center justify-center gap-1 hover:bg-muted flex-shrink-0 text-[10px] font-bold min-w-0 min-h-0"
            data-testid="wasdal-laporan-tahunan"
          >
            <FileText className="w-4 h-4" />Tahunan
          </button>
          <button
            type="button"
            onClick={muat}
            aria-label="Muat ulang"
            title="Muat ulang data pemantauan"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-reload"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <BookingNomorButton modul="wasdal" jenisNaskah="Laporan" referensi="Laporan Wasdal" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu per objek pemantauan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {Object.entries(data.label_objek || {}).map(([kunci, label]) => {
                const Icon = IKON_OBJEK[kunci] || Eye;
                const n = data.rekap?.per_objek?.[kunci] || 0;
                return (
                  <button
                    key={kunci}
                    type="button"
                    onClick={() => n > 0 && setBuka(buka === kunci ? null : kunci)}
                    disabled={n === 0}
                    title={n === 0 ? "Tidak ada temuan — objek ini tertib" : "Klik untuk lihat rincian temuan"}
                    className={`bg-card rounded-xl border p-3 text-center transition-colors min-w-0 min-h-0 ${
                      n > 0 ? "border-sky-500/40 hover:bg-sky-500/10" : "border-emerald-500/40 opacity-70"
                    }`}
                    data-testid={`wasdal-objek-${kunci}`}
                  >
                    {n > 0
                      ? <Icon className="w-5 h-5 mx-auto mb-1 text-sky-500" />
                      : <BadgeCheck className="w-5 h-5 mx-auto mb-1 text-emerald-500" />}
                    <p className="text-lg font-bold text-foreground leading-none">{n}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{n === 0 ? `${label} · tertib` : label}</p>
                  </button>
                );
              })}
            </div>

            {/* Banner agregat LEWAT TENGGAT HUKUM — dulunya hanya badge kecil
                jauh di bawah (temuan audit UI/UX): tiket penertiban/insidentil
                yang melewati tenggat PMK 207 harus langsung terlihat. */}
            {((pen?.ringkasan?.lewat_tenggat || 0) + (insi?.ringkasan?.lewat_tenggat || 0)) > 0 && (
              <div className="rounded-xl border border-red-500/50 bg-red-500/10 p-3 flex items-start gap-2.5" data-testid="wasdal-banner-tenggat">
                <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
                <div className="text-xs text-red-700 dark:text-red-300 min-w-0">
                  <b>{(pen?.ringkasan?.lewat_tenggat || 0) + (insi?.ringkasan?.lewat_tenggat || 0)} tiket LEWAT TENGGAT hukum</b>
                  {" — "}
                  {(pen?.ringkasan?.lewat_tenggat || 0) > 0 && `${pen.ringkasan.lewat_tenggat} penertiban`}
                  {(pen?.ringkasan?.lewat_tenggat || 0) > 0 && (insi?.ringkasan?.lewat_tenggat || 0) > 0 && " · "}
                  {(insi?.ringkasan?.lewat_tenggat || 0) > 0 && `${insi.ringkasan.lewat_tenggat} pemantauan insidentil`}
                  . Segera tindak lanjuti di bagian Penertiban / Pemantauan Insidentil di bawah.
                </div>
              </div>
            )}

            <p className="text-[11px] text-muted-foreground text-center">
              {data.rekap?.total || 0} temuan pemantauan — bahan pra-isi laporan wasdal;
              pelaporan resmi tetap melalui Modul Wasdal SIMAN v2.
            </p>

            {/* ── Portofolio BMN + indikator tertib + SBSK ── */}
            {porto && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="wasdal-portofolio">
                <div className="px-3 py-2.5 border-b border-border flex flex-wrap items-center gap-2 gap-y-1.5">
                  <BarChart3 className="w-4 h-4 text-sky-500 flex-shrink-0" />
                  <p className="text-xs font-bold text-foreground flex-1 min-w-[140px]"
                    title="SBSK — Standar Barang dan Standar Kebutuhan (PMK 138/PMK.06/2024)">
                    Portofolio BMN &amp; Kesesuaian SBSK (PMK 138/2024)
                  </p>
                  <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                    {Number(porto.jumlah_aset || 0).toLocaleString("id-ID")} aset
                  </span>
                </div>
                <div className="p-3 space-y-2">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {[["Aset dipantau", porto.jumlah_aset, null],
                      ["PSP terbit", porto.psp_terbit, "PSP — Penetapan Status Penggunaan"],
                      ["BMN idle diproses", porto.idle_proses, "BMN idle — Barang Milik Negara yang tidak digunakan untuk tugas dan fungsi"],
                      ["Sengketa", porto.sengketa, null]].map(([label, n, penuh]) => (
                      <div key={label} title={penuh || undefined} className="rounded-lg border border-border p-2 text-center">
                        <p className="text-base font-extrabold leading-none">{Number(n || 0).toLocaleString("id-ID")}</p>
                        <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
                      </div>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(porto.rows || []).map((r) => (
                      <span key={r.golongan} className="px-2 py-0.5 rounded-full border border-border text-[10px]">
                        <b>{r.golongan}</b> {r.uraian}: {r.jumlah_total} unit
                      </span>
                    ))}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {porto.sbsk?.length || 0} baris standar SBSK terdaftar (rawat di modul Perencanaan) —
                    sanding kebutuhan vs standar dilakukan per usulan RKBMN.
                  </p>
                </div>
              </div>
            )}

            {/* ── Rincian temuan per objek ── */}
            {Object.entries(data.label_objek || {}).map(([kunci, label]) => {
              const n = data.rekap?.per_objek?.[kunci] || 0;
              if (n === 0) return null;
              const Icon = IKON_OBJEK[kunci] || Eye;
              const terbuka = buka === kunci;
              return (
                <div key={kunci} className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setBuka(terbuka ? null : kunci)}
                    className="w-full px-3 py-2.5 flex items-center gap-2 hover:bg-muted transition-colors"
                    data-testid={`wasdal-seksi-${kunci}`}
                  >
                    <Icon className="w-4 h-4 text-sky-500 flex-shrink-0" />
                    <p className="text-xs font-bold text-foreground flex-1 text-left">{label}</p>
                    <span className="px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[10px] font-semibold">
                      {n}
                    </span>
                    <ChevronDown className={`w-4 h-4 text-muted-foreground transition-transform ${terbuka ? "rotate-180" : ""}`} />
                  </button>
                  {terbuka && (
                    <div className="border-t border-border">
                      {perJenis(kunci).map((g) => (
                        <div key={g.jenis}>
                          <p className="px-3 pt-2.5 pb-1 text-[11px] font-semibold text-sky-600 dark:text-sky-400">
                            {g.label} · {g.items.length}
                          </p>
                          <ul className="divide-y divide-border/60">
                            {g.items.map((t, i) => (
                              <li key={`${g.jenis}-${t.asset_id || t.usulan_id || t.pemanfaatan_id || i}`} className="px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <p className="text-xs font-semibold text-foreground min-w-0 truncate">
                                    {t.asset_name || t.pihak || "-"}
                                  </p>
                                  <div className="flex items-center gap-1.5 flex-shrink-0">
                                    {t.asset_code && (
                                      <span className="font-mono text-[10px] text-muted-foreground">
                                        {t.asset_code} · {t.NUP}
                                      </span>
                                    )}
                                    <button type="button"
                                      title="Buka tiket penertiban ter-prefill dari temuan ini"
                                      onClick={() => setFormPen({ data: {
                                        sumber: "pemantauan",
                                        tanggal_dasar: new Date().toISOString().slice(0, 10),
                                        objek: kunci,
                                        uraian: `${g.label}: ${t.asset_name || t.pihak || "-"}${t.detail ? ` — ${t.detail}` : ""}`,
                                        asset_id: t.asset_id || "",
                                      }, saving: false })}
                                      className="px-1.5 py-0.5 rounded text-[10px] font-semibold text-sky-600 dark:text-sky-400 border border-sky-500/40 hover:bg-sky-500/10 min-w-0 min-h-0"
                                      data-testid={`wasdal-tindaklanjut-${g.jenis}-${i}`}>
                                      Tindak lanjuti
                                    </button>
                                  </div>
                                </div>
                                {t.detail && (
                                  <p className="text-[11px] text-muted-foreground mt-0.5">{t.detail}</p>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                      {(data.terpotong?.[kunci] || 0) > 0 && (
                        <p className="text-[11px] text-muted-foreground text-center py-2">
                          +{data.terpotong[kunci]} temuan lain tidak ditampilkan (100 pertama per objek).
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {/* ── Register penertiban (≤15 hari kerja) ── */}
            {pen && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="wasdal-penertiban">
                <div className="px-3 py-2.5 border-b border-border flex flex-wrap items-center gap-2 gap-y-1.5">
                  <Gavel className="w-4 h-4 text-amber-500 flex-shrink-0" />
                  <p className="text-xs font-bold text-foreground flex-1 min-w-[140px]"
                    title={`Tindak lanjut wajib selesai ≤${pen.tenggat_hari_kerja} hari kerja sejak tanggal dasar (PMK 207/2021)`}>
                    Penertiban (≤{pen.tenggat_hari_kerja} hari kerja)
                  </p>
                  {(pen.ringkasan?.lewat_tenggat || 0) > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold">
                      {pen.ringkasan.lewat_tenggat} lewat tenggat
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                    {pen.ringkasan?.berjalan || 0} berjalan
                  </span>
                  {(pen.items || []).length > 0 && (
                    <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                      title="Ekspor register penertiban (CSV)" aria-label="Ekspor register penertiban (CSV)"
                      onClick={() => downloadFileWithProgress(`${API}/wasdal/penertiban/export`, "register_penertiban_wasdal.csv", { label: "Ekspor Register Penertiban Wasdal (CSV)" }).catch(() => {})}
                      data-testid="wasdal-penertiban-export">
                      <FileDown className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                    </Button>
                  )}
                  <Button size="sm" onClick={() => setFormPen({ data: { sumber: "pemantauan", tanggal_dasar: new Date().toISOString().slice(0, 10), objek: "", uraian: "" }, saving: false })}
                    title="Catat tiket penertiban baru" aria-label="Catat tiket penertiban baru"
                    className="h-7 text-[11px] min-h-0 bg-amber-600 hover:bg-amber-700 text-white" data-testid="wasdal-penertiban-tambah">
                    <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat</span>
                  </Button>
                </div>
                {(pen.items || []).length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-5 px-4">
                    Belum ada tiket penertiban — buka dari temuan pemantauan, surat permintaan Pengelola, atau temuan APIP/BPK.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60">
                    {pen.items.map((t) => (
                      <li key={t.id} className="p-3" data-testid={`wasdal-penertiban-${t.id}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            t.status === "selesai"
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                            {pen.label_status?.[t.status] || t.status}
                          </span>
                          <p className="text-xs font-semibold text-foreground flex-1 min-w-[140px] truncate">{t.uraian}</p>
                          {t.status === "berjalan" && t.info_tenggat?.lewat && (
                            <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />Lewat tenggat {t.tenggat}
                            </span>
                          )}
                          {t.status === "berjalan" && !t.info_tenggat?.lewat && (
                            <span className="text-[10px] text-muted-foreground">
                              sisa {t.info_tenggat?.sisa_hari_kerja ?? "-"} hari kerja (tenggat {t.tenggat})
                            </span>
                          )}
                          {isAdmin && t.status === "berjalan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              onClick={() => setSelesaiPen({ tiket: t, tindak_lanjut: "", tanggal_selesai: new Date().toISOString().slice(0, 10), saving: false })}
                              data-testid={`wasdal-penertiban-selesai-${t.id}`}>
                              Selesai
                            </Button>
                          )}
                          {isAdmin && (
                            <button type="button" aria-label="Hapus tiket" title="Hapus tiket penertiban" onClick={() => hapusPen(t)}
                              className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {[pen.label_sumber?.[t.sumber] || t.sumber,
                            t.objek && (pen.label_objek?.[t.objek] || t.objek),
                            t.asset_name && `${t.asset_name}${t.asset_code ? ` (${t.asset_code} · ${t.NUP})` : ""}`,
                            `dasar ${t.tanggal_dasar}`,
                            t.status === "selesai" && `selesai ${t.tanggal_selesai}: ${t.tindak_lanjut}`,
                            `oleh ${t.created_by}`].filter(Boolean).join(" · ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{pen.catatan}</p>
              </div>
            )}

            {/* ── Pemantauan insidentil (10 + 5 hari kerja) ── */}
            {insi && (
              <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="wasdal-insidentil">
                <div className="px-3 py-2.5 border-b border-border flex flex-wrap items-center gap-2 gap-y-1.5">
                  <Siren className="w-4 h-4 text-violet-500 flex-shrink-0" />
                  <p className="text-xs font-bold text-foreground flex-1 min-w-[140px]"
                    title={`Pelaksanaan ≤${insi.tenggat_pelaksanaan_hk} hari kerja sejak mulai; pelaporan ≤${insi.tenggat_lapor_hk} hari kerja sejak tanggal BA`}>
                    Pemantauan Insidentil ({insi.tenggat_pelaksanaan_hk}+{insi.tenggat_lapor_hk} hari kerja)
                  </p>
                  {(insi.ringkasan?.lewat_tenggat || 0) > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold">
                      {insi.ringkasan.lewat_tenggat} lewat tenggat
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                    {(insi.ringkasan?.berjalan || 0) + (insi.ringkasan?.ba_terbit || 0)} aktif
                  </span>
                  {(insi.items || []).length > 0 && (
                    <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                      title="Ekspor register pemantauan insidentil (CSV)" aria-label="Ekspor register pemantauan insidentil (CSV)"
                      onClick={() => downloadFileWithProgress(`${API}/wasdal/insidentil/export`, "register_pemantauan_insidentil.csv", { label: "Ekspor Register Pemantauan Insidentil (CSV)" }).catch(() => {})}
                      data-testid="wasdal-insidentil-export">
                      <FileDown className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                    </Button>
                  )}
                  <Button size="sm" onClick={() => setFormInsi({ data: { pemicu: "informasi_masyarakat", tanggal_mulai: new Date().toISOString().slice(0, 10), objek: "", uraian: "", lokasi: "" }, saving: false })}
                    title="Catat pemantauan insidentil baru" aria-label="Catat pemantauan insidentil baru"
                    className="h-7 text-[11px] min-h-0 bg-violet-600 hover:bg-violet-700 text-white" data-testid="wasdal-insidentil-tambah">
                    <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat</span>
                  </Button>
                </div>
                {(insi.items || []).length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-5 px-4">
                    Belum ada pemantauan insidentil — dibuka bila ada informasi masyarakat, pemberitaan media, atau hasil audit.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60">
                    {insi.items.map((t) => (
                      <li key={t.id} className="p-3" data-testid={`wasdal-insidentil-${t.id}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            t.status === "dilaporkan"
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : t.status === "ba_terbit"
                                ? "bg-sky-500/15 text-sky-600 dark:text-sky-400"
                                : "bg-violet-500/15 text-violet-600 dark:text-violet-400"}`}>
                            {insi.label_status?.[t.status] || t.status}
                          </span>
                          <p className="text-xs font-semibold text-foreground flex-1 min-w-[140px] truncate">{t.uraian}</p>
                          {t.info_tenggat?.lewat && (
                            <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold flex items-center gap-1">
                              <AlertTriangle className="w-3 h-3" />Lewat tenggat {t.info_tenggat.tahap} ({t.info_tenggat.tenggat})
                            </span>
                          )}
                          {t.info_tenggat?.tahap && !t.info_tenggat?.lewat && (
                            <span className="text-[10px] text-muted-foreground">
                              {t.info_tenggat.tahap}: sisa {t.info_tenggat.sisa_hari_kerja ?? "-"} hari kerja
                            </span>
                          )}
                          <button type="button" aria-label="Lampiran tiket" title="Lampiran tiket (scan BA/foto)"
                            onClick={() => setLampInsi({ tiket: t, uploading: false })}
                            className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                            data-testid={`wasdal-insidentil-lampiran-${t.id}`}>
                            <Paperclip className="w-3 h-3" />
                          </button>
                          <button type="button" aria-label="Unduh BA (PDF)" title="Unduh BA pemantauan (PDF)"
                            onClick={() => downloadFileWithProgress(
                              `${API}/wasdal/insidentil/${t.id}/ba-pdf`,
                              `BA_Pemantauan_Insidentil_${(t.nomor_ba || t.id.slice(0, 8)).replace(/\//g, "-")}.pdf`,
                              { label: "BA Pemantauan Insidentil" },
                            ).catch(() => {})}
                            className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                            data-testid={`wasdal-insidentil-pdf-${t.id}`}>
                            <FileDown className="w-3 h-3" />
                          </button>
                          {isAdmin && t.status === "berjalan" && (
                            <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                              title="Catat penerbitan BA — Berita Acara pemantauan"
                              onClick={() => setBaInsi({ tiket: t, nomor_ba: "", tanggal_ba: new Date().toISOString().slice(0, 10), hasil: "", saving: false })}
                              data-testid={`wasdal-insidentil-ba-${t.id}`}>
                              BA Terbit
                            </Button>
                          )}
                          {isAdmin && t.status === "ba_terbit" && (
                            <Button size="sm" className="h-7 text-[11px] min-h-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                              onClick={() => setLaporInsi({ tiket: t, tanggal_lapor: new Date().toISOString().slice(0, 10), keterangan: "", saving: false })}
                              data-testid={`wasdal-insidentil-lapor-${t.id}`}>
                              Dilaporkan
                            </Button>
                          )}
                          {isAdmin && (
                            <button type="button" aria-label="Hapus tiket" title="Hapus tiket insidentil" onClick={() => hapusInsi(t)}
                              className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {[insi.label_pemicu?.[t.pemicu] || t.pemicu,
                            t.objek && (insi.label_objek?.[t.objek] || t.objek),
                            t.lokasi,
                            `mulai ${t.tanggal_mulai}`,
                            t.nomor_ba && `BA ${t.nomor_ba} (${t.tanggal_ba})`,
                            t.tanggal_lapor && `dilaporkan ${t.tanggal_lapor}`,
                            `oleh ${t.created_by}`].filter(Boolean).join(" · ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="px-3 py-2 text-[11px] text-muted-foreground border-t border-border">{insi.catatan}</p>
              </div>
            )}

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              Menyusul: generator laporan formulir Lampiran PMK 207 — masterplan Fase 6.
            </p>
          </>
        )}
      </main>

      {/* ── Dialog catat pemantauan insidentil ── */}
      <Dialog open={!!formInsi} onOpenChange={(o) => { if (!o) setFormInsi(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Pemantauan Insidentil</DialogTitle>
            <DialogDescription className="text-xs">
              Pelaksanaan ≤{insi?.tenggat_pelaksanaan_hk || 10} hari kerja sejak mulai;
              hasil dilaporkan ≤{insi?.tenggat_lapor_hk || 5} hari kerja sejak tanggal BA.
            </DialogDescription>
          </DialogHeader>
          {formInsi && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-pemicu">Pemicu</label>
                <select id="insi-pemicu" value={formInsi.data.pemicu}
                  onChange={(e) => setFormInsi((f) => ({ ...f, data: { ...f.data, pemicu: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="wasdal-insidentil-pemicu">
                  {Object.entries(insi?.label_pemicu || {}).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-tgl">Tanggal mulai</label>
                <Input id="insi-tgl" type="date" value={formInsi.data.tanggal_mulai}
                  onChange={(e) => setFormInsi((f) => ({ ...f, data: { ...f.data, tanggal_mulai: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-objek">Objek pemantauan (opsional)</label>
                <select id="insi-objek" value={formInsi.data.objek}
                  onChange={(e) => setFormInsi((f) => ({ ...f, data: { ...f.data, objek: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground">
                  <option value="">— tidak spesifik —</option>
                  {Object.entries(insi?.label_objek || {}).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-uraian">Uraian</label>
                <Input id="insi-uraian" placeholder="mis. Laporan warga: aset ditempati pihak ketiga" value={formInsi.data.uraian}
                  onChange={(e) => setFormInsi((f) => ({ ...f, data: { ...f.data, uraian: e.target.value } }))}
                  data-testid="wasdal-insidentil-uraian" />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-lokasi">Lokasi (opsional)</label>
                <Input id="insi-lokasi" value={formInsi.data.lokasi}
                  onChange={(e) => setFormInsi((f) => ({ ...f, data: { ...f.data, lokasi: e.target.value } }))} />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setFormInsi(null)}>Batal</Button>
            <Button onClick={simpanInsi} disabled={formInsi?.saving || !formInsi?.data?.uraian?.trim()}
              className="bg-violet-600 hover:bg-violet-700 text-white" data-testid="wasdal-insidentil-simpan">
              {formInsi?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Siren className="w-4 h-4 mr-1.5" />}Buka Pemantauan
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog BA insidentil ── */}
      <Dialog open={!!baInsi} onOpenChange={(o) => { if (!o) setBaInsi(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Catat BA Pemantauan</DialogTitle>
            <DialogDescription className="text-xs">{baInsi?.tiket?.uraian}</DialogDescription>
          </DialogHeader>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-ba-nomor">Nomor BA</label>
            <Input id="insi-ba-nomor" placeholder="BA-01/WASDAL/2026" value={baInsi?.nomor_ba || ""}
              onChange={(e) => setBaInsi((s) => ({ ...s, nomor_ba: e.target.value }))}
              data-testid="wasdal-insidentil-ba-nomor" />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-ba-tgl">Tanggal BA</label>
            <Input id="insi-ba-tgl" type="date" value={baInsi?.tanggal_ba || ""}
              onChange={(e) => setBaInsi((s) => ({ ...s, tanggal_ba: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-ba-hasil">Ringkasan hasil</label>
            <Input id="insi-ba-hasil" placeholder="mis. Ditemukan penggunaan tanpa hak" value={baInsi?.hasil || ""}
              onChange={(e) => setBaInsi((s) => ({ ...s, hasil: e.target.value }))}
              data-testid="wasdal-insidentil-ba-hasil" />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setBaInsi(null)}>Batal</Button>
            <Button onClick={kirimBaInsi} disabled={baInsi?.saving || !baInsi?.nomor_ba?.trim() || !baInsi?.hasil?.trim()}
              className="bg-sky-600 hover:bg-sky-700 text-white" data-testid="wasdal-insidentil-ba-simpan">
              Simpan
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran tiket insidentil (scan BA + foto temuan) ── */}
      <Dialog open={!!lampInsi} onOpenChange={(o) => { if (!o) setLampInsi(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Lampiran Pemantauan Insidentil</DialogTitle>
            <DialogDescription className="text-xs">
              {lampInsi && `${lampInsi.tiket.uraian}. Scan BA bertanda tangan / foto temuan (PDF/JPG/PNG, maks 10MB, 10 berkas).`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampInsiInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiranInsi(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lampInsi?.uploading || (lampInsi?.tiket?.lampiran || []).length >= 10}
            onClick={() => lampInsiInputRef.current?.click()} data-testid="wasdal-insidentil-lampiran-unggah">
            {lampInsi?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lampInsi?.tiket?.lampiran || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lampInsi?.tiket?.lampiran || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/wasdal/insidentil/${lampInsi.tiket.id}/lampiran/${f.file_id}`), "_blank", "noopener")}
                    className="min-w-0 flex-1 text-left hover:underline">
                    <span className="block text-xs font-semibold text-foreground truncate">{f.filename}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {String(f.tanggal || "").slice(0, 10)} · oleh {f.oleh}
                    </span>
                  </button>
                  {isAdmin && (
                    <button type="button" aria-label="Hapus lampiran" title="Hapus lampiran" onClick={() => hapusLampiranInsi(f.file_id)}
                      className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog lapor insidentil ── */}
      <Dialog open={!!laporInsi} onOpenChange={(o) => { if (!o) setLaporInsi(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Catat Pelaporan Hasil</DialogTitle>
            <DialogDescription className="text-xs">
              {laporInsi?.tiket && `BA ${laporInsi.tiket.nomor_ba} (${laporInsi.tiket.tanggal_ba}) — lapor ≤${insi?.tenggat_lapor_hk || 5} hari kerja sejak BA.`}
            </DialogDescription>
          </DialogHeader>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-lapor-tgl">Tanggal lapor</label>
            <Input id="insi-lapor-tgl" type="date" value={laporInsi?.tanggal_lapor || ""}
              onChange={(e) => setLaporInsi((s) => ({ ...s, tanggal_lapor: e.target.value }))} />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="insi-lapor-ket">Keterangan (opsional)</label>
            <Input id="insi-lapor-ket" placeholder="mis. via Modul Wasdal SIMAN v2" value={laporInsi?.keterangan || ""}
              onChange={(e) => setLaporInsi((s) => ({ ...s, keterangan: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setLaporInsi(null)}>Batal</Button>
            <Button onClick={kirimLaporInsi} disabled={laporInsi?.saving}
              className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="wasdal-insidentil-lapor-simpan">
              Simpan
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog catat penertiban ── */}
      <Dialog open={!!formPen} onOpenChange={(o) => { if (!o) setFormPen(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Penertiban</DialogTitle>
            <DialogDescription className="text-xs">
              Tenggat otomatis {pen?.tenggat_hari_kerja || 15} hari kerja sejak tanggal dasar
              (pemantauan selesai / surat Pengelola diterima / temuan APIP-BPK).
            </DialogDescription>
          </DialogHeader>
          {formPen && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-sumber">Sumber</label>
                <select id="pen-sumber" value={formPen.data.sumber}
                  onChange={(e) => setFormPen((f) => ({ ...f, data: { ...f.data, sumber: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="wasdal-penertiban-sumber">
                  {Object.entries(pen?.label_sumber || {}).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-tgl">Tanggal dasar</label>
                <Input id="pen-tgl" type="date" value={formPen.data.tanggal_dasar}
                  onChange={(e) => setFormPen((f) => ({ ...f, data: { ...f.data, tanggal_dasar: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-objek">Objek pemantauan (opsional)</label>
                <select id="pen-objek" value={formPen.data.objek}
                  onChange={(e) => setFormPen((f) => ({ ...f, data: { ...f.data, objek: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground">
                  <option value="">— tidak spesifik —</option>
                  {Object.entries(pen?.label_objek || {}).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-uraian">Uraian</label>
                <Input id="pen-uraian" placeholder="mis. Aset dikuasai pihak ketiga tanpa hak" value={formPen.data.uraian}
                  onChange={(e) => setFormPen((f) => ({ ...f, data: { ...f.data, uraian: e.target.value } }))}
                  data-testid="wasdal-penertiban-uraian" />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setFormPen(null)}>Batal</Button>
            <Button onClick={simpanPen} disabled={formPen?.saving || !formPen?.data?.uraian?.trim()}
              className="bg-amber-600 hover:bg-amber-700 text-white" data-testid="wasdal-penertiban-simpan">
              {formPen?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Gavel className="w-4 h-4 mr-1.5" />}Buka Tiket
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Dialog selesai penertiban ── */}
      <Dialog open={!!selesaiPen} onOpenChange={(o) => { if (!o) setSelesaiPen(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Selesaikan Penertiban</DialogTitle>
            <DialogDescription className="text-xs">{selesaiPen?.tiket?.uraian}</DialogDescription>
          </DialogHeader>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-tl">Tindak lanjut</label>
            <Input id="pen-tl" placeholder="mis. Aset ditarik & BAST ulang" value={selesaiPen?.tindak_lanjut || ""}
              onChange={(e) => setSelesaiPen((s) => ({ ...s, tindak_lanjut: e.target.value }))}
              data-testid="wasdal-penertiban-tindaklanjut" />
          </div>
          <div>
            <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pen-tgl-selesai">Tanggal selesai</label>
            <Input id="pen-tgl-selesai" type="date" value={selesaiPen?.tanggal_selesai || ""}
              onChange={(e) => setSelesaiPen((s) => ({ ...s, tanggal_selesai: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setSelesaiPen(null)}>Batal</Button>
            <Button onClick={kirimSelesaiPen} disabled={selesaiPen?.saving || !selesaiPen?.tindak_lanjut?.trim()}
              className="bg-emerald-600 hover:bg-emerald-700 text-white" data-testid="wasdal-penertiban-selesai-simpan">
              Simpan
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      {confirmDialog}
    </div>
  );
}
