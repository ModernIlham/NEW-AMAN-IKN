import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Loader2, Mail, MailPlus, Inbox, FileDown,
  CheckCircle2, XCircle, Pencil, Settings2, Plus, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

const WARNA_STATUS = {
  dibooking: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  disahkan: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  dibatalkan: "bg-red-500/15 text-red-600 dark:text-red-400",
  diterima: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  diproses: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
};

const KELUAR_KOSONG = {
  perihal: "", tujuan: "", jenis_naskah: "Laporan", modul: "umum",
  kegiatan_id: "", kode_klasifikasi: "", kode_keamanan: "B",
  tanggal_surat: "", referensi: "", nomor_eksternal: "", keterangan: "",
};
const MASUK_KOSONG = {
  nomor_surat: "", pengirim: "", perihal: "", tanggal_surat: "",
  modul: "umum", kegiatan_id: "", keterangan: "",
};

/**
 * Persuratan — buku agenda & booking nomor naskah dinas lintas modul
 * (PerANRI 5/2021, pustaka §12). Surat keluar dipesan nomornya saat draf
 * (booking) lalu disahkan setelah ditandatangani atau dibatalkan (nomor
 * hangus — tidak didaur ulang); surat masuk teragenda dengan nomor sendiri.
 */
export default function PersuratanPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [ref, setRef] = useState(null);
  const [kegiatan, setKegiatan] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fJenis, setFJenis] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [formKeluar, setFormKeluar] = useState(null);
  const [formMasuk, setFormMasuk] = useState(null);
  const [formAtur, setFormAtur] = useState(null);
  const [batal, setBatal] = useState(null); // {surat, alasan}
  const [saving, setSaving] = useState(false);
  const [pratinjau, setPratinjau] = useState(null); // {nomor, sumber_klasifikasi, ...}
  const [klasifikasi, setKlasifikasi] = useState([]); // master kode klasifikasi
  const [klasBaru, setKlasBaru] = useState({ kode: "", uraian: "" });
  const pratinjauTimer = useRef(null);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), page_size: "50" });
      if (fJenis) params.append("jenis", fJenis);
      if (fStatus) params.append("status", fStatus);
      if (q.trim()) params.append("q", q.trim());
      const r = await axios.get(`${API}/persuratan?${params}`);
      setData(r.data);
      setPage(p);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat buku agenda"));
    } finally {
      setLoading(false);
    }
  }, [fJenis, fStatus, q]);

  useEffect(() => { load(1); }, [load]);

  useEffect(() => {
    axios.get(`${API}/persuratan/referensi`).then((r) => {
      setRef(r.data);
      setKlasifikasi(r.data?.klasifikasi || []);
    }).catch(() => {});
    axios.get(`${API}/inventory-activities`)
      .then((r) => setKegiatan(Array.isArray(r.data) ? r.data : (r.data?.items || [])))
      .catch(() => {});
  }, []);

  // Pratinjau nomor live: setiap field penentu nomor berubah → perkiraan
  // nomor berikutnya (counter TIDAK naik; keunikan tetap dijamin saat booking).
  useEffect(() => {
    if (!formKeluar || formKeluar.mode) { setPratinjau(null); return; }
    if (pratinjauTimer.current) clearTimeout(pratinjauTimer.current);
    pratinjauTimer.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          jenis_naskah: formKeluar.jenis_naskah || "",
          modul: formKeluar.modul || "",
          kode_klasifikasi: formKeluar.kode_klasifikasi || "",
          kode_keamanan: formKeluar.kode_keamanan || "B",
          tanggal_surat: formKeluar.tanggal_surat || "",
        });
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${params}`);
        setPratinjau(r.data);
      } catch { setPratinjau(null); }
    }, 350);
    return () => { if (pratinjauTimer.current) clearTimeout(pratinjauTimer.current); };
  }, [formKeluar]);

  const kirim = async (fn, sukses) => {
    setSaving(true);
    try {
      await fn();
      toast.success(sukses);
      setFormKeluar(null); setFormMasuk(null); setFormAtur(null); setBatal(null);
      load(page);
    } catch (e) {
      toast.error(apiErr(e, "Gagal menyimpan"));
    } finally {
      setSaving(false);
    }
  };

  const booking = () => {
    if (!formKeluar?.perihal?.trim()) { toast.error("Perihal wajib diisi"); return; }
    kirim(async () => {
      const r = await axios.post(`${API}/persuratan/keluar`, formKeluar);
      toast.info(`Nomor dibooking: ${r.data.nomor}`, { duration: 9000 });
    }, "Surat keluar terbooking");
  };

  const catatMasuk = () => {
    const f = formMasuk || {};
    if (!f.nomor_surat?.trim() || !f.pengirim?.trim() || !f.perihal?.trim()) {
      toast.error("Nomor surat, pengirim, dan perihal wajib diisi"); return;
    }
    kirim(() => axios.post(`${API}/persuratan/masuk`, formMasuk), "Surat masuk teragenda");
  };

  const transisi = (s, status, alasan = "") =>
    kirim(() => axios.post(`${API}/persuratan/${s.id}/status`, { status, alasan }),
      status === "disahkan" ? `Surat ${s.nomor} disahkan`
        : status === "dibatalkan" ? `Nomor ${s.nomor} dibatalkan (hangus)`
          : `Status → ${status}`);

  const simpanAtur = () =>
    kirim(() => axios.post(`${API}/persuratan/pengaturan`, formAtur), "Pengaturan tersimpan");

  const muatKlasifikasi = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/persuratan/klasifikasi`);
      setKlasifikasi(r.data?.items || []);
    } catch { /* abaikan */ }
  }, []);

  const tambahKlas = async () => {
    if (!klasBaru.kode.trim()) { toast.error("Kode klasifikasi wajib diisi"); return; }
    try {
      await axios.post(`${API}/persuratan/klasifikasi`, klasBaru);
      toast.success(`Kode ${klasBaru.kode} ditambahkan`);
      setKlasBaru({ kode: "", uraian: "" });
      muatKlasifikasi();
    } catch (e) { toast.error(apiErr(e, "Gagal menambah kode")); }
  };

  const hapusKlas = async (k) => {
    try {
      await axios.delete(`${API}/persuratan/klasifikasi/${k.id}`);
      toast.success(`Kode ${k.kode} dihapus`);
      muatKlasifikasi();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus kode")); }
  };

  const setAturan = (i, field, value) => setFormAtur((f) => ({
    ...f,
    peta_klasifikasi: (f.peta_klasifikasi || []).map((a, j) =>
      j === i ? { ...a, [field]: value } : a),
  }));

  const rk = data?.ringkasan;
  const items = data?.items || [];
  const setK = (k) => (e) => setFormKeluar((f) => ({ ...f, [k]: e.target.value }));
  const setM = (k) => (e) => setFormMasuk((f) => ({ ...f, [k]: e.target.value }));
  const opsiStatus = useMemo(() => (
    fJenis === "masuk" ? (ref?.status_masuk || [])
      : fJenis === "keluar" ? (ref?.status_keluar || [])
        : [...(ref?.status_keluar || []), ...(ref?.status_masuk || [])]
  ), [ref, fJenis]);

  return (
    <div className="min-h-screen bg-background" data-testid="persuratan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="persuratan-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-cyan-700 flex items-center justify-center flex-shrink-0">
            <Mail className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Registrasi Persuratan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              Buku agenda & booking nomor naskah dinas lintas modul (PerANRI 5/2021)
            </p>
          </div>
          {isAdmin && (
            <Button variant="outline" size="sm" className="gap-1.5"
              onClick={async () => {
                try {
                  const r = await axios.get(`${API}/persuratan/pengaturan`);
                  setFormAtur(r.data);
                  muatKlasifikasi();
                } catch { toast.error("Gagal memuat pengaturan"); }
              }} data-testid="persuratan-atur-btn">
              <Settings2 className="w-3.5 h-3.5" /><span className="hidden sm:inline">Format Nomor</span>
            </Button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        {rk && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="persuratan-ringkas">
            {[["Dibooking (belum sah)", rk.keluar_dibooking, "text-amber-600 dark:text-amber-400"],
              ["Keluar disahkan", rk.keluar_disahkan, "text-emerald-600 dark:text-emerald-400"],
              ["Dibatalkan (hangus)", rk.keluar_dibatalkan, "text-red-600 dark:text-red-400"],
              ["Masuk belum selesai", rk.masuk_terbuka, "text-sky-600 dark:text-sky-400"],
            ].map(([label, n, cls]) => (
              <div key={label} className="bg-card rounded-xl border border-border shadow-sm px-3 py-2">
                <p className={`text-lg font-bold ${cls}`}>{n}</p>
                <p className="text-[10px] text-muted-foreground leading-tight">{label}</p>
              </div>
            ))}
          </div>
        )}

        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3 flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[160px]">
            <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
            <Input value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Cari nomor / perihal / tujuan / pengirim…" className="pl-9 h-10"
              data-testid="persuratan-cari" />
          </div>
          <select value={fJenis} onChange={(e) => { setFJenis(e.target.value); setFStatus(""); }}
            className="h-10 rounded-md border border-input bg-background px-2 text-sm" data-testid="persuratan-f-jenis">
            <option value="">Keluar + Masuk</option>
            <option value="keluar">Surat Keluar</option>
            <option value="masuk">Surat Masuk</option>
          </select>
          <select value={fStatus} onChange={(e) => setFStatus(e.target.value)}
            className="h-10 rounded-md border border-input bg-background px-2 text-sm" data-testid="persuratan-f-status">
            <option value="">Semua status</option>
            {opsiStatus.map((s) => <option key={s.kode} value={s.kode}>{s.uraian}</option>)}
          </select>
          <Button className="h-10 gap-1.5" onClick={() => setFormKeluar({ ...KELUAR_KOSONG })}
            data-testid="persuratan-booking-btn">
            <MailPlus className="w-4 h-4" /><span className="hidden sm:inline">Booking Surat Keluar</span><span className="sm:hidden">Keluar</span>
          </Button>
          <Button variant="outline" className="h-10 gap-1.5" onClick={() => setFormMasuk({ ...MASUK_KOSONG })}
            data-testid="persuratan-masuk-btn">
            <Inbox className="w-4 h-4" /><span className="hidden sm:inline">Catat Surat Masuk</span><span className="sm:hidden">Masuk</span>
          </Button>
          <Button variant="outline" className="h-10 gap-1.5"
            onClick={() => downloadFileWithProgress(`${API}/persuratan/export${fJenis ? `?jenis=${fJenis}` : ""}`, "Buku_Agenda_Surat.csv", { label: "Buku Agenda (CSV)" }).catch(() => {})}
            data-testid="persuratan-export">
            <FileDown className="w-4 h-4" /><span className="hidden sm:inline">CSV</span>
          </Button>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading && !data ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="w-7 h-7 animate-spin text-cyan-700" /></div>
          ) : items.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Mail className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">Belum ada surat teragenda</p>
              <p className="text-xs text-muted-foreground mt-1">
                Booking nomor surat keluar SEBELUM naskah difinalkan, lalu sahkan setelah ditandatangani.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[860px]">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Agenda</th>
                    <th className="px-3 py-2.5 font-semibold">Nomor / Tanggal</th>
                    <th className="px-3 py-2.5 font-semibold">Perihal</th>
                    <th className="px-3 py-2.5 font-semibold">Dari / Kepada</th>
                    <th className="px-3 py-2.5 font-semibold">Naskah · Modul</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`persuratan-row-${s.id}`}>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${s.jenis === "keluar" ? "bg-cyan-500/15 text-cyan-700 dark:text-cyan-400" : "bg-violet-500/15 text-violet-600 dark:text-violet-400"}`}>
                          {s.jenis === "keluar" ? "K" : "M"}-{String(s.no_agenda).padStart(3, "0")}/{s.tahun}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-mono text-[12px] text-foreground break-all">{s.nomor}</p>
                        {s.nomor_eksternal && (
                          <p className="font-mono text-[10px] text-teal-700 dark:text-teal-400 break-all" title="Nomor sah dari aplikasi eksternal">eks: {s.nomor_eksternal}</p>
                        )}
                        <p className="text-[10px] text-muted-foreground">{s.tanggal_surat || "—"}</p>
                      </td>
                      <td className="px-3 py-2">
                        <p className="text-[12px] text-foreground/90">{s.perihal}</p>
                        {(s.referensi || s.nama_kegiatan) && (
                          <p className="text-[10px] text-muted-foreground truncate">{[s.referensi, s.nama_kegiatan].filter(Boolean).join(" · ")}</p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-[12px] text-foreground/80">{s.jenis === "keluar" ? (s.tujuan || "—") : (s.pengirim || "—")}</td>
                      <td className="px-3 py-2">
                        <p className="text-[11px] text-foreground/80">{s.jenis_naskah || "—"}</p>
                        <p className="text-[10px] text-muted-foreground">{s.modul}</p>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${WARNA_STATUS[s.status] || "bg-muted text-muted-foreground"}`}>
                          {s.status}
                        </span>
                        {s.alasan_batal && <p className="text-[9px] text-red-500/80 mt-0.5 max-w-[140px] truncate" title={s.alasan_batal}>{s.alasan_batal}</p>}
                      </td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        {s.jenis === "keluar" && s.status === "dibooking" && (
                          <>
                            <button type="button" onClick={() => transisi(s, "disahkan")}
                              title="Sahkan (surat final ditandatangani)" aria-label={`Sahkan ${s.nomor}`}
                              className="p-1.5 rounded-md text-emerald-600 hover:bg-emerald-500/10 min-w-0 min-h-0"
                              data-testid={`persuratan-sahkan-${s.id}`}>
                              <CheckCircle2 className="w-4 h-4" />
                            </button>
                            <button type="button" onClick={() => setBatal({ surat: s, alasan: "" })}
                              title="Batalkan (nomor hangus)" aria-label={`Batalkan ${s.nomor}`}
                              className="p-1.5 rounded-md text-red-500 hover:bg-red-500/10 min-w-0 min-h-0"
                              data-testid={`persuratan-batal-${s.id}`}>
                              <XCircle className="w-4 h-4" />
                            </button>
                            <button type="button" onClick={() => setFormKeluar({ ...KELUAR_KOSONG, ...s, mode: "edit" })}
                              title="Ubah draf" aria-label={`Ubah ${s.nomor}`}
                              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                              data-testid={`persuratan-edit-${s.id}`}>
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          </>
                        )}
                        {s.jenis === "keluar" && s.status === "disahkan" && (
                          <button type="button" onClick={() => setFormKeluar({ ...KELUAR_KOSONG, ...s, mode: "edit-final" })}
                            title="Isi nomor eksternal / keterangan" aria-label={`Ubah nomor eksternal ${s.nomor}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`persuratan-edit-final-${s.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {s.jenis === "masuk" && (
                          <button type="button" onClick={() => setFormMasuk({ ...MASUK_KOSONG, ...s, nomor_surat: s.nomor, mode: "edit" })}
                            title="Ubah surat masuk" aria-label={`Ubah surat masuk ${s.nomor}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`persuratan-edit-masuk-${s.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {s.jenis === "masuk" && s.status !== "selesai" && (
                          <Button size="sm" variant="outline" className="h-7 text-[11px]"
                            onClick={() => transisi(s, s.status === "diterima" ? "diproses" : "selesai")}
                            data-testid={`persuratan-masuk-lanjut-${s.id}`}>
                            {s.status === "diterima" ? "Proses" : "Selesai"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between px-3 py-2 border-t border-border bg-muted/30">
              <Button size="sm" variant="ghost" disabled={page <= 1 || loading} onClick={() => load(page - 1)}>Sebelumnya</Button>
              <span className="text-[11px] text-muted-foreground">Hal {data.page}/{data.total_pages} · {data.total} surat</span>
              <Button size="sm" variant="ghost" disabled={page >= data.total_pages || loading} onClick={() => load(page + 1)}>Berikutnya</Button>
            </div>
          )}
        </div>

        <p className="text-center text-[10px] text-muted-foreground pb-4">
          Kaidah: nomor dipesan (booking) saat draf → disahkan setelah tanda tangan; nomor batal hangus &
          tercatat beralasan — urutan agenda tetap utuh (PerANRI 5/2021 · buku agenda kembar).
        </p>
      </main>

      {/* ── Dialog booking / edit surat keluar ── */}
      <Dialog open={!!formKeluar} onOpenChange={(o) => { if (!o) setFormKeluar(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{formKeluar?.mode === "edit-final" ? `Nomor Eksternal — ${formKeluar?.nomor}` : formKeluar?.mode === "edit" ? `Ubah Draf — ${formKeluar?.nomor}` : "Booking Nomor Surat Keluar"}</DialogTitle>
            <DialogDescription className="text-xs">
              Nomor dipesan sekarang dan menjadi milik surat ini sampai disahkan/dibatalkan.
            </DialogDescription>
          </DialogHeader>
          {formKeluar && formKeluar.mode === "edit-final" && (
            <div className="space-y-3">
              <p className="text-[11px] text-muted-foreground">
                Surat sudah disahkan — hanya nomor eksternal (anchor dari aplikasi lain) dan keterangan yang dapat diubah.
              </p>
              <Field label="Nomor Eksternal (aplikasi lain)">
                <Input value={formKeluar.nomor_eksternal || ""} onChange={setK("nomor_eksternal")}
                  placeholder="nomor sah dari Srikandi/e-office" className="font-mono"
                  data-testid="final-nomor-eksternal" />
              </Field>
              <Field label="Keterangan"><Input value={formKeluar.keterangan || ""} onChange={setK("keterangan")} /></Field>
            </div>
          )}
          {formKeluar && formKeluar.mode !== "edit-final" && (
            <div className="space-y-3">
              <Field label="Perihal *"><Input value={formKeluar.perihal} onChange={setK("perihal")} placeholder="cth. Penyampaian LHI Semester I 2026" data-testid="keluar-perihal" /></Field>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Kepada / Tujuan"><Input value={formKeluar.tujuan} onChange={setK("tujuan")} placeholder="cth. KPKNL Balikpapan" /></Field>
                <Field label="Tanggal Surat"><Input type="date" value={formKeluar.tanggal_surat} onChange={setK("tanggal_surat")} /></Field>
                <Field label="Jenis Naskah">
                  <select value={formKeluar.jenis_naskah} onChange={setK("jenis_naskah")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" data-testid="keluar-jenis-naskah">
                    {(ref?.jenis_naskah || ["Laporan"]).map((j) => <option key={j} value={j}>{j}</option>)}
                  </select>
                </Field>
                <Field label="Modul Asal">
                  <select value={formKeluar.modul} onChange={setK("modul")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.modul || ["umum"]).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
                <Field label="Kegiatan (opsional)">
                  <select value={formKeluar.kegiatan_id} onChange={setK("kegiatan_id")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    <option value="">— tanpa kegiatan —</option>
                    {kegiatan.map((k) => <option key={k.id} value={k.id}>{k.nama_kegiatan}</option>)}
                  </select>
                </Field>
                <Field label="Klasifikasi Keamanan">
                  <select value={formKeluar.kode_keamanan} onChange={setK("kode_keamanan")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.kode_keamanan || []).map((k) => <option key={k.kode} value={k.kode}>{k.kode} — {k.uraian}</option>)}
                  </select>
                </Field>
                <Field label="Kode Klasifikasi Arsip">
                  <Input value={formKeluar.kode_klasifikasi} onChange={setK("kode_klasifikasi")}
                    list="klasifikasi-arsip-list"
                    placeholder={pratinjau?.kode_klasifikasi ? `otomatis: ${pratinjau.kode_klasifikasi}` : "cth. PL.02"}
                    className="font-mono" data-testid="keluar-klasifikasi" />
                </Field>
                <Field label="Referensi Laporan"><Input value={formKeluar.referensi} onChange={setK("referensi")} placeholder="cth. BAHI / LHI / LBKP S1" /></Field>
                <Field label="Nomor Eksternal (aplikasi lain)">
                  <Input value={formKeluar.nomor_eksternal || ""} onChange={setK("nomor_eksternal")}
                    placeholder="nomor sah dari Srikandi/e-office" className="font-mono"
                    data-testid="keluar-nomor-eksternal" />
                </Field>
              </div>
              <Field label="Keterangan"><Input value={formKeluar.keterangan} onChange={setK("keterangan")} /></Field>
              {formKeluar.mode !== "edit" && pratinjau?.nomor && (
                <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2" data-testid="keluar-pratinjau">
                  <p className="text-[10px] text-muted-foreground">Perkiraan nomor yang akan terbit:</p>
                  <p className="font-mono text-sm font-bold text-cyan-700 dark:text-cyan-400 break-all">{pratinjau.nomor}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Klasifikasi: {pratinjau.kode_klasifikasi || "(kosong)"} · {
                      pratinjau.sumber_klasifikasi === "eksplisit" ? "diisi manual"
                        : pratinjau.sumber_klasifikasi === "pemetaan" ? "otomatis dari aturan pemetaan"
                          : pratinjau.sumber_klasifikasi === "bawaan" ? "kode bawaan pengaturan"
                            : "belum ada aturan/bawaan — atur di Format Nomor"}
                    {" · "}bisa bergeser bila ada booking lain lebih dulu
                  </p>
                </div>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormKeluar(null)}>Batal</Button>
            <Button disabled={saving} data-testid="keluar-simpan"
              onClick={formKeluar?.mode === "edit-final"
                ? () => kirim(() => axios.put(`${API}/persuratan/${formKeluar.id}`, {
                    nomor_eksternal: formKeluar.nomor_eksternal,
                    keterangan: formKeluar.keterangan,
                  }), "Nomor eksternal tersimpan")
                : formKeluar?.mode === "edit"
                ? () => kirim(() => axios.put(`${API}/persuratan/${formKeluar.id}`, {
                    perihal: formKeluar.perihal, tujuan: formKeluar.tujuan,
                    jenis_naskah: formKeluar.jenis_naskah, modul: formKeluar.modul,
                    kegiatan_id: formKeluar.kegiatan_id, kode_klasifikasi: formKeluar.kode_klasifikasi,
                    tanggal_surat: formKeluar.tanggal_surat, referensi: formKeluar.referensi,
                    nomor_eksternal: formKeluar.nomor_eksternal, keterangan: formKeluar.keterangan,
                  }), "Draf surat diperbarui")
                : booking}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}
              {formKeluar?.mode ? "Simpan" : "Booking Nomor"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog surat masuk ── */}
      <Dialog open={!!formMasuk} onOpenChange={(o) => { if (!o) setFormMasuk(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{formMasuk?.mode === "edit" ? `Ubah Surat Masuk — M-${String(formMasuk.no_agenda).padStart(3, "0")}/${formMasuk.tahun}` : "Catat Surat Masuk"}</DialogTitle>
            <DialogDescription className="text-xs">
              {formMasuk?.mode === "edit" ? "Koreksi data surat masuk — nomor agenda tetap." : "Nomor agenda masuk terbit otomatis per tahun."}
            </DialogDescription>
          </DialogHeader>
          {formMasuk && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Nomor Surat (pengirim) *"><Input value={formMasuk.nomor_surat} onChange={setM("nomor_surat")} className="font-mono" data-testid="masuk-nomor" /></Field>
                <Field label="Tanggal Surat"><Input type="date" value={formMasuk.tanggal_surat} onChange={setM("tanggal_surat")} /></Field>
                <Field label="Pengirim *"><Input value={formMasuk.pengirim} onChange={setM("pengirim")} placeholder="cth. KPKNL Balikpapan" data-testid="masuk-pengirim" /></Field>
                <Field label="Modul Terkait">
                  <select value={formMasuk.modul} onChange={setM("modul")}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
                    {(ref?.modul || ["umum"]).map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </Field>
              </div>
              <Field label="Perihal *"><Input value={formMasuk.perihal} onChange={setM("perihal")} data-testid="masuk-perihal" /></Field>
              <Field label="Keterangan / disposisi"><Input value={formMasuk.keterangan} onChange={setM("keterangan")} /></Field>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormMasuk(null)}>Batal</Button>
            <Button disabled={saving} data-testid="masuk-simpan"
              onClick={formMasuk?.mode === "edit"
                ? () => {
                    const f = formMasuk;
                    if (!f.nomor_surat?.trim() || !f.pengirim?.trim() || !f.perihal?.trim()) {
                      toast.error("Nomor surat, pengirim, dan perihal wajib diisi"); return;
                    }
                    kirim(() => axios.put(`${API}/persuratan/${f.id}`, {
                      nomor_surat: f.nomor_surat, pengirim: f.pengirim,
                      perihal: f.perihal, tanggal_surat: f.tanggal_surat,
                      modul: f.modul, keterangan: f.keterangan,
                    }), "Surat masuk diperbarui");
                  }
                : catatMasuk}>
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}
              {formMasuk?.mode === "edit" ? "Simpan" : "Catat"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog pembatalan (wajib alasan) ── */}
      <Dialog open={!!batal} onOpenChange={(o) => { if (!o) setBatal(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Batalkan Nomor {batal?.surat?.nomor}?</DialogTitle>
            <DialogDescription className="text-xs">
              Nomor yang dibatalkan HANGUS — tidak dipakai surat lain, tetap tercatat di agenda dengan alasannya (kaidah kearsipan).
            </DialogDescription>
          </DialogHeader>
          <Field label="Alasan pembatalan *">
            <Input value={batal?.alasan || ""} onChange={(e) => setBatal((b) => ({ ...b, alasan: e.target.value }))}
              placeholder="cth. draf ganda / batal terbit" data-testid="batal-alasan" />
          </Field>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setBatal(null)}>Kembali</Button>
            <Button variant="destructive" disabled={saving || !(batal?.alasan || "").trim()}
              onClick={() => transisi(batal.surat, "dibatalkan", batal.alasan)} data-testid="batal-konfirmasi">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Batalkan Nomor
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog pengaturan format + klasifikasi (admin) ── */}
      <Dialog open={!!formAtur} onOpenChange={(o) => { if (!o) setFormAtur(null); }}>
        <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Pengaturan Penomoran & Klasifikasi Surat</DialogTitle>
            <DialogDescription className="text-xs">
              Susunan PerANRI 5/2021 — placeholder: {"{kode_keamanan} {urut} {kode_klasifikasi} {kode_unit} {bulan} {bulan_romawi} {tahun}"}.
            </DialogDescription>
          </DialogHeader>
          {formAtur && (
            <div className="space-y-4">
              <div className="space-y-3">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">Format Nomor</p>
                <Field label="Format Nomor">
                  <Input value={formAtur.format_nomor} className="font-mono"
                    onChange={(e) => setFormAtur((f) => ({ ...f, format_nomor: e.target.value }))}
                    data-testid="atur-format" />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Kode Unit"><Input value={formAtur.kode_unit} onChange={(e) => setFormAtur((f) => ({ ...f, kode_unit: e.target.value }))} placeholder="cth. OIKN" /></Field>
                  <Field label="Kode Klasifikasi Bawaan (fallback)"><Input value={formAtur.kode_klasifikasi_default} onChange={(e) => setFormAtur((f) => ({ ...f, kode_klasifikasi_default: e.target.value }))} placeholder="cth. UM.01" className="font-mono" /></Field>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  Contoh hasil: <span className="font-mono">B-015/PL.02/OIKN/VII/2026</span>. Perubahan hanya memengaruhi booking BERIKUTNYA.
                </p>
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">
                  Master Kode Klasifikasi Arsip
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Isi sesuai pedoman klasifikasi arsip instansi Anda — jadi pilihan di form booking &amp; bahan aturan otomatis.
                </p>
                {klasifikasi.length > 0 && (
                  <div className="max-h-36 overflow-y-auto border border-border rounded-lg divide-y divide-border/60">
                    {klasifikasi.map((k) => (
                      <div key={k.id} className="flex items-center gap-2 px-2.5 py-1">
                        <span className="font-mono text-[11px] font-semibold text-foreground w-20 flex-shrink-0">{k.kode}</span>
                        <span className="text-[11px] text-foreground/80 truncate flex-1">{k.uraian || "—"}</span>
                        <button type="button" onClick={() => hapusKlas(k)} aria-label={`Hapus ${k.kode}`}
                          className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                          data-testid={`klas-hapus-${k.kode}`}>
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Input value={klasBaru.kode} onChange={(e) => setKlasBaru((b) => ({ ...b, kode: e.target.value }))}
                    placeholder="Kode (cth. PL.02)" className="font-mono h-9 w-36" data-testid="klas-baru-kode" />
                  <Input value={klasBaru.uraian} onChange={(e) => setKlasBaru((b) => ({ ...b, uraian: e.target.value }))}
                    placeholder="Uraian (cth. Pelaporan BMN)" className="h-9 flex-1" data-testid="klas-baru-uraian" />
                  <Button variant="outline" size="sm" className="h-9 gap-1" onClick={tambahKlas} data-testid="klas-tambah">
                    <Plus className="w-3.5 h-3.5" />Tambah
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">
                  Aturan Klasifikasi Otomatis
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Saat booking, kode klasifikasi terisi otomatis dari aturan yang paling spesifik (modul + jenis naskah &gt; salah satunya); kosong = berlaku untuk semua. Kode manual di form selalu menang.
                </p>
                {(formAtur.peta_klasifikasi || []).map((a, i) => (
                  <div key={i} className="flex items-center gap-1.5" data-testid={`aturan-${i}`}>
                    <select value={a.modul || ""} onChange={(e) => setAturan(i, "modul", e.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-2 text-xs w-32">
                      <option value="">semua modul</option>
                      {(ref?.modul || []).map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                    <select value={a.jenis_naskah || ""} onChange={(e) => setAturan(i, "jenis_naskah", e.target.value)}
                      className="h-9 rounded-md border border-input bg-background px-2 text-xs flex-1">
                      <option value="">semua jenis naskah</option>
                      {(ref?.jenis_naskah || []).map((j) => <option key={j} value={j}>{j}</option>)}
                    </select>
                    <Input value={a.kode || ""} onChange={(e) => setAturan(i, "kode", e.target.value)}
                      list="klasifikasi-arsip-list" placeholder="kode" className="font-mono h-9 w-24" />
                    <button type="button" aria-label="Hapus aturan"
                      onClick={() => setFormAtur((f) => ({ ...f, peta_klasifikasi: f.peta_klasifikasi.filter((_, j) => j !== i) }))}
                      className="p-1.5 rounded text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                <Button variant="outline" size="sm" className="h-8 gap-1 text-[11px]"
                  onClick={() => setFormAtur((f) => ({ ...f, peta_klasifikasi: [...(f.peta_klasifikasi || []), { modul: "", jenis_naskah: "", kode: "" }] }))}
                  data-testid="aturan-tambah">
                  <Plus className="w-3.5 h-3.5" />Tambah Aturan
                </Button>
              </div>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setFormAtur(null)}>Batal</Button>
            <Button onClick={simpanAtur} disabled={saving} data-testid="atur-simpan">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Datalist bersama: dipakai input klasifikasi di dialog booking & pengaturan */}
      <datalist id="klasifikasi-arsip-list">
        {klasifikasi.map((k) => <option key={k.id} value={k.kode}>{k.uraian}</option>)}
      </datalist>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
      {children}
    </div>
  );
}
