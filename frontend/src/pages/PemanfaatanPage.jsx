import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, Handshake, Plus, Search, Trash2, X, Pencil,
  CalendarClock, Coins, AlertTriangle, Paperclip, Upload, Download,
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

const WARNA_STATUS = {
  aktif: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  jatuh_tempo: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  tidak_lengkap: "bg-red-500/15 text-red-600 dark:text-red-400",
  berakhir: "bg-muted text-muted-foreground",
};

const FORM_KOSONG = {
  bentuk: "sewa", mitra: "", jenis_mitra: "", mulai: "", berakhir: "",
  nilai: "", nomor_persetujuan: "", nomor_perjanjian: "", ntpn: "",
  kontribusi_tahunan: "", dasar_fasilitas: "tanpa_fasilitas",
  nomor_penetapan_fasilitas: "", pelaksana_fasilitas: "", keterangan: "",
};

// Fasilitas transaksi (PMK 18/2024 / PMK 139/2022) hanya untuk KSP/BGS-BSG
const BENTUK_DAPAT_FASILITAS = ["ksp", "bgs_bsg"];

/**
 * Pemanfaatan — Fase 5 tahap awal: register perjanjian pemanfaatan BMN
 * (PMK 115/2020). Satker = pengusul & penatausaha; status Aktif menuntut
 * nomor persetujuan Pengelola + perjanjian (sewa: + NTPN) — mencegah
 * temuan auditor tersering secara struktural. Kontribusi tahunan (KSP/
 * BGS/KSPI) tercatat per tahun ber-NTPN dengan pengingat tunggakan;
 * scan dokumen perjanjian terlampir per register.
 */
