// Dialog EKSPOR denah (Fase 6): pohon spasial → GeoJSON / KML / KMZ / SHP-zip,
// plus unduhan TEMPLATE gambar kosong (QGIS / Google Earth) — kebalikan dialog
// impor Fase 5. Ekspor bisa dibatasi ke satu subtree (node + seluruh
// keturunannya); draft ikut secara bawaan karena alur bolak-balik "perbaiki di
// QGIS lalu impor ulang" justru paling sering dipakai pada draft.
//
// Unduhan lewat axios blob (header Authorization dari interceptor global) —
// bukan token di URL — lalu disimpan via createObjectURL.
import React, { useCallback, useMemo, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Download, FileDown, Loader2, PencilRuler, X } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FORMAT = [
  { kode: "geojson", label: "GeoJSON", ket: "standar web & QGIS" },
  { kode: "kml", label: "KML", ket: "Google Earth" },
  { kode: "kmz", label: "KMZ", ket: "KML terkompresi" },
  { kode: "shp", label: "Shapefile (zip)", ket: "QGIS / ArcGIS" },
];

function simpanBlob(data, namaFile) {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = namaFile;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Segera revoke = unduhan besar bisa terputus di sebagian browser; beri jeda.
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

function namaDariHeader(headers, cadangan) {
  const cd = headers?.["content-disposition"] || "";
  const m = /filename="?([^";]+)"?/i.exec(cd);
  return (m && m[1]) || cadangan;
}

