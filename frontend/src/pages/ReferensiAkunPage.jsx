import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, Landmark, Plus, Trash2, DownloadCloud, Boxes,
  Download, ChevronRight, ChevronDown, AlertTriangle, Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

// Belanja modal (53x) → golongan aset neraca (dari digit ke-3 kode BAS).
// Dipakai menandai tiap akun belanja perolehan aset dengan golongannya.
const GOL_BELANJA = {
  "531": { gol: "2", label: "Tanah" },
  "532": { gol: "3", label: "Peralatan & Mesin" },
  "533": { gol: "4", label: "Gedung & Bangunan" },
  "534": { gol: "5", label: "Jalan, Irigasi & Jaringan" },
  "536": { gol: "6", label: "Aset Tetap Lainnya" },
};

/**
 * Referensi Akun BAS — SATU pintu Kodefikasi Segmen Akun (tidak dipecah):
 * master seluruh akun 6 digit (8 segmen, sumber referensi resmi SAKTI/SPAN)
 * + dua ATURAN PAKAI turunan sebagai tab: akun aset per golongan BMN dan
 * akun persediaan per sub-kelompok — keduanya tervalidasi lunak ke master
 * (kode di luar master hanya ditandai ⚠, tidak ditolak).
 */
export default function ReferensiAkunPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [tab, setTab] = useState("master"); // master | aset | persediaan
  const { confirm, confirmDialog } = useConfirm();

  // ── Master segmen akun ──
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [segmen, setSegmen] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [baru, setBaru] = useState({ kode: "", nama: "" });
  const [buka, setBuka] = useState({}); // {kode: true} — baris penjelasan terbuka

  // ── Pemetaan ──
  const [aset, setAset] = useState(null);        // {items}
  const [psd, setPsd] = useState(null);          // {katalog, overrides, default_akun}
  const [namaAkun, setNamaAkun] = useState({});  // {kode: nama|null} validasi lunak
  const [formAset, setFormAset] = useState({ golongan: "3", akun: "", uraian: "" });
  const [formPsd, setFormPsd] = useState({ sub_kelompok: "", akun: "" });
  // Ambang kapitalisasi intra/ekstra (PMK 181 → dapat dioverride admin)
  const [ambang, setAmbang] = useState(null);   // {efektif, default, override}
  const [formAmbang, setFormAmbang] = useState(null); // {"3": "...", "4": "..."} saat edit

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const muatMaster = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "50" });
      if (q.trim()) params.append("search", q.trim());
      if (segmen) params.append("segmen", segmen);
      const r = await axios.get(`${API}/referensi-akun?${params}`);
      setData(r.data);
      setPage(p);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat referensi akun"));
    } finally {
      setLoading(false);
    }
  }, [q, segmen]);

  // Debounce 350ms — pencarian tidak menembak request per ketukan (pola Kodefikasi).
  useEffect(() => {
    const t = setTimeout(() => muatMaster(1), 350);
    return () => clearTimeout(t);
  }, [muatMaster]);

  const muatPemetaan = useCallback(async () => {
    try {
      const [ra, rp, rk] = await Promise.all([
        axios.get(`${API}/akun-bas`), axios.get(`${API}/persediaan-akun`),
        axios.get(`${API}/pembukuan/ambang-kapitalisasi`).catch(() => null)]);
      setAset(ra.data); setPsd(rp.data);
      if (rk?.data) setAmbang(rk.data);
      const kode = new Set();
      (ra.data?.items || []).forEach((i) => i.akun && kode.add(i.akun));
      (rp.data?.katalog || []).forEach((i) => i.akun && kode.add(i.akun));
      (rp.data?.overrides || []).forEach((i) => i.akun && kode.add(i.akun));
      if (kode.size) {
        const r = await axios.get(`${API}/referensi-akun/periksa?kode=${[...kode].join(",")}`);
        setNamaAkun(r.data?.akun || {});
      }
    } catch (e) { toast.error(apiErr(e, "Gagal memuat pemetaan akun")); }
  }, []);

  useEffect(() => { muatPemetaan(); }, [muatPemetaan]);

  // Datalist akun neraca BMN dari master (13=aset tetap, 16=aset lainnya,
  // 117=persediaan) — saran saat admin memetakan golongan → akun.
  const [akunNeraca, setAkunNeraca] = useState([]);
  useEffect(() => {
    axios.get(`${API}/referensi-akun`, { params: { segmen: "13,16,117", page_size: 200 } })
      .then((r) => setAkunNeraca(r.data?.items || []))
      .catch(() => {});
  }, []);

  // Akun BELANJA dari master BAS agar SEMUA yang berkaitan aset & persediaan
  // dapat difilter: belanja modal (53xxxx = perolehan aset per golongan) &
  // belanja barang persediaan (5218xx).
  const [belanjaModal, setBelanjaModal] = useState([]);
  const [belanjaPsd, setBelanjaPsd] = useState([]);
  useEffect(() => {
    axios.get(`${API}/referensi-akun`, { params: { segmen: "53", page_size: 200 } })
      .then((r) => setBelanjaModal(r.data?.items || [])).catch(() => {});
    axios.get(`${API}/referensi-akun`, { params: { segmen: "5218", page_size: 200 } })
      .then((r) => setBelanjaPsd(r.data?.items || [])).catch(() => {});
  }, []);
  const [cariBelanja, setCariBelanja] = useState("");
  const [golBelanja, setGolBelanja] = useState("");        // prefix 3 digit
  const [cariBelanjaPsd, setCariBelanjaPsd] = useState("");
  const belanjaModalTampil = useMemo(() => {
    const cari = cariBelanja.trim().toLowerCase();
    return belanjaModal.filter((a) => {
      if (golBelanja && !String(a.kode).startsWith(golBelanja)) return false;
      return !cari || `${a.kode} ${a.nama}`.toLowerCase().includes(cari);
    });
  }, [belanjaModal, cariBelanja, golBelanja]);
  const belanjaPsdTampil = useMemo(() => {
    const cari = cariBelanjaPsd.trim().toLowerCase();
    return belanjaPsd.filter((a) => !cari || `${a.kode} ${a.nama}`.toLowerCase().includes(cari));
  }, [belanjaPsd, cariBelanjaPsd]);

  const seed = async () => {
    setSeeding(true);
    try {
      const r = await axios.post(`${API}/referensi-akun/seed`);
      toast.success(`Referensi resmi dimuat: ${r.data.dimuat} akun`);
      muatMaster(1);
    } catch (e) { toast.error(apiErr(e, "Gagal memuat referensi resmi")); }
    finally { setSeeding(false); }
  };

  const tambahAkun = async () => {
    if (!baru.kode.trim() || !baru.nama.trim()) { toast.error("Kode & nama akun wajib diisi"); return; }
    try {
      await axios.post(`${API}/referensi-akun`, baru);
      toast.success(`Akun ${baru.kode} tersimpan`);
      setBaru({ kode: "", nama: "" });
      muatMaster(page);
    } catch (e) { toast.error(apiErr(e, "Gagal menyimpan akun")); }
  };

  const hapusAkun = async (a) => {
    const ok = await confirm({
      title: `Hapus akun ${a.kode}?`, description: a.nama,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/referensi-akun/${a.kode}`);
      toast.success(`Akun ${a.kode} dihapus`);
      muatMaster(page);
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus")); }
  };

  const simpanAset = async () => {
    if (!formAset.akun.trim()) { toast.error("Kode akun wajib diisi"); return; }
    try {
      await axios.post(`${API}/akun-bas`, formAset);
      toast.success(`Golongan ${formAset.golongan} → akun ${formAset.akun}`);
      setFormAset({ golongan: "3", akun: "", uraian: "" });
      muatPemetaan();
    } catch (e) { toast.error(apiErr(e, "Gagal menyimpan pemetaan")); }
  };

  const hapusAset = async (g) => {
    const ok = await confirm({
      title: `Hapus override golongan ${g}?`,
      description: "Pemetaan akun golongan ini kembali ke nilai default riset.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/akun-bas/${g}`);
      toast.success(`Override golongan ${g} dihapus (kembali ke default)`);
      muatPemetaan();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus")); }
  };

  const simpanPsd = async () => {
    if (!formPsd.sub_kelompok.trim() || !formPsd.akun.trim()) {
      toast.error("Sub-kelompok & akun wajib diisi"); return;
    }
    try {
      await axios.post(`${API}/persediaan-akun`, formPsd);
      toast.success(`Sub-kelompok ${formPsd.sub_kelompok} → ${formPsd.akun}`);
      setFormPsd({ sub_kelompok: "", akun: "" });
      muatPemetaan();
    } catch (e) { toast.error(apiErr(e, "Gagal menyimpan pemetaan")); }
  };

  const hapusPsd = async (s) => {
    const ok = await confirm({
      title: `Hapus override ${s}?`,
      description: "Pemetaan akun sub-kelompok ini kembali ke default (117111 Barang Konsumsi).",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/persediaan-akun/${s}`);
      toast.success(`Override ${s} dihapus`);
      muatPemetaan();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus")); }
  };

  const simpanAmbang = async () => {
    const body = {};
    for (const g of ["3", "4"]) {
      const v = String(formAmbang?.[g] ?? "").replace(/[^\d]/g, "");
      if (!v || Number(v) <= 0) { toast.error(`Ambang golongan ${g} harus angka > 0`); return; }
      body[g] = Number(v);
    }
    try {
      const r = await axios.put(`${API}/pembukuan/ambang-kapitalisasi`, { ambang: body });
      toast.success("Ambang kapitalisasi tersimpan — laporan DBKP/LBKP/Posisi memakai nilai baru");
      setAmbang((a) => ({ ...(a || {}), efektif: r.data?.efektif || body, override: body }));
      setFormAmbang(null);
    } catch (e) { toast.error(apiErr(e, "Gagal menyimpan ambang")); }
  };

  const resetAmbang = async () => {
    const ok = await confirm({
      title: "Kembalikan ambang ke default PMK 181?",
      description: "Peralatan & Mesin Rp1.000.000 · Gedung & Bangunan Rp25.000.000.",
      confirmLabel: "Kembalikan",
    });
    if (!ok) return;
    try {
      const r = await axios.put(`${API}/pembukuan/ambang-kapitalisasi`, { ambang: {} });
      toast.success("Ambang kembali ke default PMK 181");
      setAmbang((a) => ({ ...(a || {}), efektif: r.data?.efektif, override: {} }));
      setFormAmbang(null);
    } catch (e) { toast.error(apiErr(e, "Gagal mengembalikan default")); }
  };

  const fmtRp = (v) => `Rp${Number(v || 0).toLocaleString("id-ID")}`;

  const TandaAkun = ({ kode }) => {
    if (!kode) return null;
    const nama = namaAkun[kode];
    if (nama === undefined) return null;
    return nama
      ? <span className="text-[10px] text-muted-foreground block truncate" title={nama}>{nama}</span>
      : <span className="text-[10px] text-amber-600 dark:text-amber-400 block" title="Kode tidak ada di master Segmen Akun BAS (peringatan — non-blocking)"><AlertTriangle className="w-3 h-3 inline mr-0.5 align-[-1px]" />tak ada di master BAS</span>;
  };

  const labelSeg = data?.label_segmen || {};
  const labelKel = data?.label_kelompok || {};

  const eksporCsv = () => {
    const params = {};
    if (q.trim()) params.search = q.trim();
    if (segmen) params.segmen = segmen;
    downloadFileWithProgress(`${API}/referensi-akun/export`, "referensi_akun_bas.csv",
      { label: "Ekspor Referensi Akun BAS (CSV)", params }).catch(() => {});
  };

  // [kunci, label lengkap, label pendek mobile]
  const TABS = [
    ["master", "Segmen Akun BAS", "Master"],
    ["aset", "Akun Aset (Golongan)", "Aset"],
    ["persediaan", "Akun Persediaan", "Persediaan"],
  ];

  return (
    <div className="min-h-screen bg-background" data-testid="referensi-akun-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali" title="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="referensi-akun-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-amber-600 flex items-center justify-center flex-shrink-0">
            <Landmark className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Akun BAS</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Kodefikasi Segmen Akun (satu master{data ? ` · ${Object.values(data.per_segmen || {}).reduce((a, b) => a + b, 0)} akun` : ""}) + aturan pakai aset & persediaan
            </p>
          </div>
          {isAdmin && tab === "master" && (
            <Button variant="outline" size="sm" className="gap-1.5" disabled={seeding} onClick={seed}
              title="Muat Referensi Resmi (isi master akun BAS)" aria-label="Muat Referensi Resmi (isi master akun BAS)"
              data-testid="referensi-akun-seed">
              {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <DownloadCloud className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">Muat Referensi Resmi</span>
            </Button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="flex bg-muted rounded-lg p-0.5 gap-0.5">
          {TABS.map(([k, label, pendek]) => (
            <button key={k} type="button" onClick={() => setTab(k)} title={label}
              className={`flex-1 truncate px-1 text-[11px] sm:text-xs font-semibold py-1.5 rounded-md transition-colors min-w-0 min-h-0 ${tab === k ? "bg-card text-amber-700 dark:text-amber-400 shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              data-testid={`referensi-akun-tab-${k}`}>
              <span className="sm:hidden">{pendek}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>

        {tab === "master" && (
          <>
            <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 space-y-2">
              {/* Satu baris di HP (pola Referensi Kode Barang): cari menyusut,
                  segmen dibatasi lebarnya, ekspor cukup ikon. */}
              <div className="flex items-center gap-2">
                <div className="relative flex-1 min-w-0">
                  <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                  <Input value={q} onChange={(e) => setQ(e.target.value)}
                    placeholder="Cari kode / nama akun…" className="pl-9 h-10" data-testid="referensi-akun-cari" />
                </div>
                <select value={segmen} onChange={(e) => setSegmen(e.target.value)}
                  aria-label="Filter segmen akun" title="Filter segmen akun"
                  className="h-10 rounded-md border border-input bg-background px-2 text-xs sm:text-sm max-w-[110px] sm:max-w-none min-w-0 flex-shrink-0" data-testid="referensi-akun-segmen">
                  <option value="">Segmen</option>
                  {Object.entries(labelSeg).map(([k, v]) => (
                    <option key={k} value={k}>{k} — {v}{data?.per_segmen?.[k] ? ` (${data.per_segmen[k]})` : ""}</option>
                  ))}
                </select>
                <Button variant="outline" size="sm" className="h-10 gap-1.5 flex-shrink-0" onClick={eksporCsv}
                  title="Ekspor CSV referensi akun" aria-label="Ekspor CSV referensi akun"
                  data-testid="referensi-akun-ekspor">
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Ekspor CSV</span>
                </Button>
              </div>
              {isAdmin && (
                <div className="flex items-center gap-2 gap-y-1.5 flex-wrap">
                  <Input value={baru.kode} onChange={(e) => setBaru((b) => ({ ...b, kode: e.target.value }))}
                    placeholder="Kode (6 digit)" className="font-mono h-9 w-32" maxLength={6} data-testid="akun-baru-kode" />
                  <Input value={baru.nama} onChange={(e) => setBaru((b) => ({ ...b, nama: e.target.value }))}
                    placeholder="Nama akun (entri manual satker)" className="h-9 flex-1 min-w-[140px]" data-testid="akun-baru-nama" />
                  <Button variant="outline" size="sm" className="h-9 gap-1" onClick={tambahAkun} data-testid="akun-tambah">
                    <Plus className="w-3.5 h-3.5" />Tambah
                  </Button>
                </div>
              )}
            </div>

            <p className="text-[11px] text-muted-foreground flex items-center gap-1">
              <ChevronRight className="w-3 h-3 flex-shrink-0" />Klik baris akun untuk membuka penjelasan resminya
            </p>

            <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
              {loading && !data ? (
                <div className="flex items-center justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-amber-600" /></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm min-w-[560px]">
                    <thead>
                      <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                        <th className="px-3 py-2.5 font-semibold w-24">Kode</th>
                        <th className="px-3 py-2.5 font-semibold">Nama Akun</th>
                        <th className="px-3 py-2.5 font-semibold">Info BMN</th>
                        {isAdmin && <th className="px-3 py-2.5 w-10"></th>}
                      </tr>
                    </thead>
                    <tbody>
                      {/* MAKNA KODE TAMPIL LANGSUNG MEMBAGI BARIS (permintaan
                          pemilik): header bertingkat muncul setiap prefiks
                          level 1–5 berganti — meniru tata letak lampiran resmi
                          KEP-211/PB/2018 (level 1–3 tebal, indentasi per
                          level). Data sudah terurut kode sehingga grup selalu
                          berdampingan. */}
                      {(data?.items || []).flatMap((a, idx, arr) => {
                        const kode = String(a.kode || "");
                        const sebelum = idx > 0 ? String(arr[idx - 1].kode || "") : "";
                        const hier = data?.hierarki || {};
                        const rows = [];
                        let namaInduk = "";
                        for (let lv = 1; lv <= 5; lv += 1) {
                          const pref = kode.slice(0, lv);
                          if (!pref || pref === sebelum.slice(0, lv)) {
                            namaInduk = hier[pref] || namaInduk;
                            continue;
                          }
                          // Nama level: hierarki resmi; level 1-2 punya cadangan
                          // label segmen/kelompok. Level 4-5 tanpa nama, atau
                          // namanya mengulang induk → dilewati (hemat baris).
                          let nama = hier[pref] || "";
                          if (!nama && lv === 1) nama = labelSeg[pref] || "";
                          if (!nama && lv === 2) nama = labelKel[pref] || "";
                          const ulang = nama && namaInduk &&
                            nama.trim().toLowerCase() === namaInduk.trim().toLowerCase();
                          if (nama) namaInduk = nama;
                          if (!nama || (ulang && lv >= 4)) continue;
                          const gaya = [
                            "bg-amber-500/20 font-bold",
                            "bg-amber-500/10 font-semibold",
                            "bg-muted/70 font-semibold",
                            "bg-muted/40",
                            "bg-muted/20",
                          ][lv - 1];
                          rows.push(
                            <tr key={`lvl-${pref}`} className={`${gaya} border-b border-border/60`} data-testid={`akun-level-${pref}`}>
                              <td colSpan={isAdmin ? 4 : 3} className="py-1" style={{ paddingLeft: `${12 + (lv - 1) * 16}px` }}>
                                <span className="font-mono text-[11px] font-bold text-amber-700 dark:text-amber-400">
                                  {pref}<span className="opacity-40">{"x".repeat(6 - lv)}</span>
                                </span>
                                <span className={`text-[11px] text-foreground ${lv <= 2 ? "uppercase" : ""}`}> — {nama}</span>
                                <span className="ml-2 text-[9px] uppercase tracking-wide text-muted-foreground">
                                  {["akun/segmen", "kelompok", "jenis", "level 4", "level 5"][lv - 1]} · {lv} digit
                                </span>
                              </td>
                            </tr>
                          );
                        }
                        const adaPenjelasan = !!String(a.penjelasan || "").trim();
                        const terbuka = !!buka[a.kode];
                        const toggle = () => adaPenjelasan && setBuka((b) => ({ ...b, [a.kode]: !b[a.kode] }));
                        rows.push(
                          <tr key={a.kode} className={`border-b border-border/60 last:border-0 hover:bg-muted/50 ${adaPenjelasan ? "cursor-pointer" : ""}`} data-testid={`akun-row-${a.kode}`} onClick={toggle}>
                            <td className="py-1.5 pl-12 sm:pl-[92px] pr-3 font-mono text-[12px] font-semibold text-foreground whitespace-nowrap">
                              {adaPenjelasan
                                ? (terbuka ? <ChevronDown className="w-3 h-3 inline mr-1 text-muted-foreground align-[-1px]" /> : <ChevronRight className="w-3 h-3 inline mr-1 text-muted-foreground align-[-1px]" />)
                                : <span className="inline-block w-3 mr-1" />}
                              {a.kode}
                            </td>
                            <td className="px-3 py-1.5 text-[12px] text-foreground/90">
                              {a.nama}
                              {a.sumber === "satker" && <span className="ml-1.5 px-1 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[9px] font-semibold">satker</span>}
                            </td>
                            <td className="px-3 py-1.5 text-[10px] text-muted-foreground">
                              {[a.uraian_bmn, a.kapitalisasi, a.kategori_neraca].filter(Boolean).join(" · ") || "—"}
                            </td>
                            {isAdmin && (
                              <td className="px-2 py-1.5">
                                <button type="button" onClick={(e) => { e.stopPropagation(); hapusAkun(a); }} aria-label={`Hapus ${a.kode}`}
                                  title={`Hapus akun ${a.kode}`}
                                  className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0">
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </td>
                            )}
                          </tr>
                        );
                        if (terbuka && adaPenjelasan) {
                          rows.push(
                            <tr key={`${a.kode}-rincian`} className="border-b border-border/60 bg-muted/30" data-testid={`akun-penjelasan-${a.kode}`}>
                              <td colSpan={isAdmin ? 4 : 3} className="pl-12 sm:pl-[92px] pr-3 py-2">
                                <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-0.5">Penjelasan</p>
                                <p className="text-[11px] leading-relaxed text-foreground/80">
                                  {a.penjelasan}
                                  {a.penjelasan_warisan && (
                                    <span className="block mt-1 text-[10px] italic text-muted-foreground">
                                      (definisi kelompok/jenis induk — akun rincian mengikuti penjelasan di atasnya)
                                    </span>
                                  )}
                                </p>
                                <p className="text-[9px] text-muted-foreground/70 mt-1">Sumber: KEP-211/PB/2018, kolom Penjelasan</p>
                              </td>
                            </tr>
                          );
                        }
                        return rows;
                      })}
                      {(data?.items || []).length === 0 && (
                        <tr>
                          <td colSpan={isAdmin ? 4 : 3} className="text-center text-xs text-muted-foreground py-8">
                            {(!q && !segmen) ? (
                              <span className="inline-flex flex-col items-center gap-2">
                                <span>Master referensi akun masih kosong.</span>
                                {isAdmin ? (
                                  <Button size="sm" variant="outline" className="gap-1.5" disabled={seeding} onClick={seed}
                                    data-testid="referensi-akun-seed-kosong">
                                    {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <DownloadCloud className="w-3.5 h-3.5" />}
                                    Muat Referensi Resmi
                                  </Button>
                                ) : (
                                  <span>Minta admin memuat referensi resmi lewat tombol di atas.</span>
                                )}
                              </span>
                            ) : "Tidak ada akun yang cocok dengan pencarian/filter — coba ubah kata kunci atau segmen."}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
              {data && data.total_pages > 1 && (
                <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
                  <Button size="sm" variant="ghost" disabled={page <= 1 || loading} onClick={() => muatMaster(page - 1)}>Sebelumnya</Button>
                  <span className="text-[11px] text-muted-foreground">Hal {data.page}/{data.total_pages} · {data.total} akun</span>
                  <Button size="sm" variant="ghost" disabled={page >= data.total_pages || loading} onClick={() => muatMaster(page + 1)}>Berikutnya</Button>
                </div>
              )}
            </div>
            <p className="text-center text-[10px] text-muted-foreground pb-2">
              Makna kode tampil LANGSUNG membagi baris: header bertingkat per level digit (1 = akun/segmen, 2 = kelompok, 3 = jenis, 4–5 = rincian) dengan indentasi — meniru tata letak lampiran resmi KEP-211/PB/2018.
              Sumber: dokumen resmi &quot;Referensi Akun&quot; SAKTI/SPAN + lampiran KEP-211/PB/2018; entri manual bertanda &quot;satker&quot;.
            </p>
          </>
        )}

        {tab === "aset" && ambang && (
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="ambang-kapitalisasi-card">
            <div className="px-3 py-2.5 border-b border-border flex items-center justify-between gap-2 gap-y-1.5 flex-wrap">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-foreground">Ambang kapitalisasi intra/ekstrakomptabel (PMK 181/PMK.06/2016)</p>
                <p className="text-[10px] text-muted-foreground">
                  Barang bernilai satuan di bawah ambang dibukukan EKSTRAKOMPTABEL (tidak masuk neraca) — dipakai DBKP, LBKP, CaLBMN &amp; Posisi BMN.
                </p>
              </div>
              {isAdmin && !formAmbang && (
                <div className="flex items-center gap-1.5">
                  {Object.keys(ambang.override || {}).length > 0 && (
                    <Button variant="ghost" size="sm" className="h-8 text-[11px]" onClick={resetAmbang}>Kembalikan default</Button>
                  )}
                  <Button variant="outline" size="sm" className="h-8 text-[11px]"
                    onClick={() => setFormAmbang({
                      3: String(ambang.efektif?.["3"] ?? ""), 4: String(ambang.efektif?.["4"] ?? "") })}
                    data-testid="ambang-ubah">
                    Ubah Ambang
                  </Button>
                </div>
              )}
            </div>
            <div className="px-3 py-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2">
              {[["3", "Peralatan dan Mesin"], ["4", "Gedung dan Bangunan"]].map(([g, label]) => (
                <div key={g} className="rounded-lg border border-border p-2.5">
                  <p className="text-[11px] font-bold text-foreground">Golongan {g} — {label}</p>
                  {formAmbang ? (
                    <Input inputMode="numeric" value={formAmbang[g]}
                      onChange={(e) => setFormAmbang((f) => ({ ...f, [g]: e.target.value.replace(/[^\d]/g, "") }))}
                      className="h-9 mt-1 font-mono" data-testid={`ambang-input-${g}`} />
                  ) : (
                    <p className="text-sm font-mono font-semibold mt-0.5">
                      ≥ {fmtRp(ambang.efektif?.[g])}
                      {ambang.override?.[g] != null && Number(ambang.override[g]) !== Number(ambang.default?.[g]) && (
                        <span className="ml-1.5 px-1 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[9px] font-semibold align-middle">override satker</span>
                      )}
                    </p>
                  )}
                  <p className="text-[10px] text-muted-foreground mt-0.5">Default PMK 181: {fmtRp(ambang.default?.[g])}</p>
                </div>
              ))}
            </div>
            {formAmbang && (
              <div className="px-3 pb-2.5 flex items-center justify-end gap-1.5">
                <Button variant="ghost" size="sm" className="h-8 text-[11px]" onClick={() => setFormAmbang(null)}>Batal</Button>
                <Button size="sm" className="h-8 text-[11px]" onClick={simpanAmbang} data-testid="ambang-simpan">Simpan Ambang</Button>
              </div>
            )}
          </div>
        )}
        {tab === "aset" && (
          <div className="space-y-3">
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="px-3 py-2.5 border-b border-border">
              <p className="text-xs font-semibold text-foreground">Aturan pakai: golongan BMN → akun neraca (dipakai DBKP/Posisi BMN)</p>
              <p className="text-[10px] text-muted-foreground">Default riset dapat ditimpa admin; akun tervalidasi lunak ke master Segmen Akun BAS.</p>
            </div>
            {isAdmin && (
              <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
                <select value={formAset.golongan} onChange={(e) => setFormAset((f) => ({ ...f, golongan: e.target.value }))}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm" data-testid="aset-golongan">
                  {(aset?.items || []).map((i) => <option key={i.golongan} value={i.golongan}>Gol {i.golongan}</option>)}
                </select>
                <Input value={formAset.akun} onChange={(e) => setFormAset((f) => ({ ...f, akun: e.target.value }))}
                  list="aset-akun-list"
                  placeholder="Akun (6 digit, cth. 132111)" className="font-mono h-9 w-44" maxLength={6} data-testid="aset-akun" />
                <datalist id="aset-akun-list">
                  {akunNeraca.map((a) => <option key={a.kode} value={a.kode}>{a.nama}</option>)}
                </datalist>
                <Input value={formAset.uraian} onChange={(e) => setFormAset((f) => ({ ...f, uraian: e.target.value }))}
                  placeholder="Uraian (ops. — otomatis dari master)" className="h-9 flex-1" />
                <Button variant="outline" size="sm" className="h-9 gap-1" onClick={simpanAset} data-testid="aset-simpan">
                  <Plus className="w-3.5 h-3.5" />Simpan
                </Button>
              </div>
            )}
            <div className="divide-y divide-border/60">
              {(aset?.items || []).map((i) => (
                <div key={i.golongan} className="px-3 py-2 flex items-center gap-3" data-testid={`aset-row-${i.golongan}`}>
                  <span className="w-14 text-[11px] font-bold text-foreground flex-shrink-0">Gol {i.golongan}</span>
                  <div className="w-28 flex-shrink-0">
                    <span className="font-mono text-[12px] text-foreground">{i.akun || "—"}</span>
                    <TandaAkun kode={i.akun} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] text-foreground/80 truncate">{i.uraian}</p>
                    <p className="text-[10px] text-muted-foreground">{i.sumber}</p>
                    {/* Tautan MASTER ASET: isi nyata yang memakai akun ini */}
                    <p className={`text-[10px] mt-0.5 ${i.jumlah_aset ? "text-sky-700 dark:text-sky-400 font-semibold" : "text-muted-foreground/60"}`}>
                      {i.jumlah_aset
                        ? `${i.jumlah_aset} aset di master · ${fmtRp(i.nilai_aset)}`
                        : "belum ada aset golongan ini di master"}
                    </p>
                  </div>
                  {isAdmin && i.sumber === "input satker" && (
                    <button type="button" onClick={() => hapusAset(i.golongan)} aria-label={`Reset golongan ${i.golongan}`}
                      title="Hapus override (kembali ke default riset)"
                      className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0 flex-shrink-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* SEMUA akun belanja modal (53xxxx) dari master BAS — perolehan aset
              per golongan; dapat difilter (cari + chip golongan). */}
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="belanja-modal-card">
            <div className="px-3 py-2.5 border-b border-border">
              <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Landmark className="w-3.5 h-3.5" />Akun belanja modal terkait aset (dari master BAS)
              </p>
              <p className="text-[10px] text-muted-foreground">
                Perolehan aset per golongan: 531 Tanah · 532 Peralatan &amp; Mesin · 533 Gedung &amp; Bangunan · 534 Jalan/Irigasi/Jaringan · 536 Aset Tetap Lainnya.
              </p>
            </div>
            <div className="px-3 py-2 border-b border-border space-y-1.5">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input value={cariBelanja} onChange={(e) => setCariBelanja(e.target.value)}
                  placeholder="Cari kode / nama akun belanja…" className="pl-8 h-9 text-xs" data-testid="belanja-modal-cari" />
              </div>
              <div className="flex items-center gap-1 flex-wrap">
                {[["", "Semua"], ...Object.entries(GOL_BELANJA).map(([p, v]) => [p, `${p} ${v.label}`])].map(([p, label]) => (
                  <button key={p || "semua"} type="button" onClick={() => setGolBelanja(p)}
                    className={`h-7 px-2 rounded-full border text-[10px] font-medium min-w-0 min-h-0 transition-colors ${golBelanja === p ? "bg-blue-600 border-blue-600 text-white" : "border-border text-muted-foreground hover:bg-muted"}`}
                    data-testid={`belanja-gol-${p || "semua"}`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="divide-y divide-border/60 max-h-72 overflow-y-auto">
              {belanjaModalTampil.map((a) => {
                const g = GOL_BELANJA[String(a.kode).slice(0, 3)];
                return (
                  <div key={a.kode} className="px-3 py-1.5 flex items-center gap-2.5" data-testid={`belanja-modal-${a.kode}`}>
                    <span className="font-mono text-[12px] text-foreground w-16 flex-shrink-0">{a.kode}</span>
                    <p className="text-[11px] text-foreground/80 flex-1 min-w-0 truncate" title={a.nama}>{a.nama}</p>
                    {g && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 flex-shrink-0">Gol {g.gol}</span>}
                  </div>
                );
              })}
              {belanjaModalTampil.length === 0 && (
                <p className="text-[11px] text-muted-foreground text-center py-4">
                  {belanjaModal.length === 0 ? "Memuat akun dari master BAS… (jika kosong, muat referensi resmi di tab Master)" : "Tidak ada akun belanja yang cocok filter."}
                </p>
              )}
            </div>
          </div>
          </div>
        )}

        {tab === "persediaan" && (
          <div className="space-y-3">
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
            <div className="px-3 py-2.5 border-b border-border">
              <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Boxes className="w-3.5 h-3.5" />Aturan pakai: sub-kelompok persediaan → akun 1171xx (dipakai laporan persediaan/LBKP)
              </p>
              <p className="text-[10px] text-muted-foreground">
                Default {psd?.default_akun} — {psd?.default_uraian}; override per sub-kelompok bila perlu. Katalog & override tervalidasi lunak ke master.
              </p>
            </div>
            {isAdmin && (
              <div className="px-3 py-2 border-b border-border flex items-center gap-2 flex-wrap">
                <Input value={formPsd.sub_kelompok} onChange={(e) => setFormPsd((f) => ({ ...f, sub_kelompok: e.target.value }))}
                  placeholder="Sub-kelompok (5 digit, cth. 10101)" className="font-mono h-9 w-52" maxLength={5} data-testid="psd-sub" />
                <select value={formPsd.akun} onChange={(e) => setFormPsd((f) => ({ ...f, akun: e.target.value }))}
                  className="h-9 rounded-md border border-input bg-background px-2 text-sm flex-1 min-w-[200px]" data-testid="psd-akun">
                  <option value="">— pilih akun 1171xx —</option>
                  {(psd?.katalog || []).map((k) => <option key={k.akun} value={k.akun}>{k.akun} — {k.uraian}</option>)}
                </select>
                <Button variant="outline" size="sm" className="h-9 gap-1" onClick={simpanPsd} data-testid="psd-simpan">
                  <Plus className="w-3.5 h-3.5" />Simpan
                </Button>
              </div>
            )}
            <div className="px-3 py-2 border-b border-border/60">
              <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">
                Katalog akun persediaan
                {(psd?.total_barang || 0) > 0 && (
                  <span className="ml-1.5 normal-case font-semibold text-sky-700 dark:text-sky-400">
                    · master: {psd.total_barang} jenis barang · {fmtRp(psd.total_nilai)}
                  </span>
                )}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {(psd?.katalog || []).map((k) => (
                  <span key={k.akun}
                    className={`px-2 py-0.5 rounded-full border text-[10px] ${k.jumlah_barang ? "border-sky-500/40 bg-sky-500/5 text-foreground" : "border-border text-foreground/80"}`}
                    title={`${namaAkun[k.akun] || ""}${k.jumlah_barang ? ` — ${k.jumlah_barang} barang di master senilai ${fmtRp(k.nilai)}` : " — belum dipakai master persediaan"}`}>
                    <span className="font-mono font-semibold">{k.akun}</span> {k.uraian}
                    {/* Tautan MASTER PERSEDIAAN: jumlah barang & nilai FIFO per akun */}
                    {(k.jumlah_barang || 0) > 0 && (
                      <span className="ml-1 font-semibold text-sky-700 dark:text-sky-400">
                        {k.jumlah_barang} brg · {fmtRp(k.nilai)}
                      </span>
                    )}
                    {namaAkun[k.akun] === null && <span className="text-amber-600 dark:text-amber-400 ml-1" title="Tak ada di master BAS"><AlertTriangle className="w-3 h-3 inline align-[-1px]" /></span>}
                  </span>
                ))}
              </div>
            </div>
            <div className="divide-y divide-border/60">
              {(psd?.overrides || []).length === 0 ? (
                <p className="text-center text-[11px] text-muted-foreground py-5">Belum ada override — semua sub-kelompok memakai default {psd?.default_akun}.</p>
              ) : (psd?.overrides || []).map((o) => (
                <div key={o.sub_kelompok} className="px-3 py-2 flex items-center gap-3" data-testid={`psd-row-${o.sub_kelompok}`}>
                  <span className="w-20 font-mono text-[12px] font-semibold text-foreground flex-shrink-0">{o.sub_kelompok}</span>
                  <div className="w-28 flex-shrink-0">
                    <span className="font-mono text-[12px] text-foreground">{o.akun}</span>
                    <TandaAkun kode={o.akun} />
                  </div>
                  <p className="flex-1 text-[12px] text-foreground/80 truncate">{o.uraian}</p>
                  {isAdmin && (
                    <button type="button" onClick={() => hapusPsd(o.sub_kelompok)} aria-label={`Hapus override ${o.sub_kelompok}`}
                      title={`Hapus override ${o.sub_kelompok} (kembali ke default)`}
                      className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0 flex-shrink-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* SEMUA akun belanja persediaan (5218xx) dari master BAS — filter. */}
          <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="belanja-psd-card">
            <div className="px-3 py-2.5 border-b border-border">
              <p className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Landmark className="w-3.5 h-3.5" />Akun belanja persediaan terkait (dari master BAS)
              </p>
              <p className="text-[10px] text-muted-foreground">
                Belanja Barang Persediaan (5218xx) — belanja yang menghasilkan persediaan.
              </p>
            </div>
            <div className="px-3 py-2 border-b border-border">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input value={cariBelanjaPsd} onChange={(e) => setCariBelanjaPsd(e.target.value)}
                  placeholder="Cari kode / nama akun belanja persediaan…" className="pl-8 h-9 text-xs" data-testid="belanja-psd-cari" />
              </div>
            </div>
            <div className="divide-y divide-border/60 max-h-72 overflow-y-auto">
              {belanjaPsdTampil.map((a) => (
                <div key={a.kode} className="px-3 py-1.5 flex items-center gap-2.5" data-testid={`belanja-psd-${a.kode}`}>
                  <span className="font-mono text-[12px] text-foreground w-16 flex-shrink-0">{a.kode}</span>
                  <p className="text-[11px] text-foreground/80 flex-1 min-w-0 truncate" title={a.nama}>{a.nama}</p>
                </div>
              ))}
              {belanjaPsdTampil.length === 0 && (
                <p className="text-[11px] text-muted-foreground text-center py-4">
                  {belanjaPsd.length === 0 ? "Memuat akun dari master BAS…" : "Tidak ada akun belanja persediaan yang cocok."}
                </p>
              )}
            </div>
          </div>
          </div>
        )}

        {/* ── Info Kodefikasi Barang (riset PMK 29/2010 + KMK 333/KM.6/2024) ── */}
        {(tab === "aset" || tab === "persediaan") && (
          <details className="bg-card rounded-xl border border-border shadow-sm overflow-hidden group" data-testid="info-kodefikasi">
            <summary className="px-3 py-2.5 cursor-pointer select-none flex items-center gap-2 text-xs font-semibold text-foreground hover:bg-muted/40">
              <Info className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              Memahami Kodefikasi Barang BMN (kaitannya dengan akun neraca)
              <span className="ml-auto text-[10px] text-muted-foreground group-open:hidden">buka</span>
            </summary>
            <div className="px-3 pb-3 space-y-2.5 text-[11px] text-foreground/85">
              <div>
                <p className="font-bold text-[11px] mb-1">Struktur kode barang: 10 digit, 5 segmen (PMK 29/PMK.06/2010, lampiran terakhir KMK 333/KM.6/2024)</p>
                <div className="overflow-x-auto">
                  <div className="flex items-stretch gap-1 font-mono text-center min-w-[420px]">
                    {[["3", "Golongan", "Peralatan & Mesin"], ["05", "Bidang", "Alat Kantor & RT"],
                      ["01", "Kelompok", "Alat Kantor"], ["04", "Sub Kelompok", "Alat Penyimpan"],
                      ["001", "Sub-sub Kelompok", "Lemari Besi/Metal"]].map(([d, seg, contoh]) => (
                      <div key={seg} className="flex-1 rounded-lg border border-border p-1.5">
                        <p className="text-sm font-bold text-amber-700 dark:text-amber-400">{d}</p>
                        <p className="text-[9px] font-sans font-semibold text-foreground">{seg}</p>
                        <p className="text-[9px] font-sans text-muted-foreground">{contoh}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Contoh 3.05.01.04.001 = Lemari Besi/Metal; identitas unik satu unit = kode barang + NUP (Nomor Urut Pendaftaran).
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div className="rounded-lg border border-border p-2">
                  <p className="font-bold mb-0.5">Golongan → perlakuan</p>
                  <ul className="space-y-0.5 text-[10px] text-foreground/80">
                    <li><b>1 Persediaan</b> — aset lancar, dicatat FIFO di modul Persediaan (akun 1171xx), tidak disusutkan.</li>
                    <li><b>2 Tanah</b> — tidak disusutkan (PMK 65/2017), tanpa ambang kapitalisasi.</li>
                    <li><b>3 Peralatan &amp; Mesin</b> — disusutkan; ambang kapitalisasi ≥ Rp1 juta/unit (PMK 181/2016).</li>
                    <li><b>4 Gedung &amp; Bangunan</b> — disusutkan; ambang ≥ Rp25 juta.</li>
                    <li><b>5 Jalan, Irigasi, Jaringan</b> — disusutkan; akun neraca per BIDANG: 134111 jalan-jembatan / 134112 irigasi / 134113 jaringan.</li>
                    <li><b>6 Aset Tetap Lainnya</b> — umumnya tidak disusutkan.</li>
                    <li><b>7 KDP</b> — belum disusutkan sampai selesai dibangun.</li>
                    <li><b>8 Aset Tak Berwujud</b> — diamortisasi; keluarga akun 162xxx (software 162151, lisensi 162161, dst.).</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-border p-2">
                  <p className="font-bold mb-0.5">Kaitan kode ↔ akun ↔ master</p>
                  <ul className="space-y-0.5 text-[10px] text-foreground/80">
                    <li>Digit pertama kode barang menentukan akun neraca (aturan pakai di tab Aset) — angka "aset di master" di tiap baris menunjukkan isi nyata master yang memakainya.</li>
                    <li>Untuk golongan 1, sub-sub kelompok dipetakan ke akun 1171xx (tab Persediaan) — barang di bawah akun tampil pada chip katalog.</li>
                    <li>Barang di bawah ambang kapitalisasi dibukukan EKSTRAKOMPTABEL (tidak masuk neraca) — ambang dapat diatur di tab Aset.</li>
                    <li>Kode barang bisa berubah lewat KMK perubahan lampiran — perubahan kode di aplikasi wajib lewat menu Reklasifikasi (jurnal 304/107) agar jejak Buku Barang utuh.</li>
                  </ul>
                </div>
              </div>
            </div>
          </details>
        )}
      </main>

      {confirmDialog}
    </div>
  );
}
