import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Loader2, ShieldCheck, Scale, BadgeCheck, Camera,
  Gavel, Paperclip, Plus, QrCode, MapPin, Search, Trash2, Umbrella,
  Upload, UserCheck, FileText, Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";
import { authMediaUrl } from "@/lib/mediaUrl";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";

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
 * sengketa dari data inventarisasi, register dokumen kepemilikan
 * ber-lampiran, checklist pengamanan fisik, dan polis asuransi; jadwal
 * pemeliharaan dikelola di modul Pemeliharaan.
 */
const WARNA_STATUS_KASUS = {
  identifikasi: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  mediasi: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  blokir: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
  litigasi: "bg-red-500/15 text-red-600 dark:text-red-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
};

const WARNA_STATUS_POLIS = {
  akan_datang: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  aktif: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  segera_berakhir: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  berakhir: "bg-red-500/15 text-red-600 dark:text-red-400",
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
  // Arsip dokumen: data GET + dialog dokumen baru + dialog lampiran
  const [dokumen, setDokumen] = useState(null);
  const [formDok, setFormDok] = useState(null);
  const [lampiranDok, setLampiranDok] = useState(null);
  const fileDokRef = useRef(null);
  // Checklist pengamanan: data GET + dialog isi checklist
  const [cek, setCek] = useState(null);
  const [formCek, setFormCek] = useState(null);
  // Register polis asuransi: data GET + dialog polis baru
  const [polis, setPolis] = useState(null);
  const [formPolis, setFormPolis] = useState(null);
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

  const muatDokumen = useCallback(() => {
    axios.get(`${API}/pengamanan/dokumen`)
      .then((r) => setDokumen(r.data))
      .catch(() => {});
  }, []);

  const muatCek = useCallback(() => {
    axios.get(`${API}/pengamanan/checklist`)
      .then((r) => setCek(r.data))
      .catch(() => {});
  }, []);

  const muatPolis = useCallback(() => {
    axios.get(`${API}/pengamanan/polis`)
      .then((r) => setPolis(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    axios.get(`${API}/pengamanan/ringkasan`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Gagal memuat ringkasan pengamanan"))
      .finally(() => setLoading(false));
    muatKasus();
    muatDokumen();
    muatCek();
    muatPolis();
  }, [muatKasus, muatDokumen, muatCek, muatPolis]);

  useEffect(() => {
    if ((!formKasus && !formDok && !formCek && !formPolis) || cari.trim().length < 2) { setHasilCari([]); return undefined; }
    clearTimeout(cariTimer.current);
    cariTimer.current = setTimeout(async () => {
      setMencari(true);
      try {
        const r = await axios.get(`${API}/assets`, { params: { search: cari.trim(), page_size: 8 } });
        setHasilCari(r.data?.items || []);
      } catch { setHasilCari([]); } finally { setMencari(false); }
    }, 300);
    return () => clearTimeout(cariTimer.current);
  }, [cari, formKasus, formDok, formCek, formPolis]);

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

  const simpanDokumen = async () => {
    if (!formDok?.aset) return;
    setFormDok((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengamanan/dokumen`, {
        ...formDok.data, asset_id: formDok.aset.id,
      });
      toast.success("Dokumen dicatat");
      setFormDok(null);
      muatDokumen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat dokumen");
      setFormDok((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusDokumen = async (d) => {
    const ok = await confirm({
      title: "Hapus dokumen dari arsip?",
      description: `${dokumen?.label_jenis?.[d.jenis] || d.jenis} ${d.nomor} — ${d.asset_name || d.asset_id}. Lampirannya ikut terhapus.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengamanan/dokumen/${d.id}`);
      toast.success("Dokumen dihapus");
      muatDokumen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus dokumen");
    }
  };

  const unggahLampiranDok = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !lampiranDok) return;
    setLampiranDok((l) => ({ ...l, uploading: true }));
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/pengamanan/dokumen/${lampiranDok.dok.id}/lampiran`, fd);
      toast.success("Lampiran terunggah");
      setLampiranDok((l) => (l ? { ...l, dok: { ...l.dok, lampiran: r.data?.lampiran || [] }, uploading: false } : l));
      muatDokumen();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal mengunggah lampiran");
      setLampiranDok((l) => (l ? { ...l, uploading: false } : l));
    }
  };

  const hapusLampiranDok = async (fileId) => {
    if (!lampiranDok) return;
    try {
      await axios.delete(`${API}/pengamanan/dokumen/${lampiranDok.dok.id}/lampiran/${fileId}`);
      toast.success("Lampiran dihapus");
      setLampiranDok((l) => (l ? { ...l, dok: { ...l.dok, lampiran: (l.dok.lampiran || []).filter((x) => x.file_id !== fileId) } } : l));
      muatDokumen();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lampiran");
    }
  };

  const simpanPolis = async () => {
    if (!formPolis?.aset) return;
    setFormPolis((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengamanan/polis`, {
        ...formPolis.data, asset_id: formPolis.aset.id,
        nilai_pertanggungan: Number(formPolis.data.nilai_pertanggungan || 0),
        premi: Number(formPolis.data.premi || 0),
      });
      toast.success("Polis dicatat");
      setFormPolis(null);
      muatPolis();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mencatat polis");
      setFormPolis((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusPolis = async (p) => {
    const ok = await confirm({
      title: "Hapus polis dari register?",
      description: `Polis ${p.nomor_polis} — ${p.asset_name || p.asset_id}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengamanan/polis/${p.id}`);
      toast.success("Polis dihapus");
      muatPolis();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus polis");
    }
  };

  // Tebakan jenis objek dari golongan kode aset (2=tanah, 4=gedung); bisa diganti
  const tebakJenisObjek = (a) => {
    const g = String(a?.asset_code || "").trim()[0];
    if (g === "2") return "tanah";
    if (g === "4") return "gedung_bangunan";
    return "lainnya";
  };

  const bukaFormCek = (aset, existing) => {
    setCari(""); setHasilCari([]);
    const jenis = existing?.jenis_objek || tebakJenisObjek(aset);
    setFormCek({
      data: { jenis_objek: jenis, butir: { ...(existing?.butir || {}) }, keterangan: existing?.keterangan || "" },
      aset, saving: false,
    });
  };

  const simpanCek = async () => {
    if (!formCek?.aset) return;
    setFormCek((f) => ({ ...f, saving: true }));
    try {
      await axios.post(`${API}/pengamanan/checklist`, {
        ...formCek.data, asset_id: formCek.aset.id,
      });
      toast.success("Checklist tersimpan");
      setFormCek(null);
      muatCek();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan checklist");
      setFormCek((f) => (f ? { ...f, saving: false } : f));
    }
  };

  const hapusCek = async (c) => {
    const ok = await confirm({
      title: "Hapus checklist?",
      description: `${c.asset_name || c.asset_id} — ${cek?.label_jenis?.[c.jenis_objek] || c.jenis_objek}.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pengamanan/checklist/${c.id}`);
      toast.success("Checklist dihapus");
      muatCek();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus checklist");
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
          <BookingNomorButton modul="pengamanan" jenisNaskah="Laporan" referensi="Laporan Pengamanan" />
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
                {(kasus?.items || []).length > 0 && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => downloadFileWithProgress(`${API}/pengamanan/kasus/export`, "register_kasus_bmn.csv", { label: "Ekspor Register BMN Bermasalah (CSV)" }).catch(() => {})}
                    data-testid="pengamanan-kasus-export">
                    <Download className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                  </Button>
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

            {/* ── Arsip dokumen kepemilikan (pustaka §11.3, PP 27/2014 Ps. 43) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pengamanan-dokumen">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Arsip Dokumen Kepemilikan</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Sertipikat / BPKB / STNK / IMB-PBG per aset + lokasi penyimpanan
                  </p>
                </div>
                {(dokumen?.ringkasan?.kedaluwarsa || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold flex-shrink-0">
                    {dokumen.ringkasan.kedaluwarsa} kedaluwarsa
                  </span>
                )}
                {(dokumen?.items || []).length > 0 && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => downloadFileWithProgress(`${API}/pengamanan/dokumen/export`, "arsip_dokumen_kepemilikan.csv", { label: "Ekspor Arsip Dokumen Kepemilikan (CSV)" }).catch(() => {})}
                    data-testid="pengamanan-dokumen-export">
                    <Download className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                  </Button>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => { setCari(""); setHasilCari([]); setFormDok({ data: { jenis: "sertipikat", nomor: "", atas_nama: "", lokasi_simpan: "pengelola_barang", berlaku_sampai: "", kategori_sertipikasi: "", keterangan: "" }, aset: null, saving: false }); }}
                  data-testid="pengamanan-dokumen-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat Dokumen</span>
                </Button>
              </div>
              {(dokumen?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada dokumen — catat sertipikat/BPKB/IMB per aset beserta lokasi penyimpanannya.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {dokumen.items.map((d) => {
                    const kedaluwarsa = d.berlaku_sampai && d.berlaku_sampai < new Date().toISOString().slice(0, 10);
                    return (
                      <li key={d.id} className="p-3" data-testid={`pengamanan-dokumen-${d.id}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold">
                            {dokumen.label_jenis?.[d.jenis] || d.jenis}
                          </span>
                          {kedaluwarsa && (
                            <span className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-600 dark:text-red-400 text-[10px] font-semibold">
                              Kedaluwarsa
                            </span>
                          )}
                          {d.kategori_sertipikasi && (
                            <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-400 text-[10px] font-semibold">
                              {dokumen.label_sertipikasi?.[d.kategori_sertipikasi] || d.kategori_sertipikasi}
                            </span>
                          )}
                          <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{d.asset_name || "-"}</p>
                          <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{d.asset_code} · {d.NUP}</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {[`No. ${d.nomor}`,
                            d.atas_nama && `a.n. ${d.atas_nama}`,
                            dokumen.label_lokasi?.[d.lokasi_simpan] || d.lokasi_simpan,
                            d.berlaku_sampai && `berlaku s.d. ${d.berlaku_sampai}`,
                            d.keterangan].filter(Boolean).join(" · ")}
                        </p>
                        <div className="flex gap-1.5 mt-1.5 items-center">
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => setLampiranDok({ dok: d, uploading: false })}
                            data-testid={`pengamanan-dokumen-${d.id}-lampiran`}>
                            <Paperclip className="w-3.5 h-3.5 mr-1" />{(d.lampiran || []).length} lampiran
                          </Button>
                          {isAdmin && (
                            <button type="button" onClick={() => hapusDokumen(d)} aria-label="Hapus dokumen"
                              className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* ── Checklist pengamanan per aset (pustaka §11.2) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pengamanan-checklist">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <BadgeCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Checklist Pengamanan per Aset</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    Butir fisik/administrasi/hukum per jenis objek — alat bantu internal
                  </p>
                </div>
                {(cek?.ringkasan?.jumlah || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 text-[10px] font-semibold flex-shrink-0">
                    {cek.ringkasan.penuh}/{cek.ringkasan.jumlah} penuh
                  </span>
                )}
                {(cek?.items || []).length > 0 && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => downloadFileWithProgress(`${API}/pengamanan/checklist/export`, "checklist_pengamanan.csv", { label: "Ekspor Checklist Pengamanan (CSV)" }).catch(() => {})}
                    data-testid="pengamanan-checklist-export">
                    <Download className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                  </Button>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => bukaFormCek(null, null)}
                  data-testid="pengamanan-checklist-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Isi Checklist</span>
                </Button>
              </div>
              {(cek?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada checklist — isi per aset (patok/plang, APAR, BPKB, dsb. sesuai jenisnya).
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {cek.items.map((c) => {
                    const s = c.skor || {};
                    const warna = s.persen === 100
                      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : (s.persen || 0) >= 50
                        ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                        : "bg-red-500/15 text-red-600 dark:text-red-400";
                    return (
                      <li key={c.id} className="p-3" data-testid={`pengamanan-checklist-${c.id}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${warna}`}>
                            {s.terpenuhi}/{s.total} butir
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                            {cek.label_jenis?.[c.jenis_objek] || c.jenis_objek}
                          </span>
                          <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{c.asset_name || "-"}</p>
                          <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{c.asset_code} · {c.NUP}</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {[`Dicek ${c.tanggal_cek} oleh ${c.petugas}`, c.keterangan].filter(Boolean).join(" · ")}
                        </p>
                        <div className="flex gap-1.5 mt-1.5 items-center">
                          <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0"
                            onClick={() => bukaFormCek({ id: c.asset_id, asset_code: c.asset_code, NUP: c.NUP, asset_name: c.asset_name }, c)}
                            data-testid={`pengamanan-checklist-${c.id}-edit`}>
                            Perbarui
                          </Button>
                          {isAdmin && (
                            <button type="button" onClick={() => hapusCek(c)} aria-label="Hapus checklist"
                              className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* ── Register polis Asuransi BMN (pustaka §11.5, PMK 43/2025) ── */}
            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="pengamanan-polis">
              <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
                <Umbrella className="w-4 h-4 text-sky-600 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-foreground">Polis Asuransi BMN</p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    PMK 43/2025 (mencabut PMK 97/2019) — pengingat masa berlaku
                  </p>
                </div>
                {(polis?.ringkasan?.per_status?.segera_berakhir || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-semibold flex-shrink-0">
                    {polis.ringkasan.per_status.segera_berakhir} segera berakhir
                  </span>
                )}
                {(polis?.items || []).length > 0 && (
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => downloadFileWithProgress(`${API}/pengamanan/polis/export`, "register_polis_asuransi.csv", { label: "Ekspor Register Polis Asuransi (CSV)" }).catch(() => {})}
                    data-testid="pengamanan-polis-export">
                    <Download className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">CSV</span>
                  </Button>
                )}
                <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                  onClick={() => { setCari(""); setHasilCari([]); setFormPolis({ data: { nomor_polis: "", penanggung: "Konsorsium Asuransi BMN", kategori_objek: "program_preferen", nilai_pertanggungan: "", premi: "", sumber_dana: "dipa", mulai: "", berakhir: "", keterangan: "" }, aset: null, saving: false }); }}
                  data-testid="pengamanan-polis-tambah">
                  <Plus className="w-3.5 h-3.5 sm:mr-1" /><span className="hidden sm:inline">Catat Polis</span>
                </Button>
              </div>
              {(polis?.items || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-4 px-3">
                  Belum ada polis — catat polis gedung/bangunan yang diasuransikan beserta masa berlakunya.
                </p>
              ) : (
                <ul className="divide-y divide-border/60">
                  {polis.items.map((p) => (
                    <li key={p.id} className="p-3" data-testid={`pengamanan-polis-${p.id}`}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${WARNA_STATUS_POLIS[p.info?.status] || "bg-muted"}`}>
                          {polis.label_status?.[p.info?.status] || p.info?.status}
                          {p.info?.status === "segera_berakhir" && ` · ${p.info.sisa_hari} hari`}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/70">
                          {polis.label_kategori?.[p.kategori_objek] || p.kategori_objek}
                        </span>
                        <p className="text-sm font-semibold text-foreground flex-1 min-w-[140px] truncate">{p.asset_name || "-"}</p>
                        <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0">{p.asset_code} · {p.NUP}</span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {[`Polis ${p.nomor_polis}`, p.penanggung,
                          `Pertanggungan Rp${Math.round(Number(p.nilai_pertanggungan || 0)).toLocaleString("id-ID")}`,
                          `Premi Rp${Math.round(Number(p.premi || 0)).toLocaleString("id-ID")} (${polis.label_sumber_dana?.[p.sumber_dana] || p.sumber_dana})`,
                          `${p.mulai} s.d. ${p.berakhir}`,
                          p.keterangan].filter(Boolean).join(" · ")}
                      </p>
                      {isAdmin && (
                        <div className="flex gap-1.5 mt-1.5">
                          <button type="button" onClick={() => hapusPolis(p)} aria-label="Hapus polis"
                            className="h-7 w-7 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-center text-[11px] text-muted-foreground pb-4">
              {polis?.catatan || cek?.catatan || dokumen?.catatan || kasus?.catatan || ""}
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

      {/* ── Dialog catat dokumen kepemilikan ── */}
      <Dialog open={!!formDok} onOpenChange={(o) => { if (!o) setFormDok(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Dokumen Kepemilikan</DialogTitle>
            <DialogDescription className="text-xs">
              Arsip salinan (pustaka §11.3) — penyimpanan sah tetap per PP 27/2014 Ps. 43 + PMK 218/2015.
            </DialogDescription>
          </DialogHeader>
          {formDok && (
            <div className="space-y-3">
              {!formDok.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-cari">Cari aset</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="dok-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="dokumen-cari" />
                  </div>
                  {mencari && <p className="text-[11px] text-muted-foreground mt-1">Mencari…</p>}
                  <ul className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormDok((f) => ({ ...f, aset: a }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`dokumen-pilih-${a.id}`}>
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
                    {formDok.aset.asset_name || "-"}{" "}
                    <span className="font-mono text-[10px] text-muted-foreground">({formDok.aset.asset_code} · {formDok.aset.NUP})</span>
                  </span>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormDok((f) => ({ ...f, aset: null }))}>
                    Ganti
                  </Button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-jenis">Jenis dokumen</label>
                  <select id="dok-jenis" value={formDok.data.jenis}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, jenis: e.target.value, lokasi_simpan: ["sertipikat", "imb_pbg"].includes(e.target.value) ? "pengelola_barang" : "pengguna_barang", kategori_sertipikasi: e.target.value === "sertipikat" ? f.data.kategori_sertipikasi : "" } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="dokumen-jenis">
                    {Object.entries(dokumen?.label_jenis || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-nomor">Nomor dokumen</label>
                  <Input id="dok-nomor" value={formDok.data.nomor}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, nomor: e.target.value } }))}
                    data-testid="dokumen-nomor" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-an">Atas nama (ops.)</label>
                  <Input id="dok-an" placeholder="Pemerintah RI c.q. …" value={formDok.data.atas_nama}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, atas_nama: e.target.value } }))}
                    data-testid="dokumen-an" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-lokasi">Lokasi penyimpanan</label>
                  <select id="dok-lokasi" value={formDok.data.lokasi_simpan}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, lokasi_simpan: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="dokumen-lokasi">
                    {Object.entries(dokumen?.label_lokasi || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-berlaku">Berlaku s.d. (ops.)</label>
                  <Input id="dok-berlaku" type="date" value={formDok.data.berlaku_sampai}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, berlaku_sampai: e.target.value } }))}
                    data-testid="dokumen-berlaku" />
                </div>
                {formDok.data.jenis === "sertipikat" && (
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-sertipikasi">Status sertipikasi (ops., kategori DJKN-BPN)</label>
                    <select id="dok-sertipikasi" value={formDok.data.kategori_sertipikasi}
                      onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, kategori_sertipikasi: e.target.value } }))}
                      className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                      data-testid="dokumen-sertipikasi">
                      <option value="">— tidak diisi —</option>
                      {Object.entries(dokumen?.label_sertipikasi || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="dok-ket">Keterangan (ops.)</label>
                  <Input id="dok-ket" value={formDok.data.keterangan}
                    onChange={(e) => setFormDok((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                    data-testid="dokumen-ket" />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormDok(null)}>Batal</Button>
                <Button size="sm" className="bg-amber-600 hover:bg-amber-700 text-white"
                  disabled={formDok.saving || !formDok.aset || !formDok.data.nomor.trim()}
                  onClick={simpanDokumen} data-testid="dokumen-simpan">
                  {formDok.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog catat polis asuransi ── */}
      <Dialog open={!!formPolis} onOpenChange={(o) => { if (!o) setFormPolis(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Catat Polis Asuransi BMN</DialogTitle>
            <DialogDescription className="text-xs">
              Register pendamping (PMK 43/2025) — perencanaan resmi tetap via SIMAN.
            </DialogDescription>
          </DialogHeader>
          {formPolis && (
            <div className="space-y-3">
              {!formPolis.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-cari">Cari aset (gedung/bangunan)</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="pol-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="polis-cari" />
                  </div>
                  {mencari && <p className="text-[11px] text-muted-foreground mt-1">Mencari…</p>}
                  <ul className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormPolis((f) => ({ ...f, aset: a }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`polis-pilih-${a.id}`}>
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
                    {formPolis.aset.asset_name || "-"}{" "}
                    <span className="font-mono text-[10px] text-muted-foreground">({formPolis.aset.asset_code} · {formPolis.aset.NUP})</span>
                  </span>
                  <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                    onClick={() => setFormPolis((f) => ({ ...f, aset: null }))}>
                    Ganti
                  </Button>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-nomor">Nomor polis</label>
                  <Input id="pol-nomor" value={formPolis.data.nomor_polis}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, nomor_polis: e.target.value } }))}
                    data-testid="polis-nomor" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-penanggung">Penanggung</label>
                  <Input id="pol-penanggung" value={formPolis.data.penanggung}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, penanggung: e.target.value } }))}
                    data-testid="polis-penanggung" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-kategori">Kategori objek (PMK 43/2025)</label>
                  <select id="pol-kategori" value={formPolis.data.kategori_objek}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, kategori_objek: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="polis-kategori">
                    {Object.entries(polis?.label_kategori || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-nilai">Nilai pertanggungan (Rp)</label>
                  <Input id="pol-nilai" type="number" min="0" value={formPolis.data.nilai_pertanggungan}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, nilai_pertanggungan: e.target.value } }))}
                    data-testid="polis-nilai" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-premi">Premi (Rp)</label>
                  <Input id="pol-premi" type="number" min="0" value={formPolis.data.premi}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, premi: e.target.value } }))}
                    data-testid="polis-premi" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-sumber">Sumber dana premi</label>
                  <select id="pol-sumber" value={formPolis.data.sumber_dana}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, sumber_dana: e.target.value } }))}
                    className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                    data-testid="polis-sumber">
                    {Object.entries(polis?.label_sumber_dana || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-mulai">Mulai</label>
                  <Input id="pol-mulai" type="date" value={formPolis.data.mulai}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, mulai: e.target.value } }))}
                    data-testid="polis-mulai" />
                </div>
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-berakhir">Berakhir</label>
                  <Input id="pol-berakhir" type="date" value={formPolis.data.berakhir}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, berakhir: e.target.value } }))}
                    data-testid="polis-berakhir" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="pol-ket">Keterangan (ops.)</label>
                  <Input id="pol-ket" value={formPolis.data.keterangan}
                    onChange={(e) => setFormPolis((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                    data-testid="polis-ket" />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setFormPolis(null)}>Batal</Button>
                <Button size="sm" className="bg-sky-600 hover:bg-sky-700 text-white"
                  disabled={formPolis.saving || !formPolis.aset || !formPolis.data.nomor_polis.trim() || !formPolis.data.mulai || !formPolis.data.berakhir}
                  onClick={simpanPolis} data-testid="polis-simpan">
                  {formPolis.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog isi checklist pengamanan ── */}
      <Dialog open={!!formCek} onOpenChange={(o) => { if (!o) setFormCek(null); }}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Checklist Pengamanan Aset</DialogTitle>
            <DialogDescription className="text-xs">
              Butir per jenis objek (pustaka §11.2) — alat bantu internal, bukan bukti hukum.
            </DialogDescription>
          </DialogHeader>
          {formCek && (
            <div className="space-y-3">
              {!formCek.aset ? (
                <div>
                  <label className="text-xs font-medium text-foreground block mb-1" htmlFor="cek-cari">Cari aset</label>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-muted-foreground" />
                    <Input id="cek-cari" className="pl-8" placeholder="nama / kode / NUP…"
                      value={cari} onChange={(e) => setCari(e.target.value)} data-testid="checklist-cari" />
                  </div>
                  {mencari && <p className="text-[11px] text-muted-foreground mt-1">Mencari…</p>}
                  <ul className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                    {hasilCari.map((a) => (
                      <li key={a.id}>
                        <button type="button"
                          onClick={() => setFormCek((f) => ({ ...f, aset: a, data: { ...f.data, jenis_objek: tebakJenisObjek(a), butir: {} } }))}
                          className="w-full text-left rounded-lg border border-border p-2 text-xs hover:bg-muted min-h-0"
                          data-testid={`checklist-pilih-${a.id}`}>
                          <span className="text-foreground/90">{a.asset_name || "-"}</span>{" "}
                          <span className="font-mono text-[10px] text-muted-foreground">({a.asset_code} · {a.NUP})</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <>
                  <div className="rounded-lg border border-border p-2 text-xs flex items-center justify-between gap-2">
                    <span className="text-foreground/90 min-w-0 truncate">
                      {formCek.aset.asset_name || "-"}{" "}
                      <span className="font-mono text-[10px] text-muted-foreground">({formCek.aset.asset_code} · {formCek.aset.NUP})</span>
                    </span>
                    <Button size="sm" variant="outline" className="h-7 text-[11px] min-h-0 flex-shrink-0"
                      onClick={() => setFormCek((f) => ({ ...f, aset: null }))}>
                      Ganti
                    </Button>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="cek-jenis">Jenis objek</label>
                    <select id="cek-jenis" value={formCek.data.jenis_objek}
                      onChange={(e) => setFormCek((f) => ({ ...f, data: { ...f.data, jenis_objek: e.target.value, butir: {} } }))}
                      className="w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground"
                      data-testid="checklist-jenis">
                      {Object.entries(cek?.label_jenis || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    {(cek?.butir_ref?.[formCek.data.jenis_objek] || []).map((b) => (
                      <label key={b.kunci} className="flex items-center gap-2 rounded-lg border border-border p-2 text-xs cursor-pointer hover:bg-muted">
                        <input type="checkbox" className="accent-emerald-600"
                          checked={!!formCek.data.butir[b.kunci]}
                          onChange={(e) => setFormCek((f) => ({ ...f, data: { ...f.data, butir: { ...f.data.butir, [b.kunci]: e.target.checked } } }))}
                          data-testid={`checklist-butir-${b.kunci}`} />
                        <span className="min-w-0 flex-1 text-foreground/90">{b.label}</span>
                        <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-semibold text-foreground/60 flex-shrink-0">{b.aspek}</span>
                      </label>
                    ))}
                  </div>
                  <div>
                    <label className="text-xs font-medium text-foreground block mb-1" htmlFor="cek-ket">Keterangan (ops.)</label>
                    <Input id="cek-ket" value={formCek.data.keterangan}
                      onChange={(e) => setFormCek((f) => ({ ...f, data: { ...f.data, keterangan: e.target.value } }))}
                      data-testid="checklist-keterangan" />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setFormCek(null)}>Batal</Button>
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      disabled={formCek.saving}
                      onClick={simpanCek} data-testid="checklist-simpan">
                      {formCek.saving ? <Loader2 className="w-4 h-4 animate-spin" /> : "Simpan"}
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog lampiran dokumen ── */}
      <Dialog open={!!lampiranDok} onOpenChange={(o) => { if (!o) setLampiranDok(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Lampiran Scan Dokumen</DialogTitle>
            <DialogDescription className="text-xs">
              {lampiranDok && `${dokumen?.label_jenis?.[lampiranDok.dok.jenis] || lampiranDok.dok.jenis} No. ${lampiranDok.dok.nomor} — PDF/gambar, maks 10MB, 10 berkas.`}
            </DialogDescription>
          </DialogHeader>
          {lampiranDok && (
            <div className="space-y-2">
              <input ref={fileDokRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" className="hidden" onChange={unggahLampiranDok} />
              <Button size="sm" variant="outline" className="w-full"
                disabled={lampiranDok.uploading || (lampiranDok.dok.lampiran || []).length >= 10}
                onClick={() => fileDokRef.current?.click()} data-testid="dokumen-lampiran-unggah">
                {lampiranDok.uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : (<><Upload className="w-4 h-4 mr-1.5" />Unggah scan</>)}
              </Button>
              {(lampiranDok.dok.lampiran || []).length === 0 ? (
                <p className="text-[11px] text-muted-foreground text-center py-3">Belum ada lampiran.</p>
              ) : (
                <ul className="space-y-1.5 max-h-64 overflow-y-auto">
                  {(lampiranDok.dok.lampiran || []).map((l) => (
                    <li key={l.file_id} className="rounded-lg border border-border p-2 text-xs flex items-center gap-2">
                      <button type="button"
                        onClick={() => window.open(authMediaUrl(`${API}/pengamanan/dokumen/${lampiranDok.dok.id}/lampiran/${l.file_id}`), "_blank", "noopener")}
                        className="min-w-0 flex-1 text-left text-foreground/90 truncate hover:underline min-h-0">
                        {l.filename}
                      </button>
                      <span className="text-[10px] text-muted-foreground flex-shrink-0">{(l.tanggal || "").slice(0, 10)}</span>
                      {isAdmin && (
                        <button type="button" onClick={() => hapusLampiranDok(l.file_id)} aria-label={`Hapus ${l.filename}`}
                          className="h-6 w-6 min-h-0 min-w-0 rounded flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10 flex-shrink-0">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
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
