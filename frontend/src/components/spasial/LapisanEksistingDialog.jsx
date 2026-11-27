// Kelola LAPISAN EKSISTING — dialog admin di halaman Hierarki Spasial.
//
// Citra: pilih berkas GeoTIFF → lokasi, batas, dan zoom terbaca otomatis →
// peramban memotongnya jadi ubin WGS84/Web Mercator dan mengunggahnya.
// Gambar: titik/garis/area yang digambar langsung di peta (EditorGambarPeta).
// Urutan: tombol naik/turun per jenis; gambar selalu di atas citra.
import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  ChevronDown, ChevronUp, Image as IkonGambar, Loader2, PenLine, Pencil, Plus, Satellite,
  Trash2, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { formatTanggalCitra, lupakanDaftarCitra } from "@/lib/lapisanCitra";

const EditorGambarPeta = lazy(() => import("./EditorGambarPeta"));

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const hariIni = () => new Date().toISOString().slice(0, 10);
const namaDariBerkas = (n) => String(n || "").replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim().slice(0, 120);
const ukuranMb = (b) => (b / 1024 / 1024).toLocaleString("id-ID", { maximumFractionDigits: 1 });

/** Body PUT dari item daftar (bidang yang boleh diubah per jenis). */
function bodyUbah(l, ubah = {}) {
  const dasar = l.jenis === "citra"
    ? { jenis: "citra", nama: l.nama, sumber: l.sumber || "", tanggal_rekam: l.tanggal_rekam, opasitas: l.opasitas, aktif: l.aktif }
    : { jenis: "gambar", nama: l.nama, fitur: l.fitur || [], label_zoom_min: l.label_zoom_min, aktif: l.aktif };
  return { ...dasar, ...ubah, version: l.version };
}

function BarisLapisan({ l, pertama, terakhir, onNaik, onTurun, onAktif, onUbah, onHapus }) {
  const memproses = l.jenis === "citra" && l.status === "memproses";
  const info = l.jenis === "citra"
    ? (memproses ? "Unggahan belum selesai" : `${formatTanggalCitra(l.tanggal_rekam)} · ${ukuranMb(l.ukuran_byte || 0)} MB`)
    : `${(l.fitur || []).length} objek`;
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border px-2 py-1.5" data-testid={`lapisan-${l.id}`}>
      <div className="flex flex-col">
        <button type="button" onClick={onNaik} disabled={pertama} aria-label={`Naikkan ${l.nama}`}
          className="min-w-0 min-h-0 w-8 h-6 sm:w-6 sm:h-5 flex items-center justify-center rounded hover:bg-muted disabled:opacity-30"
          data-testid={`lapisan-naik-${l.id}`}><ChevronUp className="w-4 h-4" /></button>
        <button type="button" onClick={onTurun} disabled={terakhir} aria-label={`Turunkan ${l.nama}`}
          className="min-w-0 min-h-0 w-8 h-6 sm:w-6 sm:h-5 flex items-center justify-center rounded hover:bg-muted disabled:opacity-30"
          data-testid={`lapisan-turun-${l.id}`}><ChevronDown className="w-4 h-4" /></button>
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate">{l.nama}</div>
        <div className={`text-xs truncate ${memproses ? "text-amber-600" : "text-muted-foreground"}`}>{info}</div>
      </div>
      {!memproses && (
        <Switch className="min-w-0 min-h-0" checked={!!l.aktif} onCheckedChange={onAktif} disabled={!l.bisa_ubah}
          aria-label={l.aktif ? `Sembunyikan ${l.nama}` : `Tampilkan ${l.nama}`} data-testid={`lapisan-aktif-${l.id}`} />
      )}
      {l.bisa_ubah && !memproses && (
        <Button variant="ghost" size="icon" onClick={onUbah} aria-label={`Ubah ${l.nama}`} data-testid={`lapisan-ubah-${l.id}`}>
          {l.jenis === "gambar" ? <PenLine className="w-4 h-4" /> : <Pencil className="w-4 h-4" />}
        </Button>
      )}
      {l.bisa_ubah && (
        <Button variant="ghost" size="icon" onClick={onHapus} aria-label={`Hapus ${l.nama}`} data-testid={`lapisan-hapus-${l.id}`}>
          <Trash2 className="w-4 h-4 text-red-600" />
        </Button>
      )}
    </div>
  );
}

