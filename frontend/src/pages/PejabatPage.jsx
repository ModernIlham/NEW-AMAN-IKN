import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, Users, AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { authMediaUrl } from "@/lib/mediaUrl";
import SignatureCapture from "@/components/ttd/SignatureCapture";
import { PenTool } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

const EMPTY = {
  mode: "tambah", nama: "", nip: "", jabatan: "", pangkat_golongan: "",
  status_kepegawaian: "", unit_kerja: "", no_hp: "", email: "",
  peran: [], jenis_pelaksana: "", unit_akuntansi: "", sk_nomor: "", sk_tanggal: "",
  berlaku_mulai: "", berlaku_selesai: "", aktif: true, keterangan: "",
};

/**
 * Referensi Pejabat Penatausahaan BMN (PMK 181/2016, #290).
 *
 * Semua user login melihat daftar pejabat; admin menambah/mengubah/menghapus.
 * Tiap pejabat punya peran (KPB, Petugas Penatausahaan/Operator SIMAK-BMN, dll.),
 * unit akuntansi, SK penunjukan & masa berlaku — dasar penanda tangan dokumen resmi.
 */
export default function PejabatPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [peranRef, setPeranRef] = useState([]);
  const [statusRef, setStatusRef] = useState([]);
  const [pelaksanaRef, setPelaksanaRef] = useState([]);
  const [unitRef, setUnitRef] = useState([]);
  const [unitList, setUnitList] = useState([]); // Master Unit Kerja (audit W4)
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [ttdUntuk, setTtdUntuk] = useState(null); // pejabat yang dikelola TTD-nya
  const [ttdSaving, setTtdSaving] = useState(false);
  const [saving, setSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const peranUraian = useCallback(
    (kode) => peranRef.find((p) => p.kode === kode)?.uraian || kode, [peranRef]);
  const statusUraian = useCallback(
    (kode) => statusRef.find((s) => s.kode === kode)?.uraian || kode, [statusRef]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/pejabat`);
      setItems(r.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat daftar pejabat"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    axios.get(`${API}/pejabat/referensi`).then((r) => {
      setPeranRef(r.data?.peran || []);
      setStatusRef(r.data?.status_kepegawaian || []);
      setPelaksanaRef(r.data?.jenis_pelaksana || []);
      setUnitRef(r.data?.unit_akuntansi || []);
    }).catch(() => {});
    // Unit kerja dari master (audit W4 #8)
    axios.get(`${API}/unit-kerja`)
      .then((r) => setUnitList([...new Set((r.data?.items || [])
        .map((u) => u.nama_unit || "").filter(Boolean))].sort()))
      .catch(() => setUnitList([]));
  }, [load]);

  const togglePeran = (kode) => setForm((f) => {
    const has = (f.peran || []).includes(kode);
    return { ...f, peran: has ? f.peran.filter((p) => p !== kode) : [...f.peran, kode] };
  });

  const submitForm = async () => {
    if (!form) return;
    if (!(form.nama || "").trim()) { toast.error("Nama pejabat wajib diisi"); return; }
    if (!(form.peran || []).length) { toast.error("Pilih minimal satu peran"); return; }
    setSaving(true);
    const body = {
      nama: form.nama, nip: form.nip, jabatan: form.jabatan,
      pangkat_golongan: form.pangkat_golongan,
      status_kepegawaian: form.status_kepegawaian, unit_kerja: form.unit_kerja,
      no_hp: form.no_hp, email: form.email, peran: form.peran,
      jenis_pelaksana: form.jenis_pelaksana,
      unit_akuntansi: form.unit_akuntansi, sk_nomor: form.sk_nomor,
      sk_tanggal: form.sk_tanggal, berlaku_mulai: form.berlaku_mulai,
      berlaku_selesai: form.berlaku_selesai, aktif: form.aktif,
      keterangan: form.keterangan,
    };
    try {
      if (form.mode === "tambah") {
        await axios.post(`${API}/pejabat`, body);
        toast.success(`Pejabat ${form.nama} ditambahkan`);
      } else {
        await axios.put(`${API}/pejabat/${form.id}`, body);
        toast.success(`Pejabat ${form.nama} diperbarui`);
      }
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan pejabat"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it) => {
    const ok = await confirm({
      title: `Hapus pejabat ${it.nama}?`,
      description: "Data pejabat ini akan dihapus dari referensi penatausahaan.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pejabat/${it.id}`);
      toast.success(`Pejabat ${it.nama} dihapus`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus pejabat"));
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = !q ? items : items.filter((it) =>
    [it.nama, it.nip, it.jabatan, it.unit_kerja, it.email]
      .some((v) => String(v || "").toLowerCase().includes(q)));

  return (
    <div className="min-h-screen bg-background" data-testid="pejabat-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pejabat-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
            <Users className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Referensi Pejabat Penatausahaan</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {items.length} pejabat · KPB, Petugas Penatausahaan/Operator SIMAK, dll. (PMK 181/2016)
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-3 sm:px-6 py-4 space-y-3">
        <div className="bg-card rounded-xl border border-border shadow-sm p-2 sm:p-3">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder="Cari nama / NIP / jabatan / unit kerja / email…" className="pl-9 h-10" data-testid="pejabat-search" />
            </div>
            {isAdmin && (
              <Button className="h-10 gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
                onClick={() => setForm({ ...EMPTY })} title="Tambah Pejabat" aria-label="Tambah Pejabat"
                data-testid="pejabat-add">
                <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah</span>
              </Button>
            )}
          </div>
        </div>

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-indigo-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <Users className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">
                {items.length === 0 ? "Belum ada pejabat" : "Tidak ada yang cocok"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {items.length === 0
                  ? (isAdmin ? "Tambah pejabat penatausahaan (KPB, Operator SIMAK-BMN, PPK, dll.)."
                    : "Minta admin menambah data pejabat penatausahaan.")
                  : "Coba kata kunci lain atau hapus pencarian."}
              </p>
              {isAdmin && items.length === 0 && (
                <Button size="sm" className="mt-3 gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white"
                  onClick={() => setForm({ ...EMPTY })} data-testid="pejabat-empty-tambah">
                  <Plus className="w-4 h-4" />Tambah Pejabat
                </Button>
              )}
              {items.length > 0 && (
                <Button variant="outline" size="sm" className="mt-3"
                  onClick={() => setSearch("")} data-testid="pejabat-clear-search">
                  Hapus pencarian
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Nama / NIP</th>
                    <th className="px-3 py-2.5 font-semibold">Peran</th>
                    <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Berlaku</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`pejabat-row-${it.id}`}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                          {it.nama}
                          {it.status_kepegawaian && (
                            <span title={statusUraian(it.status_kepegawaian)}
                              className="px-1.5 py-0.5 rounded bg-slate-500/15 text-muted-foreground text-[9px] font-semibold uppercase">
                              {statusUraian(it.status_kepegawaian).split(" (")[0]}
                            </span>
                          )}
                          {(it.jenis_pelaksana === "plt" || it.jenis_pelaksana === "plh") && (
                            <span title={it.jenis_pelaksana === "plt" ? "Pelaksana Tugas (jabatan definitif lowong)" : "Pelaksana Harian (pejabat definitif berhalangan sementara)"}
                              className="px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[9px] font-semibold uppercase">
                              {it.jenis_pelaksana === "plt" ? "Plt." : "Plh."}
                            </span>
                          )}
                        </p>
                        <p className="text-[11px] text-muted-foreground">
                          {(it.jenis_pelaksana === "plt" ? "Plt. " : it.jenis_pelaksana === "plh" ? "Plh. " : "")}
                          {it.jabatan || "—"}{it.nip ? ` · NIP ${it.nip}` : ""}
                        </p>
                        {it.unit_kerja && (
                          <p className="text-[10px] text-muted-foreground/80 truncate max-w-[160px] sm:max-w-[240px]" title={it.unit_kerja}>{it.unit_kerja}</p>
                        )}
                        {(it.berlaku_mulai || it.berlaku_selesai) && (
                          <p className="sm:hidden text-[10px] text-muted-foreground truncate">
                            Berlaku {it.berlaku_mulai || "…"} – {it.berlaku_selesai || "kini"}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {(it.peran || []).map((p) => (
                            <span key={p} title={peranUraian(p)}
                              className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 text-[10px] font-semibold">
                              {peranUraian(p).split(" — ")[0].split(" / ")[0]}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground whitespace-nowrap hidden sm:table-cell">
                        {it.berlaku_mulai || "…"} – {it.berlaku_selesai || "kini"}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        {(() => {
                          // Masa berlaku lewat = KEDALUWARSA (amber) — badge
                          // "Aktif" hijau pada pejabat kedaluwarsa menyesatkan
                          // dasar penanda tangan dokumen resmi.
                          const selesai = String(it.berlaku_selesai || "").slice(0, 10);
                          const habis = it.aktif !== false && selesai &&
                            selesai < new Date().toISOString().slice(0, 10);
                          const cls = it.aktif === false
                            ? "bg-slate-500/15 text-muted-foreground"
                            : habis
                              ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                              : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400";
                          const label = it.aktif === false ? "Nonaktif"
                            : habis ? "Kedaluwarsa" : "Aktif";
                          return (
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}
                              title={habis ? `Masa berlaku berakhir ${selesai} — perbarui SK/periode` : undefined}>
                              {label}
                            </span>
                          );
                        })()}
                      </td>
                      {isAdmin && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button type="button" onClick={() => setTtdUntuk(it)}
                            aria-label={`Kelola tanda tangan ${it.nama}`}
                            title={it.ttd_file_id ? "TTD digital tersimpan — kelola" : "Tambah tanda tangan digital"}
                            className={`p-1.5 rounded-md hover:bg-muted min-w-0 min-h-0 ${it.ttd_file_id ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground hover:text-foreground"}`}
                            data-testid={`pejabat-ttd-${it.id}`}>
                            <PenTool className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => setForm({ ...EMPTY, ...it, mode: "edit" })}
                            aria-label={`Ubah ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`pejabat-edit-${it.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            aria-label={`Hapus ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`pejabat-delete-${it.id}`}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* ── Dialog tambah / edit ── */}
      <Dialog open={!!form} onOpenChange={(o) => { if (!o) setForm(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Pejabat" : `Ubah Pejabat — ${form?.nama}`}</DialogTitle>
            <DialogDescription className="text-xs">
              Peran & masa berlaku menentukan penanda tangan dokumen resmi (KIB/BAST/LBKP) pada tanggalnya.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Nama *"><Input value={form.nama} onChange={(e) => setForm((f) => ({ ...f, nama: e.target.value }))} data-testid="pejabat-form-nama" /></Field>
                <Field label="NIP / NRP"><Input value={form.nip} onChange={(e) => setForm((f) => ({ ...f, nip: e.target.value }))} className="font-mono" /></Field>
                <Field label="Jabatan"><Input value={form.jabatan} onChange={(e) => setForm((f) => ({ ...f, jabatan: e.target.value }))} /></Field>
                <Field label="Pangkat / Golongan"><Input value={form.pangkat_golongan} onChange={(e) => setForm((f) => ({ ...f, pangkat_golongan: e.target.value }))} placeholder="cth. Penata (III/c)" /></Field>
                <Field label="Status Kepegawaian">
                  <select value={form.status_kepegawaian}
                    onChange={(e) => setForm((f) => ({ ...f, status_kepegawaian: e.target.value }))}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="pejabat-form-status">
                    <option value="">— pilih —</option>
                    {statusRef.map((s) => <option key={s.kode} value={s.kode}>{s.uraian}</option>)}
                  </select>
                </Field>
                <Field label="Unit Kerja">
                  {/* Terhubung Master Unit Kerja (audit W4 #8) */}
                  <Input value={form.unit_kerja} list="pejabat-unit-list" onChange={(e) => setForm((f) => ({ ...f, unit_kerja: e.target.value }))} placeholder="cth. Bagian Umum" />
                  <datalist id="pejabat-unit-list">
                    {unitList.map((u) => <option key={u} value={u} />)}
                  </datalist>
                </Field>
                <Field label="No. HP"><Input value={form.no_hp} onChange={(e) => setForm((f) => ({ ...f, no_hp: e.target.value }))} inputMode="tel" placeholder="cth. 0812…" /></Field>
                <Field label="Email"><Input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} placeholder="nama@instansi.go.id" data-testid="pejabat-form-email" /></Field>
              </div>

              <Field label="Peran *">
                <div className="flex flex-wrap gap-1.5">
                  {peranRef.map((p) => {
                    const on = (form.peran || []).includes(p.kode);
                    const bmd = p.domain === "bmd";
                    return (
                      <button key={p.kode} type="button" onClick={() => togglePeran(p.kode)} title={p.keterangan || ""}
                        className={`px-2.5 h-8 rounded-full border text-[11px] font-medium min-w-0 min-h-0 transition-colors ${
                          on ? "bg-indigo-600 border-indigo-600 text-white"
                            : bmd ? "border-amber-500/50 text-amber-600 dark:text-amber-400 hover:bg-amber-500/10"
                            : "border-border text-muted-foreground hover:bg-muted"}`}
                        data-testid={`pejabat-peran-${p.kode}`}>
                        {bmd && <AlertTriangle className="w-3 h-3 inline mr-0.5 align-[-1px]" />}{p.uraian.split(" — ")[0].split(" / ")[0]}
                      </button>
                    );
                  })}
                </div>
                {/* Penjelasan peran terpilih — menjawab beda tiap peran &
                    menandai istilah Barang Milik DAERAH agar tak salah pakai. */}
                {(form.peran || []).length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {(form.peran || []).map((kode) => {
                      const p = peranRef.find((x) => x.kode === kode);
                      if (!p?.keterangan) return null;
                      return (
                        <li key={kode} className={`text-[10.5px] leading-snug rounded-md px-2 py-1 ${
                          p.domain === "bmd" ? "bg-amber-500/10 text-amber-700 dark:text-amber-300"
                            : "bg-muted text-muted-foreground"}`}>
                          <span className="font-semibold">{p.uraian.split(" — ")[0].split(" (istilah")[0]}:</span>{" "}
                          {p.keterangan}
                          {p.ttd_bast && p.ttd_bast !== "tidak" && (
                            <span className="ml-1 font-medium">· BAST: {p.ttd_bast}</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Field>

              <Field label="Rangkap Jabatan Struktural (Plt/Plh)">
                <select value={form.jenis_pelaksana || ""}
                  onChange={(e) => setForm((f) => ({ ...f, jenis_pelaksana: e.target.value }))}
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                  data-testid="pejabat-form-pelaksana">
                  <option value="">Pejabat definitif (bukan Plt/Plh)</option>
                  {pelaksanaRef.map((p) => <option key={p.kode} value={p.kode}>{p.uraian}</option>)}
                </select>
                {form.jenis_pelaksana && (
                  <p className="mt-1 text-[10.5px] leading-snug rounded-md px-2 py-1 bg-amber-500/10 text-amber-700 dark:text-amber-300">
                    Tanda tangan dokumen memakai awalan{" "}
                    <span className="font-semibold">{form.jenis_pelaksana === "plt" ? "“Plt.”" : "“Plh.”"}</span>{" "}
                    di depan jabatan ({form.jabatan || "Kuasa Pengguna Barang"}), dengan nama & NIP pejabat pelaksana sendiri.
                    Isi masa berlaku SK Plt/Plh di bawah agar berakhir otomatis.
                  </p>
                )}
              </Field>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field label="Unit Akuntansi">
                  <select value={form.unit_akuntansi}
                    onChange={(e) => setForm((f) => ({ ...f, unit_akuntansi: e.target.value }))}
                    className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="pejabat-form-unit">
                    <option value="">— pilih —</option>
                    {unitRef.map((u) => <option key={u.kode} value={u.kode}>{u.kode.toUpperCase()} — {u.uraian}</option>)}
                  </select>
                </Field>
                <Field label="Status">
                  <label className="flex items-center gap-2 h-10">
                    <input type="checkbox" checked={form.aktif !== false}
                      onChange={(e) => setForm((f) => ({ ...f, aktif: e.target.checked }))}
                      className="w-4 h-4" data-testid="pejabat-form-aktif" />
                    <span className="text-sm text-foreground">Aktif</span>
                  </label>
                </Field>
                <Field label="No. SK Penunjukan"><Input value={form.sk_nomor} onChange={(e) => setForm((f) => ({ ...f, sk_nomor: e.target.value }))} /></Field>
                <Field label="Tgl SK"><Input type="date" value={form.sk_tanggal} onChange={(e) => setForm((f) => ({ ...f, sk_tanggal: e.target.value }))} /></Field>
                <Field label="Berlaku Mulai"><Input type="date" value={form.berlaku_mulai} onChange={(e) => setForm((f) => ({ ...f, berlaku_mulai: e.target.value }))} /></Field>
                <Field label="Berlaku Selesai"><Input type="date" value={form.berlaku_selesai} onChange={(e) => setForm((f) => ({ ...f, berlaku_selesai: e.target.value }))} /></Field>
              </div>
              <Field label="Keterangan"><Input value={form.keterangan} onChange={(e) => setForm((f) => ({ ...f, keterangan: e.target.value }))} /></Field>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="pejabat-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog Kelola Tanda Tangan Digital ── */}
      <Dialog open={!!ttdUntuk} onOpenChange={(o) => { if (!o) setTtdUntuk(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Tanda Tangan Digital — {ttdUntuk?.nama}</DialogTitle>
            <DialogDescription className="text-xs">
              Spesimen ini otomatis tersemat pada blok tanda tangan laporan/BA yang ditandatangani pejabat ini (mis. KPB pada DBKP/LBKP/BAST).
            </DialogDescription>
          </DialogHeader>
          {ttdUntuk?.ttd_file_id && (
            <div className="rounded-lg border border-border p-2 flex items-center justify-between gap-2 bg-muted/40">
              <img src={authMediaUrl(`${API}/ttd/spesimen/pejabat/${ttdUntuk.id}`)}
                alt="TTD tersimpan" className="max-h-16 bg-white rounded px-1" data-testid="pejabat-ttd-thumb" />
              <Button variant="outline" size="sm" className="h-8 text-xs text-red-500 hover:text-red-600"
                onClick={async () => {
                  try {
                    await axios.delete(`${API}/ttd/spesimen/pejabat/${ttdUntuk.id}`);
                    toast.success("Spesimen TTD dihapus");
                    setTtdUntuk(null); load();
                  } catch (e) { toast.error(e?.response?.data?.detail || "Gagal menghapus"); }
                }}>Hapus TTD</Button>
            </div>
          )}
          {ttdUntuk && (
            <SignatureCapture saving={ttdSaving} onSave={async (png) => {
              setTtdSaving(true);
              try {
                await axios.put(`${API}/ttd/spesimen/pejabat/${ttdUntuk.id}`, { png_base64: png });
                toast.success("Tanda tangan tersimpan");
                setTtdUntuk(null); load();
              } catch (e) {
                toast.error(e?.response?.data?.detail || "Gagal menyimpan tanda tangan");
              } finally { setTtdSaving(false); }
            }} />
          )}
        </DialogContent>
      </Dialog>
      {confirmDialog}
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