export default function PemanfaatanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bentukList, setBentukList] = useState([]);
  // Dialog: {id?, data, aset, saving}
  const [form, setForm] = useState(null);
  // Dialog catat kontribusi: {perjanjian, fields{tahun,ntpn,tanggal,jumlah}, saving}
  const [kontrib, setKontrib] = useState(null);
  // Dialog lampiran: {perjanjian, uploading}
  const [lamp, setLamp] = useState(null);
  const lampInputRef = useRef(null);
  const [cari, setCari] = useState("");
  const [hasilCari, setHasilCari] = useState([]);
  const [mencari, setMencari] = useState(false);
  const cariTimer = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muat = useCallback(() => {
    axios.get(`${API}/pemanfaatan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat register pemanfaatan"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { muat(); }, [muat]);
  useEffect(() => {
    axios.get(`${API}/pemanfaatan/bentuk`)
      .then((r) => setBentukList(r.data?.items || []))
      .catch(() => {});
  }, []);

  // Pencarian aset (debounce) untuk objek BMN
  useEffect(() => {
    if (!form || form.aset || cari.trim().length < 2) { setHasilCari([]); return undefined; }
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
  const setField = (k, v) => setForm((f) => ({ ...f, data: { ...f.data, [k]: v } }));

  const buka = (p = null) => {
    setCari(""); setHasilCari([]);
    setForm(p ? {
      id: p.id, saving: false,
      aset: p.asset_id ? { id: p.asset_id, asset_name: p.asset_name, asset_code: p.asset_code, NUP: p.NUP } : null,
      data: {
        bentuk: p.bentuk, mitra: p.mitra, jenis_mitra: p.jenis_mitra || "",
        mulai: p.mulai, berakhir: p.berakhir, nilai: String(p.nilai ?? ""),
        nomor_persetujuan: p.nomor_persetujuan || "", nomor_perjanjian: p.nomor_perjanjian || "",
        ntpn: p.ntpn || "", kontribusi_tahunan: String(p.kontribusi_tahunan ?? ""),
        dasar_fasilitas: p.dasar_fasilitas || "tanpa_fasilitas",
        nomor_penetapan_fasilitas: p.nomor_penetapan_fasilitas || "",
        pelaksana_fasilitas: p.pelaksana_fasilitas || "",
        keterangan: p.keterangan || "",
      },
    } : { id: null, aset: null, saving: false, data: { ...FORM_KOSONG } });
  };

  const simpan = async () => {
    if (!form) return;
    setForm((f) => ({ ...f, saving: true }));
    try {
      const payload = {
        ...form.data,
        nilai: parseFloat(form.data.nilai) || 0,
        kontribusi_tahunan: parseFloat(form.data.kontribusi_tahunan) || 0,
        asset_id: form.aset?.id || "",
      };
      if (form.id) await axios.put(`${API}/pemanfaatan/${form.id}`, payload);
      else await axios.post(`${API}/pemanfaatan`, payload);
      toast.success("Register pemanfaatan tersimpan");
      setForm(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan register");
      setForm((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapus = async (p) => {
    const ok = await confirm({
      title: "Hapus register?",
      description: `${labelBentuk[p.bentuk] || p.bentuk} — ${p.mitra}. Hanya untuk salah input.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pemanfaatan/${p.id}`);
      toast.success("Register dihapus");
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus");
    }
  };

  const simpanKontribusi = async () => {
    if (!kontrib) return;
    setKontrib((k) => ({ ...k, saving: true }));
    try {
      await axios.post(`${API}/pemanfaatan/${kontrib.perjanjian.id}/kontribusi`, {
        ...kontrib.fields,
        jumlah: parseFloat(kontrib.fields.jumlah) || 0,
      });
      toast.success(`Kontribusi tahun ${kontrib.fields.tahun} tercatat`);
      setKontrib(null);
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat kontribusi");
      setKontrib((k) => (k ? { ...k, saving: false } : k));
    }
  };

  // jenis lampiran aktif di dialog: "lampiran" (dokumen) | "wasdal"
  const lampPath = lamp?.jenis === "wasdal" ? "wasdal" : "lampiran";
  const lampField = lamp?.jenis === "wasdal" ? "lampiran_wasdal" : "lampiran";

  const unggahLampiran = async (fileObj) => {
    if (!lamp || !fileObj) return;
    setLamp((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", fileObj);
      const res = await axios.post(`${API}/pemanfaatan/${lamp.perjanjian.id}/${lampPath}`, fd);
      toast.success("Lampiran terunggah");
      setLamp((l) => (l ? { ...l, uploading: false,
        perjanjian: { ...l.perjanjian, [lampField]: res.data?.[lampField] || [] } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLamp((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiran = async (fileId) => {
    if (!lamp) return;
    try {
      await axios.delete(`${API}/pemanfaatan/${lamp.perjanjian.id}/${lampPath}/${fileId}`);
      toast.success("Lampiran dihapus");
      setLamp((l) => (l ? { ...l,
        perjanjian: { ...l.perjanjian,
          [lampField]: (l.perjanjian[lampField] || []).filter((x) => x.file_id !== fileId) } } : l));
      muat();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  const labelStatus = data?.label_status || {};
  const labelBentuk = data?.label_bentuk || {};
  const r = data?.ringkasan;

  return (
    <div className="min-h-screen bg-background" data-testid="pemanfaatan-page">
      {/* ── Header ── */}
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pemanfaatan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center flex-shrink-0">
            <Handshake className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Pemanfaatan — Register Perjanjian</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Sewa · Pinjam Pakai · KSP · BGS/BSG · KSPI · KETUPI (PMK 115/2020)
            </p>
          </div>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            onClick={() => downloadFileWithProgress(`${API}/pemanfaatan/export`, "register_pemanfaatan.csv", { label: "Ekspor Register Pemanfaatan (CSV)" }).catch(() => {})}
            data-testid="pemanfaatan-export">
            <Download className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">CSV</span>
          </Button>
          <Button size="sm" onClick={() => buka()} className="bg-teal-600 hover:bg-teal-700 text-white flex-shrink-0" data-testid="pemanfaatan-tambah">
            <Plus className="w-4 h-4 sm:mr-1.5" /><span className="hidden sm:inline">Catat</span>
          </Button>
          <BookingNomorButton modul="pemanfaatan" jenisNaskah="Laporan" referensi="Register Pemanfaatan" />
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
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              <div className="bg-card rounded-xl border border-emerald-500/40 p-3 text-center" data-testid="pemanfaatan-stat-aktif">
                <Handshake className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.per_status.aktif}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Aktif</p>
              </div>
              <div className="bg-card rounded-xl border border-amber-500/40 p-3 text-center" data-testid="pemanfaatan-stat-tempo">
                <CalendarClock className="w-5 h-5 text-amber-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.per_status.jatuh_tempo}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Jatuh tempo ≤60 hari</p>
              </div>
              <div className="bg-card rounded-xl border border-red-500/40 p-3 text-center" data-testid="pemanfaatan-stat-kurang">
                <AlertTriangle className="w-5 h-5 text-red-500 mx-auto mb-1" />
                <p className="text-lg font-bold text-foreground leading-none">{r.per_status.tidak_lengkap}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Dokumen belum lengkap</p>
              </div>
              <div className="bg-card rounded-xl border border-border p-3 text-center" data-testid="pemanfaatan-stat-nilai">
                <Coins className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                <p className="text-sm sm:text-base font-bold text-foreground leading-none break-all">{fmtRp(r.total_nilai)}</p>
                <p className="text-[10px] text-muted-foreground mt-1">Nilai tercatat (PNBP ke Kas Negara)</p>
              </div>
            </div>

            {/* ── Daftar register ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {data.items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <Handshake className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">Belum ada perjanjian pemanfaatan tercatat.</p>
                </div>
              ) : (
                <ul className="divide-y divide-border/60">
                  {data.items.map((p) => (
                    <li key={p.id} className="p-3" data-testid={`pemanfaatan-row-${p.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS[p.status] || "bg-muted"}`}>
                          {labelStatus[p.status] || p.status}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-teal-500/15 text-teal-600 dark:text-teal-400 text-[10px] font-semibold">
                          {labelBentuk[p.bentuk] || p.bentuk}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{p.mitra}</p>
                        <span className="text-xs font-bold text-foreground">{fmtRp(p.nilai)}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-1 truncate">
                        {p.mulai} s.d. {p.berakhir}
                        {p.asset_name && <> · {p.asset_name} <span className="font-mono">({p.asset_code} · {p.NUP})</span></>}
                        {p.nomor_perjanjian && ` · Perjanjian ${p.nomor_perjanjian}`}
                        {p.keterangan && ` · ${p.keterangan}`}
                      </p>
                      {p.kekurangan?.length > 0 && (
                        <p className="text-[11px] text-red-500/90 mt-0.5">{p.kekurangan.join("; ")}</p>
                      )}
                      {(p.peringatan_kontribusi || []).map((w) => (
                        <p key={w} className="text-[11px] text-amber-600 dark:text-amber-400 mt-0.5 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3 flex-shrink-0" />{w}
                        </p>
                      ))}
                      {(p.kontribusi || []).length > 0 && (
                        <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                          Kontribusi tercatat: {(p.kontribusi || []).map((k) => k.tahun).join(", ")}
                        </p>
                      )}
                      {p.dasar_fasilitas && p.dasar_fasilitas !== "tanpa_fasilitas" && (
                        <p className="text-[11px] text-muted-foreground mt-0.5 truncate">
                          {(data?.label_dasar_fasilitas || {})[p.dasar_fasilitas] || p.dasar_fasilitas}
                          {p.nomor_penetapan_fasilitas ? ` — ${p.nomor_penetapan_fasilitas}` : ""}
                        </p>
                      )}
                      <div className="flex gap-1.5 mt-1.5">
                        <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                          onClick={() => setLamp({ perjanjian: p, jenis: "lampiran", uploading: false })}
                          data-testid={`pemanfaatan-lampiran-${p.id}`}>
                          <Paperclip className="w-3 h-3 mr-1" />Lampiran{(p.lampiran || []).length > 0 && ` (${p.lampiran.length})`}
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                          onClick={() => setLamp({ perjanjian: p, jenis: "wasdal", uploading: false })}
                          data-testid={`pemanfaatan-wasdal-${p.id}`}>
                          <Paperclip className="w-3 h-3 mr-1" />Wasdal{(p.lampiran_wasdal || []).length > 0 && ` (${p.lampiran_wasdal.length})`}
                        </Button>
                        {Number(p.kontribusi_tahunan) > 0 && p.status !== "berakhir" && (
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => setKontrib({ perjanjian: p, saving: false, fields: { tahun: String(new Date().getFullYear()), ntpn: "", tanggal: new Date().toISOString().slice(0, 10), jumlah: String(p.kontribusi_tahunan) } })}
                            data-testid={`pemanfaatan-kontribusi-${p.id}`}>
                            Catat Kontribusi
                          </Button>
                        )}
                        <button type="button" onClick={() => buka(p)} aria-label="Ubah register"
                          className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted min-h-0 min-w-0">
                          <Pencil className="w-3 h-3" />
                        </button>
                        {isAdmin && (
                          <button type="button" onClick={() => hapus(p)} aria-label="Hapus register"
                            className="h-7 w-7 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-h-0 min-w-0">
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">{data.catatan}</p>
          </>
        )}
      </main>

      {/* ── Dialog catat/ubah register ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?.id ? "Ubah" : "Catat"} Perjanjian Pemanfaatan</DialogTitle>
            <DialogDescription className="text-xs">
              Status Aktif menuntut nomor persetujuan Pengelola + perjanjian
              {form?.data?.bentuk === "sewa" ? " + NTPN setor PNBP" : ""}.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-aset">Objek BMN (opsional)</label>
                {form.aset ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-border p-2">
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-foreground truncate">{form.aset.asset_name}</span>
                      <span className="block text-[10px] text-muted-foreground font-mono">{form.aset.asset_code} · {form.aset.NUP}</span>
                    </span>
                    <button type="button" onClick={() => setForm((f) => ({ ...f, aset: null }))} aria-label="Lepas aset"
                      className="h-7 w-7 rounded-lg border border-border text-foreground/70 flex items-center justify-center hover:bg-muted flex-shrink-0 min-h-0 min-w-0">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
                    <Input id="pmf-aset" className="pl-8" placeholder="Cari nama/kode aset (min. 2 huruf)"
                      value={cari} onChange={(e) => setCari(e.target.value)} />
                    {(mencari || hasilCari.length > 0) && cari.trim().length >= 2 && (
                      <div className="absolute z-50 mt-1 w-full max-h-44 overflow-y-auto rounded-lg border border-border bg-card shadow-lg">
                        {mencari ? (
                          <div className="flex justify-center py-3"><Loader2 className="w-4 h-4 animate-spin text-teal-600" /></div>
                        ) : hasilCari.map((a) => (
                          <button key={a.id} type="button"
                            onClick={() => { setForm((f) => ({ ...f, aset: a })); setCari(""); setHasilCari([]); }}
                            className="w-full px-2.5 py-1.5 text-left hover:bg-muted">
                            <span className="block text-xs font-semibold text-foreground truncate">{a.asset_name}</span>
                            <span className="block text-[10px] text-muted-foreground font-mono">{a.asset_code} · {a.NUP}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-bentuk">Bentuk</label>
                <select id="pmf-bentuk" value={form.data.bentuk}
                  onChange={(e) => setField("bentuk", e.target.value)}
                  className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                  data-testid="pemanfaatan-bentuk">
                  {(bentukList.length ? bentukList : [{ key: "sewa", label: "Sewa", maks_tahun: 5 }]).map((b) => (
                    <option key={b.key} value={b.key}>{b.label} (maks {b.maks_tahun} th)</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-mitra">Mitra</label>
                <Input id="pmf-mitra" placeholder="cth. PT Maju Bersama"
                  value={form.data.mitra} onChange={(e) => setField("mitra", e.target.value)}
                  data-testid="pemanfaatan-mitra" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-jmitra">Jenis Mitra</label>
                <Input id="pmf-jmitra" placeholder="BUMN/PT/koperasi/Pemda"
                  value={form.data.jenis_mitra} onChange={(e) => setField("jenis_mitra", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-mulai">Mulai</label>
                <Input id="pmf-mulai" type="date" value={form.data.mulai}
                  onChange={(e) => setField("mulai", e.target.value)} data-testid="pemanfaatan-mulai" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-akhir">Berakhir</label>
                <Input id="pmf-akhir" type="date" value={form.data.berakhir}
                  onChange={(e) => setField("berakhir", e.target.value)} data-testid="pemanfaatan-berakhir" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-nilai">Nilai (Rp)</label>
                <Input id="pmf-nilai" type="number" min="0" placeholder="0"
                  value={form.data.nilai} onChange={(e) => setField("nilai", e.target.value)} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-setuju">No. Persetujuan Pengelola</label>
                <Input id="pmf-setuju" placeholder="cth. S-11/KNL.05/2026"
                  value={form.data.nomor_persetujuan} onChange={(e) => setField("nomor_persetujuan", e.target.value)}
                  data-testid="pemanfaatan-persetujuan" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-pj">No. Perjanjian</label>
                <Input id="pmf-pj" value={form.data.nomor_perjanjian}
                  onChange={(e) => setField("nomor_perjanjian", e.target.value)} />
              </div>
              {form.data.bentuk === "sewa" && (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-ntpn">NTPN Setor PNBP</label>
                  <Input id="pmf-ntpn" className="font-mono" value={form.data.ntpn}
                    onChange={(e) => setField("ntpn", e.target.value)} data-testid="pemanfaatan-ntpn" />
                </div>
              )}
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-kontrib">Kontribusi tahunan (Rp, 0 = tidak ada)</label>
                <Input id="pmf-kontrib" type="number" min="0" placeholder="0"
                  value={form.data.kontribusi_tahunan}
                  onChange={(e) => setField("kontribusi_tahunan", e.target.value)}
                  data-testid="pemanfaatan-kontribusi-tahunan" />
              </div>
              {BENTUK_DAPAT_FASILITAS.includes(form.data.bentuk) && (
                <>
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-fasilitas">
                      Fasilitas transaksi (pendampingan — bukan bentuk pemanfaatan)
                    </label>
                    <select id="pmf-fasilitas" value={form.data.dasar_fasilitas}
                      onChange={(e) => setField("dasar_fasilitas", e.target.value)}
                      className="w-full h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground"
                      data-testid="pemanfaatan-dasar-fasilitas">
                      {Object.entries(data?.label_dasar_fasilitas || { tanpa_fasilitas: "Tanpa fasilitas" }).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                  {form.data.dasar_fasilitas !== "tanpa_fasilitas" && (
                    <>
                      <div>
                        <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-fas-no">No. penetapan fasilitas</label>
                        <Input id="pmf-fas-no" value={form.data.nomor_penetapan_fasilitas}
                          onChange={(e) => setField("nomor_penetapan_fasilitas", e.target.value)}
                          data-testid="pemanfaatan-nomor-fasilitas" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-fas-pelaksana">Pelaksana fasilitas (BUMN)</label>
                        <Input id="pmf-fas-pelaksana" placeholder="mis. PT PII" value={form.data.pelaksana_fasilitas}
                          onChange={(e) => setField("pelaksana_fasilitas", e.target.value)} />
                      </div>
                    </>
                  )}
                </>
              )}
              <div className="col-span-2">
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-ket">Keterangan</label>
                <Input id="pmf-ket" value={form.data.keterangan}
                  onChange={(e) => setField("keterangan", e.target.value)} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={simpan} disabled={form?.saving}
              className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="pemanfaatan-simpan">
              {form?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Handshake className="w-4 h-4 mr-1.5" />}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran (dokumen perjanjian ATAU laporan wasdal) ── */}
      <Dialog open={!!lamp} onOpenChange={(o) => { if (!o) setLamp(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{lamp?.jenis === "wasdal" ? "Lampiran Wasdal" : "Lampiran Dokumen"}</DialogTitle>
            <DialogDescription className="text-xs">
              {lamp && `${labelBentuk[lamp.perjanjian.bentuk] || lamp.perjanjian.bentuk} — ${lamp.perjanjian.mitra}. ${lamp.jenis === "wasdal"
                ? "Laporan monitoring/BA peninjauan lapangan atas pelaksanaan pemanfaatan (PDF/JPG/PNG, maks 10MB, 10 berkas)."
                : "Scan persetujuan/perjanjian/bukti setor (PDF/JPG/PNG, maks 10MB, 10 berkas)."}`}
            </DialogDescription>
          </DialogHeader>
          <input ref={lampInputRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) unggahLampiran(f); }} />
          <Button size="sm" variant="outline" className="h-8 text-xs min-h-0 self-start"
            disabled={lamp?.uploading || (lamp?.perjanjian?.[lampField] || []).length >= 10}
            onClick={() => lampInputRef.current?.click()} data-testid="pemanfaatan-lampiran-unggah">
            {lamp?.uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            Unggah Berkas
          </Button>
          {(lamp?.perjanjian?.[lampField] || []).length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">Belum ada lampiran.</p>
          ) : (
            <ul className="space-y-1.5">
              {(lamp?.perjanjian?.[lampField] || []).map((f) => (
                <li key={f.file_id} className="rounded-lg border border-border p-2 flex items-center gap-2">
                  <button type="button"
                    onClick={() => window.open(authMediaUrl(`${API}/pemanfaatan/${lamp.perjanjian.id}/${lampPath}/${f.file_id}`), "_blank", "noopener")}
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

      {/* ── Dialog catat kontribusi tahunan ── */}
      <Dialog open={!!kontrib} onOpenChange={(o) => { if (!o) setKontrib(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Catat Kontribusi Tahunan</DialogTitle>
            <DialogDescription className="text-xs">
              {kontrib && `${labelBentuk[kontrib.perjanjian.bentuk] || kontrib.perjanjian.bentuk} — ${kontrib.perjanjian.mitra}. PNBP disetor mitra ke Kas Negara; NTPN sebagai bukti.`}
            </DialogDescription>
          </DialogHeader>
          {kontrib && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-k-tahun">Tahun</label>
                <Input id="pmf-k-tahun" inputMode="numeric" maxLength={4} value={kontrib.fields.tahun}
                  onChange={(e) => setKontrib((k) => ({ ...k, fields: { ...k.fields, tahun: e.target.value.replace(/\D/g, "") } }))}
                  data-testid="pemanfaatan-k-tahun" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-k-tgl">Tanggal setor</label>
                <Input id="pmf-k-tgl" type="date" value={kontrib.fields.tanggal}
                  onChange={(e) => setKontrib((k) => ({ ...k, fields: { ...k.fields, tanggal: e.target.value } }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-k-ntpn">NTPN</label>
                <Input id="pmf-k-ntpn" className="font-mono" value={kontrib.fields.ntpn}
                  onChange={(e) => setKontrib((k) => ({ ...k, fields: { ...k.fields, ntpn: e.target.value } }))}
                  data-testid="pemanfaatan-k-ntpn" />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pmf-k-jumlah">Jumlah (Rp)</label>
                <Input id="pmf-k-jumlah" type="number" min="0" value={kontrib.fields.jumlah}
                  onChange={(e) => setKontrib((k) => ({ ...k, fields: { ...k.fields, jumlah: e.target.value } }))} />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setKontrib(null)}>Batal</Button>
            <Button onClick={simpanKontribusi} disabled={kontrib?.saving}
              className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="pemanfaatan-k-simpan">
              {kontrib?.saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Coins className="w-4 h-4 mr-1.5" />}Catat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}
