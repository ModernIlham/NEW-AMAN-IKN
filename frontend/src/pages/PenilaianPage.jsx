import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Scale, Coins, TrendingDown, Wallet, AlertTriangle,
  BookOpen, FileSignature, Plus, Pencil, Search, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Penilaian — Fase 5 tahap awal: posisi penyusutan aset tetap
 * (PMK 65/2017: garis lurus tanpa residu, semesteran, konvensi semester
 * penuh; masa manfaat KMK 295/2019 jo. 266/2023 per kelompok). Revaluasi
 * dan referensi masa manfaat yang dapat dikelola menyusul.
 */
export default function PenilaianPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [perTanggal, setPerTanggal] = useState(new Date().toISOString().slice(0, 10));
  // Referensi masa manfaat: {items} | null; dialog: {kode, uraian, tahun, saving, edit}
  const [ref, setRef] = useState(null);
  const [formRef, setFormRef] = useState(null);
  // Register koreksi nilai: data GET + dialog catat {data, aset, saving}
  const [koreksi, setKoreksi] = useState(null);
  const [formKoreksi, setFormKoreksi] = useState(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muatKoreksi = useCallback(() => {
    axios.get(`${API}/penilaian/koreksi`)
      .then((r) => setKoreksi(r.data))
      .catch(() => {});
  }, []);
  useEffect(() => { muatKoreksi(); }, [muatKoreksi]);

  useEffect(() => {
    if (!formKoreksi || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, formKoreksi]);

  const simpanKoreksi = async () => {
    if (!formKoreksi?.aset) return;
    setFormKoreksi((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penilaian/koreksi`, {
        ...formKoreksi.data, asset_id: formKoreksi.aset.id,
        nilai_lama: Number(formKoreksi.data.nilai_lama || 0),
        nilai_baru: Number(formKoreksi.data.nilai_baru || 0),
        masa_manfaat_semester: parseInt(formKoreksi.data.masa_manfaat_semester, 10) || 0,
      });
      toast.success("Koreksi nilai dicatat");
      setFormKoreksi(null);
      muatKoreksi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat koreksi");
      setFormKoreksi((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const tandaiSakti = async (k) => {
    const ok = await confirm({
      title: "Tandai tercatat di SAKTI?",
      description: `${k.nomor_dokumen} — ${k.asset_name || k.asset_id}. Pastikan sudah divalidasi & di-approve di SAKTI.`,
      confirmLabel: "Tandai",
    });
    if (!ok) return;
    try {
      await axios.post(`${API}/penilaian/koreksi/${k.id}/sakti`);
      toast.success("Ditandai tercatat di SAKTI");
      muatKoreksi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menandai");
    }
  };

  const hapusKoreksi = async (k) => {
    const ok = await confirm({
      title: "Hapus catatan koreksi?",
      description: `${koreksi?.label_jenis?.[k.jenis] || k.jenis} ${k.nomor_dokumen} — ${k.asset_name || k.asset_id}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/penilaian/koreksi/${k.id}`);
      toast.success("Catatan dihapus");
      muatKoreksi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus");
    }
  };

  const muatPosisi = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/penilaian/penyusutan`, { params: { per_tanggal: perTanggal } })
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat posisi penyusutan"))
      .finally(() => setLoading(false));
  }, [perTanggal]);
  const muatRef = useCallback(() => {
    axios.get(`${API}/penilaian/masa-manfaat`)
      .then((r) => setRef(r.data))
      .catch(() => {});
  }, []);
  useEffect(() => { muatPosisi(); }, [muatPosisi]);
  useEffect(() => { muatRef(); }, [muatRef]);

  const simpanRef = async () => {
    if (!formRef) return;
    setFormRef((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/penilaian/masa-manfaat`, {
        kode: formRef.kode.trim(), uraian: formRef.uraian,
        tahun: parseInt(formRef.tahun, 10) || 0,
      });
      toast.success("Referensi masa manfaat tersimpan");
      setFormRef(null);
      muatRef();
      muatPosisi(); // posisi ikut peta terbaru
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan referensi");
      setFormRef((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusRef = async (m) => {
    const ok = await confirm({
      title: `Hapus entri ${m.kode}?`,
      description: "Entri satker dihapus; bila kelompok ini punya nilai bawaan riset, nilai itu berlaku lagi.",
      confirmLabel: "Hapus",
      variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/penilaian/masa-manfaat/${m.kode}`);
      toast.success("Entri dihapus");
      muatRef();
      muatPosisi();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus entri");
    }
  };

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;

  return (
    <div className="min-h-screen bg-background" data-testid="penilaian-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="penilaian-back"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-violet-600 flex items-center justify-center flex-shrink-0">
            <Scale className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Penilaian — Posisi Penyusutan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Garis lurus semesteran (PMK 65/2017) · masa manfaat KMK 295/2019 jo. 266/2023
            </p>
          </div>
          <Input
            type="date"
            value={perTanggal}
            onChange={(e) => e.target.value && setPerTanggal(e.target.value)}
            className="h-8 w-36 text-xs flex-shrink-0"
            data-testid="penilaian-tanggal"
            aria-label="Posisi per tanggal"
          />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-violet-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Kartu ringkasan ── */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-perolehan">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.nilai_perolehan)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan ({data.total.jumlah} aset disusutkan)</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-akumulasi">
                <TrendingDown className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.akumulasi)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Akumulasi penyusutan</p>
              </div>
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="penilaian-stat-buku">
                <Wallet className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(data.total.nilai_buku)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai buku</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="penilaian-stat-habis">
                <AlertTriangle className="w-5 h-5 text-amber-500 mx-auto mb-1" />
                <p className="text-base font-bold text-foreground leading-none">{data.jumlah_habis}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Habis masa manfaat (nilai buku 0, tetap tersaji)</p>
              </div>
            </div>

            {/* ── Per golongan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border">
                <p className="text-xs font-bold text-foreground">Per Golongan — posisi per {data.per_tanggal}</p>
              </div>
              {data.per_golongan.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Belum ada aset yang dapat dihitung — lengkapi tanggal perolehan & referensi masa manfaat.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.per_golongan.map((g) => (
                    <li key={g.golongan} className="px-3 py-2" data-testid={`penilaian-gol-${g.golongan}`}>
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold text-foreground truncate">
                          {g.golongan} — {g.uraian} <span className="text-muted-foreground font-normal">({g.jumlah} aset)</span>
                        </p>
                        <p className="text-xs font-bold text-foreground flex-shrink-0">{fmtRp(g.nilai_buku)}</p>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Perolehan {fmtRp(g.nilai_perolehan)} − akumulasi {fmtRp(g.akumulasi)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* ── Daftar telaah ── */}
            {(data.henti.length > 0 || data.tanpa_referensi.length > 0) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="bg-card rounded-xl border border-red-500/40 shadow-sm overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-xs font-bold text-foreground">Telaah Henti Susut ({data.henti.length})</p>
                  </div>
                  <ul className="divide-y divide-border/60 max-h-64 overflow-y-auto">
                    {data.henti.map((a) => (
                      <li key={a.id} className="px-3 py-1.5">
                        <p className="text-[11px] font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-red-500/90">{a.alasan}</p>
                      </li>
                    ))}
                    {data.henti.length === 0 && <li className="text-[11px] text-muted-foreground text-center py-3">Tidak ada.</li>}
                  </ul>
                </div>
                <div className="bg-card rounded-xl border border-amber-500/40 shadow-sm overflow-hidden">
                  <div className="px-3 py-2 border-b border-border">
                    <p className="text-xs font-bold text-foreground">Perlu Referensi/Data ({data.tanpa_referensi.length})</p>
                  </div>
                  <ul className="divide-y divide-border/60 max-h-64 overflow-y-auto">
                    {data.tanpa_referensi.map((a) => (
                      <li key={a.id} className="px-3 py-1.5">
                        <p className="text-[11px] font-semibold text-foreground truncate">{a.asset_name || "-"}</p>
                        <p className="text-[10px] text-amber-600 dark:text-amber-400">{a.alasan}</p>
                      </li>
                    ))}
                    {data.tanpa_referensi.length === 0 && <li className="text-[11px] text-muted-foreground text-center py-3">Tidak ada.</li>}
                  </ul>
                </div>
              </div>
            )}

            {Object.keys(data.tidak || {}).length > 0 && (
              <div className="bg-card rounded-xl border border-border p-3">
                <p className="text-xs font-bold text-foreground mb-1">Bukan objek penyusutan</p>
                {Object.entries(data.tidak).map(([alasan, n]) => (
                  <p key={alasan} className="text-[11px] text-muted-foreground">{n} aset — {alasan}</p>
                ))}
              </div>
            )}

            {/* ── Register koreksi nilai & hasil penilaian (PMK 99/2024 + 118/2017) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="penilaian-koreksi">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-teal-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Koreksi Nilai & Hasil Penilaian</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Revaluasi/koreksi per aset (LHIP/Laporan Penilaian/BA) — resmi di SAKTI
                  </p>
                </div>
                {(koreksi?.ringkasan?.belum_tercatat_sakti || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold flex-shrink-0">
                    {koreksi.ringkasan.belum_tercatat_sakti} belum di SAKTI
                  </span>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => { setCari(""); setHasilCari([]); setFormKoreksi({ data: { jenis: "revaluasi", jenis_dokumen: "lhip", nomor_dokumen: "", tanggal_dokumen: "", nilai_lama: "", nilai_baru: "", penilai_pelaksana: "", dampak_masa_manfaat: "tetap", masa_manfaat_semester: "", catatan: "" }, aset: null, saving: false }); }}
                  data-testid="penilaian-koreksi-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat</span>
                </Button>
              </div>
              {(koreksi?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada catatan — rekam hasil revaluasi/koreksi nilai saat LHIP/BA diterima dari KPKNL.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {koreksi.items.map((k) => (
                    <li key={k.id} className="p-3" data-testid={`penilaian-koreksi-${k.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-600 dark:text-teal-400 text-[10px] font-semibold">
                          {koreksi.label_jenis?.[k.jenis] || k.jenis}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${k.status_sakti === "tercatat_sakti" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}>
                          {koreksi.label_sakti?.[k.status_sakti] || k.status_sakti}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{k.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{k.asset_code} · {k.NUP}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[`${koreksi.label_dokumen?.[k.jenis_dokumen] || k.jenis_dokumen} ${k.nomor_dokumen} (${k.tanggal_dokumen})`,
                          `Rp${Math.round(Number(k.nilai_lama || 0)).toLocaleString("id-ID")} → Rp${Math.round(Number(k.nilai_baru || 0)).toLocaleString("id-ID")}`,
                          k.dampak_masa_manfaat === "masa_manfaat_baru" && `masa manfaat baru ${k.masa_manfaat_semester} smt (akumulasi reset)`,
                          k.penilai_pelaksana, k.catatan, `oleh ${k.created_by}`].filter(Boolean).join(" · ")}
                      </p>
                      <div className="flex gap-1.5 mt-1.5 items-center">
                        {k.status_sakti === "belum_dicatat" && (
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => tandaiSakti(k)}
                            data-testid={`penilaian-koreksi-${k.id}-sakti`}>
                            Tandai tercatat di SAKTI
                          </Button>
                        )}
                        {isAdmin && (
                          <button type="button" onClick={() => hapusKoreksi(k)} aria-label="Hapus koreksi"
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

            {/* ── Referensi masa manfaat ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-border flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-violet-500" />
                <p className="text-xs font-bold text-foreground flex-1">Referensi Masa Manfaat (KMK 295/2019 jo. 266/2023)</p>
                {isAdmin && (
                  <button
                    type="button"
                    onClick={() => setFormRef({ kode: "", uraian: "", tahun: "", saving: false, edit: false })}
                    className="h-7 px-2.5 rounded-lg border border-border text-xs font-semibold text-foreground/80 flex items-center gap-1 hover:bg-muted min-h-0"
                    data-testid="penilaian-ref-tambah"
                  >
                    <Plus className="w-3.5 h-3.5" />Tambah
                  </button>
                )}
              </div>
              <ul className="divide-y divide-border/60 max-h-72 overflow-y-auto">
                {(ref?.items || []).map((m) => (
                  <li key={m.kode} className="px-3 py-1.5 flex items-center gap-2" data-testid={`penilaian-ref-${m.kode}`}>
                    <span className="font-mono text-xs text-foreground w-14 flex-shrink-0">{m.kode}</span>
                    <span className="text-[11px] text-muted-foreground truncate flex-1">
                      {m.uraian || "—"} · <span className={m.sumber === "input satker" ? "text-emerald-600 dark:text-emerald-400" : ""}>{m.sumber}</span>
                    </span>
                    <span className="text-xs font-bold text-foreground flex-shrink-0">{m.tahun} th</span>
                    {isAdmin && (
                      <>
                        <button type="button" aria-label={`Ubah ${m.kode}`}
                          onClick={() => setFormRef({ kode: m.kode, uraian: m.uraian || "", tahun: String(m.tahun), saving: false, edit: true })}
                          className="h-6 w-6 rounded border border-border text-foreground/70 flex items-center justify-center hover:bg-muted flex-shrink-0 min-h-0 min-w-0">
                          <Pencil className="w-3 h-3" />
                        </button>
                        {m.sumber === "input satker" && (
                          <button type="button" aria-label={`Hapus ${m.kode}`}
                            onClick={() => hapusRef(m)}
                            className="h-6 w-6 rounded border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </>
                    )}
                  </li>
                ))}
                {(ref?.items || []).length === 0 && (
                  <li className="text-[11px] text-muted-foreground text-center py-3">Memuat referensi…</li>
                )}
              </ul>
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog referensi masa manfaat ── */}
      <Dialog open={!!formRef} onOpenChange={(o) => { if (!o) setFormRef(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{formRef?.edit ? "Ubah" : "Tambah"} Masa Manfaat</DialogTitle>
            <DialogDescription className="text-xs">
              Kunci = kelompok kodefikasi 5 digit (golongan 3/4/5). Isi dari
              lampiran KMK 295/2019 jo. 266/2023 — entri satker menimpa bawaan.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pnl-kode">Kode kelompok</label>
              <Input id="pnl-kode" className="font-mono" placeholder="30201" maxLength={5}
                value={formRef?.kode || ""} disabled={!!formRef?.edit}
                onChange={(e) => setFormRef((f) => ({ ...f, kode: e.target.value }))}
                data-testid="penilaian-ref-kode" />
            </div>
            <div>
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pnl-tahun">Masa manfaat (tahun)</label>
              <Input id="pnl-tahun" type="number" min="1" max="60"
                value={formRef?.tahun || ""}
                onChange={(e) => setFormRef((f) => ({ ...f, tahun: e.target.value }))}
                data-testid="penilaian-ref-tahun" />
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pnl-uraian">Uraian kelompok</label>
              <Input id="pnl-uraian" placeholder="cth. Alat Angkutan Darat Bermotor"
                value={formRef?.uraian || ""}
                onChange={(e) => setFormRef((f) => ({ ...f, uraian: e.target.value }))} />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormRef(null)}>Batal</Button>
            <Button onClick={simpanRef} disabled={formRef?.saving}
              className="bg-violet-600 hover:bg-violet-700 text-white" data-testid="penilaian-ref-simpan">
              {formRef?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <BookOpen className="w-4 h-4 mr-1.5" />}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog catat koreksi nilai ── */}
      <Dialog open={!!formKoreksi} onOpenChange={(o) => { if (!o) setFormKoreksi(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Koreksi Nilai / Hasil Penilaian</DialogTitle>
            <DialogDescription className="text-xs">
              AMAN bukan penilai — nilai wajar sah dari Laporan Penilaian DJKN; pencatatan resmi di SAKTI.
            </DialogDescription>
          </DialogHeader>
          {formKoreksi && (
            <div className="space-y-3">
              {!formKoreksi.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-cari">Cari aset</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="kor-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="koreksi-cari" />
                  </div>
                  <ul className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormKoreksi((f) => ({ ...f, aset: a, data: { ...f.data, nilai_lama: a.purchase_price ?? f.data.nilai_lama } }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`koreksi-pilih-${a.id}`}>
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
                    {formKoreksi.aset.asset_name || "-"}{" "}
                    <span className="font-mono text-[10px] text-muted-foreground">({formKoreksi.aset.asset_code} · {formKoreksi.aset.NUP})</span>
                  </span>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormKoreksi((f) => ({ ...f, aset: null }))}>
                    Ganti
                  </Button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-jenis">Jenis</label>
                  <select id="kor-jenis" value={formKoreksi.data.jenis}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="koreksi-jenis">
                    {Object.entries(koreksi?.label_jenis || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-dok">Jenis dokumen</label>
                  <select id="kor-dok" value={formKoreksi.data.jenis_dokumen}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, jenis_dokumen: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="koreksi-dok">
                    {Object.entries(koreksi?.label_dokumen || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-nomor">Nomor dokumen</label>
                  <Input id="kor-nomor" value={formKoreksi.data.nomor_dokumen}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, nomor_dokumen: e.target.value } }))}
                    data-testid="koreksi-nomor" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-tanggal">Tanggal dokumen</label>
                  <Input id="kor-tanggal" type="date" value={formKoreksi.data.tanggal_dokumen}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, tanggal_dokumen: e.target.value } }))}
                    data-testid="koreksi-tanggal" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-lama">Nilai lama (Rp)</label>
                  <Input id="kor-lama" type="number" min="0" value={formKoreksi.data.nilai_lama}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, nilai_lama: e.target.value } }))}
                    data-testid="koreksi-lama" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-baru">Nilai baru (Rp)</label>
                  <Input id="kor-baru" type="number" min="0" value={formKoreksi.data.nilai_baru}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, nilai_baru: e.target.value } }))}
                    data-testid="koreksi-baru" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-dampak">Dampak masa manfaat</label>
                  <select id="kor-dampak" value={formKoreksi.data.dampak_masa_manfaat}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, dampak_masa_manfaat: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="koreksi-dampak">
                    {Object.entries(koreksi?.label_dampak || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                {formKoreksi.data.dampak_masa_manfaat === "masa_manfaat_baru" && (
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-smt">Masa manfaat baru (semester)</label>
                    <Input id="kor-smt" type="number" min="1" value={formKoreksi.data.masa_manfaat_semester}
                      onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, masa_manfaat_semester: e.target.value } }))}
                      data-testid="koreksi-smt" />
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-penilai">Penilai/pelaksana (ops.)</label>
                  <Input id="kor-penilai" placeholder="Tim Penilai KPKNL …" value={formKoreksi.data.penilai_pelaksana}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, penilai_pelaksana: e.target.value } }))}
                    data-testid="koreksi-penilai" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="kor-catatan">Catatan (ops.)</label>
                  <Input id="kor-catatan" value={formKoreksi.data.catatan}
                    onChange={(e) => setFormKoreksi((f) => ({ ...f, data: { ...f.data, catatan: e.target.value } }))}
                    data-testid="koreksi-catatan" />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormKoreksi(null)}>Batal</Button>
                <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-white"
                  disabled={formKoreksi.saving || !formKoreksi.aset || !formKoreksi.data.nomor_dokumen.trim() || !formKoreksi.data.tanggal_dokumen}
                  onClick={simpanKoreksi} data-testid="koreksi-simpan">
                  {formKoreksi.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
