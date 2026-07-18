import React, { useRef, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import SignatureCanvas from "react-signature-canvas";
import { Button } from "@/components/ui/button";
import { Loader2, Eraser, Upload, PenLine, Camera } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * SignatureCapture — tangkap tanda tangan digital sebagai PNG transparan.
 *
 * Dua mode:
 *  - "Gambar": kanvas signature_pad (goresan bézier variable-width mulus,
 *    latar transparan) → getTrimmedCanvas().toDataURL('image/png').
 *  - "Foto": unggah foto TTD di kertas → backend hapus background otomatis
 *    (POST /ttd/olah-foto, Pillow) → pratinjau PNG transparan.
 *
 * onSave(dataUrlPng) dipanggil dengan data-URL PNG transparan.
 * tokenQuery (opsional): token e-sign untuk penanda tangan TAMU — diteruskan
 * sebagai ?token= ke /ttd/olah-foto (tanpa header Authorization).
 */
export default function SignatureCapture({ onSave, saving = false, tokenQuery = "" }) {
  const [mode, setMode] = useState("gambar");   // "gambar" | "foto"
  const [fotoPng, setFotoPng] = useState(null);  // data-URL hasil olah foto
  const [olah, setOlah] = useState(false);
  const sigRef = useRef(null);
  const fileRef = useRef(null);

  const bersihkan = useCallback(() => {
    sigRef.current?.clear();
    setFotoPng(null);
  }, []);

  const olahFoto = useCallback(async (file) => {
    if (!file) return;
    setOlah(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const url = `${API}/ttd/olah-foto${tokenQuery ? `?token=${encodeURIComponent(tokenQuery)}` : ""}`;
      const r = await axios.post(url, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      setFotoPng(r.data?.png_base64 || null);
      toast.success("Background dihapus — periksa hasilnya");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal memproses foto");
    } finally {
      setOlah(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }, [tokenQuery]);

  const simpan = useCallback(() => {
    let png = null;
    if (mode === "gambar") {
      if (!sigRef.current || sigRef.current.isEmpty()) {
        toast.error("Gambar tanda tangan dulu di kotak");
        return;
      }
      try {
        png = sigRef.current.getTrimmedCanvas().toDataURL("image/png");
      } catch {
        png = sigRef.current.toDataURL("image/png");
      }
    } else {
      if (!fotoPng) { toast.error("Unggah & proses foto dulu"); return; }
      png = fotoPng;
    }
    onSave?.(png);
  }, [mode, fotoPng, onSave]);

  return (
    <div className="space-y-3" data-testid="signature-capture">
      <div className="grid grid-cols-2 gap-1 p-1 rounded-xl border border-border bg-card">
        <button type="button" onClick={() => setMode("gambar")}
          className={`h-9 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 min-h-0 ${mode === "gambar" ? "bg-blue-600 text-white" : "text-muted-foreground"}`}
          data-testid="ttd-mode-gambar">
          <PenLine className="w-3.5 h-3.5" />Gambar langsung
        </button>
        <button type="button" onClick={() => setMode("foto")}
          className={`h-9 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 min-h-0 ${mode === "foto" ? "bg-blue-600 text-white" : "text-muted-foreground"}`}
          data-testid="ttd-mode-foto">
          <Camera className="w-3.5 h-3.5" />Foto (hapus BG)
        </button>
      </div>

      {mode === "gambar" ? (
        <div className="rounded-xl border-2 border-dashed border-border bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(120,120,120,0.05)_10px,rgba(120,120,120,0.05)_20px)] overflow-hidden">
          <SignatureCanvas ref={sigRef}
            penColor="#0f172a"
            minWidth={0.7} maxWidth={2.9} velocityFilterWeight={0.7}
            canvasProps={{ width: 560, height: 200, className: "w-full touch-none", "data-testid": "ttd-canvas" }} />
        </div>
      ) : (
        <div className="rounded-xl border-2 border-dashed border-border p-3 text-center space-y-2 bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(120,120,120,0.05)_10px,rgba(120,120,120,0.05)_20px)]">
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(e) => olahFoto(e.target.files?.[0])} data-testid="ttd-foto-input" />
          {fotoPng ? (
            <img src={fotoPng} alt="Pratinjau TTD" className="max-h-40 mx-auto" data-testid="ttd-foto-preview" />
          ) : (
            <p className="text-xs text-muted-foreground py-6">
              Foto tanda tangan pada kertas <b>terang & polos</b>, goresan gelap — background otomatis dihapus.
            </p>
          )}
          <Button type="button" variant="outline" size="sm" className="h-8 text-xs" disabled={olah}
            onClick={() => fileRef.current?.click()} data-testid="ttd-foto-pilih">
            {olah ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Upload className="w-3.5 h-3.5 mr-1.5" />}
            {fotoPng ? "Ganti foto" : "Pilih / ambil foto"}
          </Button>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <Button type="button" variant="outline" size="sm" className="h-9 text-xs" onClick={bersihkan}>
          <Eraser className="w-3.5 h-3.5 mr-1.5" />Bersihkan
        </Button>
        <Button type="button" size="sm" className="h-9 text-xs" onClick={simpan} disabled={saving} data-testid="ttd-simpan">
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}Simpan Tanda Tangan
        </Button>
      </div>
    </div>
  );
}
