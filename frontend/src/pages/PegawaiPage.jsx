import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Search, Plus, Pencil, Trash2, Loader2, IdCard, Upload, Download,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";
import { downloadFileWithProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function getApiError(err, fallback) {
  return err?.response?.data?.detail || fallback;
}

const EMPTY = {
  mode: "tambah", nama: "", nip: "", gelar_depan: "", gelar_belakang: "",
  jenis_kelamin: "", tempat_lahir: "", tanggal_lahir: "", agama: "",
  status_perkawinan: "", status_kepegawaian: "", sub_kategori_non_asn: "",
  pangkat_golongan: "", jabatan: "", jenis_jabatan: "", kategori_pegawai: "",
  eselon: "", eselon1: "", eselon2: "", eselon3: "", eselon4: "", eselon5: "",
  unit_kerja: "", unit_organisasi: "", npwp: "", pendidikan_terakhir: "",
  no_hp: "", email: "", alamat: "", nama_bank: "", no_rekening: "",
  nomor_kontrak: "", tgl_mulai_kontrak: "", tgl_selesai_kontrak: "",
  tmt_jabatan: "", status: "aktif", keterangan: "",
};

// Status kontrak Non-ASN utk badge (pemegang aset berisiko saat kontrak habis).
function statusKontrak(p) {
  const sel = String(p.tgl_selesai_kontrak || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(sel)) return null;
  const sisa = Math.ceil((new Date(sel) - new Date()) / 86400000);
  if (sisa < 0) return { habis: true, teks: `Kontrak berakhir ${Math.abs(sisa)} hari lalu` };
  if (sisa <= 30) return { segera: true, teks: `Kontrak berakhir dalam ${sisa} hari` };
  return null;
}

// Nama + gelar untuk tampilan (samakan dengan nama_lengkap di backend).
function namaLengkap(p) {
  const depan = (p.gelar_depan || "").trim();
  const belakang = (p.gelar_belakang || "").trim();
  let out = `${depan} ${(p.nama || "").trim()}`.trim();
  if (belakang) out = `${out}, ${belakang}`;
  return out;
}

/**
 * Master Pegawai (data kepegawaian menyeluruh satker, adopsi SIMAN-G).
 *
 * Berbeda dari Referensi Pejabat (khusus penanda tangan/penatausahaan):
 * halaman ini menampung SELURUH pegawai + unit kerjanya sebagai rujukan
 * lintas modul. Semua user login melihat; admin mengelola (CRUD).
 */
export default function PegawaiPage({ user, onBack }) {
  const isAdmin = user?.role === "admin";
  const [items, setItems] = useState([]);
  const [rekap, setRekap] = useState(null);
  const [ref, setRef] = useState({ jenis_kelamin: [], status_kepegawaian: [], jenis_jabatan: [], kategori_pegawai: [], sub_kategori_non_asn: [], agama: [], status_perkawinan: [], status: [] });
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [mengimpor, setMengimpor] = useState(false);
  const [hasilImpor, setHasilImpor] = useState(null);
  const fileRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  useBackGuard(useCallback(() => onBack?.(), [onBack]));

  const uraian = useCallback((list, kode) => (ref[list] || []).find((o) => o.kode === kode)?.uraian || kode, [ref]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/pegawai`);
      setItems(r.data?.items || []);
    } catch (err) {
      toast.error(getApiError(err, "Gagal memuat daftar pegawai"));
    } finally {
      setLoading(false);
    }
    // Rekap per unit kerja (ringkasan adopsi SIMAN-G) — best-effort.
    axios.get(`${API}/pegawai/rekap-unit`)
      .then((r) => setRekap(r.data))
      .catch(() => setRekap(null));
  }, []);

  useEffect(() => {
    load();
    axios.get(`${API}/pegawai/referensi`).then((r) => setRef({
      jenis_kelamin: r.data?.jenis_kelamin || [],
      status_kepegawaian: r.data?.status_kepegawaian || [],
      jenis_jabatan: r.data?.jenis_jabatan || [],
      kategori_pegawai: r.data?.kategori_pegawai || [],
      sub_kategori_non_asn: r.data?.sub_kategori_non_asn || [],
      agama: r.data?.agama || [],
      status_perkawinan: r.data?.status_perkawinan || [],
      status: r.data?.status || [],
    })).catch(() => {});
  }, [load]);

  const unduhTemplate = () => {
    downloadFileWithProgress(`${API}/pegawai/template-impor`, "template_impor_pegawai.csv",
      { label: "Template Impor Pegawai (CSV)" }).catch(() => {});
  };

  const pilihBerkas = () => fileRef.current?.click();

  const onBerkasDipilih = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // reset agar file sama bisa dipilih ulang
    if (!file) return;
    setMengimpor(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/pegawai/impor`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setHasilImpor(r.data);
      toast.success(`Impor selesai: ${r.data.dibuat} baru, ${r.data.diperbarui} diperbarui`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal mengimpor pegawai"));
    } finally {
      setMengimpor(false);
    }
  };

  const submitForm = async () => {
    if (!form) return;
    if (!(form.nama || "").trim()) { toast.error("Nama pegawai wajib diisi"); return; }
    setSaving(true);
    const body = { ...form };
    delete body.mode; delete body.id; delete body.created_at; delete body.updated_at;
    try {
      if (form.mode === "tambah") {
        await axios.post(`${API}/pegawai`, body);
        toast.success(`Pegawai ${form.nama} ditambahkan`);
      } else {
        await axios.put(`${API}/pegawai/${form.id}`, body);
        toast.success(`Pegawai ${form.nama} diperbarui`);
      }
      setForm(null);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menyimpan pegawai"));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (it) => {
    const ok = await confirm({
      title: `Hapus pegawai ${it.nama}?`,
      description: "Data pegawai ini akan dihapus dari master pegawai.",
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/pegawai/${it.id}`);
      toast.success(`Pegawai ${it.nama} dihapus`);
      load();
    } catch (err) {
      toast.error(getApiError(err, "Gagal menghapus pegawai"));
    }
  };

  const q = search.trim().toLowerCase();
  const filtered = useMemo(() => (!q ? items : items.filter((it) =>
    [it.nama, it.nip, it.jabatan, it.unit_kerja, it.email]
      .some((v) => String(v || "").toLowerCase().includes(q)))), [items, q]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="min-h-screen bg-background" data-testid="pegawai-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali ke Beranda Modul"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="pegawai-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-sky-600 flex items-center justify-center flex-shrink-0">
            <IdCard className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Master Pegawai</h1>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {items.length} pegawai · data kepegawaian menyeluruh &amp; unit kerja (adopsi SIMAN-G)
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
                placeholder="Cari nama / NIP / jabatan / unit kerja / email…" className="pl-9 h-10" data-testid="pegawai-search" />
            </div>
            {isAdmin && (
              <>
                <input ref={fileRef} type="file" accept=".xlsx,.xlsm,.csv" className="hidden"
                  onChange={onBerkasDipilih} data-testid="pegawai-impor-file" />
                <Button variant="outline" className="h-10 gap-1.5" onClick={unduhTemplate}
                  data-testid="pegawai-template">
                  <Download className="w-4 h-4" /><span className="hidden sm:inline">Template</span>
                </Button>
                <Button variant="outline" className="h-10 gap-1.5" disabled={mengimpor}
                  onClick={pilihBerkas} data-testid="pegawai-impor">
                  {mengimpor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  <span className="hidden sm:inline">Impor Excel</span>
                </Button>
                <Button variant="outline" className="h-10 gap-1.5"
                  onClick={() => setForm({ ...EMPTY })} data-testid="pegawai-add">
                  <Plus className="w-4 h-4" /><span className="hidden sm:inline">Tambah</span>
                </Button>
              </>
            )}
          </div>
        </div>

        {rekap && (rekap.unit || []).length > 0 && (
          <div className="bg-card rounded-xl border border-border shadow-sm p-2.5 sm:p-3" data-testid="pegawai-rekap-unit">
            <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground mb-2">
              Rekap per Unit Kerja — {rekap.jumlah_unit} unit · {rekap.jumlah_pegawai} pegawai
            </p>
            <div className="flex flex-wrap gap-1.5">
              {rekap.unit.map((u) => {
                const tanpaUnit = u.unit_kerja === "(unit kerja belum dicatat)";
                return (
                  <button key={u.unit_kerja} type="button"
                    onClick={() => !tanpaUnit && setSearch(search === u.unit_kerja ? "" : u.unit_kerja)}
                    disabled={tanpaUnit}
                    className={`px-2 py-1 rounded-full border text-[11px] min-w-0 min-h-0 ${
                      search === u.unit_kerja
                        ? "border-sky-500 bg-sky-500/15 text-sky-600 dark:text-sky-400 font-semibold"
                        : tanpaUnit
                          ? "border-border/60 text-muted-foreground/70 cursor-default"
                          : "border-border text-foreground/80 hover:bg-muted"}`}
                    data-testid={`pegawai-rekap-chip-${u.unit_kerja}`}>
                    {u.unit_kerja} <span className="font-bold">{u.jumlah}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 px-4">
              <IdCard className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm font-medium text-foreground">
                {items.length === 0 ? "Belum ada pegawai" : "Tidak ada yang cocok"}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {isAdmin ? "Tambah data pegawai satker (seluruh pegawai & unit kerjanya)."
                  : "Minta admin menambah data pegawai."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                    <th className="px-3 py-2.5 font-semibold">Nama / NIP</th>
                    <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Jabatan / Unit Kerja</th>
                    <th className="px-3 py-2.5 font-semibold">Status</th>
                    {isAdmin && <th className="px-3 py-2.5 font-semibold text-right">Aksi</th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id} className="border-b border-border/60 last:border-0 hover:bg-muted/50" data-testid={`pegawai-row-${it.id}`}>
                      <td className="px-3 py-2">
                        <p className="font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
                          {namaLengkap(it)}
                          {it.status_kepegawaian && (
                            <span className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-600 dark:text-sky-400 text-[9px] font-semibold uppercase">
                              {uraian("status_kepegawaian", it.status_kepegawaian).split(" (")[0]}
                            </span>
                          )}
                          {(() => {
                            const k = statusKontrak(it);
                            if (!k) return null;
                            return (
                              <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-semibold ${k.habis ? "bg-red-500/15 text-red-600 dark:text-red-400" : "bg-amber-500/15 text-amber-600 dark:text-amber-400"}`}
                                title={k.teks}>
                                <AlertTriangle className="w-2.5 h-2.5" />{k.teks}
                              </span>
                            );
                          })()}
                        </p>
                        <p className="text-[11px] text-muted-foreground font-mono">{it.nip || "—"}</p>
                      </td>
                      <td className="px-3 py-2 hidden sm:table-cell">
                        <p className="text-[12px] text-foreground/90">{it.jabatan || "—"}</p>
                        <p className="text-[10px] text-muted-foreground/80">{it.unit_kerja || ""}</p>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          (it.status || "aktif") === "aktif"
                            ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                            : "bg-slate-500/15 text-muted-foreground"}`}>
                          {uraian("status", it.status || "aktif")}
                        </span>
                      </td>
                      {isAdmin && (
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          <button type="button" onClick={() => setForm({ ...EMPTY, ...it, mode: "edit" })}
                            aria-label={`Ubah ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted min-w-0 min-h-0"
                            data-testid={`pegawai-edit-${it.id}`}>
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button type="button" onClick={() => remove(it)}
                            aria-label={`Hapus ${it.nama}`}
                            className="p-1.5 rounded-md text-muted-foreground hover:text-red-600 hover:bg-red-500/10 min-w-0 min-h-0"
                            data-testid={`pegawai-delete-${it.id}`}>
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
        <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?.mode === "tambah" ? "Tambah Pegawai" : `Ubah Pegawai — ${form?.nama}`}</DialogTitle>
            <DialogDescription className="text-xs">
              Data kepegawaian menyeluruh — dipakai sebagai rujukan lintas modul (pemegang barang, penanggung jawab ruangan, dll.).
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-4">
              <Group title="Identitas">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <Field label="Gelar Depan"><Input value={form.gelar_depan} onChange={set("gelar_depan")} placeholder="cth. Dr." /></Field>
                  <Field label="Nama *" span2><Input value={form.nama} onChange={set("nama")} data-testid="pegawai-form-nama" /></Field>
                  <Field label="Gelar Belakang"><Input value={form.gelar_belakang} onChange={set("gelar_belakang")} placeholder="cth. S.E." /></Field>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="NIP / NRP"><Input value={form.nip} onChange={set("nip")} className="font-mono" inputMode="numeric" placeholder="18 digit (opsional)" data-testid="pegawai-form-nip" /></Field>
                  <Field label="NPWP"><Input value={form.npwp} onChange={set("npwp")} className="font-mono" /></Field>
                  <Field label="Jenis Kelamin">
                    <Select value={form.jenis_kelamin} onChange={set("jenis_kelamin")} data-testid="pegawai-form-jk" opts={ref.jenis_kelamin} />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Tempat Lahir"><Input value={form.tempat_lahir} onChange={set("tempat_lahir")} /></Field>
                    <Field label="Tgl Lahir"><Input type="date" value={form.tanggal_lahir} onChange={set("tanggal_lahir")} /></Field>
                  </div>
                </div>
              </Group>

              <Group title="Kepegawaian">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Status Kepegawaian">
                    <Select value={form.status_kepegawaian} onChange={set("status_kepegawaian")} data-testid="pegawai-form-status-peg" opts={ref.status_kepegawaian} />
                  </Field>
                  <Field label="Pangkat / Golongan"><Input value={form.pangkat_golongan} onChange={set("pangkat_golongan")} placeholder="cth. Penata (III/c)" /></Field>
                  {form.status_kepegawaian === "non_asn" && (
                    <Field label="Sub-Kategori Non-ASN">
                      <Select value={form.sub_kategori_non_asn} onChange={set("sub_kategori_non_asn")} opts={ref.sub_kategori_non_asn} />
                    </Field>
                  )}
                  <Field label="Jenis Jabatan">
                    <Select value={form.jenis_jabatan} onChange={set("jenis_jabatan")} opts={ref.jenis_jabatan} />
                  </Field>
                  <Field label="Kategori Pegawai (UU ASN)">
                    <Select value={form.kategori_pegawai} onChange={set("kategori_pegawai")} opts={ref.kategori_pegawai} />
                  </Field>
                  <Field label="Eselon (teks)"><Input value={form.eselon} onChange={set("eselon")} placeholder="cth. IV.a" /></Field>
                  <Field label="Status di Satker">
                    <Select value={form.status} onChange={set("status")} data-testid="pegawai-form-status" opts={ref.status} allowEmpty={false} />
                  </Field>
                  <Field label="TMT Jabatan"><Input type="date" value={form.tmt_jabatan} onChange={set("tmt_jabatan")} /></Field>
                </div>
                {/* Kontrak Non-ASN — pemantauan pemegang aset saat kontrak berakhir. */}
                {form.status_kepegawaian === "non_asn" && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-2.5 rounded-lg bg-muted/40 border border-border/60">
                    <Field label="Nomor Kontrak"><Input value={form.nomor_kontrak} onChange={set("nomor_kontrak")} placeholder="cth. 001/KONTRAK/2026" /></Field>
                    <Field label="Mulai Kontrak"><Input type="date" value={form.tgl_mulai_kontrak} onChange={set("tgl_mulai_kontrak")} /></Field>
                    <Field label="Selesai Kontrak"><Input type="date" value={form.tgl_selesai_kontrak} onChange={set("tgl_selesai_kontrak")} /></Field>
                  </div>
                )}
              </Group>

              <Group title="Jabatan & Unit Kerja">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Jabatan" span2><Input value={form.jabatan} onChange={set("jabatan")} placeholder="cth. Analis Pengelolaan BMN" /></Field>
                </div>
                {/* Unit kerja berjenjang (Eselon I–V) — bila diisi, jenjang
                    terdalam otomatis menjadi Unit Kerja efektif di server. */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Eselon 1"><Input value={form.eselon1} onChange={set("eselon1")} placeholder="cth. Kedeputian / Sekretariat" data-testid="pegawai-form-eselon1" /></Field>
                  <Field label="Eselon 2"><Input value={form.eselon2} onChange={set("eselon2")} placeholder="cth. Direktorat / Biro" /></Field>
                  <Field label="Eselon 3"><Input value={form.eselon3} onChange={set("eselon3")} placeholder="cth. Bagian / Subdirektorat" /></Field>
                  <Field label="Eselon 4"><Input value={form.eselon4} onChange={set("eselon4")} placeholder="cth. Subbagian / Seksi" /></Field>
                  <Field label="Eselon 5"><Input value={form.eselon5} onChange={set("eselon5")} /></Field>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="Unit Kerja (ringkas)"><Input value={form.unit_kerja} onChange={set("unit_kerja")} placeholder="otomatis dari Eselon terdalam bila kosong" data-testid="pegawai-form-unit" /></Field>
                  <Field label="Unit Organisasi / Satker"><Input value={form.unit_organisasi} onChange={set("unit_organisasi")} /></Field>
                </div>
              </Group>

              <Group title="Kontak, Bank & Lainnya">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <Field label="No. HP"><Input value={form.no_hp} onChange={set("no_hp")} inputMode="tel" placeholder="cth. 0812…" /></Field>
                  <Field label="Email"><Input type="email" value={form.email} onChange={set("email")} placeholder="nama@instansi.go.id" data-testid="pegawai-form-email" /></Field>
                  <Field label="Agama">
                    <Select value={form.agama} onChange={set("agama")} opts={ref.agama} />
                  </Field>
                  <Field label="Status Perkawinan">
                    <Select value={form.status_perkawinan} onChange={set("status_perkawinan")} opts={ref.status_perkawinan} />
                  </Field>
                  <Field label="Pendidikan Terakhir"><Input value={form.pendidikan_terakhir} onChange={set("pendidikan_terakhir")} placeholder="cth. S1 Akuntansi" /></Field>
                  <Field label="Alamat"><Input value={form.alamat} onChange={set("alamat")} /></Field>
                  <Field label="Nama Bank"><Input value={form.nama_bank} onChange={set("nama_bank")} placeholder="cth. BRI" /></Field>
                  <Field label="No. Rekening"><Input value={form.no_rekening} onChange={set("no_rekening")} className="font-mono" inputMode="numeric" /></Field>
                </div>
                <Field label="Keterangan"><Input value={form.keterangan} onChange={set("keterangan")} /></Field>
              </Group>
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submitForm} disabled={saving} data-testid="pegawai-form-save">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : null}Simpan
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog hasil impor ── */}
      <Dialog open={!!hasilImpor} onOpenChange={(o) => { if (!o) setHasilImpor(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Hasil Impor Pegawai</DialogTitle>
            <DialogDescription className="text-xs">
              Baris dinormalkan otomatis (status kepegawaian &amp; status keberadaan dipetakan, NIP dibersihkan, unit kerja dari Eselon terdalam).
            </DialogDescription>
          </DialogHeader>
          {hasilImpor && (
            <div className="space-y-3">
              <div className="grid grid-cols-4 gap-2 text-center">
                {[["Dibaca", hasilImpor.dibaca, "text-foreground"],
                  ["Baru", hasilImpor.dibuat, "text-emerald-600 dark:text-emerald-400"],
                  ["Diperbarui", hasilImpor.diperbarui, "text-sky-600 dark:text-sky-400"],
                  ["Dilewati", hasilImpor.dilewati, "text-amber-600 dark:text-amber-400"]].map(([l, v, c]) => (
                  <div key={l} className="rounded-lg border border-border p-2">
                    <p className={`text-lg font-bold ${c}`}>{v}</p>
                    <p className="text-[10px] text-muted-foreground">{l}</p>
                  </div>
                ))}
              </div>
              {(hasilImpor.catatan || []).length > 0 && (
                <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-2.5">
                  <p className="text-[11px] font-bold text-amber-700 dark:text-amber-400 mb-1">
                    Catatan ({hasilImpor.catatan.length} baris dilewati):
                  </p>
                  <ul className="text-[10px] text-muted-foreground space-y-0.5 max-h-40 overflow-y-auto">
                    {hasilImpor.catatan.map((c, i) => <li key={i}>• {c}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setHasilImpor(null)}>Tutup</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}

function Group({ title, children }) {
  return (
    <div className="space-y-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border/60 pb-1">{title}</p>
      {children}
    </div>
  );
}

function Field({ label, children, span2 }) {
  return (
    <div className={span2 ? "col-span-2" : ""}>
      <label className="text-xs font-medium text-foreground block mb-1">{label}</label>
      {children}
    </div>
  );
}

function Select({ value, onChange, opts, allowEmpty = true, ...rest }) {
  return (
    <select value={value} onChange={onChange}
      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm" {...rest}>
      {allowEmpty && <option value="">— pilih —</option>}
      {(opts || []).map((o) => <option key={o.kode} value={o.kode}>{o.uraian}</option>)}
    </select>
  );
}
