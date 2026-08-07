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
import { AlertTriangle, FileUp, Info, Loader2, Play, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { TENGGAT_BAKA, TENGGAT_BERAT } from "@/lib/muatAndal";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const JEDA_POLL_MS = 1500;
// Cermin plafon server (MAKS_UKURAN_IMPOR): ditolak di sini agar file 200 MB tak
// diunggah dulu baru ditolak — hemat kuota data operator lapangan.
const MAKS_UKURAN_MB = 20;
// Polling berhenti setelah 15 menit ATAU 8 kegagalan jaringan BERURUTAN. Tanpa
// batas ini satu server mati membuat dialog memanggil /jobs selamanya (temuan
// tinjauan). Berhenti polling ≠ impor gagal: job tetap jalan di server.
const BATAS_POLL_MS = 15 * 60 * 1000;
const MAKS_GAGAL_BERUNTUN = 8;

// Semua penulis job di repo ini memakai `done: true` saat berakhir, tetapi kosakata
// status-nya campur: worker impor menulis 'failed', sedangkan penyapu job macet
// (jobs.bersihkan_job_basi) menulis 'error'. Cek ketiganya supaya job yang
// di-relabel penyapu tak dipoll selamanya (temuan tinjauan).
const selesaiJob = (j) =>
  !!j && (j.done === true || ["done", "failed", "error"].includes(j.status));
const suksesJob = (j) => !!j && j.status === "done";

/**
 * Tebak kolom mana yang paling layak jadi NAMA node, dari sampel pratinjau.
 *
 * Versi pertama hanya mencocokkan /nama|name|label/ — dan file GIS instansi
 * kerap sama sekali tak memakai kata itu. Shapefile BWP IKN, misalnya, berkolom
 * OBJECTID / BWP / ROMAWI / KETERANGAN: tak satu pun cocok, sehingga SELURUH
 * baris jatuh ke nama bawaan "Kawasan impor 1…6". Enam node memang terbentuk,
 * tetapi di pohon semuanya terbaca sebagai sampah generik — dan operator wajar
 * menyimpulkan "hanya baris pertama yang terbaca" (laporan lapangan).
 *
 * Karena itu tebakan kini melihat ISI, bukan hanya nama kolom:
 * kolom yang nilainya SERAGAM tak membedakan apa pun, kolom yang seluruhnya
 * angka hampir pasti id internal, dan kolom yang terlalu panjang adalah
 * deskripsi — bukan nama.
 */
export function tebakFieldNama(pratinjau) {
  const sampel = (pratinjau || {}).sampel || {};
  const fields = (pratinjau || {}).fields || [];
  let terbaik = "";
  let skorTerbaik = 0;
  for (const f of fields) {
    const nilai = (sampel[f] || []).map((v) => String(v || "").trim()).filter(Boolean);
    if (!nilai.length) continue;
    const unik = new Set(nilai).size;
    const rerata = nilai.reduce((a, v) => a + v.length, 0) / nilai.length;
    // Seluruhnya angka → hampir pasti OBJECTID/FID, bukan nama.
    if (nilai.every((v) => /^-?\d+([.,]\d+)?$/.test(v))) continue;
    // Terlalu panjang = kalimat deskripsi; terlalu pendek = kode satu huruf.
    if (rerata > 60) continue;
    let skor = unik / nilai.length;            // makin membedakan, makin baik
    if (/nama|name|label|judul|title/i.test(f)) skor += 1.0;   // isyarat kuat
    if (rerata >= 4) skor += 0.3;              // bukan kode 1–2 huruf
    if (/^(id|fid|objectid|gid|kode|code)$/i.test(f)) skor -= 0.8;
    if (skor > skorTerbaik) { skorTerbaik = skor; terbaik = f; }
  }
  return terbaik;
}

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
  const hidupRef = useRef(true);   // false setelah unmount — hentikan polling & setState
  const reqRef = useRef(0);        // nomor urut permintaan pratinjau (anti balapan)

  useEffect(() => {
    hidupRef.current = true;
    return () => { hidupRef.current = false; clearTimeout(pollRef.current); };
  }, []);

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
    if (f.size > MAKS_UKURAN_MB * 1024 * 1024) {
      toast.error(`File melebihi ${MAKS_UKURAN_MB} MB — pecah dulu per kawasan`);
      return;
    }
    // Pilih file A lalu cepat pilih file B: balasan A bisa mendarat SETELAH B dan
    // menimpa pratinjau B (field/sampel milik file yang salah). Hanya balasan
    // dari permintaan TERAKHIR yang boleh menulis state (temuan tinjauan).
    const seq = ++reqRef.current;
    setFile(f); setPratinjau(null); setJob(null);
    setMemuat(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await axios.post(`${API}/spasial/impor/pratinjau`, fd,
                                 { timeout: TENGGAT_BERAT });
      if (!hidupRef.current || seq !== reqRef.current) return;
      setPratinjau(r.data);
      setFieldNama(tebakFieldNama(r.data));
    } catch (e) {
      if (!hidupRef.current || seq !== reqRef.current) return;
      setFile(null);
      toast.error(e?.response?.data?.detail || "File tidak dapat dibaca");
    } finally {
      if (hidupRef.current && seq === reqRef.current) setMemuat(false);
    }
  }, []);

  // Berhenti MEMANTAU (bukan berhenti mengimpor). Job hidup di server, jadi
  // panelnya ditandai berakhir secara lokal supaya spinner tak berputar terus
  // menyiratkan pemantauan yang sudah mati.
  const hentikanPantau = useCallback((pesan) => {
    setBerjalan(false);
    setJob((j) => ({ ...(j || {}), status: "error", done: true, message: pesan }));
    toast.warning(pesan, { duration: 10000 });
  }, []);

  const poll = useCallback(async (jobId, mulaiPada = 0, gagal = 0) => {
    if (!hidupRef.current) return;             // dialog sudah ditutup
    const t0 = mulaiPada || Date.now();
    try {
      // TENGGAT WAJIB di sini. Kedua pagar di bawah — MAKS_GAGAL_BERUNTUN dan
      // BATAS_POLL_MS — hanya dievaluasi SETELAH permintaan ini selesai. Tanpa
      // tenggat, server yang menggantung membuat `await` ini tak pernah kembali,
      // sehingga kedua pagar itu tak pernah dijangkau: rantai polling berhenti
      // diam-diam, spinner berputar selamanya, dan pesan "berhenti memantau"
      // yang sudah disiapkan tak pernah muncul.
      const r = await axios.get(`${API}/jobs/${jobId}`, { timeout: TENGGAT_BAKA });
      if (!hidupRef.current) return;
      setJob(r.data);
      if (selesaiJob(r.data)) {
        setBerjalan(false);
        if (suksesJob(r.data)) {
          toast.success(r.data.message || "Impor selesai");
          onSaved?.();                       // muat ulang pohon — draft baru tampil
        } else {
          toast.error(r.data.message || r.data.error_message || "Impor gagal");
        }
        return;
      }
      gagal = 0;                              // satu balasan sehat menyetel ulang
    } catch {
      if (!hidupRef.current) return;
      if (++gagal >= MAKS_GAGAL_BERUNTUN) {
        hentikanPantau("Koneksi ke server terputus — impor mungkin MASIH "
                       + "berjalan; tutup dialog lalu muat ulang pohon nanti");
        return;
      }
    }
    if (Date.now() - t0 > BATAS_POLL_MS) {
      hentikanPantau("Impor berjalan lebih lama dari perkiraan — pemantauan "
                     + "dihentikan; node draft tetap muncul bertahap di pohon");
      return;
    }
    pollRef.current = setTimeout(() => poll(jobId, t0, gagal), JEDA_POLL_MS);
  }, [onSaved, hentikanPantau]);

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
      const r = await axios.post(`${API}/spasial/impor`, fd,
                                 { timeout: TENGGAT_BERAT });
      poll(r.data.job_id);
    } catch (e) {
      setBerjalan(false);
      toast.error(e?.response?.data?.detail || "Gagal memulai impor");
    }
  }, [file, tipe, parentId, fieldNama, fieldKode, perbaiki, poll]);

  const selesai = selesaiJob(job);

  // Menutup saat job berjalan BOLEH: job hidup di server (bukan di tab ini), jadi
  // mengunci dialog hanya menyandera operator tanpa melindungi apa pun. Muat ulang
  // pohon supaya draft yang SUDAH tertulis langsung terlihat (temuan tinjauan).
  const tutup = useCallback(() => {
    if (berjalan) {
      toast.info("Impor berlanjut di latar belakang — node draft muncul "
                 + "bertahap di pohon spasial");
      onSaved?.();
    }
    onClose?.();
  }, [berjalan, onClose, onSaved]);

  return (
    <Dialog open onOpenChange={(o) => !o && tutup()}>
      {/* Lebar naik + tinggi dibatasi layar & bisa digulir. Sebelumnya dialog
          memakai lebar tetap tanpa plafon tinggi: file dengan banyak kolom
          atribut membuat panel pratinjau mendorong tombol "Mulai Impor" keluar
          layar, dan teks panjang terpotong di tepi kanan (laporan lapangan).

          `[&>*]:min-w-0` ITU WAJIB, bukan hiasan. DialogContent adalah CSS
          `grid` ber-`overflow-hidden`. Anak sebuah grid ber-`min-width:auto`,
          jadi anak yang isinya tak bisa menyusut (teks `nowrap`, tabel, kata
          panjang tanpa spasi) MELEBARKAN trek grid melewati lebar dialog — dan
          `overflow-x: hidden` lalu MEMOTONGNYA tanpa menyisakan bilah gulir
          untuk menjangkaunya lagi. Itulah "informasi terpotong" yang dilaporkan
          setelah impor selesai. Membolehkan anak menyusut menutup seluruh kelas
          bug itu sekaligus, bukan hanya satu barisnya. */}
      <DialogContent
        className="max-w-2xl w-[calc(100vw-2rem)] [&>*]:min-w-0"
        data-testid="impor-denah-dialog">
        <DialogHeader>
          <DialogTitle className="text-sm">Impor Denah dari File GIS</DialogTitle>
          <DialogDescription className="text-xs">
            Shapefile (zip .shp+.dbf), KML, KMZ, atau GeoJSON — maks {MAKS_UKURAN_MB} MB.
            Hasil impor masuk sebagai <b>draft</b> — periksa dulu, baru aktifkan.
          </DialogDescription>
        </DialogHeader>

        {/* Langkah 1: file + pratinjau */}
        <label className="flex items-center gap-2 border border-dashed border-border rounded-lg px-3 py-2.5 cursor-pointer hover:bg-muted/50">
          <FileUp className="w-4 h-4 text-teal-600 shrink-0" />
          <span className="text-xs truncate flex-1">
            {file ? file.name : "Pilih file… (.zip / .kml / .kmz / .geojson)"}
          </span>
          {memuat && <Loader2 className="w-4 h-4 animate-spin shrink-0" />}
          {/* value dikosongkan agar memilih file BERNAMA SAMA lagi tetap memicu
              onChange — mis. setelah memperbaiki .cpg lalu men-zip ulang. */}
          <input type="file" className="hidden" accept=".zip,.kml,.kmz,.geojson,.json"
                 disabled={berjalan}
                 onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; pilihFile(f); }}
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
            {/* `truncate` DIGANTI pembungkusan: memotong sampel di tepi kanan
                menyembunyikan justru nilai yang dipakai operator memutuskan
                field mana yang benar. Daftar panjang digulir, bukan dipotong. */}
            <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
              {Object.entries(pratinjau.sampel || {}).slice(0, 8).map(([k, v]) => (
                <p key={k} className="text-muted-foreground break-words">
                  <span className="font-mono">{k}</span>: {v.join(", ")}
                </p>
              ))}
            </div>
            {(pratinjau.peringatan || []).map((p, i) => (
              <p key={i} className="flex items-start gap-1 text-amber-700 dark:text-amber-300">
                <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span className="break-words min-w-0">{p}</span>
              </p>
            ))}
            {pratinjau.jumlah_fitur > 1 && (
              <p className="flex items-start gap-1 text-teal-700 dark:text-teal-300 pt-0.5">
                <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span className="break-words min-w-0">
                  Setiap baris menjadi <b>satu node tersendiri</b> — file ini akan
                  membentuk <b>{pratinjau.jumlah_fitur}</b> node sekaligus di bawah
                  induk yang dipilih. Pilih <b>Field nama</b> di bawah agar
                  masing-masing bernama sesuai atributnya.
                </span>
              </p>
            )}
          </div>
        )}

        {/* Langkah 2: pemetaan */}
        {pratinjau && !selesai && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
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
            <label className="sm:col-span-2 flex items-center gap-2 pt-1">
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
            {selesai && (
              <p className={`break-words ${suksesJob(job) ? "font-medium" : "text-red-600"}`}>
                {job.message || job.error_message || "Impor berakhir tanpa keterangan"}
              </p>
            )}
            {(job.peringatan || []).map((p, i) => (
              <p key={i} className="text-amber-700 dark:text-amber-300 break-words">⚠ {p}</p>
            ))}
            {/* ALASAN DILEWATI ADALAH INTI PANEL INI — JANGAN DIPOTONG.
                Dulu baris ini ber-`truncate` (white-space:nowrap + ellipsis),
                sehingga justru keterangan yang menjelaskan KENAPA sebuah node
                gagal terpangkas di tepi kanan; yang tersisa di layar operator
                hanyalah "dilewati: BWP 2 — topologi: geometri terl…".
                Alasannya kini dibungkus penuh, dan daftar panjang DIGULIR
                (bukan dipotong) supaya tinggi dialog tetap terkendali. */}
            {(job.dilewati || []).length > 0 && (
              <div className="max-h-40 overflow-y-auto space-y-1 pr-1
                              border-t border-border/60 pt-1.5">
                {(job.dilewati || []).map((d, i) => (
                  <p key={i} className="text-muted-foreground break-words">
                    dilewati: <b>{d.nama}</b> — {d.alasan}
                  </p>
                ))}
                {Number(job.jumlah_dilewati) > (job.dilewati || []).length && (
                  <p className="text-muted-foreground">
                    …dan {job.jumlah_dilewati - job.dilewati.length} lainnya
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={tutup}
                  data-testid="impor-tutup">
            <X className="w-3.5 h-3.5 mr-1" />
            {selesai ? "Tutup" : berjalan ? "Tutup (lanjut di latar)" : "Batal"}
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
