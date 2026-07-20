import React, { useRef, useState, useCallback, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import SignatureCanvas from "react-signature-canvas";
import { Button } from "@/components/ui/button";
import { Loader2, Eraser, Upload, PenLine, Camera } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Foto kamera HP modern bisa >10MB — perkecil DI KLIEN sebelum unggah
// (server toh men-downscale ke 1600px): hemat kuota & jauh lebih cepat di
// jaringan seluler. Gagal decode (mis. HEIC) → kirim file asli apa adanya.
async function perkecilFoto(file, maksSisi = 1600) {
  try {
    const bmp = await createImageBitmap(file);
    const sk = Math.min(1, maksSisi / Math.max(bmp.width, bmp.height));
    if (sk >= 1 && file.size < 2 * 1024 * 1024) return file;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * sk);
    canvas.height = Math.round(bmp.height * sk);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.9));
    return blob ? new File([blob], "ttd.jpg", { type: "image/jpeg" }) : file;
  } catch {
    return file;
  }
}

/**
 * SignatureCapture — tangkap tanda tangan digital sebagai PNG transparan.
 *
 * Dua mode:
 *  - "Gambar": kanvas signature_pad (goresan bézier variable-width mulus,
 *    latar transparan) → getTrimmedCanvas().toDataURL('image/png').
 *  - "Foto": unggah foto TTD di kertas → backend hapus background otomatis
 *    (POST /ttd/olah-foto, Pillow) → pratinjau PNG transparan.
 *
 * Keandalan lapangan:
 *  - clearOnResize={false} + goresan DISKALAKAN ulang saat rotasi/resize —
 *    tanda tangan tidak pernah hilang/terpotong di tengah menggambar
 *    (Chrome Android memicu resize saat address bar menciut).
 *  - drafKey (opsional): goresan & hasil olah foto disimpan ke
 *    sessionStorage — reload/tab terbunuh tidak menghapus tanda tangan.
 *  - Foto kamera diperkecil di klien sebelum diunggah.
 *
 * onSave(dataUrlPng) dipanggil dengan data-URL PNG transparan.
 * tokenQuery (opsional): token e-sign untuk penanda tangan TAMU.
 */
export default function SignatureCapture({ onSave, saving = false, tokenQuery = "", drafKey = "", labelSimpan = "Simpan Tanda Tangan" }) {
  const [mode, setMode] = useState("gambar");   // "gambar" | "foto"
  const [fotoPng, setFotoPng] = useState(null);  // data-URL hasil olah foto
  const [olah, setOlah] = useState(false);
  const sigRef = useRef(null);
  const fileRef = useRef(null);
  const wrapRef = useRef(null);
  const ukuranRef = useRef({ w: 0, h: 0 }); // ukuran CSS kanvas terakhir

  const simpanDraf = useCallback(() => {
    if (!drafKey) return;
    try {
      const goresan = sigRef.current?.toData?.() || [];
      sessionStorage.setItem(drafKey, JSON.stringify({
        goresan, foto: fotoPng, w: ukuranRef.current.w, h: ukuranRef.current.h,
      }));
    } catch { /* kuota penuh — draf best-effort */ }
  }, [drafKey, fotoPng]);

  // Kanvas HARUS diukur ulang mengikuti lebar container × devicePixelRatio —
  // width/height statis + CSS w-full membuat koordinat goresan MELESET dari
  // jari/kursor (skala CSS ≠ skala bitmap) dan buram di layar HP. Pola resmi
  // signature_pad: set bitmap = ukuran CSS × ratio lalu ctx.scale(ratio).
  useEffect(() => {
    if (mode !== "gambar") return;
    const resize = () => {
      const canvas = sigRef.current?.getCanvas?.();
      const wrap = wrapRef.current;
      if (!canvas || !wrap) return;
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      const w = wrap.clientWidth || 560;
      // Tinggi mengikuti lebar (rasio nyaman menggores) — tidak lagi fix
      // 200px yang gepeng di tablet/desktop.
      const h = Math.max(180, Math.min(280, Math.round(w * 0.42)));
      // Goresan yang ada DISKALAKAN ke ukuran baru (bukan koordinat absolut)
      // sehingga rotasi portrait↔landscape tidak memotong tanda tangan.
      const lama = ukuranRef.current;
      let goresan = sigRef.current?.toData?.() || [];
      if (goresan.length && lama.w > 0 && lama.h > 0 && (lama.w !== w || lama.h !== h)) {
        const fx = w / lama.w, fy = h / lama.h;
        goresan = goresan.map((g) => ({
          ...g,
          points: (g.points || []).map((pt) => ({ ...pt, x: pt.x * fx, y: pt.y * fy })),
        }));
      }
      ukuranRef.current = { w, h };
      canvas.width = w * ratio;
      canvas.height = h * ratio;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      canvas.getContext("2d").scale(ratio, ratio);
      sigRef.current?.clear();
      if (goresan.length) sigRef.current?.fromData?.(goresan);
    };
    resize();
    // Pulihkan draf (reload / tab terbunuh) sekali setelah kanvas siap.
    if (drafKey) {
      try {
        const d = JSON.parse(sessionStorage.getItem(drafKey) || "null");
        if (d?.foto) setFotoPng(d.foto);
        if (d?.goresan?.length && sigRef.current) {
          const { w, h } = ukuranRef.current;
          const fx = d.w > 0 ? w / d.w : 1, fy = d.h > 0 ? h / d.h : 1;
          sigRef.current.fromData(d.goresan.map((g) => ({
            ...g,
            points: (g.points || []).map((pt) => ({ ...pt, x: pt.x * fx, y: pt.y * fy })),
          })));
        }
      } catch { /* draf korup — abaikan */ }
    }
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const bersihkan = useCallback(() => {
    sigRef.current?.clear();
    setFotoPng(null);
    if (drafKey) { try { sessionStorage.removeItem(drafKey); } catch { /* noop */ } }
  }, [drafKey]);

  const olahFoto = useCallback(async (file) => {
    if (!file) return;
    setOlah(true);
    try {
      const kecil = await perkecilFoto(file);
      const fd = new FormData();
      fd.append("file", kecil, kecil.name || file.name || "ttd.jpg");
      const url = `${API}/ttd/olah-foto${tokenQuery ? `?token=${encodeURIComponent(tokenQuery)}` : ""}`;
      const r = await axios.post(url, fd,
        { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      setFotoPng(r.data?.png_base64 || null);
      toast.success("Background dihapus — periksa hasilnya");
    } catch (e) {
      toast.error(e?.response?.data?.detail
        || (e?.code === "ECONNABORTED" ? "Waktu habis — jaringan lambat, coba lagi" : "Gagal memproses foto"));
    } finally {
      setOlah(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }, [tokenQuery]);

  // Draf foto ikut tersimpan begitu hasil olah berubah.
  useEffect(() => { if (fotoPng !== null) simpanDraf(); }, [fotoPng, simpanDraf]);

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
        <div ref={wrapRef}
          className="rounded-xl border-2 border-dashed border-border bg-[repeating-linear-gradient(45deg,transparent,transparent_10px,rgba(120,120,120,0.05)_10px,rgba(120,120,120,0.05)_20px)] overflow-hidden">
          <SignatureCanvas ref={sigRef}
            penColor="#0f172a"
            minWidth={0.7} maxWidth={2.9} velocityFilterWeight={0.7}
            clearOnResize={false}
            onEnd={simpanDraf}
            canvasProps={{ className: "touch-none block", "data-testid": "ttd-canvas" }} />
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
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}{labelSimpan}
        </Button>
      </div>
    </div>
  );
}
