import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ArrowLeft, Building2, DatabaseZap, Loader2, Pencil, RefreshCcw, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { useBackGuard } from "@/hooks/useBackGuard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function apiErr(e, fb) { return e?.response?.data?.detail || fb; }

const FORM_KOSONG = {
  kode_satker: "", nama_satker: "", nama_unit_organisasi: "", nama_sub_unit: "",
  alamat: "", tempat_laporan: "", tembusan_laporan: "", telepon: "", email: "",
};

/**
 * Master Satker — satker sebagai entitas kelas satu (multi-satker, DB bersama).
 * Kop laporan per-satker: field yang diisi di sini MENIMPA setelan global
 * untuk semua laporan kegiatan satker ybs. (resolusi kegiatan → satker → global).
 *
 * `SatkerPanel` = isi + logika tanpa header halaman — dipakai halaman ini DAN
 * tab "Per-Satker" pada halaman Pengaturan terpadu.
 */
export function SatkerPanel({ user }) {
  const isAdmin = user?.role === "admin";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sinkron, setSinkron] = useState(false);
  const [backfill, setBackfill] = useState(null); // {kode_sisa, jalan, laporan}
  const [form, setForm] = useState(null);      // profil satker saat dialog edit
  const [saving, setSaving] = useState(false);
  const { confirm, confirmDialog } = useConfirm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/satker`);
      setData(r.data);
    } catch (e) {
      toast.error(apiErr(e, "Gagal memuat master satker"));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const jalankanSinkron = async () => {
    setSinkron(true);
    try {
      const r = await axios.post(`${API}/satker/sinkron`);
      toast.success(r.data?.baru
        ? `${r.data.baru} satker dari kegiatan didaftarkan ke master`
        : "Semua satker kegiatan sudah terdaftar");
      load();
    } catch (e) { toast.error(apiErr(e, "Gagal sinkron")); }
    finally { setSinkron(false); }
  };

  const jalankanBackfill = async () => {
    setBackfill((b) => ({ ...b, jalan: true }));
    try {
      const r = await axios.post(`${API}/satker/backfill`,
        backfill?.kode_sisa ? { kode_satker_sisa: backfill.kode_sisa } : {});
      setBackfill((b) => ({ ...b, jalan: false, laporan: r.data }));
      toast.success(`Backfill selesai — ${r.data.total} dokumen lama terisi kode satker`);
      load();
    } catch (e) {
      toast.error(apiErr(e, "Gagal menjalankan backfill"));
      setBackfill((b) => ({ ...b, jalan: false }));
    }
  };

  const bukaEdit = (it) => setForm({
    ...FORM_KOSONG,
    ...Object.fromEntries(Object.keys(FORM_KOSONG).map((k) => [k, it[k] || ""])),
    _baru: !it.terdaftar,
  });

  const simpan = async () => {
    if (!form.kode_satker.trim() || !form.nama_satker.trim()) {
      toast.error("Kode & nama satker wajib diisi"); return;
    }
    setSaving(true);
    try {
      const { _baru, ...body } = form;
      await axios.put(`${API}/satker/${encodeURIComponent(form.kode_satker.trim())}`, body);
      toast.success(`Profil satker ${form.kode_satker} tersimpan — kop laporan kegiatan satker ini mengikuti`);
      setForm(null);
      load();
    } catch (e) { toast.error(apiErr(e, "Gagal menyimpan satker")); }
    finally { setSaving(false); }
  };

  const hapus = async (it) => {
    const ok = await confirm({
      title: `Hapus satker ${it.kode_satker}?`,
      description: `${it.nama_satker} — hanya bisa dihapus bila tidak dipakai kegiatan.`,
      confirmLabel: "Hapus", variant: "danger",
    });
    if (!ok) return;
    try {
      await axios.delete(`${API}/satker/${encodeURIComponent(it.kode_satker)}`);
      toast.success("Satker dihapus dari master");
      load();
    } catch (e) { toast.error(apiErr(e, "Gagal menghapus")); }
  };

  const items = data?.items || [];

  return (
    <div className="space-y-2.5">
      {isAdmin && (
        <div className="flex items-center justify-end gap-1.5">
          <Button variant="outline" size="sm" className="h-9 text-xs" disabled={sinkron}
            onClick={jalankanSinkron} data-testid="satker-sinkron">
            {sinkron ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <RefreshCcw className="w-3.5 h-3.5 mr-1.5" />}
            Sinkron dari Kegiatan
          </Button>
          <Button variant="outline" size="sm" className="h-9 text-xs"
            title="Isi kode satker pada data lama (dari relasi aset→kegiatan; sisanya opsional ke satu satker)"
            onClick={() => setBackfill({ kode_sisa: "", jalan: false, laporan: null })}
            data-testid="satker-backfill">
            <DatabaseZap className="w-3.5 h-3.5 mr-1.5" />Backfill Data Lama
          </Button>
          <Button size="sm" className="h-9 text-xs" onClick={() => setForm({ ...FORM_KOSONG, _baru: true })}
            data-testid="satker-tambah">
            Tambah
          </Button>
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>
      ) : items.length === 0 ? (
        <div className="py-16 text-center space-y-2">
          <Building2 className="w-10 h-10 mx-auto text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">Belum ada satker.</p>
          <p className="text-xs text-muted-foreground">
            Satker terdaftar OTOMATIS saat kegiatan pertama dibuat, atau klik <b>Sinkron dari Kegiatan</b>.
          </p>
        </div>
      ) : (
        items.map((it) => (
          <div key={it.kode_satker} className="rounded-xl border border-border bg-card p-3 flex items-start gap-3"
            data-testid={`satker-row-${it.kode_satker}`}>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[12px] px-1.5 py-0.5 rounded bg-muted">{it.kode_satker}</span>
                <span className="truncate">{it.nama_satker || <i className="text-muted-foreground">tanpa nama</i>}</span>
                {!it.terdaftar && (
                  <span className="px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 text-[10px] font-bold">
                    belum di master
                  </span>
                )}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {it.jumlah_kegiatan || 0} kegiatan
                {it.alamat ? ` · ${it.alamat}` : ""}
                {it.tempat_laporan ? ` · tempat laporan: ${it.tempat_laporan}` : ""}
              </p>
              {(it.nama_unit_organisasi || it.nama_sub_unit) && (
                <p className="text-[10px] text-muted-foreground mt-0.5 truncate">
                  Kop: {[it.nama_unit_organisasi, it.nama_sub_unit].filter(Boolean).join(" › ")}
                </p>
              )}
            </div>
            {isAdmin && (
              <div className="flex items-center gap-1 flex-shrink-0">
                <button type="button" onClick={() => bukaEdit(it)} aria-label={`Ubah ${it.kode_satker}`}
                  className="h-8 w-8 rounded-lg border border-border flex items-center justify-center hover:bg-muted min-w-0 min-h-0"
                  data-testid={`satker-edit-${it.kode_satker}`}>
                  <Pencil className="w-3.5 h-3.5" />
                </button>
                {it.terdaftar && !it.jumlah_kegiatan && (
                  <button type="button" onClick={() => hapus(it)} aria-label={`Hapus ${it.kode_satker}`}
                    className="h-8 w-8 rounded-lg border border-border text-red-500 flex items-center justify-center hover:bg-red-500/10 min-w-0 min-h-0">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>
        ))
      )}
      <p className="text-center text-[10px] text-muted-foreground pt-1 pb-3">
        Resolusi kop laporan: nilai kegiatan (paling spesifik) → profil satker di sini → Pengaturan global.
        Field kosong = ikut lapisan di atasnya.
      </p>

      {/* ── Dialog backfill data lama ── */}
      <Dialog open={!!backfill} onOpenChange={(o) => !o && setBackfill(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Backfill Kode Satker — Data Lama</DialogTitle>
            <DialogDescription>
              Dokumen lama tanpa kode satker diisi otomatis dari relasi aset→kegiatan.
              Sisanya (persediaan, pengadaan, dsb.) dapat diklaim ke satu satker (opsional).
              Idempoten — hanya mengisi yang kosong.
            </DialogDescription>
          </DialogHeader>
          {backfill && (
            <div className="space-y-2.5">
              <div>
                <label className="text-xs font-semibold text-muted-foreground">
                  Klaim sisa data lama ke satker (opsional)
                </label>
                <select value={backfill.kode_sisa}
                  onChange={(e) => setBackfill({ ...backfill, kode_sisa: e.target.value })}
                  className="w-full h-9 mt-1 rounded-md border border-input bg-background px-3 text-sm"
                  data-testid="backfill-kode-sisa">
                  <option value="">— jangan klaim (hanya dari relasi aset) —</option>
                  {items.filter((s) => s.terdaftar).map((s) => (
                    <option key={s.kode_satker} value={s.kode_satker}>
                      {s.kode_satker} — {s.nama_satker}
                    </option>
                  ))}
                </select>
              </div>
              {backfill.laporan && (
                <div className="rounded-lg bg-muted/60 p-2.5 max-h-44 overflow-y-auto">
                  <p className="text-[11px] font-bold mb-1">
                    Total terisi: {backfill.laporan.total} dokumen
                  </p>
                  {Object.entries(backfill.laporan.per_koleksi || {})
                    .filter(([, n]) => n > 0)
                    .map(([k, n]) => (
                      <p key={k} className="text-[10px] text-muted-foreground">{k}: {n}</p>
                    ))}
                  {backfill.laporan.total === 0 && (
                    <p className="text-[10px] text-muted-foreground">
                      Tidak ada dokumen lama yang perlu diisi.
                    </p>
                  )}
                </div>
              )}
              <div className="flex justify-end gap-1.5">
                <Button variant="outline" size="sm" className="h-9 text-xs"
                  onClick={() => setBackfill(null)}>Tutup</Button>
                <Button size="sm" className="h-9 text-xs" disabled={backfill.jalan}
                  onClick={jalankanBackfill} data-testid="backfill-jalankan">
                  {backfill.jalan ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <DatabaseZap className="w-3.5 h-3.5 mr-1.5" />}
                  Jalankan Backfill
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Dialog profil satker ── */}
      <Dialog open={!!form} onOpenChange={(o) => !o && setForm(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{form?._baru ? "Daftarkan Satker" : `Profil Satker ${form?.kode_satker}`}</DialogTitle>
            <DialogDescription>
              Field kop yang diisi menimpa setelan global untuk laporan satker ini; kosongkan untuk ikut global.
            </DialogDescription>
          </DialogHeader>
          {form && (
            <div className="space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Kode satker *</label>
                  <Input value={form.kode_satker} disabled={!form._baru}
                    onChange={(e) => setForm({ ...form, kode_satker: e.target.value })}
                    placeholder="cth. 527xxx" className="h-9 mt-1 font-mono" data-testid="satker-form-kode" />
                </div>
                <div>
                  <label className="text-xs font-semibold text-muted-foreground">Nama satker *</label>
                  <Input value={form.nama_satker}
                    onChange={(e) => setForm({ ...form, nama_satker: e.target.value })}
                    placeholder="cth. KPKNL Balikpapan" className="h-9 mt-1" data-testid="satker-form-nama" />
                </div>
              </div>
              <div className="rounded-xl border border-border p-2.5 space-y-2">
                <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide">Kop laporan (override global)</p>
                {[["nama_unit_organisasi", "Unit organisasi (baris 2 kop)"],
                  ["nama_sub_unit", "Sub-unit (baris 3 kop — default: nama satker)"],
                  ["alamat", "Alamat"],
                  ["tempat_laporan", "Tempat laporan (kota ttd)"],
                  ["telepon", "Telepon"], ["email", "Email"]].map(([k, label]) => (
                  <div key={k}>
                    <label className="text-xs text-muted-foreground">{label}</label>
                    <Input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                      className="h-9 mt-0.5" data-testid={`satker-form-${k}`} />
                  </div>
                ))}
                <div>
                  <label className="text-xs text-muted-foreground">Tembusan laporan (pisahkan per baris)</label>
                  <textarea value={form.tembusan_laporan}
                    onChange={(e) => setForm({ ...form, tembusan_laporan: e.target.value })}
                    rows={2}
                    className="w-full mt-0.5 rounded-md border border-input bg-background px-3 py-2 text-sm" />
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setForm(null)} className="h-9 text-xs">Batal</Button>
            <Button onClick={simpan} disabled={saving} className="h-9 text-xs" data-testid="satker-form-simpan">
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}Simpan Profil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {confirmDialog}
    </div>
  );
}

export default function SatkerPage({ user, onBack }) {
  useBackGuard(useCallback(() => onBack?.(), [onBack]));
  return (
    <div className="min-h-screen bg-background" data-testid="satker-page">
      <header className="bg-card/95 backdrop-blur-sm border-b border-border px-3 sm:px-6 py-2.5 sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center gap-3">
          <button type="button" onClick={onBack} aria-label="Kembali"
            className="h-9 w-9 rounded-lg border border-border text-foreground/80 flex items-center justify-center hover:bg-muted flex-shrink-0"
            data-testid="satker-back">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="w-9 h-9 rounded-lg bg-emerald-700 flex items-center justify-center flex-shrink-0">
            <Building2 className="w-4 h-4 text-white" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm sm:text-base font-bold text-foreground leading-tight">Master Satker</h1>
            <p className="text-[11px] text-muted-foreground leading-tight truncate">
              Profil & kop per-satker — menimpa setelan global pada laporan satker ybs.
            </p>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto p-3 sm:p-6">
        <SatkerPanel user={user} />
      </main>
    </div>
  );
}
