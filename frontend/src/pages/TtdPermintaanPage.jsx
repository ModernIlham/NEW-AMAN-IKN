import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, BadgeCheck, Copy, FileDown, FileSignature, Link2,
  Loader2, PenTool, Plus, Search, ShieldCheck, Trash2, Users, XCircle,
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
  terkirim: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  sebagian: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  selesai: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  batal: "bg-red-500/15 text-red-600 dark:text-red-400",
};
const WARNA_SIGNER = {
  ditandatangani: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  aktif: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  menunggu: "bg-muted text-muted-foreground",
};

const SIGNER_KOSONG = { nama: "", nip: "", jabatan: "" };
const FORM_KOSONG = { judul: "", doc_type: "dokumen", mode: "paralel", signers: [{ ...SIGNER_KOSONG }] };

function fmtWaktu(iso) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("id-ID", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

async function salin(teks) {
  try {
    await navigator.clipboard.writeText(teks);
    toast.success("Link disalin — bagikan via WA/email ke penanda tangan");
  } catch {
    toast.error("Gagal menyalin — salin manual dari kolom link");
  }
}

/**
 * TtdPermintaanPage — dasbor Tanda Tangan Elektronik:
 * buat permintaan e-sign (link per penanda tangan, mode paralel/berurutan),
 * pantau status, salin/bagikan link, unduh Lembar Pengesahan PDF.
 */
export default function TtdPermintaanPage({ user, onBack }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [form, setForm] = useState(null);          // FORM_KOSONG saat dialog buka
  const [saving, setSaving] = useState(false);
  const [hasil, setHasil] = useState(null);        // {judul, links:[{nama,link}]} pasca-buat
  const [detail, setDetail] = useState(null);      // record permintaan terpilih
  const [pegawai, setPegawai] = useState([]);

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/ttd/permintaan`);
      setItems(r.data?.items || []);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat permintaan tanda tangan"));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  // Master pegawai untuk saran nama (datalist) — opsional, gagal senyap.
  useEffect(() => {
    axios.get(`${API}/pegawai`)
      .then((r) => setPegawai(r.data?.items || []))
      .catch(() => {});
  }, []);

  const tampil = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items;
    return items.filter((it) =>
      (it.judul || "").toLowerCase().includes(s) ||
      (it.signers || []).some((sg) => (sg.nama || "").toLowerCase().includes(s)));
  }, [items, q]);

  const ubahSigner = (i, k, v) => {
    setForm((f) => {
      const signers = f.signers.map((s, idx) => (idx === i ? { ...s, [k]: v } : s));
      return { ...f, signers };
    });
  };
  const isiDariPegawai = (i, nama) => {
    const p = pegawai.find((pg) => pg.nama === nama);
    if (!p) return;
    setForm((f) => {
      const signers = f.signers.map((s, idx) => (idx === i
        ? { nama: p.nama || "", nip: p.nip || "", jabatan: p.jabatan || "" } : s));
      return { ...f, signers };
    });
  };

  const buat = async () => {
    if (!form.judul.trim()) { toast.error("Judul dokumen wajib diisi"); return; }
    if (form.signers.some((s) => !s.nama.trim())) {
      toast.error("Nama semua penanda tangan wajib diisi"); return;
    }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/ttd/permintaan`, form);
      setHasil(r.data);
      setForm(null);
      load();
    } catch (e) {
      toast.error(apiErr(e, "Gagal membuat permintaan"));
    } finally {
      setSaving(false);
    }
  };

  const batalkan = async (it) => {
    try {
      await axios.delete(`${API}/ttd/permintaan/${it.id}`);
      toast.success("Permintaan dibatalkan");
      setDetail(null);
      load();
    } catch (e) {
      toast.error(apiErr(e, "Gagal membatalkan"));
    }
  };

  const bukaDetail = async (it) => {
    try {
      const r = await axios.get(`${API}/ttd/permintaan/${it.id}`);
      setDetail(r.data);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat detail"));
    }
  };

  const unduhLembar = async (it) => {
    try {
      await downloadFileWithProgress(
        `${API}/ttd/permintaan/${it.id}/lembar-pdf`,
        `Lembar_TTD_${(it.judul || it.id).slice(0, 30).replace(/[^\w-]+/g, "_")}.pdf`);
    } catch (e) {
      toast.error(apiErr(e, "Gagal mengunduh lembar pengesahan"));
    }
  };

  const linkVerifikasi = (id) => `${window.location.origin}/ttd/verifikasi/${id}`;

  return (
    <div className="min-h-screen bg-background" data-testid="ttd-permintaan-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="ttd-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-blue-700 flex items-center justify-center flex-shrink-0">
            <FileSignature className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Tanda Tangan Elektronik</h1>
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              Kirim link e-sign · pantau status · unduh lembar pengesahan
            </p>
          </div>
          <Button size="sm" className="h-9 text-xs" onClick={() => setForm({ ...FORM_KOSONG, signers: [{ ...SIGNER_KOSONG }] })}
            data-testid="ttd-buat">
            <Plus className="w-3.5 h-3.5 mr-1" />Minta TTD
          </Button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto p-3 sm:p-6 space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari judul / nama penanda tangan…"
            className="pl-9 h-10" data-testid="ttd-cari" />
        </div>

        {loading ? (
          <div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>
        ) : tampil.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <PenTool className="w-10 h-10 mx-auto text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">Belum ada permintaan tanda tangan.</p>
            <p className="text-xs text-muted-foreground">
              Klik <b>Minta TTD</b> — setiap penanda tangan mendapat <b>link pribadi</b> untuk
              menandatangani dari HP/komputernya tanpa akun.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {tampil.map((it) => (
              <button key={it.id} type="button" onClick={() => bukaDetail(it)}
                className="w-full text-left rounded-xl border border-border bg-card p-3 hover:bg-muted/60 transition-colors"
                data-testid={`ttd-item-${it.id}`}>
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-bold truncate">{it.judul}</p>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase flex-shrink-0 ${WARNA_STATUS[it.status] || "bg-muted text-muted-foreground"}`}>
                    {it.status}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1 flex items-center gap-3 flex-wrap">
                  <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" />
                    {it.selesai_jumlah}/{it.jumlah} menandatangani</span>
                  <span>{it.mode === "berurutan" ? "Berurutan" : "Paralel"}</span>
                  <span>{fmtWaktu(it.created_at)}</span>
                  <span className="text-muted-foreground/70">oleh {it.created_by}</span>
                </p>
              </button>
            ))}
          </div>
        )}
      </main>

      {/* ── Dialog buat permintaan ── */}
      <Dialog open={!!form} onOpenChange={(o) => !o && setForm(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Minta Tanda Tangan</DialogTitle>
            <DialogDescription>
              Setiap penanda tangan mendapat link pribadi (berlaku 14 hari, sekali pakai).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-muted-foreground">Judul dokumen *</label>
                <Input value={form.judul} onChange={(e) => setForm({ ...form, judul: e.target.value })}
                  placeholder="mis. BAST Serah Terima Laptop — Subbag Umum" className="h-10 mt-1"
                  data-testid="ttd-form-judul" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Jenis dokumen</label>
                  <select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}
                    className="w-full h-10 mt-1 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="ttd-form-jenis">
                    <option value="dokumen">Dokumen umum</option>
                    <option value="bast">BAST</option>
                    <option value="berita_acara">Berita Acara</option>
                    <option value="laporan">Laporan</option>
                    <option value="surat">Surat</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Urutan tanda tangan</label>
                  <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}
                    className="w-full h-10 mt-1 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="ttd-form-mode">
                    <option value="paralel">Paralel — semua bisa langsung</option>
                    <option value="berurutan">Berurutan — sesuai giliran</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-muted-foreground">Penanda tangan (urut)</label>
                  <Button type="button" variant="outline" size="sm" className="h-7 text-[11px]"
                    onClick={() => setForm((f) => ({ ...f, signers: [...f.signers, { ...SIGNER_KOSONG }] }))}
                    data-testid="ttd-form-tambah-signer">
                    <Plus className="w-3 h-3 mr-1" />Tambah
                  </Button>
                </div>
                {form.signers.map((s, i) => (
                  <div key={i} className="rounded-xl border border-border p-2.5 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded-full bg-blue-600/10 text-blue-600 text-[10px] font-bold flex items-center justify-center flex-shrink-0">{i + 1}</span>
                      <Input value={s.nama} list="ttd-pegawai-list"
                        onChange={(e) => { ubahSigner(i, "nama", e.target.value); isiDariPegawai(i, e.target.value); }}
                        placeholder="Nama lengkap *" className="h-9 text-sm" data-testid={`ttd-form-nama-${i}`} />
                      {form.signers.length > 1 && (
                        <button type="button" aria-label="Hapus penanda tangan"
                          onClick={() => setForm((f) => ({ ...f, signers: f.signers.filter((_, idx) => idx !== i) }))}
                          className="h-9 w-9 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 flex-shrink-0">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-1.5 pl-6">
                      <Input value={s.nip} onChange={(e) => ubahSigner(i, "nip", e.target.value)}
                        placeholder="NIP (opsional)" className="h-8 text-xs" />
                      <Input value={s.jabatan} onChange={(e) => ubahSigner(i, "jabatan", e.target.value)}
                        placeholder="Jabatan (opsional)" className="h-8 text-xs" />
                    </div>
                  </div>
                ))}
                <datalist id="ttd-pegawai-list">
                  {pegawai.map((p) => <option key={p.id} value={p.nama} />)}
                </datalist>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setForm(null)} className="h-9 text-xs">Batal</Button>
            <Button onClick={buat} disabled={saving} className="h-9 text-xs" data-testid="ttd-form-simpan">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Link2 className="w-3.5 h-3.5 mr-1.5" />}
              Buat &amp; Dapatkan Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog hasil (links) ── */}
      <Dialog open={!!hasil} onOpenChange={(o) => !o && setHasil(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BadgeCheck className="w-5 h-5 text-emerald-500" />Link siap dibagikan
            </DialogTitle>
            <DialogDescription>
              Bagikan link di bawah ke MASING-MASING penanda tangan (WA/email). Link bersifat
              pribadi &amp; sekali pakai — jangan tertukar.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-[50vh] overflow-y-auto">
            {(hasil?.links || []).map((l, i) => {
              const penuh = l.link.startsWith("http") ? l.link : `${window.location.origin}${l.link}`;
              return (
                <div key={i} className="rounded-xl border border-border p-2.5 space-y-1.5">
                  <p className="text-xs font-bold">{i + 1}. {l.nama}</p>
                  <div className="flex items-center gap-1.5">
                    <Input readOnly value={penuh} className="h-8 text-[11px] font-mono" onFocus={(e) => e.target.select()} />
                    <Button type="button" variant="outline" size="sm" className="h-8 text-[11px] flex-shrink-0"
                      onClick={() => salin(penuh)} data-testid={`ttd-salin-${i}`}>
                      <Copy className="w-3 h-3 mr-1" />Salin
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button onClick={() => setHasil(null)} className="h-9 text-xs">Selesai</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog detail/status ── */}
      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-6">{detail.judul}</DialogTitle>
                <DialogDescription>
                  {detail.mode === "berurutan" ? "Berurutan" : "Paralel"} · dibuat {fmtWaktu(detail.created_at)} oleh {detail.created_by}
                  {" · "}
                  <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold uppercase ${WARNA_STATUS[detail.status] || ""}`}>{detail.status}</span>
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-2">
                {(detail.signers || []).map((s) => (
                  <div key={s.signer_id} className="rounded-xl border border-border p-2.5 flex items-center gap-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold truncate">{s.urutan}. {s.nama}</p>
                      <p className="text-[11px] text-muted-foreground truncate">
                        {s.jabatan || "-"}{s.nip ? ` · NIP ${s.nip}` : ""}
                        {s.signed_at ? ` · ${fmtWaktu(s.signed_at)}` : ""}
                      </p>
                    </div>
                    {s.status === "ditandatangani" && s.signature_file_id ? (
                      <img alt={`TTD ${s.nama}`}
                        src={`${API}/ttd/tandatangan/${detail.id}/gambar/${s.signer_id}?token=${localStorage.getItem("media_token") || localStorage.getItem("token") || ""}`}
                        className="h-10 max-w-[90px] object-contain bg-white rounded border border-border p-0.5 flex-shrink-0" />
                    ) : null}
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold flex-shrink-0 ${WARNA_SIGNER[s.status] || "bg-muted text-muted-foreground"}`}>
                      {s.status}
                    </span>
                  </div>
                ))}
                <div className="rounded-xl bg-muted/60 p-2.5 text-[11px] text-muted-foreground flex items-start gap-2">
                  <ShieldCheck className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>
                    Verifikasi publik: <button type="button" className="underline font-semibold"
                      onClick={() => salin(linkVerifikasi(detail.id))}>salin link verifikasi</button>{" "}
                    — bisa dipindai dari QR pada Lembar Pengesahan.
                  </span>
                </div>
              </div>
              <DialogFooter className="flex-wrap gap-1.5">
                {detail.status !== "batal" && (
                  <Button variant="outline" onClick={() => batalkan(detail)} className="h-9 text-xs text-red-600">
                    <XCircle className="w-3.5 h-3.5 mr-1.5" />Batalkan
                  </Button>
                )}
                <Button variant="outline" onClick={() => unduhLembar(detail)} className="h-9 text-xs"
                  data-testid="ttd-unduh-lembar">
                  <FileDown className="w-3.5 h-3.5 mr-1.5" />Lembar Pengesahan (PDF)
                </Button>
                <Button onClick={() => setDetail(null)} className="h-9 text-xs">Tutup</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