function Bagian({ judul, ikon: Ikon, daftar, kosong, onPindah, ...aksi }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
        <Ikon className="w-3.5 h-3.5" /> {judul}
        {daftar.length > 1 && <span className="font-normal">· atas = paling depan</span>}
      </h3>
      {daftar.length === 0 && <p className="text-xs text-muted-foreground px-1">{kosong}</p>}
      {daftar.map((l, i) => (
        <BarisLapisan key={l.id} l={l} pertama={i === 0} terakhir={i === daftar.length - 1}
          onNaik={() => onPindah(daftar, i, -1)} onTurun={() => onPindah(daftar, i, 1)}
          onAktif={(v) => aksi.onAktif(l, v)} onUbah={() => aksi.onUbah(l)} onHapus={() => aksi.onHapus(l)} />
      ))}
    </section>
  );
}

export default function LapisanEksistingDialog({ onClose }) {
  const [daftar, setDaftar] = useState([]);
  const [memuat, setMemuat] = useState(true);
  const [form, setForm] = useState(null);        // {mode: "citra"|"ubah"|"gambar", ...}
  const [sibuk, setSibuk] = useState(false);
  const [progres, setProgres] = useState(null);  // {selesai, total}
  const [editor, setEditor] = useState(null);    // lapisan gambar yang dibuka
  const sumberRef = useRef(null);
  const sinyalRef = useRef({ batal: false });
  const fileRef = useRef(null);
  const { confirm, confirmDialog } = useConfirm();

  const muat = useCallback(async () => {
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/peta-lapisan`);
      setDaftar(Array.isArray(r.data?.items) ? r.data.items : []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Daftar lapisan gagal dimuat");
    } finally {
      setMemuat(false);
    }
  }, []);
  useEffect(() => { muat(); }, [muat]);

  // Jangan biarkan tab tertutup di tengah unggahan.
  useEffect(() => {
    if (!progres) return undefined;
    const tahan = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", tahan);
    return () => window.removeEventListener("beforeunload", tahan);
  }, [progres]);

  useEffect(() => () => { sumberRef.current?.tutup?.(); }, []);

  const urut = (jenis) => daftar.filter((l) => l.jenis === jenis).sort((a, b) => (b.urutan || 0) - (a.urutan || 0));
  const citra = urut("citra");
  const gambar = urut("gambar");

  const selesaiUbah = () => { lupakanDaftarCitra(); muat(); };

  const pindah = async (bagian, i, arah) => {
    const j = i + arah;
    if (j < 0 || j >= bagian.length) return;
    const baru = [...bagian];
    [baru[i], baru[j]] = [baru[j], baru[i]];
    try {
      // Tampilan: atas → bawah; server: indeks pertama = paling bawah.
      await axios.put(`${API}/peta-lapisan-urutan`, { ids: [...baru].reverse().map((l) => l.id) });
      selesaiUbah();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Urutan gagal disimpan");
    }
  };

  const aturAktif = async (l, aktif) => {
    try {
      await axios.put(`${API}/peta-lapisan/${l.id}`, bodyUbah(l, { aktif }));
      selesaiUbah();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengubah lapisan");
    }
  };

  const hapus = async (l) => {
    const ok = await confirm({ title: `Hapus "${l.nama}"?`, description: "Lapisan ini hilang dari peta semua pengguna.", confirmText: "Hapus", danger: true });
    if (!ok) return;
    try {
      await axios.delete(`${API}/peta-lapisan/${l.id}`);
      toast.success("Lapisan dihapus");
      selesaiUbah();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus lapisan");
    }
  };

  const ubah = (l) => {
    if (l.jenis === "gambar") { setEditor(l); return; }
    setForm({ mode: "ubah", l, nama: l.nama, tanggal_rekam: l.tanggal_rekam, sumber: l.sumber || "",
      opasitas: Math.round((l.opasitas ?? 1) * 100) });
  };

  // ── Unggah citra ──────────────────────────────────────────────────────────
  const pilihBerkas = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setForm({ mode: "citra", membaca: true, namaBerkas: file.name });
    try {
      const { bukaGeoTiff } = await import("@/lib/ubinCitra");
      sumberRef.current?.tutup?.();
      const s = await bukaGeoTiff(file);
      sumberRef.current = s;
      setForm({ mode: "citra", namaBerkas: file.name, nama: namaDariBerkas(file.name),
        tanggal_rekam: s.tanggal || hariIni(), sumber: "", rencana: s.rencana,
        luas: { lebarKm: s.lebar * s.meterPerPiksel / 1000, tinggiKm: s.tinggi * s.meterPerPiksel / 1000 },
        resolusiCm: s.meterPerPiksel * 100 });
    } catch (err) {
      setForm(null);
      toast.error(err?.message || "Berkas tidak bisa dibaca");
    }
  };

  const mulaiUnggah = async () => {
    const s = sumberRef.current;
    if (!s || !form?.nama?.trim()) { toast.error("Nama citra wajib diisi"); return; }
    setSibuk(true);
    sinyalRef.current = { batal: false };
    let id = null;
    try {
      const { pilihFormatUbin, potongCitra } = await import("@/lib/ubinCitra");
      const format = await pilihFormatUbin();
      const { zmin, zmaks } = s.rencana;
      const r = await axios.post(`${API}/peta-lapisan`, {
        jenis: "citra", nama: form.nama.trim(), tanggal_rekam: form.tanggal_rekam, sumber: form.sumber,
        batas: s.batas, zoom_min: zmin, zoom_maks: zmaks, format, crs_asal: s.crs.label,
      });
      id = r.data.id;
      setProgres({ selesai: 0, total: s.rencana.jumlah });
      const kirim = async (isi) => {
        for (let coba = 1; ; coba += 1) {
          const fd = new FormData();
          isi.forEach(({ nama, blob }) => fd.append("files", blob, nama));
          try {
            await axios.post(`${API}/peta-lapisan/${id}/ubin`, fd, { timeout: 120000 });
            return;
          } catch (err) {
            const status = err?.response?.status;
            if (coba >= 3 || (status && status < 500)) throw err;
            await new Promise((ok) => setTimeout(ok, 1500 * coba));
          }
        }
      };
      await potongCitra(s, { zmin, zmaks, format, kirim, sinyal: sinyalRef.current, onProgres: setProgres });
      await axios.post(`${API}/peta-lapisan/${id}/selesai`);
      toast.success("Citra siap tampil di peta");
      setForm(null);
      sumberRef.current?.tutup?.(); sumberRef.current = null;
    } catch (err) {
      if (id) await axios.delete(`${API}/peta-lapisan/${id}`).catch(() => {});
      toast.error(sinyalRef.current.batal ? "Unggahan dibatalkan"
        : (err?.response?.data?.detail || err?.message || "Unggahan gagal"));
    } finally {
      setSibuk(false); setProgres(null);
      selesaiUbah();
    }
  };

  const simpanUbahCitra = async () => {
    setSibuk(true);
    try {
      await axios.put(`${API}/peta-lapisan/${form.l.id}`, bodyUbah(form.l, {
        nama: form.nama, tanggal_rekam: form.tanggal_rekam, sumber: form.sumber, opasitas: form.opasitas / 100,
      }));
      setForm(null);
      selesaiUbah();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan");
    } finally {
      setSibuk(false);
    }
  };

  const buatGambar = async () => {
    if (!form?.nama?.trim()) { toast.error("Nama lapisan wajib diisi"); return; }
    setSibuk(true);
    try {
      const r = await axios.post(`${API}/peta-lapisan`, { jenis: "gambar", nama: form.nama.trim(), fitur: [] });
      setForm(null);
      selesaiUbah();
      setEditor({ ...r.data, bisa_ubah: true });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal membuat lapisan");
    } finally {
      setSibuk(false);
    }
  };

  const isi = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const persen = progres?.total ? Math.min(100, Math.round(progres.selesai / progres.total * 100)) : 0;

  return (
    <>
      {/* Dialog disembunyikan selama editor terbuka: dialog modal menahan
          klik di luar isinya, padahal editor berada di luar dialog. */}
      <Dialog open={!editor} onOpenChange={(v) => { if (!v && !progres && !editor) onClose?.(); }}>
        {confirmDialog}
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="lapisan-eksisting-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Satellite className="w-5 h-5 text-amber-600" /> Lapisan Eksisting</DialogTitle>
            <DialogDescription>Citra dan gambar kondisi lapangan terbaru di atas peta.</DialogDescription>
          </DialogHeader>
          <input ref={fileRef} type="file" accept=".tif,.tiff,image/tiff" className="hidden" onChange={pilihBerkas}
            data-testid="lapisan-berkas" />

          {!form && (memuat
            ? <div className="py-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin" /></div>
            : <div className="space-y-4">
                <Bagian judul="Gambar" ikon={PenLine} daftar={gambar} kosong="Belum ada gambar."
                  onPindah={pindah} onAktif={aturAktif} onUbah={ubah} onHapus={hapus} />
                <Bagian judul="Citra" ikon={IkonGambar} daftar={citra} kosong="Belum ada citra."
                  onPindah={pindah} onAktif={aturAktif} onUbah={ubah} onHapus={hapus} />
              </div>)}

          {form?.mode === "citra" && (
            <div className="space-y-3" data-testid="form-unggah-citra">
              <p className="text-sm text-muted-foreground truncate">{form.namaBerkas}</p>
              {form.membaca
                ? <div className="flex items-center gap-2 text-sm"><Loader2 className="w-4 h-4 animate-spin" /> Membaca lokasi citra…</div>
                : <>
                    <div className="rounded-lg bg-muted px-3 py-2 text-xs space-y-0.5" data-testid="ringkasan-citra">
                      <div>Lokasi terbaca otomatis · ±{form.luas.lebarKm.toFixed(1)} × {form.luas.tinggiKm.toFixed(1)} km</div>
                      <div>Resolusi ±{form.resolusiCm.toFixed(1)} cm · zoom {form.rencana.zmin}–{form.rencana.zmaks}
                        · {form.rencana.jumlah.toLocaleString("id-ID")} ubin</div>
                    </div>
                    <Input value={form.nama} onChange={isi("nama")} placeholder="Nama citra" disabled={sibuk} data-testid="citra-nama" />
                    <div className="grid grid-cols-2 gap-2">
                      <Input type="date" value={form.tanggal_rekam} onChange={isi("tanggal_rekam")} disabled={sibuk}
                        aria-label="Tanggal rekam" data-testid="citra-tanggal" />
                      <Input value={form.sumber} onChange={isi("sumber")} placeholder="Sumber (opsional)" disabled={sibuk}
                        data-testid="citra-sumber" />
                    </div>
                    {progres && (
                      <div className="space-y-1" data-testid="progres-unggah">
                        <div className="h-2 rounded bg-muted overflow-hidden">
                          <div className="h-full bg-teal-600 transition-all" style={{ width: `${persen}%` }} />
                        </div>
                        <p className="text-xs text-muted-foreground">Memproses {persen}% — biarkan halaman ini terbuka.</p>
                      </div>
                    )}
                  </>}
            </div>
          )}

          {form?.mode === "ubah" && (
            <div className="space-y-2" data-testid="form-ubah-citra">
              <Input value={form.nama} onChange={isi("nama")} placeholder="Nama citra" data-testid="ubah-nama" />
              <div className="grid grid-cols-2 gap-2">
                <Input type="date" value={form.tanggal_rekam} onChange={isi("tanggal_rekam")} aria-label="Tanggal rekam" />
                <Input value={form.sumber} onChange={isi("sumber")} placeholder="Sumber" />
              </div>
              <label className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Opasitas</span>
                <input type="range" min={10} max={100} value={form.opasitas} onChange={isi("opasitas")}
                  className="flex-1 min-w-0 min-h-0 h-4 accent-teal-600" data-testid="ubah-opasitas" />
                <span className="w-9 text-right tabular-nums">{form.opasitas}%</span>
              </label>
            </div>
          )}

          {form?.mode === "gambar" && (
            <Input value={form.nama || ""} onChange={isi("nama")} placeholder="Nama gambar, mis. Jalan baru 2026" autoFocus
              data-testid="gambar-nama" />
          )}

          <DialogFooter className="gap-2">
            {!form && (
              <>
                <Button variant="outline" onClick={() => setForm({ mode: "gambar", nama: "" })} data-testid="lapisan-gambar-baru">
                  <Plus className="w-4 h-4 mr-1" /> Gambar baru
                </Button>
                <Button onClick={() => fileRef.current?.click()} data-testid="lapisan-unggah-citra">
                  <Upload className="w-4 h-4 mr-1" /> Unggah citra
                </Button>
              </>
            )}
            {form && (
              <Button variant="outline" disabled={sibuk && !progres}
                onClick={() => { if (progres) { sinyalRef.current.batal = true; } else setForm(null); }}
                data-testid="lapisan-batal">
                Batal
              </Button>
            )}
            {form?.mode === "citra" && !form.membaca && (
              <Button onClick={mulaiUnggah} disabled={sibuk} data-testid="citra-mulai">
                {sibuk ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Upload className="w-4 h-4 mr-1" />} Unggah
              </Button>
            )}
            {form?.mode === "ubah" && (
              <Button onClick={simpanUbahCitra} disabled={sibuk} data-testid="ubah-simpan">Simpan</Button>
            )}
            {form?.mode === "gambar" && (
              <Button onClick={buatGambar} disabled={sibuk} data-testid="gambar-buat">Mulai menggambar</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {editor && (
        <Suspense fallback={null}>
          <EditorGambarPeta lapisan={editor} onClose={() => { setEditor(null); selesaiUbah(); }}
            onSaved={(baru) => { setEditor({ ...editor, ...baru }); selesaiUbah(); }} />
        </Suspense>
      )}
    </>
  );
}
