// Dialog IMPOR denah (Fase 5): SHP-zip / KML / KMZ / GeoJSON → node DRAFT.
//
// Alur dua langkah yang disengaja:
// 1. PRATINJAU (sinkron) — file diperiksa tanpa menulis apa pun: format, cacah
//    fitur, CRS terdeteksi, daftar field atribut + SAMPEL nilainya. Sampel ini
//    penting: nama ber-mojibake (encoding DBF salah) harus terlihat SEBELUM
//    tersimpan, bukan sesudahnya.
// 2. IMPOR (job latar) — operator memilih tingkat, induk, field nama/kode, dan
//    saklar perbaikan topologi otomatis; hasilnya node ber-status DRAFT yang
//    tak ikut deteksi/peta sampai diperiksa dan diaktifkan manusia.
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { AlertTriangle, FileUp, Loader2, Play, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const JEDA_POLL_MS = 1500;

export default function ImporDenahDialog({ levels, nodes, labelLevel, onClose, onSaved }) {
  const [file, setFile] = useState(null);
  const [pratinjau, setPratinjau] = useState(null);
  const [memuat, setMemuat] = useState(false);
  const [tipe, setTipe] = useState("");
  const [parentId, setParentId] = useState("");
  const [fieldNama, setFieldNama] = useState("");
  const [fieldKode, setFieldKode] = useState("");
  const [perbaiki, setPerbaiki] = useState(true);
  const [job, setJob] = useState(null);          // dokumen job terakhir dari polling
  const [berjalan, setBerjalan] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => () => clearTimeout(pollRef.current), []);

  const ordinalTipe = useMemo(() => {
    const l = (levels || []).find((x) => x.kode_baku === tipe);
    return l ? Number(l.ordinal_level) : null;
  }, [levels, tipe]);

  // Induk yang sah = tingkat LEBIH LUAS dari tipe yang dipilih (ordinal lebih
  // kecil). Server tetap memvalidasi; filter ini hanya merapikan pilihan.
  const kandidatInduk = useMemo(() => {
    if (ordinalTipe === null) return [];
    return (nodes || []).filter((n) => Number(n.ordinal_level) < ordinalTipe);
  }, [nodes, ordinalTipe]);

  const pilihFile = useCallback(async (f) => {
    if (!f) return;
    setFile(f); setPratinjau(null); setJob(null);
    setMemuat(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await axios.post(`${API}/spasial/impor/pratinjau`, fd);
      setPratinjau(r.data);
      // Prapilih field nama yang paling mungkin benar.
      const fields = r.data?.fields || [];
      const tebakan = fields.find((x) => /nama|name|label/i.test(x)) || "";
      setFieldNama(tebakan);
    } catch (e) {
      setFile(null);
      toast.error(e?.response?.data?.detail || "File tidak dapat dibaca");
    } finally {
      setMemuat(false);
    }
  }, []);

  const poll = useCallback(async (jobId) => {
    try {
      const r = await axios.get(`${API}/jobs/${jobId}`);
      setJob(r.data);
      if (r.data?.status === "done" || r.data?.status === "failed") {
        setBerjalan(false);
        if (r.data.status === "done") {
          toast.success(r.data.message || "Impor selesai");
          onSaved?.();                       // muat ulang pohon — draft baru tampil
        } else {
          toast.error(r.data.message || "Impor gagal");
        }
        return;
      }
    } catch { /* jaringan goyah — coba lagi pada tick berikutnya */ }
    pollRef.current = setTimeout(() => poll(jobId), JEDA_POLL_MS);
  }, [onSaved]);

  const mulai = useCallback(async () => {
    if (!file || !tipe) return;
    setBerjalan(true); setJob(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("tipe", tipe);
      fd.append("parent_id", parentId);
      // "(nama bawaan)" = pakai <name> KML / properti name — kirim kosong.
      fd.append("field_nama", fieldNama === "(nama bawaan)" ? "" : fieldNama);
      fd.append("field_kode", fieldKode);
      fd.append("perbaiki", perbaiki ? "true" : "false");
      const r = await axios.post(`${API}/spasial/impor`, fd);
      poll(r.data.job_id);
    } catch (e) {
      setBerjalan(false);
      toast.error(e?.response?.data?.detail || "Gagal memulai impor");
    }
  }, [file, tipe, parentId, fieldNama, fieldKode, perbaiki, poll]);

  const selesai = job && (job.status === "done" || job.status === "failed");

  return (
    <Dialog open onOpenChange={(o) => !o && !berjalan && onClose?.()}>
      <DialogContent className="max-w-lg" data-testid="impor-denah-dialog">
        <DialogHeader>
          <DialogTitle className="text-sm">Impor Denah dari File GIS</DialogTitle>
          <DialogDescription className="text-xs">
            Shapefile (zip .shp+.dbf), KML, KMZ, atau GeoJSON. Hasil impor masuk
            sebagai <b>draft</b> — periksa dulu, baru aktifkan.
          </DialogDescription>
        </DialogHeader>

        {/* Langkah 1: file + pratinjau */}
        <label className="flex items-center gap-2 border border-dashed border-border rounded-lg px-3 py-2.5 cursor-pointer hover:bg-muted/50">
          <FileUp className="w-4 h-4 text-teal-600 shrink-0" />
          <span className="text-xs truncate flex-1">
            {file ? file.name : "Pilih file… (.zip / .kml / .kmz / .geojson)"}
          </span>
          {memuat && <Loader2 className="w-4 h-4 animate-spin shrink-0" />}
          <input type="file" className="hidden" accept=".zip,.kml,.kmz,.geojson,.json"
                 disabled={berjalan}
                 onChange={(e) => pilihFile(e.target.files?.[0])}
                 data-testid="impor-file" />
        </label>

        {pratinjau && (
          <div className="rounded-lg border border-border p-2.5 space-y-1.5 text-xs" data-testid="impor-pratinjau">
            <p>
              <b>{pratinjau.jumlah_fitur}</b> fitur poligon · format{" "}
              <b>{String(pratinjau.format || "").toUpperCase()}</b>
              {pratinjau.crs?.jenis === "utm" && (
                <> · UTM zona {pratinjau.crs.zona}{pratinjau.crs.utara ? "U" : "S"} → WGS84</>
              )}
            </p>
            {Object.entries(pratinjau.sampel || {}).slice(0, 4).map(([k, v]) => (
              <p key={k} className="text-muted-foreground truncate">
                <span className="font-mono">{k}</span>: {v.join(", ")}
              </p>
            ))}
            {(pratinjau.peringatan || []).map((p, i) => (
              <p key={i} className="flex items-start gap-1 text-amber-700 dark:text-amber-300">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />{p}
              </p>
            ))}
          </div>
        )}

        {/* Langkah 2: pemetaan */}
        {pratinjau && !selesai && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            <label className="space-y-1">
              <span className="font-medium">Jadikan tingkat</span>
              <select value={tipe} onChange={(e) => { setTipe(e.target.value); setParentId(""); }}
                      className="w-full h-8 rounded-md border border-border bg-background px-2"
                      disabled={berjalan} data-testid="impor-tipe">
                <option value="">— pilih —</option>
                {(levels || []).map((l) => (
                  <option key={l.kode_baku} value={l.kode_baku}>{l.label || l.label_ui}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="font-medium">Di bawah induk</span>
              <select value={parentId} onChange={(e) => setParentId(e.target.value)}
                      className="w-full h-8 rounded-md border border-border bg-background px-2"
                      disabled={berjalan || !tipe} data-testid="impor-induk">
                <option value="">(tanpa induk / akar)</option>
                {kandidatInduk.map((n) => (
                  <option key={n.id} value={n.id}>
                    {(labelLevel?.[n.tipe] || n.tipe)} · {n.nama}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="font-medium">Field nama</span>
              <select value={fieldNama} onChange={(e) => setFieldNama(e.target.value)}
                      className="w-full h-8 rounded-md border border-border bg-background px-2"
                      disabled={berjalan} data-testid="impor-field-nama">
                <option value="">(nama bawaan / otomatis)</option>
                {(pratinjau.fields || []).map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <label className="space-y-1">
              <span className="font-medium">Field kode <span className="text-muted-foreground">(opsional)</span></span>
              <select value={fieldKode} onChange={(e) => setFieldKode(e.target.value)}
                      className="w-full h-8 rounded-md border border-border bg-background px-2"
                      disabled={berjalan} data-testid="impor-field-kode">
                <option value="">(tanpa kode)</option>
                {(pratinjau.fields || []).map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <label className="col-span-2 flex items-center gap-2 pt-1">
              <input type="checkbox" checked={perbaiki} disabled={berjalan}
                     onChange={(e) => setPerbaiki(e.target.checked)}
                     data-testid="impor-perbaiki" />
              <span>
                Perbaiki topologi otomatis (make_valid) — hanya bila luas tak
                berubah &gt; 1%; selain itu fitur dilewati dengan alasan
              </span>
            </label>
          </div>
        )}

        {/* Progres / hasil job */}
        {job && (
          <div className="rounded-lg border border-border p-2.5 text-xs space-y-1.5" data-testid="impor-hasil">
            {!selesai && (
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-teal-600" />
                <div className="flex-1">
                  <div className="h-1.5 rounded bg-muted overflow-hidden">
                    <div className="h-full bg-teal-600 transition-all"
                         style={{ width: `${job.progress || 0}%` }} />
                  </div>
                  <p className="text-muted-foreground mt-1">{job.message || "Memproses…"}</p>
                </div>
              </div>
            )}
            {selesai && <p className={job.status === "failed" ? "text-red-600" : "font-medium"}>{job.message}</p>}
            {(job.peringatan || []).map((p, i) => (
              <p key={i} className="text-amber-700 dark:text-amber-300">⚠ {p}</p>
            ))}
            {(job.dilewati || []).slice(0, 8).map((d, i) => (
              <p key={i} className="text-muted-foreground truncate">
                dilewati: <b>{d.nama}</b> — {d.alasan}
              </p>
            ))}
            {Number(job.jumlah_dilewati) > 8 && (
              <p className="text-muted-foreground">…dan {job.jumlah_dilewati - 8} lainnya</p>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => onClose?.()}
                  disabled={berjalan} data-testid="impor-tutup">
            <X className="w-3.5 h-3.5 mr-1" />{selesai ? "Tutup" : "Batal"}
          </Button>
          {!selesai && (
            <Button size="sm" onClick={mulai}
                    disabled={!file || !tipe || memuat || berjalan}
                    data-testid="impor-mulai">
              {berjalan ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                        : <Play className="w-3.5 h-3.5 mr-1" />}
              Mulai Impor
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
