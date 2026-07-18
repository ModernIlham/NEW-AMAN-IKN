import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Tags } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { makeDownloadProgress } from "@/lib/downloadFile";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const UKURAN = [
  ["besar", "Besar", "A4: 12/hal (±98×46) · A3: 27/hal (±94×44)"],
  ["sedang", "Sedang", "A4: 27/hal (±65×30) · A3: 65/hal (±56×30)"],
  ["kecil", "Kecil", "A4: 48/hal (±48×22) · A3: 102/hal (±46×23)"],
  ["per_aset", "Sesuai pilihan per aset", "memakai field \"Ukuran Stiker\" tiap aset — hasil dikelompokkan besar → sedang → kecil"],
];

/**
 * Dialog Cetak Stiker Label BMN — 3 ukuran × kertas A4/A3, cakupan mengikuti
 * FILTER AKTIF daftar aset (semua halaman) atau halaman yang sedang tampil.
 * Desain label meniru contoh label resmi satker (logo + nama instansi + kode
 * register + kode/NUP/nama + QR yang dikenali pemindai internal).
 */
export default function CetakStikerDialog({ open, onOpenChange, buildParams, totalItems, pageAssets }) {
  const [ukuran, setUkuran] = useState("sedang");
  const [kertas, setKertas] = useState("A4");
  const [cakupan, setCakupan] = useState("filter"); // filter | halaman
  const [sibuk, setSibuk] = useState(false);

  const cetak = async () => {
    setSibuk(true);
    const progress = makeDownloadProgress("Stiker label BMN (PDF)");
    try {
      const params = cakupan === "halaman"
        ? new URLSearchParams({ asset_ids: (pageAssets || []).map((a) => a.id).join(",") })
        : (buildParams?.() || new URLSearchParams());
      params.set("ukuran", ukuran);
      params.set("kertas", kertas);
      const r = await axios.get(`${API}/stiker/label?${params.toString()}`, {
        responseType: "blob", timeout: 180000,
        onDownloadProgress: progress.onDownloadProgress,
      });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const win = window.open(url, "_blank");
      if (!win) {
        const a = document.createElement("a");
        a.href = url; a.download = `stiker_label_${ukuran}_${kertas}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      progress.success(`Stiker ${ukuran} (${kertas}) siap dicetak`);
      onOpenChange(false);
    } catch (err) {
      // Blob error → baca detail JSON bila ada.
      let detail = "Gagal membuat stiker";
      try {
        const teks = await err?.response?.data?.text?.();
        detail = JSON.parse(teks || "{}").detail || detail;
      } catch { /* biarkan pesan default */ }
      progress.error(detail);
      toast.error(detail);
    } finally {
      setSibuk(false);
    }
  };

  const jumlah = cakupan === "halaman" ? (pageAssets || []).length : (totalItems || 0);

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!sibuk) onOpenChange(o); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Tags className="w-4 h-4" />Cetak Stiker Label BMN</DialogTitle>
          <DialogDescription className="text-xs">
            Desain mengikuti label resmi satker: logo + nama instansi + nama satker, kode barang/NUP, nama barang, dan QR yang dikenali pemindai aplikasi. Grid otomatis memenuhi seluruh ruang kertas (sisa hanya margin &amp; celah potong).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <p className="text-xs font-semibold text-foreground mb-1.5">Cakupan aset</p>
            <div className="space-y-1">
              {[["filter", `Semua hasil filter aktif (${totalItems || 0} aset)`],
                ["halaman", `Halaman yang tampil saja (${(pageAssets || []).length} aset)`]].map(([k, label]) => (
                <label key={k} className="flex items-center gap-2 text-xs text-foreground/90 cursor-pointer">
                  <input type="radio" name="stiker-cakupan" checked={cakupan === k}
                    onChange={() => setCakupan(k)} data-testid={`stiker-cakupan-${k}`} />
                  {label}
                </label>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-foreground mb-1.5">Ukuran stiker</p>
            <div className="space-y-1">
              {UKURAN.map(([k, label, ket]) => (
                <label key={k} className="flex items-start gap-2 text-xs text-foreground/90 cursor-pointer">
                  <input type="radio" name="stiker-ukuran" className="mt-0.5" checked={ukuran === k}
                    onChange={() => setUkuran(k)} data-testid={`stiker-ukuran-${k}`} />
                  <span><b>{label}</b> <span className="text-muted-foreground">— {ket}</span></span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold text-foreground mb-1.5">Kertas</p>
            <div className="flex gap-3">
              {["A4", "A3"].map((k) => (
                <label key={k} className="flex items-center gap-2 text-xs text-foreground/90 cursor-pointer">
                  <input type="radio" name="stiker-kertas" checked={kertas === k}
                    onChange={() => setKertas(k)} data-testid={`stiker-kertas-${k}`} />
                  {k}
                </label>
              ))}
            </div>
          </div>
          {jumlah > 2000 && (
            <p className="text-[11px] text-amber-700 dark:text-amber-400">
              Hasil filter {jumlah} aset — melebihi batas 2000 stiker per unduhan; persempit filter atau cetak bertahap.
            </p>
          )}
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" disabled={sibuk} onClick={() => onOpenChange(false)}>Batal</Button>
          <Button onClick={cetak} disabled={sibuk || jumlah === 0} data-testid="stiker-cetak">
            {sibuk ? <Loader2 className="w-4 h-4 animate-spin mr-1.5" /> : <Tags className="w-4 h-4 mr-1.5" />}
            Buat PDF Stiker
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
