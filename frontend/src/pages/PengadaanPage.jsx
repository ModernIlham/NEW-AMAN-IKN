import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ShoppingCart, Plus, Search, Trash2, X, Coins,
  ClipboardCheck, Download, Link2, Paperclip, Upload, PackagePlus, Boxes,
  Check, Circle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { authMediaUrl } from "@/lib/mediaUrl";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BARANG_KOSONG = { uraian: "", kode: "", jumlah: "1", harga_satuan: "" };

/**
 * Pengadaan — Fase 4 tahap awal: register perolehan per dokumen
 * (Perpres 16/2018 jo. 46/2025, pustaka §10): satu entri per BAST/kontrak,
 * checklist dokumen sumber (penangkal "BAST tercecer"), tautan barang ke
 * aset master + penanda ekstrakomptabel PMK 181. Pencatatan resmi tetap
 * di SAKTI; barang belum tertaut dapat dibuatkan draft aset otomatis
 * (tombol "Buat Draft Aset", NUP berurut).
 */
export default function PengadaanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Dialog perolehan baru: {data, barang: [], saving}
  const [form, setForm] = useState(null);
  // Dialog tautkan aset: {perolehan, index, saving}
  const [taut, setTaut] = useState(null);
  // Dialog lampiran berkas: {perolehan, uploading}
  const [lamp, setLamp] = useState(null);
  // Dialog buat draft aset dari perolehan (evaluasi #5): {perolehan, activityId, saving}
  const [draftAset, setDraftAset] = useState(null);
  const [kegiatanList, setKegiatanList] = useState([]);
  const lampInputRef = useRef(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  // Opsi usulan penganggaran untuk dropdown tautan (#117 ↔ #115)
  const [opsiAnggaran, setOpsiAnggaran] = useState([]);

  const muat = useCallback(() => {
    axios.get(`${API}/pengadaan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register perolehan"))
      .finally(() => setLoading(false));
    // Daftar usulan penganggaran (opsional — kegagalan tak menahan register)
    axios.get(`${API}/penganggaran`)
      .then((r) => setOpsiAnggaran(r.data?.items || []))
      .catch(() => setOpsiAnggaran([]));
    // Daftar kegiatan inventarisasi — tujuan "buat draft aset" (best-effort)
    axios.get(`${API}/inventory-activities`)
      .then((r) => setKegiatanList(Array.isArray(r.data) ? r.data : []))
      .catch(() => setKegiatanList([]));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  useEffect(() => {
    if (!taut || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, taut]);

  const fmtRp = (n) => `Rp${Math.round(Number(n || 0)).toLocaleString("id-ID")}`;
  const labelJenis = data?.label_jenis || {};
  const kodeJenis = data?.kode_jenis || {};
  const labelDokumen = data?.label_dokumen || {};
  const dokumenWajib = data?.dokumen_wajib || {};

  const simpanPerolehan = async () => {
    if (!form) return;
    setForm((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengadaan`, {
        ...form.data,
        barang: form.barang.map((b) => ({
          ...b, jumlah: Number(b.jumlah || 0), harga_satuan: Number(b.harga_satuan || 0),
        })),
      });
      toast.success("Perolehan dicatat");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat perolehan");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const toggleDokumen = async (p, kunci) => {
    try {
      await axios.put(`${API}/pengadaan/${p.id}/dokumen`, {
        dokumen: { [kunci]: !(p.dokumen || {})[kunci] },
      });
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memperbarui checklist");
    }
  };

  const tautkan = async (assetId) => {
    if (!taut) return;
    setTaut((t) => ({ ...t, saving: true }));
    try {
      await axios.post(`${API}/pengadaan/${taut.perolehan.id}/tautkan`, {
        index: taut.index, asset_id: assetId,
      });
      toast.success(assetId ? "Barang tertaut ke aset" : "Tautan dilepas");
      setTaut(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menautkan");
      setTaut((t) => (t ? { ...t, saving: false } : t));
    }
  };

  const unggahLampiran = async (fileObj) => {
    if (!lamp || !fileObj) return;
    setLamp((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const res = await axios.post(`${API}/pengadaan/${lamp.perolehan.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLamp((l) => (l ? { ...l, uploading: false,
        perolehan: { ...l.perolehan, lampiran_berkas: res.data?.lampiran_berkas || [] } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLamp((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiran = async (fileId) => {
    if (!lamp) return;
    try {
      await axios.delete(`${API}/pengadaan/${lamp.perolehan.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLamp((l) => (l ? { ...l,
        perolehan: { ...l.perolehan,
          lampiran_berkas: (l.perolehan.lampiran_berkas || []).filter((x) => x.file_id !== fileId) } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  // Buat aset draft dari baris barang yang belum bertaut (evaluasi #5).
  const buatDraftAset = async () => {
    if (!draftAset) return;
    if (!draftAset.activityId) { toast.error("Pilih kegiatan inventarisasi tujuan"); return; }
    setDraftAset((d) => ({ ...d, saving: true }));
    try {
      const r = await axios.post(`${API}/pengadaan/${draftAset.perolehan.id}/buat-draft-aset`, {
        activity_id: draftAset.activityId,
      });
      const d = r.data || {};
      toast.success(`${d.dibuat} aset draft dibuat di "${d.kegiatan}"`
        + (d.dilewati_tertaut ? ` · ${d.dilewati_tertaut} sudah tertaut` : "")
        + (d.dilewati_tanpa_kode ? ` · ${d.dilewati_tanpa_kode} dilewati (tanpa kode barang)` : ""));
      if ((d.gagal || []).length) {
        toast.warning(`${d.gagal.length} baris gagal — contoh: ${d.gagal[0]}`);
      }
      setDraftAset(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat draft aset");
      setDraftAset((d) => (d ? { ...d, saving: false } : d));
    }
  };

  const hapus = async (p) => {
    const ok = await confirm({
      title: "Hapus register perolehan?",
      description: `${p.nomor_bast} — ${p.pihak}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengadaan/${p.id}`);
      toast.success("Register perolehan dihapus");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus");
    }
  };

  const setFormBarang = (i, k, v) => setForm((f) => ({
    ...f, barang: f.barang.map((b, idx) => (idx === i ? { ...b, [k]: v } : b)),
  }));
  // Buka dialog catat perolehan baru — dipakai tombol header & empty-state
  const bukaFormBaru = () => setForm({
    data: { jenis: "pembelian", pihak: "", nomor_kontrak: "", nomor_bast: "", tanggal_bast: new Date().toISOString().slice(0, 10), keterangan: "", penganggaran_id: "" },
    barang: [{ ...BARANG_KOSONG }], saving: false,
  });
  const r = data?.ringkasan;

  return (
    <div className="min-h-screen bg-background" data-testid="pengadaan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex flex-wrap items-center gap-2 sm:gap-3 gap-y-2">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pengadaan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-orange-600 flex items-center justify-center flex-shrink-0">
            <ShoppingCart className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight truncate">Pengadaan — Register Perolehan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Dokumen sumber per BAST/kontrak (Perpres 16/2018 jo. 46/2025)
            </p>
          </div>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            onClick={() => downloadFileWithProgress(`${API}/pengadaan/export`, "register_pengadaan.csv", { label: "Ekspor Register Pengadaan (CSV)" }).catch(() => {})}
            data-testid="pengadaan-export">
            <Download className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">CSV</span>
          </Button>
          <Button size="sm" onClick={bukaFormBaru}
            className="bg-orange-600 hover:bg-orange-700 text-white flex-shrink-0" data-testid="pengadaan-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Catat Perolehan</span>
          </Button>
          <BookingNomorButton modul="pengadaan" jenisNaskah="Berita Acara" referensi="BAST Perolehan" />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-orange-600" />
          </div>
        ) : !data ? null : (
          <>
            {/* ── Ringkasan ── */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pengadaan-stat-jumlah">
                <ShoppingCart className="w-5 h-5 text-orange-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.jumlah}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Perolehan tercatat</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pengadaan-stat-nilai">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-lg font-bold text-foreground leading-none break-all">{fmtRp(r.nilai)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai perolehan</p>
              </div>
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="pengadaan-stat-dokumen">
                <ClipboardCheck className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.dokumen_lengkap}/{r.jumlah}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Dokumen lengkap</p>
              </div>
              <div className={`bg-card rounded-xl border p-3 text-center ${r.belum_tertaut > 0 ? "border-amber-500/40" : "border-border"}`} data-testid="pengadaan-stat-tertaut">
                <Link2 className={`w-5 h-5 mx-auto mb-1 ${r.belum_tertaut > 0 ? "text-amber-500" : "text-muted-foreground"}`} />
                <p className="text-lg font-bold text-foreground leading-none">{r.belum_tertaut}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Barang belum tertaut aset</p>
              </div>
            </div>

            {/* ── Daftar perolehan ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <ShoppingCart className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Belum ada perolehan tercatat — mulai dari BAST/kontrak terbaru.</p>
                  <Button size="sm" className="mt-3 bg-orange-600 hover:bg-orange-700 text-white"
                    onClick={bukaFormBaru} data-testid="pengadaan-empty-tambah">
                    <Plus className="w-4 h-4 mr-1.5" />Catat Perolehan Pertama
                  </Button>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((p) => (
                    <li key={p.id} className="p-3" data-testid={`pengadaan-row-${p.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-600 dark:text-orange-400 text-[10px] font-semibold">
                          {labelJenis[p.jenis] || p.jenis} · {kodeJenis[p.jenis]}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{p.pihak}</p>
                        <span className="text-xs font-bold text-foreground whitespace-nowrap">{fmtRp(p.nilai)}</span>
                        {(() => {
                          const w = dokumenWajib[p.jenis] || [];
                          if (!w.length) return null;
                          const n = w.filter((k) => (p.dokumen || {})[k]).length;
                          return (
                            <span title={`${n} dari ${w.length} dokumen wajib tersedia`}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold flex-shrink-0 ${
                                n === w.length
                                  ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                                  : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                              }`}
                              data-testid={`pengadaan-dok-ringkas-${p.id}`}>
                              {n}/{w.length} dok
                            </span>
                          );
                        })()}
                        {(p.barang || []).some((b) => !b.asset_id) && (
                          <button type="button" aria-label="Buat draft aset dari perolehan"
                            title="Buat draft aset untuk barang yang belum bertaut"
                            onClick={() => setDraftAset({ perolehan: p, activityId: "", saving: false })}
                            className="h-7 px-2 rounded-lg border border-emerald-500/40 bg-emerald-600/10 text-emerald-600 dark:text-emerald-400 flex items-center gap-1 text-[10px] font-semibold hover:bg-emerald-600/20 min-h-0 min-w-0"
                            data-testid={`pengadaan-draft-aset-${p.id}`}>
                            <PackagePlus className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Buat Draft Aset</span>
                          </button>
                        )}
                        {(p.barang || []).some((b) => String(b.kode || "").startsWith("1") && !b.psd_item_id) && (
                          <button type="button" aria-label="Daftarkan barang konsumsi ke Persediaan"
                            title="Barang ber-kode '1…' → master persediaan + transaksi masuk berjurnal FIFO"
                            onClick={async () => {
                              try {
                                const r = await axios.post(`${API}/pengadaan/${p.id}/daftarkan-persediaan`);
                                const d = r.data || {};
                                toast.success(`${d.masuk || 0} barang masuk persediaan (${d.dibuat_master || 0} master baru)`);
                                if ((d.gagal || []).length) toast.warning(`Gagal: ${d.gagal.join("; ")}`, { duration: 9000 });
                                muat();
                              } catch (e) {
                                toast.error(e?.response?.data?.detail || "Gagal mendaftarkan ke persediaan");
                              }
                            }}
                            className="h-7 px-2 rounded-lg border border-cyan-500/40 bg-cyan-600/10 text-cyan-600 dark:text-cyan-400 flex items-center gap-1 text-[10px] font-semibold hover:bg-cyan-600/20 min-h-0 min-w-0"
                            data-testid={`pengadaan-daftarkan-psd-${p.id}`}>
                            <Boxes className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Daftarkan ke Persediaan</span>
                          </button>
                        )}
                        <button type="button" aria-label="Lampiran berkas"
                          onClick={() => setLamp({ perolehan: p, uploading: false })}
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0"
                          data-testid={`pengadaan-lampiran-${p.id}`}>
                          <Paperclip className="w-3.5 h-3.5" />
                        </button>
                        {isAdmin && (
                          <button type="button" aria-label="Hapus perolehan" onClick={() => hapus(p)}
                            className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        {`BAST ${p.nomor_bast} (${p.tanggal_bast})`}
                        {p.nomor_kontrak && ` · Kontrak ${p.nomor_kontrak}`}
                        {p.keterangan && ` · ${p.keterangan}`}
                        {` · oleh ${p.created_by}`}
                      </p>
                      {p.penganggaran_id && (
                        <p className="text-[11px] text-violet-600 dark:text-violet-400 mt-0.5 truncate" data-testid={`pengadaan-anggaran-${p.id}`}>
                          Anggaran: {p.penganggaran_uraian || "(usulan)"}
                          {p.penganggaran_tahun && ` · TA ${p.penganggaran_tahun}`}
                          {p.penganggaran_nomor_dipa && ` · ${p.penganggaran_nomor_dipa}`}
                        </p>
                      )}
                      {/* Checklist dokumen sumber */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {(dokumenWajib[p.jenis] || []).map((k) => {
                          const ada = !!(p.dokumen || {})[k];
                          return (
                            <button key={k} type="button" onClick={() => toggleDokumen(p, k)}
                              title="Klik untuk menandai dokumen ada/belum"
                              className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border transition-colors min-h-0 ${
                                ada
                                  ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/40"
                                  : "bg-muted text-muted-foreground border-border hover:text-foreground"
                              }`}
                              data-testid={`pengadaan-dok-${p.id}-${k}`}>
                              {ada ? <Check className="w-3 h-3 inline mr-0.5" /> : <Circle className="w-3 h-3 inline mr-0.5" />}
                              {labelDokumen[k] || k}
                            </button>
                          );
                        })}
                      </div>
                      {/* Daftar barang */}
                      <ul className="mt-1.5 space-y-1">
                        {(p.barang || []).map((b, i) => (
                          <li key={`${p.id}-${i}`} className="rounded-lg border border-border/70 px-2 py-1.5 flex flex-wrap items-center gap-2">
                            <span className="min-w-0 flex-1">
                              <span className="block text-xs font-semibold text-foreground truncate">
                                {b.uraian} <span className="font-normal text-muted-foreground">×{b.jumlah} @ {fmtRp(b.harga_satuan)}</span>
                              </span>
                              {b.asset_id ? (
                                <span className="block text-[10px] text-emerald-600 dark:text-emerald-400 font-mono truncate">
                                  <Link2 className="w-3 h-3 inline mr-0.5 align-[-2px]" />{b.asset_name} ({b.asset_code} · {b.NUP})
                                </span>
                              ) : (
                                <span className="block text-[10px] text-amber-600 dark:text-amber-400">Belum tertaut ke aset master</span>
                              )}
                            </span>
                            {b.ekstrakomptabel && (
                              <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                                Ekstrakomptabel
                              </span>
                            )}
                            <Button size="sm" variant="outline" className="h-6 text-[10px] min-h-0 px-2"
                              onClick={() => { setCari(""); setHasilCari([]); setTaut({ perolehan: p, index: i, saving: false }); }}
                              data-testid={`pengadaan-taut-${p.id}-${i}`}>
                              {b.asset_id ? "Ubah Tautan" : "Tautkan"}
                            </Button>
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog perolehan baru ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Perolehan</DialogTitle>
            <DialogDescription className="text-xs">
              Satu entri per dokumen BAST/kontrak — BAST adalah pemicu pencatatan BMN.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-jenis">Jenis perolehan</label>
                <select id="pgd-jenis" value={form.data.jenis}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, jenis: e.target.value } }))}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pengadaan-jenis">
                  {Object.entries(labelJenis).length
                    ? Object.entries(labelJenis).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                    : <option value="pembelian">Pembelian</option>}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-pihak">Penyedia/pemberi</label>
                <Input id="pgd-pihak" placeholder="cth. CV Sumber Rejeki" value={form.data.pihak}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, pihak: e.target.value } }))}
                  data-testid="pengadaan-pihak" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-kontrak">No. Kontrak/SPK (opsional)</label>
                <Input id="pgd-kontrak" value={form.data.nomor_kontrak}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, nomor_kontrak: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-bast">No. BAST</label>
                <Input id="pgd-bast" placeholder="BAST-01/2026" value={form.data.nomor_bast}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, nomor_bast: e.target.value } }))}
                  data-testid="pengadaan-nomor-bast" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-tgl">Tanggal BAST</label>
                <Input id="pgd-tgl" type="date" value={form.data.tanggal_bast}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, tanggal_bast: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-ket">Keterangan</label>
                <Input id="pgd-ket" value={form.data.keterangan}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))} />
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pgd-anggaran">Usulan Penganggaran terkait (opsional)</label>
                <select id="pgd-anggaran" value={form.data.penganggaran_id}
                  onChange={(e) => setForm((f) => ({ ...f, data: { ...f.data, penganggaran_id: e.target.value } }))}
                  className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  data-testid="pengadaan-penganggaran">
                  <option value="">— Tidak ditautkan —</option>
                  {opsiAnggaran.map((u) => (
                    <option key={u.id} value={u.id}>
                      {`${u.tahun_anggaran || "?"} · ${u.uraian || "(tanpa uraian)"}${u.nomor_dipa ? ` · ${u.nomor_dipa}` : ""}`}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-span-2 space-y-2">
                <p className="text-xs font-medium text-foreground">Daftar barang</p>
                {form.barang.map((b, i) => (
                  <div key={i} className="rounded-lg border border-border p-2 grid grid-cols-6 sm:grid-cols-8 gap-2">
                    <div className="col-span-6 sm:col-span-3">
                      <Input placeholder="Uraian barang" value={b.uraian}
                        onChange={(e) => setFormBarang(i, "uraian", e.target.value)}
                        data-testid={`pengadaan-barang-uraian-${i}`} />
                    </div>
                    <div className="col-span-3 sm:col-span-2">
                      <Input placeholder="Kode (ops.)" className="font-mono" value={b.kode}
                        onChange={(e) => setFormBarang(i, "kode", e.target.value)} />
                    </div>
                    <div className="col-span-1">
                      <Input type="number" min="1" placeholder="Jml" value={b.jumlah}
                        onChange={(e) => setFormBarang(i, "jumlah", e.target.value)} />
                    </div>
                    <div className="col-span-2 sm:col-span-2 flex gap-1">
                      <Input type="number" min="0" placeholder="Harga satuan" value={b.harga_satuan}
                        onChange={(e) => setFormBarang(i, "harga_satuan", e.target.value)}
                        data-testid={`pengadaan-barang-harga-${i}`} />
                      {form.barang.length > 1 && (
                        <button type="button" aria-label="Hapus baris barang"
                          onClick={() => setForm((f) => ({ ...f, barang: f.barang.filter((_, idx) => idx !== i) }))}
                          className="h-9 w-9 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0 min-h-0 min-w-0">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <Button size="sm" variant="outline" className="h-8 text-xs min-h-0"
                  onClick={() => setForm((f) => ({ ...f, barang: [...f.barang, { ...BARANG_KOSONG }] }))}>
                  <Plus className="w-3.5 h-3.5 mr-1" />Tambah baris
                </Button>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpanPerolehan} disabled={form?.saving}
              className="bg-orange-600 hover:bg-orange-700 text-white" data-testid="pengadaan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <ShoppingCart className="w-4 h-4 mr-1.5" />}Catat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog tautkan aset ── */}
      <Dialog open={!!taut} onOpenChange={(o) => { if (!o) setTaut(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tautkan ke Aset Master</DialogTitle>
            <DialogDescription className="text-xs">
              {taut && `${taut.perolehan.barang?.[taut.index]?.uraian || ""} — cegah entri ganda dengan menautkan ke aset yang sudah dicatat.`}
            </DialogDescription>
          </DialogHeader>
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
            <Input className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
              value={cari} onChange={(e) => setCari(e.target.value)} data-testid="pengadaan-cari-aset" />
          </div>
          {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
            <div className="max-h-52 overflow-y-auto rounded-lg border border-border">
              {mencari ? (
                <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-orange-600" /></div>
              ) : hasilCari.map((a) => (
                <button key={a.id} type="button" onClick={() => tautkan(a.id)} disabled={taut?.saving}
                  className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                  <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                  <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP} · {a.condition}</span>
                </button>
              ))}
            </div>
          )}
          <DialogFooter className="gap-2">
            {taut?.perolehan?.barang?.[taut?.index]?.asset_id && (
              <Button variant="outline" className="text-red-500 hover:text-red-600" disabled={taut?.saving}
                onClick={() => tautkan("")}>
                Lepas Tautan
              </Button>
            )}
            <Button variant="outline" onClick={() => setTaut(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran berkas perolehan ── */}
      <Dialog open={!!lamp} onOpenChange={(o) => { if (!o) setLamp(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Lampiran Berkas Perolehan</DialogTitle>
            <DialogDescription className="text-xs">
              {lamp && `BAST ${lamp.perolehan.nomor_bast} — ${lamp.perolehan.pihak}. Scan kontrak/BAPHP/BAST/kuitansi/SP2D (PDF/JPG/PNG, maks 10MB, 10 berkas).`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiran(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lamp?.uploading || (lamp?.perolehan?.lampiran_berkas || []).length >= 10}
            onClick={() => lampInputRef.current?.click()} data-testid="pengadaan-lampiran-unggah">
            {lamp?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lamp?.perolehan?.lampiran_berkas || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran berkas.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lamp?.perolehan?.lampiran_berkas || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/pengadaan/${lamp.perolehan.id}/lampiran/${f.file_id}`), "_blank", "noopener")}
                    className="min-w-0 flex-1 text-left hover:underline">
                    <span className="block text-xs font-semibold text-foreground truncate">{f.filename}</span>
                    <span className="block text-[10px] text-muted-foreground">
                      {String(f.tanggal || "").slice(0, 10)} · oleh {f.oleh}
                    </span>
                  </button>
                  {isAdmin && (
                    <button type="button" aria-label="Hapus lampiran" onClick={() => hapusLampiran(f.file_id)}
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

      {/* ── Dialog buat draft aset dari perolehan (evaluasi #5) ── */}
      <Dialog open={!!draftAset} onOpenChange={(o) => { if (!o) setDraftAset(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Buat Draft Aset — BAST {draftAset?.perolehan?.nomor_bast}</DialogTitle>
            <DialogDescription className="text-xs">
              Tiap baris barang yang <strong>belum bertaut</strong> dibuatkan aset draft
              (status &quot;Belum Diinventarisasi&quot;) di kegiatan terpilih — NUP otomatis,
              harga/tanggal/BAST terisi dari perolehan, lalu tertaut balik. Baris tanpa
              kode barang dilewati (isi kode dulu lewat Tautkan/registrasi).
            </DialogDescription>
          </DialogHeader>
          {draftAset && (
            <div className="space-y-3">
              <p className="text-xs text-foreground/90">
                {(draftAset.perolehan.barang || []).filter((b) => !b.asset_id && (b.kode || "").trim()).length} baris siap dibuatkan draft
                {(draftAset.perolehan.barang || []).some((b) => !b.asset_id && !(b.kode || "").trim())
                  && ` · ${(draftAset.perolehan.barang || []).filter((b) => !b.asset_id && !(b.kode || "").trim()).length} baris tanpa kode akan dilewati`}
              </p>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="draft-aset-kegiatan">Kegiatan inventarisasi tujuan</label>
                <select id="draft-aset-kegiatan" value={draftAset.activityId}
                  onChange={(e) => setDraftAset((d) => ({ ...d, activityId: e.target.value }))}
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                  data-testid="pengadaan-draft-kegiatan">
                  <option value="">— pilih kegiatan —</option>
                  {kegiatanList.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.nama_kegiatan || k.id}{k.tahun ? ` (${k.tahun})` : ""}
                    </option>
                  ))}
                </select>
                {kegiatanList.length === 0 && (
                  <p className="text-[10px] text-muted-foreground mt-1">Belum ada kegiatan inventarisasi — buat dulu di halaman kegiatan.</p>
                )}
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setDraftAset(null)}>Batal</Button>
            <Button onClick={buatDraftAset} disabled={draftAset?.saving || !draftAset?.activityId}
              data-testid="pengadaan-draft-submit">
              {draftAset?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <PackagePlus className="w-4 h-4 mr-1.5" />}
              Buat Draft
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
