import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Eye, RefreshCw, ChevronDown, BadgeCheck,
  UserCheck, Handshake, ArrowLeftRight, BookOpen, ShieldCheck, FileText,
  Gavel, Plus, Trash2, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

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
 * Modul Wasdal SIMAN v2). BA pemantauan insidentil menyusul.
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

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

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

  useEffect(() => { muat(); muatPen(); }, [muat, muatPen]);

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
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <Eye className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Wasdal — Pemantauan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {data ? `${data.periode?.label} · ${data.total_aset} aset dipantau` : "PMK 207/PMK.06/2021"}
            </p>
          </div>
          <button
            type="button"
            aria-label="Unduh laporan pemantauan (PDF)"
            onClick={() => downloadFileWithProgress(
              `${API}/wasdal/laporan-pdf`,
              `Laporan_Wasdal_${(data?.periode?.label || "periode").replace(/\s/g, "_")}.pdf`,
              { label: "Laporan Hasil Pemantauan Wasdal" },
            ).catch(() => {})}
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-laporan"
          >
            <FileText className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={muat}
            aria-label="Muat ulang"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="wasdal-reload"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
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
                    className={`bg-card rounded-xl border p-3 text-center transition-colors min-w-0 min-h-0 ${
                      n > 0 ? "border-sky-500/40 hover:bg-sky-500/10" : "border-emerald-500/40 opacity-70"
                    }`}
                    data-testid={`wasdal-objek-${kunci}`}
                  >
                    {n > 0
                      ? <Icon className="w-5 h-5 mx-auto mb-1 text-sky-500" />
                      : <BadgeCheck className="w-5 h-5 mx-auto mb-1 text-emerald-500" />}
                    <p className="text-lg font-bold text-foreground leading-none">{n}</p>
                    <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
                  </button>
                );
              })}
            </div>

            <p className="text-[11px] text-muted-foreground text-center">
              {data.rekap?.total || 0} temuan pemantauan — bahan pra-isi laporan wasdal;
              pelaporan resmi tetap melalui Modul Wasdal SIMAN v2.
            </p>

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
                                  {t.asset_code && (
                                    <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">
                                      {t.asset_code} · {t.NUP}
                                    </span>
                                  )}
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
                <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                  <Gavel className="w-4 h-4 text-amber-500" />
                  <p className="text-xs font-bold text-foreground flex-1">Penertiban (≤{pen.tenggat_hari_kerja} hari kerja)</p>
                  {(pen.ringkasan?.lewat_tenggat || 0) > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold">
                      {pen.ringkasan.lewat_tenggat} lewat tenggat
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                    {pen.ringkasan?.berjalan || 0} berjalan
                  </span>
                  <Button size="sm" onClick={() => setFormPen({ data: { sumber: "pemantauan", tanggal_dasar: new Date().toISOString().slice(0, 10), objek: "", uraian: "" }, saving: false })}
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
                            <button type="button" aria-label="Hapus tiket" onClick={() => hapusPen(t)}
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

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              Menyusul: BA pemantauan insidentil (10+5 hari kerja) dan generator
              laporan formulir PMK 207 — masterplan Fase 6.
            </p>
          </>
        )}
      </main>

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
    </div>
  );
}
