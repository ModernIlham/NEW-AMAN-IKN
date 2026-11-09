import React, { memo, useState, useCallback, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { hitungSebaran } from "@/components/ui/stacked-cards-interaction";
import { Loader2, X, ChevronLeft, ChevronRight, MapPin, Tag, User, QrCode, FileCheck, FileX, StickyNote, Download, Maximize2, RotateCw, Trash2 } from "lucide-react";
import { authMediaUrl } from "../../lib/mediaUrl";
import { peekAnim } from "../../lib/lightboxAnim";
import { namaBerkasFoto, pemantauMacet, persenUnduh, pesanGagalUnduh } from "../../lib/unduhFoto";
import { FullscreenPhoto } from "./PhotoPreview";
import ConfirmPhotoDelete from "./ConfirmPhotoDelete";
import { patchHapusFoto } from "../../lib/fotoAset";
import { getSatkerAktif } from "../../lib/satkerAktif";
import { idUnik } from "../../lib/idAntrean";
import { getApiError } from "../../lib/utils";
import { useBackGuard } from "../../hooks/useBackGuard";
import { toast } from "sonner";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatPrice = (p) => {
  if (!p) return null;
  const num = typeof p === "string" ? parseFloat(p) : p;
  return isNaN(num) ? null : `Rp ${num.toLocaleString("id-ID")}`;
};

// Bangun URL foto (varian tajam w=1280) + thumbnail kecil dari data aset yang
// SUDAH di tangan — baris peta / kartu galeri sudah membawa photo_count +
// version. Dipakai agar foto MULAI dimuat SEKETIKA tanpa menunggu round-trip
// /assets/{id} (penyebab "loading lama walau fotonya sudah ada").
function buildPhotoUrls(src) {
  const id = src?.id;
  const count = Number(src?.photo_count) || 0;
  const version = Number(src?.version) || 1;
  if (id && count > 0) {
    return {
      count, version,
      photos: Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${id}/photos/${i}?v=${version}&w=1280`)),
      thumbs: Array.from({ length: count }, (_, i) => authMediaUrl(`${API}/assets/${id}/photos/${i}?v=${version}&thumb=1`)),
    };
  }
  const uri = src?.thumbnail ? [src.thumbnail] : []; // fallback data-URI (cover legacy)
  return { count: uri.length, version, photos: uri, thumbs: uri };
}

// ============================================================================
// LIGHTBOX - Photo gallery with full asset info
// Dipakai bersama oleh galeri (AssetGalleryView) dan popup marker peta
// (AssetMapFullView) — supaya pengalaman "buka foto" identik di kedua tempat.
// ============================================================================
const Lightbox = memo(({ asset, onClose: closeRequested, onEdit, onAssetUpdated, siblings = null, onSelectAsset = null }) => {
  // Foto diseed SEKETIKA dari data aset yang diklik (peta/galeri sudah bawa
  // photo_count + version) supaya <img> mulai memuat langsung — bukan setelah
  // round-trip metadata. `builtRef` mengingat jumlah/versi terakhir yang
  // dipakai membangun URL agar hasil fetch tak mengganti array foto bila tak
  // berubah (array baru → efek imgLoading menyala → kedip cepat).
  const seed = useRef(null);
  if (seed.current === null) seed.current = buildPhotoUrls(asset);
  const [fullAsset, setFullAsset] = useState(null);
  const [photos, setPhotos] = useState(seed.current.photos);
  const [thumbs, setThumbs] = useState(seed.current.thumbs); // placeholder kecil per-foto (instan)
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(seed.current.photos.length === 0);
  // Mulai dalam keadaan "memuat" bila ada foto (varian tajam w=1280 belum
  // ter-cache) → langsung tampil placeholder blur + spinner, bukan berkedip
  // dari foto tajam-lalu-hilang saat efek menyalakan loading.
  const [imgLoading, setImgLoading] = useState(seed.current.photos.length > 0);
  const startX = useRef(0);
  // Ikut menyimpan `id`: dua ASET berbeda bisa punya count+version SAMA (mis.
  // sama-sama 1 foto versi 1) — tanpa membandingkan id, URL foto tak dibangun
  // ulang saat pindah aset → foto "tersangkut" milik aset lama.
  const builtRef = useRef({ id: asset?.id, count: seed.current.count, version: seed.current.version });
  const [downloading, setDownloading] = useState(false);
  const [unduhPersen, setUnduhPersen] = useState(null); // null = panjang isi tak diketahui
  const batalUnduhRef = useRef(null);                   // AbortController unduhan berjalan
  const [rot, setRot] = useState(0); // rotasi tampilan foto (0/90/180/270) — preview saja
  const [fullscreen, setFullscreen] = useState(false); // penampil foto layar penuh DALAM aplikasi
  const closeFullscreen = useCallback(() => setFullscreen(false), []);
  const [rotating, setRotating] = useState(false); // putar PERMANEN sedang diproses server
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [metadataReady, setMetadataReady] = useState(false);
  const deleteLock = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const assetRef = useRef(asset);
  assetRef.current = asset;
  const activeId = useRef(asset?.id);
  activeId.current = asset?.id;
  const metadataGeneration = useRef(0);
  const metadataScope = useRef(getSatkerAktif());
  const onClose = useCallback(() => { if (!deleteLock.current) closeRequested(); }, [closeRequested]);
  const requestDelete = () => {
    const current = fullAsset || asset;
    if (!onEdit || !metadataReady || rotating || deleteLock.current || !photos.length) return;
    if (metadataScope.current !== getSatkerAktif()) {
      toast.error("Satker berubah. Tutup dan buka ulang foto sebelum menghapus."); return;
    }
    setDeleteTarget({ asset: current, index: idx, src: photos[idx], scope: getSatkerAktif(), key: idUnik("hapus-foto-") });
  };
  const deletePhoto = async () => {
    const target = deleteTarget;
    if (!target || deleteLock.current) return;
    if (target.asset.id !== activeId.current || target.scope !== getSatkerAktif()) {
      setDeleteTarget(null); toast.error("Aset atau satker berubah. Buka ulang foto sebelum menghapus."); return;
    }
    deleteLock.current = true; setDeleting(true);
    metadataGeneration.current++;
    try {
      const response = await axios.patch(`${API}/assets/${target.asset.id}`, patchHapusFoto(target.asset, target.index), {
        headers: { "If-Match": String(target.asset.version), "Idempotency-Key": target.key, "X-Satker-Aktif": target.scope || "" },
      });
      const updated = { ...target.asset, ...response.data };
      if (mounted.current && activeId.current === updated.id && getSatkerAktif() === target.scope) {
        const next = buildPhotoUrls({ ...updated, thumbnail: Number(updated.photo_count) ? updated.thumbnail : null });
        builtRef.current = { id: updated.id, count: next.count, version: next.version };
        setFullAsset(updated); setPhotos(next.photos); setThumbs(next.thumbs);
        setIdx(Math.min(target.index, Math.max(0, next.count - 1)));
        setDeleteTarget(null);
        toast.success("Foto dihapus");
        onAssetUpdated?.(updated);
      }
    } catch (error) {
      if (!mounted.current || activeId.current !== target.asset.id) return;
      if (error.response?.status === 409) {
        setDeleteTarget(null);
        toast.error("Susunan foto telah berubah. Tutup dan buka ulang foto sebelum mencoba lagi.");
        setMetadataReady(false);
      } else toast.error(getApiError(error, "Penghapusan belum terkonfirmasi. Periksa koneksi lalu coba kembali."));
    } finally { deleteLock.current = false; if (mounted.current) setDeleting(false); }
  };


  // Navigasi antar-ASET (bukan antar-foto): geser/klik pada kartu info → aset
  // sebelum/sesudah sesuai urutan & filter aktif (daftar `siblings` dari
  // pemanggil). Optional — bila tak diberi siblings, fitur ini nonaktif mulus.
  const sibIndex = (siblings && asset) ? siblings.findIndex((s) => s?.id === asset.id) : -1;
  const hasPrevAsset = sibIndex > 0;
  const hasNextAsset = sibIndex >= 0 && sibIndex < siblings.length - 1;
  const goAsset = useCallback((dir) => {
    if (deleteLock.current || deleteTarget || !siblings || !onSelectAsset || sibIndex < 0) return;
    const ni = sibIndex + dir;
    if (ni < 0 || ni >= siblings.length) return;
    onSelectAsset(siblings[ni]);
  }, [siblings, onSelectAsset, sibIndex, deleteTarget]);

  // Geser kartu info: umpan balik drag + snap; lepas melewati ambang → pindah
  // aset. stopPropagation agar TIDAK ikut memicu geser-foto pada overlay.
  const infoStartX = useRef(null);
  const [infoDragX, setInfoDragX] = useState(0);
  const onInfoTouchStart = useCallback((e) => { e.stopPropagation(); infoStartX.current = e.touches[0].clientX; }, []);
  const onInfoTouchMove = useCallback((e) => {
    e.stopPropagation();
    if (infoStartX.current == null) return;
    let dx = e.touches[0].clientX - infoStartX.current;
    if ((dx > 0 && !hasPrevAsset) || (dx < 0 && !hasNextAsset)) dx *= 0.25; // redam bila mentok
    setInfoDragX(Math.max(-120, Math.min(120, dx)));
  }, [hasPrevAsset, hasNextAsset]);
  const onInfoTouchEnd = useCallback((e) => {
    e.stopPropagation();
    const dx = infoStartX.current == null ? 0 : e.changedTouches[0].clientX - infoStartX.current;
    infoStartX.current = null;
    setInfoDragX(0);
    if (Math.abs(dx) > 60) { if (dx > 0) goAsset(-1); else goAsset(1); }
  }, [goAsset]);

  // Unduh foto ASLI (resolusi penuh) — yang tampil hanya varian preview w=1280.
  //
  // KENAPA `timeout: 0`. `axios.defaults.timeout` dipasang 20 detik di App.js
  // sebagai LANTAI tenggat untuk permintaan data. Foto asli dari kamera HP
  // berukuran beberapa megabyte; di jaringan lapangan transfernya lewat dari 20
  // detik dan axios memutusnya di tengah jalan — itulah "sering gagal mengunduh"
  // yang dilaporkan. Membuka Layar Penuh lebih dulu "menyembuhkannya" hanya
  // karena <img> mengambil URL yang SAMA tanpa terikat tenggat axios, sehingga
  // berkasnya tersimpan di cache HTTP dan permintaan ini selesai seketika.
  //
  // Tenggat tetap adalah alat yang salah untuk unduhan besar. Bahaya asli yang
  // dijaga tenggat global — soket menggantung — tetap ditutup, tapi oleh
  // `pemantauMacet`: yang diputus adalah transfer yang BERHENTI mengalir, bukan
  // transfer yang lambat namun terus jalan.
  const downloadOriginal = useCallback(async () => {
    const cur = fullAsset || asset;
    const id = cur?.id;
    if (!id) return;
    // Klik saat sedang berjalan = BATALKAN (tombol berubah jadi silang).
    if (batalUnduhRef.current) { batalUnduhRef.current.abort(); return; }
    const ctrl = new AbortController();
    batalUnduhRef.current = ctrl;
    let macet = false;
    const pantau = pemantauMacet(() => { macet = true; try { ctrl.abort(); } catch { /* noop */ } });
    setDownloading(true);
    setUnduhPersen(null);
    try {
      const url = authMediaUrl(`${API}/assets/${id}/photos/${idx}?v=${builtRef.current.version}`); // tanpa w → asli
      const res = await axios.get(url, {
        responseType: "blob",
        timeout: 0,
        signal: ctrl.signal,
        onDownloadProgress: (e) => {
          pantau.maju();
          setUnduhPersen(persenUnduh(e.loaded, e.total));
        },
      });
      const blobUrl = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = namaBerkasFoto(cur, idx, res.data?.type);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1500);
    } catch (err) {
      // Batal atas permintaan pengguna sendiri tak perlu dilaporkan sebagai galat.
      const dibatalkanSendiri = !macet
        && (err?.code === "ERR_CANCELED" || err?.name === "CanceledError" || err?.name === "AbortError");
      if (!dibatalkanSendiri) toast.error(pesanGagalUnduh(err, macet));
    } finally {
      pantau.hentikan();
      batalUnduhRef.current = null;
      setDownloading(false);
      setUnduhPersen(null);
    }
  }, [fullAsset, asset, idx]);

  // Lightbox ditutup di tengah unduhan → putuskan permintaannya.
  useEffect(() => () => { try { batalUnduhRef.current?.abort(); } catch { /* noop */ } }, []);

  // Putar foto PERMANEN di server (mengubah berkas asli) lalu muat ulang dengan
  // versi baru → thumbnail, galeri, unduh, dan layar penuh SEMUA ikut berputar
  // (permintaan "berubah total tanpa terkecuali"). Umpan balik instan lewat
  // rotasi tampilan sementara selagi server memproses; dikembalikan bila gagal.
  const rotatePhotoPersist = useCallback(async () => {
    const cur = fullAsset || asset;
    const id = cur?.id;
    if (!id || rotating || deleteLock.current || deleteTarget || photos.length === 0) return;
    setRotating(true);
    setRot((r) => (r + 90) % 360); // umpan balik instan (CSS) selama proses
    try {
      const res = await axios.post(`${API}/assets/${id}/photos/${idx}/rotate`, { degrees: 90 });
      const newVersion = Number(res.data?.version) || (builtRef.current.version + 1);
      builtRef.current = { ...builtRef.current, version: newVersion };
      // Bangun ulang URL dgn versi baru → berkas yang kini sudah diputar di
      // server dimuat ulang. Efek [idx, photos] otomatis reset rot=0.
      const next = buildPhotoUrls({ ...cur, photo_count: builtRef.current.count, version: newVersion });
      setPhotos(next.photos);
      setThumbs(next.thumbs);
      setFullAsset((fa) => (fa ? { ...fa, version: newVersion } : fa));
    } catch {
      setRot((r) => (r - 90 + 360) % 360); // gagal → kembalikan tampilan
      toast.error(navigator.onLine === false
        ? "Perlu koneksi internet untuk memutar foto permanen"
        : "Gagal memutar foto di server");
    } finally {
      setRotating(false);
    }
  }, [fullAsset, asset, idx, rotating, photos.length, deleteTarget]);

  useEffect(() => {
    const asset = assetRef.current;
    if (!asset?.id) return undefined;
    setDeleteTarget(null); setMetadataReady(false);
    const generation = ++metadataGeneration.current;
    const scope = getSatkerAktif();
    metadataScope.current = scope;
    // Aset berganti (mis. dari galeri) → seed ulang foto. Pada MOUNT pertama
    // state sudah diseed via useState di atas, jadi lewati agar tak set ulang
    // (yang memicu kedip). w=1280: varian preview tajam (~100-250KB), di-resize
    // & di-cache server sekali (ETag/Cache-Control tetap berlaku).
    const init = buildPhotoUrls(asset);
    if (asset.id !== builtRef.current.id || init.count !== builtRef.current.count || init.version !== builtRef.current.version) {
      builtRef.current = { id: asset.id, count: init.count, version: init.version };
      setPhotos(init.photos);
      setThumbs(init.thumbs);
      setIdx(0);
      setLoading(init.photos.length === 0);
    }
    setFullAsset(asset);
    // Fetch ringan (tanpa base64) HANYA untuk memperkaya panel info +
    // rekonsiliasi jumlah/versi. Foto sudah tampil; array hanya dibangun ulang
    // bila jumlah/versi BERBEDA — sehingga tak me-reset foto yang sedang dimuat.
    let alive = true;
    axios.get(`${API}/assets/${asset.id}?exclude_media=true`, { headers: { "X-Satker-Aktif": scope || "" } })
      .then(r => {
        if (!alive || generation !== metadataGeneration.current || scope !== getSatkerAktif()) return;
        const data = r.data;
        setMetadataReady(true);
        // GABUNG, bukan ganti: respons exclude_media TIDAK menghitung
        // doc_total/doc_checked/doc_summary (field itu hanya di proyeksi list).
        // Mengganti fullAsset dengan data mentah membuat badge "Dok x/y" dari
        // seed galeri MUNCUL lalu HILANG (kedip). Merge → field segar dari server
        // menang, tapi hitungan dokumen dari seed dipertahankan.
        setFullAsset({ ...asset, ...data });
        const c = Number(data.photo_count) || 0;
        const v = Number(data.version) || 1;
        if (c !== builtRef.current.count || v !== builtRef.current.version) {
          const next = buildPhotoUrls({ ...asset, photo_count: c, version: v });
          builtRef.current = { id: asset.id, count: next.count, version: next.version };
          setPhotos(next.photos);
          setThumbs(next.thumbs);
          setIdx(i => Math.min(i, Math.max(0, next.photos.length - 1)));
        }
      })
      .catch(() => { /* tampilan awal dari data asset tetap dipakai */ })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [asset?.id, asset?.thumbnail]);

  useEffect(() => {
    const handler = (e) => {
      if (deleteTarget || deleting) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setIdx(i => (i - 1 + photos.length) % photos.length);
      if (e.key === "ArrowRight") setIdx(i => (i + 1) % photos.length);
      // ↑/↓ = pindah antar-ASET (bila daftar siblings tersedia)
      if (e.key === "ArrowUp") goAsset(-1);
      if (e.key === "ArrowDown") goAsset(1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [photos.length, onClose, goAsset, deleteTarget, deleting]);

  // Foto berpindah → tandai "sedang memuat" agar tampil spinner (bukan foto lama
  // yang terlihat "freeze"). Dibersihkan oleh onLoad/onError <img>. Bila foto
  // sudah di-cache (mis. hasil preload), onLoad langsung memicu clear.
  useEffect(() => { if (photos.length > 0) setImgLoading(true); setRot(0); }, [idx, photos]);

  // Preload foto tetangga (berikutnya & sebelumnya) agar navigasi mulus — saat
  // ditampilkan sudah dari cache sehingga tak terkesan freeze.
  useEffect(() => {
    if (photos.length <= 1) return undefined;
    const imgs = [];
    [(idx + 1) % photos.length, (idx - 1 + photos.length) % photos.length].forEach((i) => {
      if (i === idx) return;
      const im = new Image();
      im.src = photos[i];
      imgs.push(im);
    });
    return () => { imgs.forEach((im) => { im.src = ""; }); };
  }, [idx, photos]);

  // Preload DINI foto pertama + thumbnail aset TETANGGA (sebelum & sesudah)
  // sesuai urutan/filter aktif — sehingga pindah antar-aset terasa instan &
  // seamless (gambar tujuan sudah di cache saat kartu berganti). Baris
  // peta/galeri sudah membawa photo_count+version, jadi URL bisa dibangun
  // tanpa round-trip.
  useEffect(() => {
    if (!siblings || sibIndex < 0) return undefined;
    const imgs = [];
    [sibIndex - 1, sibIndex + 1].forEach((i) => {
      if (i < 0 || i >= siblings.length) return;
      const built = buildPhotoUrls(siblings[i]);
      if (built.thumbs[0]) { const t = new Image(); t.src = built.thumbs[0]; imgs.push(t); }
      if (built.photos[0]) { const im = new Image(); im.src = built.photos[0]; imgs.push(im); }
    });
    return () => { imgs.forEach((im) => { im.src = ""; }); };
  }, [siblings, sibIndex]);

  // Back/Undo browser saat lightbox terbuka → tutup lightbox, bukan pindah
  // halaman. Komponen ini hanya ter-mount saat terbuka, jadi guard aktif penuh.
  useBackGuard(onClose);

  // Lock background scroll while the lightbox is open (stops the page
  // behind from scrolling / "bocor" under the popup on mobile).
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  const onTouchStart = useCallback((e) => { startX.current = e.touches[0].clientX; }, []);
  const onTouchEnd = useCallback((e) => {
    const diff = e.changedTouches[0].clientX - startX.current;
    if (!deleteTarget && !deleting && photos.length > 0 && Math.abs(diff) > 50) {
      if (diff > 0) setIdx(i => (i - 1 + photos.length) % photos.length);
      else setIdx(i => (i + 1) % photos.length);
    }
  }, [photos.length, deleteTarget, deleting]);

  if (!asset) return null;
  const a = fullAsset || asset;
  const price = formatPrice(a.purchase_price);
  const invStatus = a.inventory_status || "Belum Diinventarisasi";
  const docChecked = a.doc_checked || 0;
  const docTotal = a.doc_total || 0;
  // Parameter animasi geser kartu info (opacity peek + skala kartu depan).
  const anim = peekAnim(infoDragX);
  // Sebaran kartu tetangga (model tumpukan kartu) — intensitasnya mengikuti
  // jarak geser, jadi kartu "membuka" bertahap alih-alih meloncat.
  const _sebar = { spreadDistance: 28, rotationAngle: 4, intensitas: Math.abs(infoDragX) / 120 };
  const sebaranNext = hitungSebaran(2, { ..._sebar, aktif: infoDragX < 0 });
  const sebaranPrev = hitungSebaran(1, { ..._sebar, aktif: infoDragX > 0 });
  // URL foto ASLI (resolusi penuh) untuk penampil layar penuh.
  const fullSrc = a?.id ? authMediaUrl(`${API}/assets/${a.id}/photos/${idx}?v=${builtRef.current.version}`) : (photos[idx] || null);

  return createPortal(
    <div
      className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-md flex flex-col items-center justify-center"
      role="dialog" aria-modal="true" aria-label="Penampil foto aset"
      onClick={onClose}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      data-testid="gallery-lightbox"
    >
      {/* Close button */}
      <button
        type="button"
        aria-label="Tutup penampil foto"
        autoFocus
        className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors"
        onClick={onClose}
        data-testid="lightbox-close"
      >
        <X className="w-5 h-5" />
      </button>

      {/* Photo area */}
      <div className="relative flex-1 flex items-center justify-center w-full max-w-4xl px-4" onClick={(e) => e.stopPropagation()}>
        {/* Toolbar foto (kiri-atas, tumpuk vertikal): Unduh asli · Layar penuh
            (HD asli, DALAM aplikasi — Back kembali ke lightbox, bukan keluar app) ·
            Putar 90°. Ikon di lingkaran gelap semi-transparan + cincin putih agar
            kontras di light/dark & di atas warna foto apa pun. Lightbox tampil
            preview (w=1280). */}
        {!loading && photos.length > 0 && (
          <div className="absolute left-2 top-2 z-10 flex flex-col gap-1.5" onClick={(e) => e.stopPropagation()}>
            {/* Sengaja TIDAK di-`disabled` saat mengunduh: foto asli bisa
                puluhan MB di jaringan lapangan, dan tombol mati tanpa jalan
                keluar membuat operator mengira aplikasinya menggantung. Selama
                berjalan tombol menampilkan persentase dan berfungsi sebagai
                BATAL. */}
            <button
              onClick={(e) => { e.stopPropagation(); downloadOriginal(); }}
              title={downloading
                ? `Mengunduh foto asli${unduhPersen != null ? ` ${unduhPersen}%` : ""} — ketuk untuk membatalkan`
                : "Unduh foto asli (resolusi penuh)"}
              aria-label={downloading ? "Batalkan unduhan foto asli" : "Unduh foto asli"}
              className="w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors"
              data-testid="lightbox-download"
            >
              {downloading
                ? (unduhPersen != null
                  ? <span className="text-[10px] font-bold tabular-nums" data-testid="lightbox-download-persen">{unduhPersen}%</span>
                  : <Loader2 className="w-5 h-5 animate-spin" />)
                : <Download className="w-5 h-5" />}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setFullscreen(true); }}
              title="Layar penuh (foto HD asli)"
              aria-label="Layar penuh (foto HD asli)"
              className="w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors"
              data-testid="lightbox-fullscreen"
            >
              <Maximize2 className="w-5 h-5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); rotatePhotoPersist(); }}
              disabled={rotating || deleting}
              title="Putar foto 90° (permanen — berlaku di semua tampilan & unduhan)"
              aria-label="Putar foto 90 derajat secara permanen"
              className="w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors disabled:opacity-70"
              data-testid="lightbox-rotate"
            >
              {rotating ? <Loader2 className="w-5 h-5 animate-spin" /> : <RotateCw className="w-5 h-5" />}
            </button>
            {onEdit && <button type="button" onClick={requestDelete} disabled={!metadataReady || rotating || deleting}
              aria-label="Hapus foto" title="Hapus foto" data-testid="lightbox-delete"
              className="w-11 h-11 rounded-full bg-red-600/90 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center disabled:opacity-50">
              {deleting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Trash2 className="w-5 h-5" />}
            </button>}
          </div>
        )}
        {loading ? (
          <Loader2 className="w-10 h-10 text-slate-700 dark:text-white animate-spin" />
        ) : photos.length > 0 ? (
          <>
            <img
              key={photos[idx]}
              src={photos[idx]}
              alt={a.name || a.asset_name || "Foto aset"}
              onLoad={() => setImgLoading(false)}
              onError={() => setImgLoading(false)}
              className={`object-contain rounded-lg shadow-2xl transition-all duration-200 ${imgLoading ? "opacity-0" : "opacity-100"}`}
              // Saat diputar 90°/270° tinggi↔lebar bertukar; batas dimensi ditukar
              // agar foto tetap muat di layar (tak melimpah ke panel info).
              style={{
                transform: rot ? `rotate(${rot}deg)` : undefined,
                maxHeight: rot % 180 === 90 ? "75vw" : "60vh",
                maxWidth: rot % 180 === 90 ? "60vh" : "100%",
              }}
              draggable={false}
            />
            {imgLoading && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none" data-testid="lightbox-img-loading">
                {/* Placeholder instan: thumbnail kecil diperbesar + blur, supaya
                    pengguna langsung melihat foto yang DITUJU (bukan foto lama)
                    selagi versi tajamnya diunduh. */}
                {thumbs[idx] && (
                  <img src={thumbs[idx]} alt="" aria-hidden="true" draggable={false}
                    className="max-h-[60vh] max-w-full object-contain rounded-lg blur-md scale-[1.02] opacity-80" />
                )}
                <Loader2 className="absolute w-10 h-10 text-white drop-shadow animate-spin" />
              </div>
            )}
            {photos.length > 1 && (
              <>
                <button className="absolute left-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors" onClick={(e) => { e.stopPropagation(); setIdx(i => (i - 1 + photos.length) % photos.length); }}>
                  <ChevronLeft className="w-6 h-6" />
                </button>
                <button className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-black/50 hover:bg-black/70 text-white ring-1 ring-white/40 shadow-lg flex items-center justify-center backdrop-blur-sm transition-colors" onClick={(e) => { e.stopPropagation(); setIdx(i => (i + 1) % photos.length); }}>
                  <ChevronRight className="w-6 h-6" />
                </button>
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-xs px-2 py-0.5 rounded-full backdrop-blur-sm">
                  {idx + 1} / {photos.length}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="text-slate-700 dark:text-white/60 text-sm font-medium">Tidak ada foto</div>
        )}
      </div>

      {/* Info panel — GESER kiri/kanan untuk PINDAH ANTAR-ASET sesuai urutan/
          filter aktif (tanpa tombol panah — cukup swipe); FOTO tak ikut tergeser. */}
      <div className="w-full max-w-4xl px-4 pb-4 pt-2" onClick={(e) => e.stopPropagation()}>
        <div className="relative" onTouchStart={onInfoTouchStart} onTouchMove={onInfoTouchMove} onTouchEnd={onInfoTouchEnd}>
          {/* Peek kartu tetangga: mulai SAMAR (petunjuk bisa digeser antar-aset),
              opacity BERTAMBAH mengikuti geseran ke sisi itu (peekAnim) → kartu
              berikut/sebelumnya "muncul" makin jelas seiring jempol menggeser. */}
          {/* Model TUMPUKAN KARTU (stacked-cards): kartu tetangga tak lagi
              sekadar memudar — ia MENYEBAR ke samping sambil MIRING mengikuti
              seberapa jauh jari menggeser (hitungSebaran, intensitas 0..1),
              lalu merapat kembali dengan pegas saat dilepas. */}
          {hasNextAsset && (
            <motion.div
              aria-hidden="true"
              className="absolute inset-y-2 left-10 -right-2 rounded-xl bg-white/70 dark:bg-slate-700/70 border border-white/40 dark:border-white/10 shadow-lg"
              animate={{ opacity: anim.nextOpacity, ...sebaranNext }}
              transition={infoDragX ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 26 }}
            />
          )}
          {hasPrevAsset && (
            <motion.div
              aria-hidden="true"
              className="absolute inset-y-2 right-10 -left-2 rounded-xl bg-white/70 dark:bg-slate-700/70 border border-white/40 dark:border-white/10 shadow-lg"
              animate={{ opacity: anim.prevOpacity, ...sebaranPrev }}
              transition={infoDragX ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 26 }}
            />
          )}
          <motion.div
            className="relative bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-xl p-3 border border-white/50 dark:border-white/15 shadow-xl"
            animate={{ x: infoDragX, scale: infoDragX ? anim.frontScale : 1 }}
            transition={infoDragX ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 26 }}
          >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0 space-y-1.5">
              <h3 className="text-slate-900 dark:text-white font-semibold text-sm truncate">{a.name || a.asset_name || "Tanpa Nama"}</h3>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-700 dark:text-white/80">
                {a.asset_code && <span className="flex items-center gap-0.5"><QrCode className="w-3 h-3" /> {a.asset_code}</span>}
                {(a.nup || a.NUP) && <span>NUP: {a.nup || a.NUP}</span>}
                {a.location && <span className="flex items-center gap-0.5"><MapPin className="w-3 h-3" /> {a.location}</span>}
                {a.category && <span className="flex items-center gap-0.5"><Tag className="w-3 h-3" /> {a.category}</span>}
                {(a.person_responsible || a.user) && <span className="flex items-center gap-0.5"><User className="w-3 h-3" /> {a.person_responsible || a.user}</span>}
                {price && <span className="font-semibold text-emerald-700 dark:text-emerald-300">{price}</span>}
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {a.condition && <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.condition === 'Baik' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/50 dark:text-emerald-100' : a.condition === 'Rusak Ringan' ? 'bg-amber-100 text-amber-700 dark:bg-amber-600/50 dark:text-amber-100' : 'bg-red-100 text-red-700 dark:bg-red-600/50 dark:text-red-100'}`}>{a.condition}</span>}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${invStatus === 'Ditemukan' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/40 dark:text-emerald-200' : invStatus === 'Tidak Ditemukan' ? 'bg-red-100 text-red-700 dark:bg-red-600/40 dark:text-red-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-600/40 dark:text-slate-200'}`}>{invStatus}</span>
                {docTotal > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full flex items-center gap-0.5 font-medium ${docChecked === docTotal ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-600/40 dark:text-emerald-200' : 'bg-amber-100 text-amber-700 dark:bg-amber-600/40 dark:text-amber-200'}`}>
                    {docChecked === docTotal ? <FileCheck className="w-2.5 h-2.5" /> : <FileX className="w-2.5 h-2.5" />}
                    Dok {docChecked}/{docTotal}
                  </span>
                )}
                {a.stiker_status && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${a.stiker_status === 'Sudah Terpasang' ? 'bg-violet-100 text-violet-700 dark:bg-violet-600/40 dark:text-violet-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-600/40 dark:text-slate-200'}`}>
                    <StickyNote className="w-2.5 h-2.5 inline mr-0.5" />
                    {a.stiker_status === 'Sudah Terpasang' ? 'Stiker ✓' : 'Stiker ✗'}
                  </span>
                )}
              </div>
            </div>
            {onEdit && (
              <button
                className="flex-shrink-0 text-xs bg-teal-600/80 hover:bg-teal-700 text-white px-3 py-1.5 rounded-lg transition-colors"
                onClick={(e) => { e.stopPropagation(); onClose(); onEdit(a); }}
              >
                Edit
              </button>
            )}
          </div>
            {sibIndex >= 0 && siblings.length > 1 && (
              <div className="mt-2 text-center text-[10px] text-slate-500 dark:text-white/50">
                Aset {sibIndex + 1} / {siblings.length} · geser untuk pindah aset
              </div>
            )}
          </motion.div>
        </div>
      </div>
      {deleteTarget && <ConfirmPhotoDelete src={deleteTarget.src} busy={deleting}
        onCancel={() => setDeleteTarget(null)} onConfirm={deletePhoto} />}
      {fullscreen && fullSrc && (
        <FullscreenPhoto src={fullSrc} alt={a.name || a.asset_name} rot={rot} onClose={closeFullscreen}>
          {onEdit && <button type="button" disabled={!metadataReady || rotating || deleting}
            onClick={e => { e.stopPropagation(); setFullscreen(false); requestDelete(); }} aria-label="Hapus foto"
            data-testid="lightbox-fullscreen-delete" className="absolute left-3 top-3 z-10 w-11 h-11 rounded-full bg-red-600/90 text-white flex items-center justify-center disabled:opacity-50"><Trash2 className="w-5 h-5" /></button>}
        </FullscreenPhoto>
      )}
    </div>,
    document.body
  );
});
Lightbox.displayName = "Lightbox";

export default Lightbox;
