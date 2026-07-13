import React, { memo, useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  X, Camera, MapPin, Clock, Pencil, SwitchCamera, Loader2, Check, Trash2,
  ChevronLeft, ChevronRight, RotateCcw, AlertTriangle, Zap, ZapOff, Sun, ScanLine,
} from "lucide-react";
import { toast } from "sonner";
import { useBackGuard } from "../../hooks/useBackGuard";
import { extractScannedCode } from "./QrScanButton";
import { haptic } from "../../lib/haptics";
import {
  STATUS_OPTIONS, CONDITION_OPTIONS, SUB_KLASIFIKASI_OPTIONS,
  PENGGUNA_MELEKAT_OPTIONS, PENGGUNA_NAME_LABELS, OPERASIONAL_JENIS_OPTIONS,
} from "./InventoryFieldSheet";

// Chip pilihan sekali-ketuk (versi ringkas SegButton lembar inventarisasi)
const CamChip = ({ selected, cls, onClick, children, testId }) => (
  <button type="button" onClick={onClick} aria-pressed={selected} data-testid={testId}
    className={`h-10 rounded-lg border text-[11px] font-semibold px-1 text-center leading-tight transition-colors ${selected ? cls : "bg-background border-border text-foreground/80"}`}>
    {children}
  </button>
);

const camSelectCls = "w-full h-9 px-2 rounded-lg border border-border bg-background text-sm text-foreground";
const camInputCls = "w-full h-9 px-2.5 rounded-lg border border-border bg-background text-sm text-foreground";

// Pesan error kamera per jenis (fungsi murni di luar komponen agar tidak
// menjadi dependency effect).
function cameraErrMsg(err) {
  switch (err?.name) {
    case "NotAllowedError": case "SecurityError": return "Akses kamera ditolak. Izinkan kamera di pengaturan situs, lalu Coba Lagi.";
    case "NotFoundError": case "OverconstrainedError": return "Kamera tidak ditemukan di perangkat ini.";
    case "NotReadableError": case "AbortError": return "Kamera sedang dipakai aplikasi lain. Tutup aplikasi itu lalu Coba Lagi.";
    default: return "Gagal membuka kamera. Coba Lagi atau gunakan tombol Galeri/Kamera biasa.";
  }
}

// Preset perbesaran (zoom) dari kemampuan track kamera — mis. 1×, 2×, 5×.
function makeZoomPresets(caps) {
  if (!caps || !(Number(caps.max) > Number(caps.min))) return [];
  const min = Number(caps.min), max = Number(caps.max);
  const cand = [0.5, 1, 2, 3, 5, 10].filter((z) => z >= min - 1e-6 && z <= max + 1e-6);
  const out = Array.from(new Set([Number(min.toFixed(2)), ...cand])).sort((a, b) => a - b);
  return out.slice(0, 6);
}
const fmtZoom = (z) => (Number.isInteger(z) ? String(z) : z.toFixed(1).replace(/\.0$/, ""));

// Batas gestur kecerahan (filter CSS di pratinjau + dibakar saat memotret).
const BRIGHT_MIN = 0.4, BRIGHT_MAX = 2.0;
// canvas 2d `filter` tidak didukung Safari lama — deteksi sekali di module.
const CANVAS_FILTER_OK = (() => {
  try {
    const c = document.createElement("canvas").getContext("2d");
    // Cek SEBELUM assignment: pada WebKit lama (iOS <= 17) `filter` bukan IDL
    // attribute — assignment hanya membuat expando yang readback-nya lolos.
    return typeof c.filter === "string";
  } catch { return false; }
})();

