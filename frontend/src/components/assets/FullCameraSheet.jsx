import React, { memo, useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  X, Camera, MapPin, Clock, Pencil, SwitchCamera, Loader2, Check, Trash2,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { useBackGuard } from "../../hooks/useBackGuard";

/**
 * Mode Kamera Penuh (ala aplikasi Timemark) untuk surveyor inventarisasi.
 *
 * Halaman khusus fullscreen di mana SEMUA kebutuhan lapangan bisa diakses
 * tanpa meninggalkan kamera:
 *  - Pratinjau kamera langsung (getUserMedia, kamera belakang).
 *  - Jam berjalan + koordinat GPS yang SELALU ter-update (watchPosition,
 *    maximumAge:0) tanpa perlu refresh.
 *  - Info aset yang sedang diinput (nama/kode/NUP/lokasi + jumlah foto).
 *  - Tombol rana: foto yang diambil DISTEMPEL watermark (waktu, GPS, kode &
 *    nama aset, lokasi) seperti Timemark, lalu masuk ke daftar foto form.
 *  - Strip thumbnail semua foto + hapus per-foto (salah foto tinggal hapus).
 *  - Panel "Edit Info" untuk membetulkan data aset langsung dari kamera.
 *  - Tombol Back HP menutup mode kamera (kembali ke form), bukan keluar app.
 *
 * Komponen ini hanya di-mount saat terbuka; semua resource (stream kamera,
 * watch GPS, interval jam) dibersihkan saat unmount.
 */
const FullCameraSheet = memo(function FullCameraSheet({
  formData,
  photos = [],
  maxPhotos = 6,
  isEditing = false,
  assetIndex = -1,
  totalAssetsInView = 0,
  savedCount = 0,
  onClose,
  onCapture,       // (dataUrl) => void — foto baru (sudah distempel + terkompresi)
  onRemovePhoto,   // (index) => void
  onSetField,      // (name, value) => void — edit info aset dari panel
  onGpsFix,        // ({lat, lng}) => void — tiap fix GPS baru (update form + cache)
  onSaveAndNew,    // () => void — simpan aset ini lalu siapkan aset baru
  onReviewSaved,   // () => void — simpan lalu tinjau aset tersimpan sebelumnya
  onNavigate,      // (dir) => void — 'prev' | 'next' (mode edit aset yang sudah ada)
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const gpsRef = useRef(null); // fix terakhir utk stempel foto (hindari re-render race)
  const [ready, setReady] = useState(false);
  const [starting, setStarting] = useState(true);
  const [facing, setFacing] = useState("environment");
  const [now, setNow] = useState(() => new Date());
  const [gps, setGps] = useState(null); // {lat, lng, accuracy}
  const [editOpen, setEditOpen] = useState(false);
  const [confirmIdx, setConfirmIdx] = useState(null); // index foto yang mau dihapus

  // Back HP: tutup panel edit dulu, lalu konfirmasi hapus, lalu kamera.
  useBackGuard(useCallback(() => {
    if (editOpen) { setEditOpen(false); return; }
    if (confirmIdx !== null) { setConfirmIdx(null); return; }
    onClose();
  }, [editOpen, confirmIdx, onClose]));

  // Kunci scroll latar selama kamera terbuka
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Jam berjalan (1 detik)
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // GPS live: watchPosition dengan maximumAge:0 — terus ter-update tanpa refresh
  useEffect(() => {
    if (!navigator.geolocation) return undefined;
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const fix = {
          lat: pos.coords.latitude.toFixed(6),
          lng: pos.coords.longitude.toFixed(6),
          accuracy: Number.isFinite(pos.coords.accuracy) ? Math.round(pos.coords.accuracy) : null,
        };
        gpsRef.current = fix;
        setGps(fix);
        try { onGpsFix?.(fix); } catch { /* update form tidak boleh mematikan kamera */ }
      },
      () => { /* sementara tidak dapat fix — biarkan watch berjalan */ },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [onGpsFix]);

  // Nyalakan kamera (dan restart saat flip depan/belakang)
  useEffect(() => {
    let cancelled = false;
    setReady(false);
    setStarting(true);
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          await video.play().catch(() => {});
        }
        setReady(true);
      } catch (err) {
        if (!cancelled) {
          if (err?.name === "NotAllowedError") toast.error("Akses kamera ditolak. Izinkan di pengaturan browser.");
          else toast.error("Gagal membuka kamera");
          onClose();
        }
      } finally {
        if (!cancelled) setStarting(false);
      }
    })();
    return () => {
      cancelled = true;
      if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    };
  }, [facing, onClose]);

  const fmtTanggal = now.toLocaleDateString("id-ID", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
  const fmtJam = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  // Kontrol alur beruntun
  const maxReached = photos.length >= maxPhotos;
  const backAction = isEditing ? () => onNavigate?.("prev") : onReviewSaved;
  const canBack = isEditing ? assetIndex > 0 : (!!onReviewSaved && totalAssetsInView > 0);
  const canNext = isEditing && assetIndex >= 0 && assetIndex < totalAssetsInView - 1;

  // Ambil foto: gambar frame video ke canvas, stempel watermark ala Timemark,
  // hasilkan JPEG (sisi terpanjang ≤1920, q0.85 — setara pipeline kompresi form).
  const capture = useCallback(() => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) { toast.error("Kamera belum siap"); return; }
    if (photos.length >= maxPhotos) { toast.error(`Maks ${maxPhotos} foto`); return; }
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) { toast.error("Kamera belum siap"); return; }
    const scale = Math.min(1, 1920 / Math.max(vw, vh));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(vw * scale);
    canvas.height = Math.round(vh * scale);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // — Watermark Timemark: blok semi-transparan kiri-bawah —
    const fix = gpsRef.current;
    const t = new Date();
    const lines = [
      `${t.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" })}  ${t.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`,
      fix ? `GPS ${fix.lat}, ${fix.lng}${fix.accuracy != null ? ` (±${fix.accuracy} m)` : ""}` : "GPS: —",
      `${formData?.asset_code || "—"}${formData?.NUP ? `  NUP ${formData.NUP}` : ""}`,
      (formData?.asset_name || "Aset Baru") + (formData?.location ? ` • ${formData.location}` : ""),
    ];
    const fs = Math.max(13, Math.round(canvas.width * 0.018));
    const lh = Math.round(fs * 1.4);
    const pad = Math.round(fs * 0.8);
    ctx.font = `600 ${fs}px Arial, sans-serif`;
    const boxW = Math.min(canvas.width - pad * 2, Math.max(...lines.map(l => ctx.measureText(l).width)) + pad * 2);
    const boxH = lh * lines.length + pad * 1.4;
    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(pad / 2, canvas.height - boxH - pad / 2, boxW, boxH);
    ctx.fillStyle = "#fff";
    lines.forEach((l, i) => {
      ctx.fillText(l, pad / 2 + pad * 0.7, canvas.height - boxH - pad / 2 + pad * 0.4 + lh * (i + 1) - fs * 0.25, boxW - pad * 1.4);
    });

    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    onCapture(dataUrl);
  }, [photos.length, maxPhotos, formData, onCapture]);

  // Form ringkas & padat: field penting saja, 2 kolom. Kode Aset & NUP
  // read-only (sudah distandby-kan ke kategori dummy + NUP otomatis).
  const EDIT_FIELDS = [
    { name: "asset_name", label: "Nama Aset", full: true },
    { name: "asset_code", label: "Kode Aset", readOnly: true },
    { name: "NUP", label: "NUP", readOnly: true },
    { name: "location", label: "Lokasi" },
    { name: "user", label: "Pengguna" },
    { name: "notes", label: "Catatan", full: true },
  ];

  return createPortal(
    <div className="fixed inset-0 z-[120] bg-black flex flex-col" data-testid="full-camera-sheet">
      {/* Pratinjau kamera */}
      <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
      {(starting || !ready) && (
        <div className="absolute inset-0 flex items-center justify-center text-white/80">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      )}

      {/* ── Overlay atas: jam + GPS live + info aset ── */}
      <div className="relative z-10 p-3 pt-4 bg-gradient-to-b from-black/70 to-transparent text-white space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-1.5 text-[13px] font-semibold tabular-nums">
              <Clock className="w-3.5 h-3.5 flex-shrink-0" />{fmtTanggal} • {fmtJam}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] font-mono">
              <MapPin className={`w-3.5 h-3.5 flex-shrink-0 ${gps ? "text-emerald-400" : "text-white/50"}`} />
              {gps ? `${gps.lat}, ${gps.lng}${gps.accuracy != null ? ` (±${gps.accuracy} m)` : ""}` : "Mencari sinyal GPS…"}
            </div>
            <div className="text-[11px] text-white/90 truncate">
              <span className="font-semibold">{formData?.asset_name || "Aset Baru"}</span>
              {formData?.asset_code ? ` — ${formData.asset_code}` : ""}{formData?.NUP ? ` NUP ${formData.NUP}` : ""}
              {formData?.location ? ` • ${formData.location}` : ""}
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Tutup kamera" data-testid="full-camera-close"
            className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center flex-shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="flex-1" />

      {/* ── Overlay bawah: thumbnail + kontrol ── */}
      <div className="relative z-10 bg-gradient-to-t from-black/80 to-transparent pt-6 pb-4 px-3 space-y-3">
        {photos.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {photos.map((p, i) => (
              <div key={i} className="relative flex-shrink-0">
                <img src={p} alt={`Foto ${i + 1}`} className="w-14 h-14 object-cover rounded-lg border border-white/30" />
                <button type="button" aria-label={`Hapus foto ${i + 1}`} onClick={() => setConfirmIdx(i)}
                  data-testid={`full-camera-del-${i}`}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center shadow">
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between">
          <button type="button" onClick={() => setEditOpen(true)} data-testid="full-camera-edit-btn"
            className="flex flex-col items-center gap-1 text-white/90 text-[10px] font-medium w-16">
            <span className="w-11 h-11 rounded-full bg-white/15 flex items-center justify-center"><Pencil className="w-5 h-5" /></span>
            Edit Info
          </button>
          <button type="button" onClick={capture} disabled={!ready || photos.length >= maxPhotos}
            aria-label="Ambil foto" data-testid="full-camera-shutter"
            className="w-[72px] h-[72px] rounded-full border-4 border-white flex items-center justify-center disabled:opacity-40">
            <span className="w-14 h-14 rounded-full bg-white flex items-center justify-center">
              <Camera className="w-6 h-6 text-black/70" />
            </span>
          </button>
          <button type="button" onClick={() => setFacing(f => (f === "environment" ? "user" : "environment"))}
            data-testid="full-camera-flip"
            className="flex flex-col items-center gap-1 text-white/90 text-[10px] font-medium w-16">
            <span className="w-11 h-11 rounded-full bg-white/15 flex items-center justify-center"><SwitchCamera className="w-5 h-5" /></span>
            Balik
          </button>
        </div>

        {/* Alur beruntun: simpan & aset baru + maju/mundur antar aset tersimpan.
            Ditonjolkan saat foto sudah penuh (maks). */}
        <div className={`grid grid-cols-3 gap-2 ${maxReached ? "ring-1 ring-white/40 rounded-xl p-1" : ""}`}>
          <button type="button" onClick={backAction} disabled={!canBack} data-testid="full-camera-prev"
            className="h-11 rounded-lg bg-white/15 text-white text-xs font-semibold flex items-center justify-center gap-1 disabled:opacity-30 disabled:pointer-events-none">
            <ChevronLeft className="w-4 h-4" />Sebelumnya
          </button>
          <button type="button" onClick={onSaveAndNew} data-testid="full-camera-savenew"
            className="h-11 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center justify-center gap-1 transition-colors">
            <Check className="w-4 h-4" />Simpan & Baru
          </button>
          <button type="button" onClick={() => onNavigate?.("next")} disabled={!canNext} data-testid="full-camera-next"
            className="h-11 rounded-lg bg-white/15 text-white text-xs font-semibold flex items-center justify-center gap-1 disabled:opacity-30 disabled:pointer-events-none">
            Berikutnya<ChevronRight className="w-4 h-4" />
          </button>
        </div>
        <div className="text-center text-[11px] text-white/70">
          {photos.length}/{maxPhotos} foto{maxReached ? " (penuh)" : ""} • {savedCount} tersimpan sesi ini
          {isEditing && totalAssetsInView > 0 ? ` • aset ${assetIndex + 1}/${totalAssetsInView}` : ""}
        </div>
      </div>

      {/* ── Konfirmasi hapus foto ── */}
      {confirmIdx !== null && (
        <div className="absolute inset-0 z-20 bg-black/70 flex items-center justify-center p-6" onClick={() => setConfirmIdx(null)}>
          <div className="bg-card rounded-2xl p-4 w-full max-w-xs space-y-3" onClick={e => e.stopPropagation()}>
            <img src={photos[confirmIdx]} alt="Foto yang akan dihapus" className="w-full h-40 object-cover rounded-lg" />
            <p className="text-sm text-foreground font-medium text-center">Hapus foto ini?</p>
            <div className="grid grid-cols-2 gap-2">
              <button type="button" onClick={() => setConfirmIdx(null)}
                className="h-10 rounded-lg border border-border text-sm font-medium text-foreground/80">Batal</button>
              <button type="button" data-testid="full-camera-del-confirm"
                onClick={() => { onRemovePhoto(confirmIdx); setConfirmIdx(null); toast.success("Foto dihapus"); }}
                className="h-10 rounded-lg bg-red-600 text-white text-sm font-semibold flex items-center justify-center gap-1.5">
                <Trash2 className="w-4 h-4" />Hapus
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Panel Edit Info (bottom sheet di dalam kamera) ── */}
      {editOpen && (
        <div className="absolute inset-0 z-20 bg-black/60 flex flex-col justify-end" onClick={() => setEditOpen(false)}>
          <div className="bg-card rounded-t-2xl p-4 max-h-[70vh] overflow-y-auto space-y-3" onClick={e => e.stopPropagation()} data-testid="full-camera-edit-panel">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Edit Info Aset</h3>
              <button type="button" onClick={() => setEditOpen(false)} aria-label="Tutup panel edit"
                className="w-8 h-8 rounded-full inline-flex items-center justify-center text-muted-foreground hover:bg-muted">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {EDIT_FIELDS.map(f => (
                <div key={f.name} className={`space-y-0.5 ${f.full ? "col-span-2" : ""}`}>
                  <label className="text-[11px] text-muted-foreground">{f.label}{f.readOnly ? " (otomatis)" : ""}</label>
                  <input
                    value={formData?.[f.name] || ""}
                    onChange={e => onSetField(f.name, e.target.value)}
                    readOnly={f.readOnly}
                    data-testid={`full-camera-edit-${f.name}`}
                    className={`w-full h-9 px-2.5 rounded-lg border border-border text-sm text-foreground ${f.readOnly ? "bg-muted text-muted-foreground" : "bg-background"}`}
                  />
                </div>
              ))}
            </div>
            <button type="button" onClick={() => setEditOpen(false)} data-testid="full-camera-edit-done"
              className="w-full h-11 rounded-lg bg-blue-600 text-white text-sm font-semibold flex items-center justify-center gap-1.5">
              <Check className="w-4 h-4" />Selesai
            </button>
          </div>
        </div>
      )}
    </div>,
    document.body
  );
});

FullCameraSheet.displayName = "FullCameraSheet";
export default FullCameraSheet;