export default function EksporDenahDialog({ nodes, labelLevel, onClose }) {
  const [format, setFormat] = useState("geojson");
  const [dalam, setDalam] = useState("");         // "" = seluruh pohon satker
  const [sertakanDraft, setSertakanDraft] = useState(true);
  // "asli" (bawaan) atau "optimize". Bawaan ASLI disengaja: berkas ekspor jadi
  // arsip cadangan dan bahan QGIS — memberi versi sederhana diam-diam membuat
  // presisi survei hilang sedikit demi sedikit di tiap putaran ekspor–impor.
  const [geometri, setGeometri] = useState("asli");
  const [sibuk, setSibuk] = useState("");         // kunci tombol yang sedang mengunduh

  const pilihanSubtree = useMemo(
    () => [...(nodes || [])].sort((a, b) =>
      (a.ordinal_level - b.ordinal_level)
      || String(a.nama || "").localeCompare(String(b.nama || ""))),
    [nodes]);

  const unduh = useCallback(async (url, kunci, namaCadangan) => {
    setSibuk(kunci);
    try {
      const r = await axios.get(url, { responseType: "blob" });
      simpanBlob(r.data, namaDariHeader(r.headers, namaCadangan));
      toast.success("File terunduh");
    } catch (e) {
      // Galat blob perlu dibaca dulu — response.data adalah Blob, bukan JSON.
      let pesan = "Ekspor gagal";
      try {
        pesan = JSON.parse(await e.response.data.text()).detail || pesan;
      } catch { /* biarkan pesan umum */ }
      toast.error(pesan);
    } finally {
      setSibuk("");
    }
  }, []);

  const ekspor = useCallback(() => {
    const q = new URLSearchParams({
      format, sertakan_draft: String(sertakanDraft), geometri });
    if (dalam) q.set("dalam", dalam);
    unduh(`${API}/spasial/ekspor?${q}`, "ekspor",
      `denah${geometri === "optimize" ? "-optimize" : ""}.${format}`);
  }, [format, dalam, sertakanDraft, geometri, unduh]);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-md" data-testid="ekspor-denah-dialog">
        <DialogHeader>
          <DialogTitle className="text-sm">Ekspor Denah ke File GIS</DialogTitle>
          <DialogDescription className="text-xs">
            Hasil ekspor terbaca di QGIS / ArcGIS / Google Earth dan bisa
            diimpor balik ke aplikasi ini.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2 text-xs">
          <label className="space-y-1 block">
            <span className="font-medium">Format</span>
            <select value={format} onChange={(e) => setFormat(e.target.value)}
                    className="w-full h-8 rounded-md border border-border bg-background px-2"
                    data-testid="ekspor-format">
              {FORMAT.map((f) => (
                <option key={f.kode} value={f.kode}>{f.label} — {f.ket}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 block">
            <span className="font-medium">Cakupan</span>
            <select value={dalam} onChange={(e) => setDalam(e.target.value)}
                    className="w-full h-8 rounded-md border border-border bg-background px-2"
                    data-testid="ekspor-cakupan">
              <option value="">Seluruh denah satker</option>
              {pilihanSubtree.map((n) => (
                <option key={n.id} value={n.id}>
                  {(labelLevel?.[n.tipe] || n.tipe)} · {n.nama} (dan seisinya)
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 block">
            <span className="font-medium">Isi geometri</span>
            <select value={geometri} onChange={(e) => setGeometri(e.target.value)}
                    className="w-full h-8 rounded-md border border-border bg-background px-2"
                    data-testid="ekspor-geometri">
              <option value="asli">Asli — presisi survei penuh (disarankan)</option>
              <option value="optimize">Optimize — ringan, untuk berbagi cepat</option>
            </select>
            <span className="block text-[10px] text-muted-foreground">
              {geometri === "asli"
                ? "Berkas arsip & bahan QGIS. Pakai ini bila hasilnya akan diimpor balik."
                : "Verteks disederhanakan (bentuk hampir sama, berkas jauh lebih kecil). "
                  + "Nama berkas ditandai \u201coptimize\u201d agar penerima tahu."}
            </span>
          </label>
          <label className="flex items-center gap-2 pt-0.5">
            <input type="checkbox" checked={sertakanDraft}
                   onChange={(e) => setSertakanDraft(e.target.checked)}
                   data-testid="ekspor-draft" />
            <span>Sertakan node berstatus draft</span>
          </label>
          <Button size="sm" className="w-full" onClick={ekspor}
                  disabled={!!sibuk} data-testid="ekspor-unduh">
            {sibuk === "ekspor" ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                : <Download className="w-3.5 h-3.5 mr-1" />}
            Unduh Ekspor
          </Button>
        </div>

        {/* Template gambar kosong — alur "gambar di luar, impor balik" */}
        <div className="rounded-lg border border-dashed border-border p-2.5 space-y-1.5 text-xs">
          <p className="flex items-center gap-1.5 font-medium">
            <PencilRuler className="w-3.5 h-3.5 text-teal-600" />
            Template gambar (belum punya denah?)
          </p>
          <p className="text-muted-foreground">
            Unduh kerangka kosong ber-skema, gambar denah di aplikasi favorit,
            lalu impor balik — kolomnya sudah cocok dengan pemetaan impor.
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1" disabled={!!sibuk}
                    onClick={() => unduh(`${API}/spasial/ekspor/template?format=shp`,
                                         "tpl-shp", "template-denah-qgis.zip")}
                    data-testid="ekspor-template-shp">
              {sibuk === "tpl-shp" ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                   : <FileDown className="w-3.5 h-3.5 mr-1" />}
              QGIS (SHP)
            </Button>
            <Button variant="outline" size="sm" className="flex-1" disabled={!!sibuk}
                    onClick={() => unduh(`${API}/spasial/ekspor/template?format=kml`,
                                         "tpl-kml", "template-denah-google-earth.kml")}
                    data-testid="ekspor-template-kml">
              {sibuk === "tpl-kml" ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                   : <FileDown className="w-3.5 h-3.5 mr-1" />}
              Google Earth (KML)
            </Button>
          </div>
        </div>

        <div className="flex justify-end pt-1">
          <Button variant="outline" size="sm" onClick={() => onClose?.()}
                  data-testid="ekspor-tutup">
            <X className="w-3.5 h-3.5 mr-1" />Tutup
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