// Bakar kecerahan ke frame canvas TANPA ctx.filter (fallback Safari):
// terang → overlay putih mode 'screen'; gelap → overlay abu mode 'multiply'.
function bakeBrightnessFallback(ctx, w, h, b) {
  ctx.save();
  if (b > 1) {
    ctx.globalCompositeOperation = "screen";
    ctx.fillStyle = `rgba(255,255,255,${Math.min(0.85, (b - 1) * 0.55)})`;
  } else {
    ctx.globalCompositeOperation = "multiply";
    const v = Math.round(255 * Math.max(0, b));
    ctx.fillStyle = `rgb(${v},${v},${v})`;
  }
  ctx.fillRect(0, 0, w, h);
  ctx.restore();
}

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
  hasMoreToLoad = false,
  savedCount = 0,
  busy = false,
  onClose,
  onCapture,       // (dataUrl) => void — foto baru (sudah distempel + terkompresi)
  onRemovePhoto,   // (index) => void
  onSetField,      // (name, value) => void — edit info aset dari panel
  onGpsFix,        // ({lat, lng}) => void — tiap fix GPS baru (update form + cache)
  onSaveAndNew,    // () => void — simpan aset ini lalu siapkan aset baru
  onReviewSaved,   // () => void — simpan lalu tinjau aset tersimpan sebelumnya
  onNavigate,      // (dir) => void — 'prev' | 'next' (mode edit aset yang sudah ada)
  preparing = false, // aset baru sedang disiapkan → overlay loading ringan
  onScanAsset,     // (code) => void — QR aset terdeteksi (mode edit inventarisasi)
  onSaveAndScanNext, // () => void — simpan aset ini lalu langsung scan QR berikutnya
  autoScan = false, // buka kamera langsung dalam keadaan memindai QR
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const gpsRef = useRef(null); // fix terakhir utk stempel foto (hindari re-render race)
  // onClose disimpan di ref agar effect kamera TIDAK bergantung padanya (induk
  // mengirim arrow baru tiap render, dan GPS live memicu render ~1x/detik →
  // dulu ini me-restart getUserMedia terus-menerus / preview berkedip).
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; });

  const [ready, setReady] = useState(false);
  const [starting, setStarting] = useState(true);
  const [facing, setFacing] = useState("environment");
  const [now, setNow] = useState(() => new Date());
  const [gps, setGps] = useState(null); // {lat, lng, accuracy}
  const [gpsDenied, setGpsDenied] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [confirmIdx, setConfirmIdx] = useState(null); // index foto yang mau dihapus
  const [camError, setCamError] = useState(null); // { name, msg } bila gagal buka kamera
  const [suspended, setSuspended] = useState(false); // track berhenti (background/lock/direbut app lain)
  const [camNonce, setCamNonce] = useState(0); // bump utk coba-sambung-ulang kamera
  const [gpsNonce, setGpsNonce] = useState(0); // bump utk coba-lagi GPS
  // Zoom sesuai spek kamera perangkat (mis. 0.5× / 1× / 2× / 5× — tergantung
  // rentang zoom yang diekspos browser; di banyak Android nilai <1 = ultrawide).
  const [zoomCaps, setZoomCaps] = useState(null); // { min, max, step } bila track mendukung zoom
  const [zoom, setZoom] = useState(1);
  // Senter/flash (torch) — hanya bila kamera aktif mengeksposnya.
  const [torchSupported, setTorchSupported] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const torchOnRef = useRef(false); // nilai terakhir utk re-apply saat kamera restart
  // Kecerahan via gestur: sentuh area foto → indikator muncul; tahan & geser
  // atas/bawah → atur. Diterapkan sebagai filter CSS di pratinjau dan dibakar
  // ke hasil foto saat memotret.
  const [brightness, setBrightness] = useState(1);
  const brightnessRef = useRef(1);
  const [brightUI, setBrightUI] = useState(false);
  const brightTimerRef = useRef(null);
  const brightDragRef = useRef(null); // { startY, startB, moved }
  // Scan QR aset (mode edit inventarisasi): pakai stream kamera yang SAMA.
  const scanSupported = typeof window !== "undefined" && "BarcodeDetector" in window;
  const [scanActive, setScanActive] = useState(() => !!(autoScan && scanSupported && onScanAsset));
  const scanDetectorRef = useRef(null);

  const supported = typeof navigator !== "undefined" && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);

  // Back HP: tutup scanner/panel edit dulu, lalu konfirmasi hapus, lalu kamera.
  useBackGuard(useCallback(() => {
    if (editOpen) { setEditOpen(false); return; }
    if (confirmIdx !== null) { setConfirmIdx(null); return; }
    if (scanActive) { setScanActive(false); return; }
    onCloseRef.current?.();
  }, [editOpen, confirmIdx, scanActive]));

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

  // GPS live: watchPosition dengan maximumAge:0 — terus ter-update tanpa refresh.
  // Error izin (code 1) ditandai agar surveyor diberi tahu + tombol Coba Lagi.
  useEffect(() => {
    if (!navigator.geolocation) { setGpsDenied(true); return undefined; }
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const fix = {
          lat: pos.coords.latitude.toFixed(6),
          lng: pos.coords.longitude.toFixed(6),
          accuracy: Number.isFinite(pos.coords.accuracy) ? Math.round(pos.coords.accuracy) : null,
        };
        gpsRef.current = fix;
        setGps(fix);
        setGpsDenied(false);
        try { onGpsFix?.(fix); } catch { /* update form tidak boleh mematikan kamera */ }
      },
      (err) => { if (err && err.code === 1) setGpsDenied(true); },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [onGpsFix, gpsNonce]);

  // Nyalakan kamera (restart hanya saat flip kamera / coba-sambung-ulang — TIDAK
  // pada tiap render). Menangani: fitur tak didukung, izin ditolak, kamera
  // direbut app lain, dan track yang berhenti (background/lock) tanpa menutup
  // sheet secara diam-diam.
  useEffect(() => {
    if (!supported) { setCamError({ name: "unsupported", msg: "Kamera langsung tidak didukung di browser/perangkat ini. Gunakan tombol Galeri/Kamera biasa." }); setStarting(false); return undefined; }
    let cancelled = false;
    let track = null;
    let onEnded = null;
    setReady(false); setStarting(true); setCamError(null); setSuspended(false);
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        });
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        track = stream.getVideoTracks()[0];
        if (track) {
          // Track berhenti (screen lock / app background / direbut app lain):
          // tandai suspended supaya rana dinonaktifkan & tak memotret frame beku.
          onEnded = () => { if (!cancelled) { setReady(false); setSuspended(true); } };
          track.addEventListener("ended", onEnded);
          // Baca kemampuan zoom kamera aktif.
          try {
            const caps = track.getCapabilities?.() || {};
            if (caps.zoom && Number(caps.zoom.max) > Number(caps.zoom.min)) {
              setZoomCaps({ min: Number(caps.zoom.min), max: Number(caps.zoom.max), step: Number(caps.zoom.step) || 0.1 });
              setZoom(Number(track.getSettings?.().zoom) || Number(caps.zoom.min));
            } else setZoomCaps(null);
          } catch { setZoomCaps(null); }
          // Senter/flash: tampilkan tombol hanya bila track mendukung torch,
          // dan pulihkan keadaan senter setelah kamera restart (flip/reconnect).
          try {
            const caps = track.getCapabilities?.() || {};
            const hasTorch = !!caps.torch;
            setTorchSupported(hasTorch);
            if (hasTorch && torchOnRef.current) {
              track.applyConstraints({ advanced: [{ torch: true }] })
                .then(() => setTorchOn(true))
                .catch(() => setTorchOn(false)); // keinginan (ref) dipertahankan
            } else if (!hasTorch) {
              // Kamera ini tak punya torch (mis. kamera depan) — matikan UI saja,
              // keinginan tetap tersimpan agar flip balik menyalakannya lagi.
              setTorchOn(false);
            }
          } catch { setTorchSupported(false); }
        }
        const video = videoRef.current;
        if (video) { video.srcObject = stream; await video.play().catch(() => {}); }
        setReady(true);
      } catch (err) {
        if (!cancelled) setCamError({ name: err?.name || "error", msg: cameraErrMsg(err) }); // JANGAN auto-close
      } finally {
        if (!cancelled) setStarting(false);
      }
    })();
    return () => {
      cancelled = true;
      if (track && onEnded) track.removeEventListener("ended", onEnded);
      if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    };
  }, [facing, camNonce, supported]);

  // Terapkan zoom ke track aktif (perbesaran optik/digital sesuai kemampuan).
  const applyZoom = useCallback(async (z) => {
    const track = streamRef.current?.getVideoTracks?.()[0];
    if (!track || !track.applyConstraints) return;
    try { await track.applyConstraints({ advanced: [{ zoom: z }] }); setZoom(z); } catch { /* tak didukung */ }
  }, []);

  const zoomPresets = makeZoomPresets(zoomCaps);

  // Nyalakan/matikan senter (torch) pada track aktif.
  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks?.()[0];
    if (!track || !track.applyConstraints) return;
    const next = !torchOnRef.current;
    try {
      await track.applyConstraints({ advanced: [{ torch: next }] });
      torchOnRef.current = next;
      setTorchOn(next);
    } catch { toast.error("Senter tidak didukung kamera ini"); }
  }, []);

  // — Gestur kecerahan: sentuh area foto → indikator; tahan & geser vertikal —
  const bumpBrightUI = useCallback(() => {
    setBrightUI(true);
    if (brightTimerRef.current) clearTimeout(brightTimerRef.current);
    brightTimerRef.current = setTimeout(() => setBrightUI(false), 1600);
  }, []);
  useEffect(() => () => { if (brightTimerRef.current) clearTimeout(brightTimerRef.current); }, []);

  const setBright = useCallback((b) => {
    const v = Math.min(BRIGHT_MAX, Math.max(BRIGHT_MIN, b));
    brightnessRef.current = v;
    setBrightness(v);
  }, []);

  const onBrightPointerDown = useCallback((e) => {
    // Hanya jari/kursor utama; jangan ganggu pinch dua jari.
    if (!e.isPrimary) { brightDragRef.current = null; return; }
    brightDragRef.current = { startY: e.clientY, startB: brightnessRef.current, moved: false };
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* opsional */ }
    bumpBrightUI();
  }, [bumpBrightUI]);

  const onBrightPointerMove = useCallback((e) => {
    const drag = brightDragRef.current;
    if (!drag) return;
    const dy = drag.startY - e.clientY; // geser ke atas = lebih terang
    if (Math.abs(dy) > 6) drag.moved = true;
    if (drag.moved) {
      setBright(drag.startB + dy / 220);
      bumpBrightUI();
    }
  }, [setBright, bumpBrightUI]);

  // ── Tap-to-focus: ketuk (bukan geser) di area kamera → fokus di titik itu ──
  const [focusRipple, setFocusRipple] = useState(null); // { x, y, id } koordinat DALAM video
  const focusTimerRef = useRef(null);
  const focusIdRef = useRef(0);
  const tapFocus = useCallback((clientX, clientY) => {
    const el = videoRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const x = clientX - rect.left;
    const y = clientY - rect.top;
    focusIdRef.current += 1;
    setFocusRipple({ x, y, id: focusIdRef.current });
    if (focusTimerRef.current) clearTimeout(focusTimerRef.current);
    focusTimerRef.current = setTimeout(() => setFocusRipple(null), 700);
    // Best-effort: minta kamera fokus ke titik (0..1). Banyak browser mengabaikan
    // pointsOfInterest — efek visual tetap memberi umpan balik ketukan.
    const track = streamRef.current?.getVideoTracks?.()[0];
    if (track?.applyConstraints) {
      const nx = Math.min(1, Math.max(0, x / rect.width));
      const ny = Math.min(1, Math.max(0, y / rect.height));
      track.applyConstraints({ advanced: [{ focusMode: "single-shot", pointsOfInterest: [{ x: nx, y: ny }] }] })
        .catch(() => {});
    }
  }, []);

  const lastDragMovedRef = useRef(false);
  const onBrightPointerUp = useCallback((e) => {
    const moved = !!brightDragRef.current?.moved;
    lastDragMovedRef.current = moved;
    brightDragRef.current = null;
    // Ketukan cepat (tanpa geser) & benar-benar dilepas (bukan cancel) → fokus.
    if (!moved && e && e.type === "pointerup" && e.isPrimary !== false) tapFocus(e.clientX, e.clientY);
  }, [tapFocus]);
  const resetBright = useCallback(() => {
    // Dua drag cepat memicu dblclick sintetis — jangan hapus hasil atur barusan.
    if (lastDragMovedRef.current) { lastDragMovedRef.current = false; return; }
    setBright(1); bumpBrightUI();
  }, [setBright, bumpBrightUI]);

  // Deteksi QR pada stream kamera aktif selama mode pemindaian menyala.
  // Dijeda saat panel Edit Info / konfirmasi hapus terbuka — QR liar di rak
  // tidak boleh menyimpan form setengah-terketik & berpindah aset diam-diam.
  useEffect(() => {
    if (!scanActive || !scanSupported || !onScanAsset) return undefined;
    if (editOpen || confirmIdx !== null) return undefined;
    let stopped = false;
    let detecting = false;
    (async () => {
      try {
        let formats = ["qr_code", "code_128", "code_39"];
        try {
          const avail = await window.BarcodeDetector.getSupportedFormats();
          formats = formats.filter((f) => avail.includes(f));
        } catch { /* pakai daftar default */ }
        scanDetectorRef.current = new window.BarcodeDetector(formats.length ? { formats } : undefined);
      } catch { if (!stopped) setScanActive(false); }
    })();
    const timer = setInterval(async () => {
      const video = videoRef.current;
      if (stopped || detecting || !scanDetectorRef.current || !video || video.readyState < 2) return;
      detecting = true;
      try {
        const codes = await scanDetectorRef.current.detect(video);
        // Batal Scan / unmount saat detect() masih terbang → jangan tembak.
        if (stopped) return;
        if (codes && codes.length > 0) {
          const code = extractScannedCode(codes[0].rawValue || "");
          stopped = true;
          setScanActive(false);
          if (code) onScanAsset(code);
          else toast.error("QR tidak berisi kode yang dikenali");
        }
      } catch { /* frame belum siap — coba lagi di tick berikutnya */ }
      finally { detecting = false; }
    }, 300);
    return () => { stopped = true; clearInterval(timer); };
  }, [scanActive, scanSupported, onScanAsset, editOpen, confirmIdx]);

  const startScan = useCallback(() => {
    if (!scanSupported) { toast.error("Scanner QR tidak didukung browser ini"); return; }
    setScanActive(true);
  }, [scanSupported]);

  // Kembali ke depan (unlock/foreground): kalau track sudah mati, sambung ulang;
  // kalau masih hidup, cukup play() lagi.
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState !== "visible") return;
      const tr = streamRef.current?.getVideoTracks?.()[0];
      if (!tr || tr.readyState !== "live") setCamNonce((n) => n + 1);
      else { setSuspended(false); videoRef.current?.play?.().catch(() => {}); }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const fmtTanggal = now.toLocaleDateString("id-ID", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
  const fmtJam = now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  // Kontrol alur beruntun
  const maxReached = photos.length >= maxPhotos;
  // Getar berbeda per aksi (umpan balik taktil tanpa melihat layar): simpan =
  // getar mantap; pindah aset = tik (maju tunggal, mundur ganda → arah terasa
  // beda). haptic() best-effort (diabaikan bila perangkat/preferensi tak dukung).
  const saveAndNew = useCallback(() => { haptic("save"); onSaveAndNew?.(); }, [onSaveAndNew]);
  const saveAndScanNext = useCallback(() => { haptic("save"); onSaveAndScanNext?.(); }, [onSaveAndScanNext]);
  const navHaptic = useCallback((dir) => { haptic(dir === "next" ? "navNext" : "navPrev"); onNavigate?.(dir); }, [onNavigate]);
  const backAction = isEditing ? () => navHaptic("prev") : onReviewSaved;
  const canBack = isEditing ? assetIndex > 0 : (!!onReviewSaved && totalAssetsInView > 0);
  // Lanjut bila masih ada aset di daftar, ATAU masih ada halaman berikutnya
  // yang bisa dimuat (ritme input kamera lintas halaman tak terputus).
  const canNext = isEditing && assetIndex >= 0
    && (assetIndex < totalAssetsInView - 1 || hasMoreToLoad);
  // Nama Aset WAJIB diisi sebelum memotret (rana dikunci selama kosong).
  const nameFilled = !!(formData?.asset_name || "").trim();

  // Ambil foto: gambar frame video ke canvas, stempel watermark ala Timemark,
  // hasilkan JPEG (sisi terpanjang ≤1920, q0.85 — setara pipeline kompresi form).
  const capture = useCallback(() => {
    const video = videoRef.current;
    // Track harus 'live' — cegah memotret frame BEKU saat kamera terputus
    // (background/lock) padahal watermark akan mencap waktu & GPS terbaru.
    const track = streamRef.current?.getVideoTracks?.()[0];
    if (suspended || !track || track.readyState !== "live") {
      toast.error("Kamera terputus — menyambungkan ulang…");
      setCamNonce((n) => n + 1);
      return;
    }
    if (!video || video.readyState < 2) { toast.error("Kamera belum siap"); return; }
    if (photos.length >= maxPhotos) { toast.error(`Maks ${maxPhotos} foto`); return; }
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) { toast.error("Kamera belum siap"); return; }
    const scale = Math.min(1, 1920 / Math.max(vw, vh));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(vw * scale);
    canvas.height = Math.round(vh * scale);
    const ctx = canvas.getContext("2d");
    // Bakar kecerahan gestur ke hasil foto agar sama dengan pratinjau.
    const bright = brightnessRef.current;
    if (bright !== 1 && CANVAS_FILTER_OK) ctx.filter = `brightness(${bright})`;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    ctx.filter = "none";
    if (bright !== 1 && !CANVAS_FILTER_OK) bakeBrightnessFallback(ctx, canvas.width, canvas.height, bright);

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
    haptic("shutter"); // tik ringan saat foto benar-benar terambil
    onCapture(dataUrl);
  }, [photos.length, maxPhotos, formData, onCapture, suspended]);

  // Getar SEKALI saat akurasi GPS mencapai SANGAT presisi (≤4 m) — "kunci
  // akurat" terasa tanpa harus melihat cincin. Rising-edge via ref agar tidak
  // bergetar terus-menerus selama tetap ≤4 m.
  const gpsExcellentRef = useRef(false);
  useEffect(() => {
    const acc = gps?.accuracy;
    const excellent = typeof acc === "number" && acc <= 4;
    if (excellent && !gpsExcellentRef.current) haptic("gpsLock");
    gpsExcellentRef.current = excellent;
  }, [gps?.accuracy]);

  // Form ringkas & padat: field penting saja, 2 kolom. Kode Aset & NUP
  // read-only (sudah distandby-kan ke kategori dummy + NUP otomatis).
  // Mode edit menambah field identifikasi (kode register & serial number)
  // untuk alur koreksi cepat via scan QR.
  const EDIT_FIELDS = [
    { name: "asset_name", label: "Nama Aset", full: true, required: true },
    { name: "asset_code", label: "Kode Aset", readOnly: true },
    { name: "NUP", label: "NUP", readOnly: true },
    ...(isEditing ? [
      { name: "kode_register", label: "Kode Register" },
      { name: "serial_number", label: "Serial Number" },
    ] : []),
    { name: "location", label: "Lokasi" },
    { name: "user", label: "Pengguna" },
    { name: "notes", label: "Catatan", full: true },
  ];
  // Mode scan-edit inventarisasi: "Pengguna" pindah ke seksi Pengguna Barang
  // (dengan melekat-ke + NIP/NIK) — jangan tampil dobel di grid identitas.
  const visibleEditFields = (isEditing && onScanAsset)
    ? EDIT_FIELDS.filter(f => f.name !== "user")
    : EDIT_FIELDS;

  // ── Gating akurasi GPS: jaga agar koordinat range lebar tak terekam ──
  // Toleransi dilonggarkan untuk mempercepat alur lapangan: koordinat boleh
  // direkam hingga ≤8 m. Cincin: HIJAU ≤6 m (baik), KUNING 6–8 m (masih boleh —
  // dipercepat), MERAH >8 m (rana DIKUNCI + diredupkan). ≤4 m = SANGAT AKURAT
  // (jarang) → effect lebih heboh. GPS mati/ditolak → tak menggate. Masih
  // mencari fix (belum ada akurasi) → tahan rana sampai fix akurat didapat.
  const gpsAcc = gps?.accuracy;
  const accExcellent = typeof gpsAcc === "number" && gpsAcc <= 4;              // sangat akurat (jarang)
  const accGood = typeof gpsAcc === "number" && gpsAcc <= 6;                   // hijau (baik)
  const accFair = typeof gpsAcc === "number" && gpsAcc > 6 && gpsAcc <= 8;     // kuning (masih boleh)
  const accOk = typeof gpsAcc === "number" && gpsAcc <= 8;                     // ≤8 m → boleh potret
  const accPoor = typeof gpsAcc === "number" && gpsAcc > 8;                    // >8 m → rana dikunci
  const gpsBlocked = !gpsDenied && (gpsAcc == null || gpsAcc > 8);
  const ringColor = gpsDenied ? null
    : accGood ? "#22c55e" : accFair ? "#eab308" : accPoor ? "#ef4444" : "#64748b";

  return createPortal(
    <div className="fixed inset-0 z-[120] bg-black flex flex-col" role="dialog" aria-modal="true" aria-label="Mode Kamera Penuh" data-testid="full-camera-sheet">
      {/* Pratinjau kamera (filter kecerahan mengikuti gestur) */}
      <video ref={videoRef} className="absolute inset-0 w-full h-full object-cover" playsInline muted
        style={brightness !== 1 ? { filter: `brightness(${brightness})` } : undefined} />

      {/* Cincin akurasi GPS di tepi area kamera — hijau ≤6 m, kuning 6–8 m
          (keduanya berkedip & boleh potret), merah >8 m (rana dikunci). ≤4 m:
          cincin lebih tebal + cahaya dalam (heboh). Tak tampil bila GPS mati. */}
      {ringColor && (
        <div aria-hidden="true" data-testid="full-camera-gps-ring"
          className={`absolute inset-0 z-[6] pointer-events-none ${accOk ? "animate-pulse" : ""}`}
          style={{ boxShadow: accExcellent
            ? "inset 0 0 0 6px #22c55e, inset 0 0 48px rgba(34,197,94,0.55)"
            : `inset 0 0 0 4px ${ringColor}` }} />
      )}
      {/* ≤4 m SANGAT AKURAT (jarang): cincin ping kedua + badge ajakan segera
          memotret — dorong pengguna menangkap titik paling presisi. */}
      {accExcellent && (
        <>
          <div aria-hidden="true" data-testid="full-camera-gps-excellent-ping"
            className="absolute inset-3 z-[6] pointer-events-none rounded-3xl border-4 border-emerald-400/80 animate-ping" />
          <div className="absolute top-16 left-1/2 -translate-x-1/2 z-[8] pointer-events-none px-1">
            <span className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-emerald-500 text-white text-xs font-extrabold shadow-lg animate-bounce whitespace-nowrap">
              🎯 Akurasi ±{gpsAcc} m — segera potret!
            </span>
          </div>
        </>
      )}
      {/* Reticle tap-to-focus: menyebar TEPAT dari titik sentuh lalu memudar.
          Anchor div tanpa transform di (x,y); cincin & titik dipusatkan via
          margin negatif (bukan -translate) karena `animate-ping` menimpa
          `transform` → dulu cincin lompat ke pojok kiri-atas & tak center. */}
      {focusRipple && (
        <div key={focusRipple.id} aria-hidden="true" data-testid="full-camera-focus-ring"
          className="absolute z-[7] pointer-events-none" style={{ left: focusRipple.x, top: focusRipple.y }}>
          <span className="absolute -ml-8 -mt-8 w-16 h-16 rounded-full border-2 border-white/95 animate-ping" />
          <span className="absolute -ml-1 -mt-1 w-2 h-2 rounded-full bg-white/95" />
        </div>
      )}

      {/* Lapisan gestur kecerahan: sentuh → indikator; tahan & geser atas/bawah
          → atur; ketuk dua kali → kembali normal. Di bawah overlay kontrol. */}
      {ready && !camError && !suspended && (
        <div
          className="absolute inset-0 z-[5]"
          style={{ touchAction: "none" }}
          data-testid="full-camera-bright-layer"
          onPointerDown={onBrightPointerDown}
          onPointerMove={onBrightPointerMove}
          onPointerUp={onBrightPointerUp}
          onPointerCancel={onBrightPointerUp}
          onDoubleClick={resetBright}
        />
      )}

      {/* Indikator kecerahan (muncul saat gestur aktif) */}
      {brightUI && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2 z-[8] flex flex-col items-center gap-1.5 pointer-events-none" data-testid="full-camera-bright-ui">
          <Sun className="w-4 h-4 text-amber-300 drop-shadow" />
          <div className="w-1.5 h-40 rounded-full bg-white/25 overflow-hidden flex flex-col justify-end">
            <div className="w-full bg-amber-300 rounded-full"
              style={{ height: `${((brightness - BRIGHT_MIN) / (BRIGHT_MAX - BRIGHT_MIN)) * 100}%` }} />
          </div>
          <span className="text-[10px] font-bold text-white drop-shadow tabular-nums">{Math.round(brightness * 100)}%</span>
        </div>
      )}
      {(starting || (!ready && !camError)) && (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-white/80 gap-2" role="status" aria-live="polite">
          <Loader2 className="w-8 h-8 animate-spin" />
          <span className="text-xs">Menyalakan kamera…</span>
        </div>
      )}

      {/* Gagal buka kamera: pesan jelas + Coba Lagi + Tutup (jangan auto-close) */}
      {camError && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-4 px-8 text-center bg-black/85" data-testid="full-camera-error">
          <AlertTriangle className="w-10 h-10 text-amber-400" />
          <p className="text-sm text-white/90 max-w-xs">{camError.msg}</p>
          <div className="flex items-center gap-2">
            {supported && (
              <button type="button" onClick={() => { setCamError(null); setCamNonce((n) => n + 1); }}
                data-testid="full-camera-retry"
                className="h-11 px-4 rounded-lg bg-blue-600 text-white text-sm font-semibold flex items-center gap-1.5">
                <RotateCcw className="w-4 h-4" />Coba Lagi
              </button>
            )}
            <button type="button" onClick={() => onCloseRef.current?.()}
              className="h-11 px-4 rounded-lg bg-white/15 text-white text-sm font-medium">Tutup</button>
          </div>
        </div>
      )}

      {/* Kamera terputus (background/lock/direbut app lain): jangan memotret frame beku */}
      {suspended && !camError && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 px-8 text-center bg-black/80" data-testid="full-camera-suspended">
          <Camera className="w-9 h-9 text-white/70" />
          <p className="text-sm text-white/90">Kamera terputus. Sambungkan kembali untuk melanjutkan.</p>
          <button type="button" onClick={() => { setSuspended(false); setCamNonce((n) => n + 1); }}
            className="h-11 px-4 rounded-lg bg-blue-600 text-white text-sm font-semibold flex items-center gap-1.5">
            <RotateCcw className="w-4 h-4" />Sambungkan
          </button>
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
              <MapPin className={`w-3.5 h-3.5 flex-shrink-0 ${gps ? "text-emerald-400" : gpsDenied ? "text-amber-400" : "text-white/50"}`} />
              {gps ? `${gps.lat}, ${gps.lng}${gps.accuracy != null ? ` (±${gps.accuracy} m)` : ""}`
                : gpsDenied ? <span className="text-amber-300">GPS mati/ditolak</span> : "Mencari sinyal GPS…"}
              {!gps && gpsDenied && (
                <button type="button" onClick={() => { setGpsDenied(false); setGpsNonce((n) => n + 1); }}
                  data-testid="full-camera-gps-retry"
                  className="ml-1 px-1.5 py-0.5 rounded bg-white/15 text-[10px] font-sans font-medium">Coba lagi</button>
              )}
            </div>
            {/* Info aset — TIAP field satu baris (nama, kategori, kode+NUP,
                lokasi). Teks yang tak muat boleh turun ke baris ke-2, lalu
                baru dipotong "…" (line-clamp-2). */}
            <div className="text-[11px] text-white/90 leading-tight space-y-0.5">
              <div className="font-semibold line-clamp-2">{formData?.asset_name || "Aset Baru"}</div>
              {formData?.category && (
                <div className="text-white/80 line-clamp-2">
                  <span className="text-white/50">Kategori:</span> {formData.category}
                </div>
              )}
              {(formData?.asset_code || formData?.NUP) && (
                <div className="font-mono text-white/80 line-clamp-2">
                  {formData?.asset_code || "—"}{formData?.NUP ? ` · NUP ${formData.NUP}` : ""}
                </div>
              )}
              {formData?.location && (
                <div className="text-white/80 line-clamp-2">
                  <span className="text-white/50">Lokasi:</span> {formData.location}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {!!onScanAsset && scanSupported && (
              <button type="button" onClick={startScan} aria-label="Scan QR aset" data-testid="full-camera-scan"
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${scanActive ? "bg-emerald-500 text-white" : "bg-black/50 text-white"}`}>
                <ScanLine className="w-5 h-5" />
              </button>
            )}
            {torchSupported && (
              <button type="button" onClick={toggleTorch} aria-label={torchOn ? "Matikan flash" : "Nyalakan flash"}
                aria-pressed={torchOn} data-testid="full-camera-torch"
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${torchOn ? "bg-amber-400 text-black" : "bg-black/50 text-white"}`}>
                {torchOn ? <Zap className="w-5 h-5" /> : <ZapOff className="w-5 h-5" />}
              </button>
            )}
            <button type="button" onClick={onClose} aria-label="Tutup kamera" data-testid="full-camera-close"
              className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1" />

      {/* ── Overlay bawah: thumbnail + kontrol ── */}
      <div className="relative z-10 bg-gradient-to-t from-black/80 to-transparent pt-6 pb-4 px-3 space-y-3">
        {photos.length > 0 && !scanActive && (
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
        {/* Zoom sesuai spek kamera (0.5× / 1× / 2× dst.). Tampil hanya bila
            perangkat mengekspos rentang zoom. */}
        {zoomPresets.length >= 2 && (
          <div className="flex items-center justify-center gap-1.5 flex-wrap" data-testid="full-camera-lensbar">
            {zoomPresets.map((z) => (
              <button key={z} type="button" onClick={() => applyZoom(z)}
                data-testid={`full-camera-zoom-${z}`}
                className={`h-8 min-w-[42px] px-2 rounded-full text-[11px] font-bold transition-colors ${Math.abs((zoom || 1) - z) < 0.05 ? "bg-amber-400 text-black" : "bg-white/20 text-white hover:bg-white/30"}`}>
                {fmtZoom(z)}×
              </button>
            ))}
          </div>
        )}
        {/* Wajib isi Nama Aset dulu sebelum memotret — rana dikunci selama kosong. */}
        {!nameFilled && !scanActive && (
          <button type="button" onClick={() => setEditOpen(true)} data-testid="full-camera-need-name"
            className="mx-auto flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-amber-400/90 text-black text-[11px] font-semibold">
            <AlertTriangle className="w-3.5 h-3.5" />Isi Nama Aset (<span className="text-red-700">*</span>) dulu untuk memotret
          </button>
        )}
        {scanActive ? (
          /* Mode pindai: kontrol rana disembunyikan agar tidak tumpang tindih */
          <div className="space-y-2" data-testid="full-camera-scan-controls">
            <div className="text-center space-y-0.5">
              <p className="text-white text-sm font-semibold drop-shadow">Arahkan ke QR/barcode stiker aset</p>
              <p className="text-white/70 text-[11px] drop-shadow">Aset yang cocok langsung terbuka untuk diedit</p>
            </div>
            <button type="button" onClick={() => setScanActive(false)} data-testid="full-camera-scan-cancel"
              className="w-full h-12 rounded-xl bg-white/20 backdrop-blur text-white text-sm font-bold">
              Batal Scan
            </button>
          </div>
        ) : (
        <div className="flex items-center justify-between">
          <button type="button" onClick={() => setEditOpen(true)}
            data-testid="full-camera-edit-btn"
            className={`flex flex-col items-center gap-1 text-[10px] font-medium w-16 ${!nameFilled ? "text-amber-300" : "text-white/90"}`}>
            <span className={`w-11 h-11 rounded-full flex items-center justify-center ${!nameFilled ? "bg-amber-400/30 ring-2 ring-amber-300 animate-pulse" : "bg-white/15"}`}><Pencil className="w-5 h-5" /></span>
            Edit Info{!nameFilled ? " *" : ""}
          </button>
          <button type="button" onClick={capture} disabled={!ready || photos.length >= maxPhotos || !nameFilled || gpsBlocked}
            aria-label="Ambil foto" data-testid="full-camera-shutter"
            title={gpsBlocked ? (gpsAcc == null ? "Menunggu sinyal GPS akurat…" : `Akurasi GPS ±${gpsAcc} m terlalu lebar (maks ±8 m)`) : undefined}
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
        )}

        {/* Alur beruntun: simpan & aset baru + maju/mundur antar aset tersimpan.
            Ditonjolkan saat foto sudah penuh (maks). */}
        {!scanActive && (
        <div className={`grid grid-cols-3 gap-2 ${maxReached ? "ring-1 ring-white/40 rounded-xl p-1" : ""}`}>
          <button type="button" onClick={backAction} disabled={!canBack || busy} data-testid="full-camera-prev"
            className="h-11 rounded-lg bg-white/15 text-white text-xs font-semibold flex items-center justify-center gap-1 disabled:opacity-30 disabled:pointer-events-none">
            <ChevronLeft className="w-4 h-4" />Sebelumnya
          </button>
          {isEditing && onScanAsset && onSaveAndScanNext ? (
            /* Alur lapangan scan-edit: simpan lalu LANGSUNG buka scanner lagi */
            <button type="button" onClick={() => { saveAndScanNext(); setScanActive(true); }} disabled={busy}
              data-testid="full-camera-save-scan"
              className="h-11 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1 transition-colors disabled:opacity-60 disabled:pointer-events-none">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScanLine className="w-4 h-4" />}Simpan & Scan
            </button>
          ) : (
            <button type="button" onClick={saveAndNew} disabled={busy} data-testid="full-camera-savenew"
              className="h-11 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center justify-center gap-1 transition-colors disabled:opacity-60 disabled:pointer-events-none">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}Simpan & Baru
            </button>
          )}
          <button type="button" onClick={() => navHaptic("next")} disabled={!canNext || busy} data-testid="full-camera-next"
            className="h-11 rounded-lg bg-white/15 text-white text-xs font-semibold flex items-center justify-center gap-1 disabled:opacity-30 disabled:pointer-events-none">
            Berikutnya<ChevronRight className="w-4 h-4" />
          </button>
        </div>
        )}
        {isEditing && onScanAsset && onSaveAndScanNext && !scanActive && (
          <button type="button" onClick={saveAndNew} disabled={busy} data-testid="full-camera-savenew"
            className="w-full h-9 rounded-lg bg-white/10 text-white/85 text-[11px] font-semibold flex items-center justify-center gap-1 disabled:opacity-40 disabled:pointer-events-none">
            <Check className="w-3.5 h-3.5" />Simpan & Aset Baru
          </button>
        )}
        <div className="text-center text-[11px] text-white/70">
          {photos.length}/{maxPhotos} foto{maxReached ? " (penuh)" : ""} • {savedCount} tersimpan sesi ini
          {isEditing && totalAssetsInView > 0 ? ` • aset ${assetIndex + 1}/${totalAssetsInView}` : ""}
        </div>
        {photos.length > 0 && !gps && (
          <div className="text-center text-[11px] text-amber-300 font-medium">
            Menunggu sinyal GPS — koordinat wajib untuk menyimpan aset yang sudah difoto.
          </div>
        )}
      </div>

      {/* ── Mode pemindaian QR aset (edit inventarisasi) ── */}
      {scanActive && (
        <div className="absolute inset-0 z-[9] pointer-events-none" data-testid="full-camera-scan-overlay">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-52 h-52 border-2 border-emerald-400/90 rounded-xl shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" />
          </div>
        </div>
      )}

      {/* ── Aset baru sedang disiapkan (setelah Simpan & Baru) ── */}
      {preparing && (
        <div className="absolute inset-x-0 top-24 z-[15] flex justify-center pointer-events-none" role="status" aria-live="polite" data-testid="full-camera-preparing">
          <div className="flex items-center gap-2 px-3.5 py-2 rounded-full bg-black/70 text-white text-xs font-medium shadow-lg">
            <Loader2 className="w-4 h-4 animate-spin text-amber-300" />
            {isEditing ? "Memuat data aset…" : "Menyiapkan aset baru…"}
          </div>
        </div>
      )}

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
          <div className="bg-card rounded-t-2xl p-4 max-h-[82vh] overflow-y-auto space-y-3" onClick={e => e.stopPropagation()} data-testid="full-camera-edit-panel">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-foreground">Edit Info Aset</h3>
              <button type="button" onClick={() => setEditOpen(false)} aria-label="Tutup panel edit"
                className="w-8 h-8 rounded-full inline-flex items-center justify-center text-muted-foreground hover:bg-muted">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {visibleEditFields.map(f => (
                <div key={f.name} className={`space-y-0.5 ${f.full ? "col-span-2" : ""}`}>
                  <label className="text-[11px] text-muted-foreground">
                    {f.label}{f.required && <span className="text-red-500"> *</span>}{f.readOnly ? " (otomatis)" : ""}
                  </label>
                  <input
                    value={formData?.[f.name] || ""}
                    onChange={e => onSetField(f.name, e.target.value)}
                    readOnly={f.readOnly}
                    autoFocus={f.name === "asset_name" && !(formData?.asset_name || "").trim()}
                    data-testid={`full-camera-edit-${f.name}`}
                    className={`w-full h-9 px-2.5 rounded-lg border text-sm text-foreground ${f.readOnly ? "bg-muted text-muted-foreground border-border" : (f.required && !(formData?.[f.name] || "").trim() ? "bg-background border-red-400" : "bg-background border-border")}`}
                  />
                </div>
              ))}
            </div>

            {/* Mode scan-edit inventarisasi: field SAMA dengan lembar edit
                cepat — status, kondisi, detail kondisional, stiker, pengguna —
                agar scan → lengkapi → Simpan & Scan berjalan tanpa keluar. */}
            {isEditing && onScanAsset && (
              <div className="space-y-3" data-testid="full-camera-edit-inventaris">
                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-foreground">Status Inventarisasi</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    {STATUS_OPTIONS.map(o => (
                      <CamChip key={o.value} selected={formData?.inventory_status === o.value} cls={o.selected}
                        onClick={() => onSetField("inventory_status", o.value)} testId={`cam-status-${o.value}`}>
                        {o.value}
                      </CamChip>
                    ))}
                  </div>
                </div>

                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-foreground">Kondisi Fisik</p>
                  <div className="grid grid-cols-3 gap-1.5">
                    {CONDITION_OPTIONS.map(o => (
                      <CamChip key={o.value} selected={formData?.condition === o.value} cls={o.selected}
                        onClick={() => onSetField("condition", o.value)} testId={`cam-condition-${o.value}`}>
                        {o.value}
                      </CamChip>
                    ))}
                  </div>
                </div>

                {formData?.inventory_status === "Tidak Ditemukan" && (
                  <div className="space-y-1.5 rounded-lg border border-red-300/60 p-2">
                    <p className="text-[11px] font-bold text-foreground">Detail Tidak Ditemukan</p>
                    <select value={formData?.klasifikasi_tidak_ditemukan || ""} className={camSelectCls}
                      onChange={e => onSetField("klasifikasi_tidak_ditemukan", e.target.value)} data-testid="cam-klasifikasi">
                      <option value="">Pilih klasifikasi…</option>
                      <option value="Kesalahan Pencatatan">Kesalahan Pencatatan</option>
                      <option value="Tidak Ditemukan Lainnya">Tidak Ditemukan Lainnya</option>
                    </select>
                    {!!formData?.klasifikasi_tidak_ditemukan && (
                      <select value={formData?.sub_klasifikasi || ""} className={camSelectCls}
                        onChange={e => onSetField("sub_klasifikasi", e.target.value)} data-testid="cam-sub-klasifikasi">
                        <option value="">Pilih sub klasifikasi…</option>
                        {(SUB_KLASIFIKASI_OPTIONS[formData.klasifikasi_tidak_ditemukan] || []).map(o => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    )}
                    <input value={formData?.uraian_tidak_ditemukan || ""} placeholder="Uraian tidak ditemukan"
                      onChange={e => onSetField("uraian_tidak_ditemukan", e.target.value)} className={camInputCls} />
                  </div>
                )}

                {formData?.inventory_status === "Berlebih" && (
                  <div className="space-y-1.5 rounded-lg border border-purple-300/60 p-2">
                    <p className="text-[11px] font-bold text-foreground">Detail Berlebih</p>
                    <input value={formData?.asal_usul_berlebih || ""} placeholder="Asal usul BMN berlebih"
                      onChange={e => onSetField("asal_usul_berlebih", e.target.value)} className={camInputCls} />
                    <input value={formData?.keterangan_berlebih || ""} placeholder="Keterangan berlebih"
                      onChange={e => onSetField("keterangan_berlebih", e.target.value)} className={camInputCls} />
                  </div>
                )}

                {formData?.inventory_status === "Sengketa" && (
                  <div className="space-y-1.5 rounded-lg border border-rose-300/60 p-2">
                    <p className="text-[11px] font-bold text-foreground">Detail Sengketa</p>
                    <input value={formData?.nomor_perkara || ""} placeholder="Nomor perkara"
                      onChange={e => onSetField("nomor_perkara", e.target.value)} className={camInputCls} />
                    <input value={formData?.pihak_bersengketa || ""} placeholder="Pihak bersengketa"
                      onChange={e => onSetField("pihak_bersengketa", e.target.value)} className={camInputCls} />
                    <input value={formData?.keterangan_sengketa || ""} placeholder="Keterangan sengketa"
                      onChange={e => onSetField("keterangan_sengketa", e.target.value)} className={camInputCls} />
                  </div>
                )}

                {formData?.condition === "Rusak Berat" && (
                  <div className="space-y-1.5 rounded-lg border border-amber-300/60 p-2">
                    <p className="text-[11px] font-bold text-foreground">Tindak Lanjut Rusak Berat</p>
                    <input value={formData?.tindak_lanjut || ""} placeholder="Tindak lanjut"
                      onChange={e => onSetField("tindak_lanjut", e.target.value)} className={camInputCls} />
                  </div>
                )}

                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-foreground">Stiker</p>
                  <div className="grid grid-cols-2 gap-1.5">
                    <CamChip selected={formData?.stiker_status === "Sudah Terpasang"} cls="bg-blue-600 border-blue-600 text-white"
                      onClick={() => onSetField("stiker_status", "Sudah Terpasang")} testId="cam-stiker-sudah">Sudah Terpasang</CamChip>
                    <CamChip selected={formData?.stiker_status === "Belum Terpasang"} cls="bg-blue-600 border-blue-600 text-white"
                      onClick={() => onSetField("stiker_status", "Belum Terpasang")} testId="cam-stiker-belum">Belum</CamChip>
                  </div>
                  {formData?.stiker_status === "Sudah Terpasang" && (
                    <select value={formData?.stiker_ukuran || ""} className={camSelectCls}
                      onChange={e => onSetField("stiker_ukuran", e.target.value)} data-testid="cam-stiker-ukuran">
                      <option value="">Pilih ukuran stiker…</option>
                      <option value="Kecil">Kecil (3x1.5cm)</option>
                      <option value="Sedang">Sedang (5x3cm)</option>
                      <option value="Besar">Besar (8x5cm)</option>
                    </select>
                  )}
                </div>

                <div className="space-y-1">
                  <p className="text-[11px] font-bold text-foreground">Pengguna Barang</p>
                  <div className="grid grid-cols-3 gap-1.5">
                    {PENGGUNA_MELEKAT_OPTIONS.map(o => (
                      <CamChip key={o} selected={formData?.pengguna_melekat_ke === o} cls="bg-indigo-600 border-indigo-600 text-white"
                        onClick={() => onSetField("pengguna_melekat_ke", o)} testId={`cam-melekat-${o}`}>{o}</CamChip>
                    ))}
                  </div>
                  {formData?.pengguna_melekat_ke === "Operasional" && (
                    <div className="grid grid-cols-2 gap-1.5">
                      {OPERASIONAL_JENIS_OPTIONS.map(o => (
                        <CamChip key={o} selected={formData?.operasional_jenis === o} cls="bg-indigo-600 border-indigo-600 text-white"
                          onClick={() => onSetField("operasional_jenis", o)} testId={`cam-opjenis-${o}`}>{o}</CamChip>
                      ))}
                    </div>
                  )}
                  {formData?.pengguna_melekat_ke === "Jabatan" && (
                    <input value={formData?.pengguna_jabatan || ""} placeholder="Nama jabatan"
                      onChange={e => onSetField("pengguna_jabatan", e.target.value)} className={camInputCls} data-testid="cam-pengguna-jabatan" />
                  )}
                  <input value={formData?.user || ""}
                    placeholder={PENGGUNA_NAME_LABELS[formData?.pengguna_melekat_ke] || "Nama Pengguna"}
                    onChange={e => onSetField("user", e.target.value)} className={camInputCls} data-testid="cam-pengguna-nama" />
                  <input value={formData?.pengguna_nip || ""} placeholder="NIP/NIK pegawai pengguna"
                    onChange={e => onSetField("pengguna_nip", e.target.value)} className={camInputCls} data-testid="cam-pengguna-nip" />
                </div>
              </div>
            )}

            <div className={`grid gap-2 ${isEditing && onScanAsset && onSaveAndScanNext ? "grid-cols-2" : "grid-cols-1"}`}>
              <button type="button" onClick={() => setEditOpen(false)} data-testid="full-camera-edit-done"
                className="h-11 rounded-lg bg-blue-600 text-white text-sm font-semibold flex items-center justify-center gap-1.5">
                <Check className="w-4 h-4" />Selesai
              </button>
              {isEditing && onScanAsset && onSaveAndScanNext && (
                <button type="button" data-testid="full-camera-edit-save-scan"
                  onClick={() => { setEditOpen(false); saveAndScanNext(); setScanActive(true); }}
                  disabled={busy}
                  className="h-11 rounded-lg bg-emerald-600 text-white text-sm font-bold flex items-center justify-center gap-1.5 disabled:opacity-60">
                  <ScanLine className="w-4 h-4" />Simpan & Scan
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>,
    document.body
  );
});

FullCameraSheet.displayName = "FullCameraSheet";
export default FullCameraSheet;
