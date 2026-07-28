// Editor DENAH satu node — gambar/ubah/hapus poligon langsung di aplikasi
// (Fase 4). Dimuat LAZY dari SpasialMasterPage: Leaflet + geoman itu berat dan
// mayoritas kunjungan halaman pohon tak pernah membuka editor.
//
// Alur simpan: goresan geoman → fiturKeGeometri (lib murni) → pratinjau
// POST /spasial/validasi-geometri (galat topologi MEMBLOKIR; peringatan
// containment TIDAK — kebijakan backend, lihat topologi_utils.py) → PUT node.
// Bila topologi rusak, server bisa mengusulkan hasil `make_valid`; usulan itu
// DITAWARKAN ke operator, tak pernah diterapkan diam-diam.
import React, { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "@geoman-io/leaflet-geoman-free";
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css";
import "@/lib/leafletImageOverlayRotated";   // efek samping: L.imageOverlay.rotated
import axios from "axios";
import { toast } from "sonner";
import { TENGGAT_BAKA, pesanGalat } from "@/lib/muatAndal";
import {
  Loader2, Save, Trash2, Wand2, X, AlertTriangle,
  ImagePlus, Move, Check, RotateCcw, RefreshCw,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { fiturKeGeometri, payloadSimpan, pusatAwal } from "@/lib/denahEditor";
import { gayaFitur } from "@/lib/spasialDenah";
import { sudutKeLatLng, latLngKeSudut, URUTAN_SUDUT } from "@/lib/denahOverlay";
import { authMediaUrl } from "@/lib/mediaUrl";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAKS_GAMBAR_OVERLAY_MB = 10;

// Marker sudut penempatan gambar — divIcon polos ber-style inline (class
// Tailwind tak selalu sampai ke pane Leaflet).
const LABEL_SUDUT = { tl: "1", tr: "2", bl: "3" };
const JUDUL_SUDUT = { tl: "Kiri-atas gambar", tr: "Kanan-atas gambar", bl: "Kiri-bawah gambar" };
function ikonSudut(k) {
  return L.divIcon({
    className: "",
    html: `<div title="${JUDUL_SUDUT[k]}" style="width:22px;height:22px;border-radius:50%;` +
      `background:#0d9488;color:#fff;font:700 11px/22px sans-serif;text-align:center;` +
      `border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);cursor:move">${LABEL_SUDUT[k]}</div>`,
    iconSize: [22, 22], iconAnchor: [11, 11],
  });
}

// Terjemahan tooltip geoman yang benar-benar tampil di toolbar kita.
const TERJEMAHAN_ID = {
  tooltips: {
    placeMarker: "Klik untuk menaruh titik",
    firstVertex: "Klik untuk menaruh verteks pertama",
    continueLine: "Klik untuk verteks berikutnya",
    finishPoly: "Klik verteks pertama untuk menutup poligon",
  },
  buttonTitles: {
    drawPolyButton: "Gambar poligon",
    drawPolylineButton: "Gambar garis pembelah",
    editButton: "Ubah verteks",
    dragButton: "Geser bentuk",
    cutButton: "Potong lubang",
    deleteButton: "Hapus bentuk",
  },
};

export default function DenahEditor({ node, onClose, onSaved }) {
  // Node DOM peta sebagai STATE (callback ref), bukan useRef: effect init harus
  // jalan TEPAT saat node terpasang. Dengan useRef + dep [], node yang belum
  // siap membuat effect return diam SELAMANYA (lihat catatan di effect init).
  const [wadahEl, setWadahEl] = useState(null);
  const [galatInit, setGalatInit] = useState("");
  // Kegagalan MEMUAT data node (beda dari galatInit = peta gagal dibuat).
  // Menetap di layar sampai berhasil dimuat ulang — lihat catatan di effect.
  const [galatMuat, setGalatMuat] = useState("");
  const [ulangMuat, setUlangMuat] = useState(0);   // dinaikkan tombol "Coba lagi"
  // Pesan tahap yang SEDANG dikerjakan — spinner tanpa keterangan
  // membuat pemuatan berat terbaca sebagai aplikasi macet.
  const [tahap, setTahap] = useState("");
  const mapRef = useRef(null);
  const grupGambarRef = useRef(null);    // layer yang BOLEH diedit (bentuk node ini)
  // Renderer CANVAS khusus KONTEKS (batas induk + tetangga). Poligon kawasan
  // hasil impor bisa puluhan ribu verteks; merendernya sebagai SVG default
  // membangun ratusan <path> secara SINKRON dan MEMBEKUKAN main thread —
  // spinner ikut membeku sehingga tampak "loading terus". Canvas menggambar
  // ribuan bentuk tanpa itu. Bentuk yang DIEDIT tetap SVG (geoman butuh
  // verteks path), jadi hanya konteks yang dipindah ke canvas.
  const rendererKonteksRef = useRef(null);
  const [memuat, setMemuat] = useState(true);
  // Peta siap = init selesai. Efek pemuat DIGERBANG oleh ini: dulu ia membaca
  // mapRef.current langsung dan RETURN DIAM bila map belum ada — meninggalkan
  // `memuat` tersangkut true (spinner selamanya, peta tak pernah tampil).
  // Kini pemuat baru jalan setelah peta siap, dan tak pernah keluar tanpa
  // membereskan spinner (temuan bug lapangan).
  const [petaSiap, setPetaSiap] = useState(false);
  const [menyimpan, setMenyimpan] = useState(false);
  const [cek, setCek] = useState(null);  // hasil pratinjau validasi terakhir
  const [kotor, setKotor] = useState(false);
  // Dokumen node SEGAR dari server. PUT mengganti SELURUH field NodeIn, jadi
  // membangun payload dari prop `node` (snapshot baris pohon, bisa berumur
  // menit) akan MEMBALIKKAN suntingan orang lain — ganti nama / pindah induk
  // yang terjadi setelah pohon dimuat ikut terhapus (temuan tinjauan).
  const [detailNode, setDetailNode] = useState(null);
  // Overlay gambar denah (Fase 7): milik node ini atau warisan moyang terdekat.
  const [overlay, setOverlay] = useState(null);
  const [aturPosisi, setAturPosisi] = useState(false);
  const [opasitas, setOpasitas] = useState(0.7);
  const [sibukOverlay, setSibukOverlay] = useState(false);
  const overlayLayerRef = useRef(null);
  const markerSudutRef = useRef([]);
  const sudutKiniRef = useRef(null);     // sudut mengikuti drag marker (tanpa re-render)
  const sudutAsliRef = useRef(null);     // untuk Batal saat mengatur posisi
  const fileOverlayRef = useRef(null);
  // Pemicu belah dipegang REF: handler geoman dipasang sekali saat init,
  // sedangkan fungsinya perlu membaca state terbaru tiap dipanggil.
  const belahRef = useRef(null);
  const [belah, setBelah] = useState(null);   // {bagian, garis} pratinjau
  const { confirm, confirmDialog } = useConfirm();

  const nodeId = node?.id;

  // ── Init peta + geoman ────────────────────────────────────────────────────
  // DIGERBANG `wadahEl` (callback ref), BUKAN containerRef.current. Dulu effect
  // memeriksa `if (!containerRef.current) return` dengan dep array [] — bila
  // node DOM belum terpasang saat effect pertama jalan, effect RETURN DIAM dan
  // TAK PERNAH DIULANG: peta tak pernah dibuat (tanpa tombol zoom/toolbar) dan
  // `memuat` tetap true selamanya → spinner berputar di atas area putih polos,
  // TANPA galat di console. Callback ref membuat effect jalan TEPAT saat node
  // tersedia (bug lapangan, dibuktikan screenshot: nol chrome Leaflet).
  useEffect(() => {
    if (!wadahEl || mapRef.current) return undefined;
    let map;
    try {
      map = L.map(wadahEl, {
        zoomControl: true, attributionControl: true, maxZoom: 22,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 22, maxNativeZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
    } catch (e) {
      // Kegagalan init HARUS terlihat operator — bukan spinner tanpa akhir.
      setGalatInit(String(e?.message || e || "Peta gagal dimuat"));
      setMemuat(false);
      return undefined;
    }

    // Pane khusus gambar denah: DI ATAS ubin (200), DI BAWAH vektor gambar
    // (overlayPane 400) — alas jiplak tak boleh menutupi poligon, dan tak
    // boleh menelan klik alat gambar.
    const pane = map.createPane("denah-gambar");
    pane.style.zIndex = 350;
    pane.style.pointerEvents = "none";

    const grup = new L.FeatureGroup().addTo(map);
    grupGambarRef.current = grup;
    rendererKonteksRef.current = L.canvas({ padding: 0.5 });

    // Geoman DIPASANG TERPISAH ber-try/catch: bila plugin gagal (versi tak
    // cocok / bundel rusak), peta + ubin TETAP tampil dan node lama tetap
    // terlihat — hanya alat gambar yang absen, dengan pesan jelas. Sebelumnya
    // satu exception di sini membatalkan seluruh init secara senyap.
    try {
    map.pm.setLang("id_kustom", TERJEMAHAN_ID, "en");
    // WAJIB: tanpa ini `_getContainingLayer()` geoman mengembalikan MAP, sehingga
    // "Hapus bentuk" hanya melepas layer dari PETA — registry `_layers` milik
    // FeatureGroup tetap memegangnya. kumpulkanGeometri meng-iterasi grup, jadi
    // bentuk yang "dihapus" tersimpan kembali dengan toast sukses palsu
    // (temuan tinjauan). Dengan layerGroup disetel, create/cut/remove geoman
    // otomatis menambah & mengeluarkan dari grup yang benar.
    map.pm.setGlobalOptions({ layerGroup: grup });
    map.pm.addControls({
      position: "topleft",
      drawPolygon: true, cutPolygon: true,
      editMode: true, dragMode: true, removalMode: true,
      // Bentuk lain tak bermakna untuk denah — sembunyikan agar tak membingungkan.
      drawMarker: false, drawCircleMarker: false,
      // Garis diaktifkan KHUSUS sebagai alat belah (Fase 16) — bukan
      // untuk menggambar bentuk node, yang selalu poligon.
      drawPolyline: true,
      drawRectangle: true, drawCircle: false, drawText: false, rotateMode: false,
    });
    // Dengan setGlobalOptions({layerGroup}) di atas, geoman sendiri yang
    // menambah/mengeluarkan layer dari `grup` — handler ini cukup menandai
    // "ada perubahan" dan membatalkan hasil validasi lama. `removeLayer`
    // defensif tetap dipasang untuk jalur yang melewatkan layerGroup
    // (mis. Edit.remove saat verteks tersisa di bawah minimum).
    // Garis yang digambar BUKAN bentuk node — ia perintah BELAH (Fase 16).
    // Bentuk node selalu poligon, jadi tipe layer sudah cukup membedakannya
    // tanpa mode/tombol tambahan yang harus diingat operator.
    map.on("pm:create", (e) => {
      const lyr = e?.layer;
      const garis = lyr instanceof L.Polyline && !(lyr instanceof L.Polygon);
      if (garis) {
        let gj = null;
        try { gj = lyr.toGeoJSON()?.geometry || null; } catch { gj = null; }
        try { grup.removeLayer(lyr); lyr.remove(); } catch { /* sudah lepas */ }
        if (gj) belahRef.current?.(gj);
        return;                       // garis TIDAK ikut jadi bentuk node
      }
      setKotor(true); setCek(null);
    });
    map.on("pm:cut", (e) => {
      try { grup.removeLayer(e.originalLayer); } catch { /* sudah lepas */ }
      setKotor(true); setCek(null);
    });
    map.on("pm:remove", (e) => {
      try { grup.removeLayer(e.layer); } catch { /* sudah lepas */ }
      setKotor(true); setCek(null);
    });
    grup.on("pm:edit pm:dragend", () => { setKotor(true); setCek(null); });
    } catch (e) {
      setGalatInit("Alat gambar (geoman) gagal dimuat: "
                   + String(e?.message || e) + " — peta tetap bisa dilihat.");
    }

    mapRef.current = map;

    // "Leaflet blank di dalam modal": peta dibuat saat DIALOG MASIH BERANIMASI
    // → kontainer berukuran 0 → 0 ubin dimuat → peta putih polos (tanpa ubin,
    // tombol zoom, maupun toolbar gambar), tampak seperti loading selamanya.
    // Di HP animasi lebih lambat sehingga invalidateSize 80 ms saja terlalu
    // dini (bug lapangan — screenshot: area peta putih tanpa chrome). PENAWAR
    // yang andal: ResizeObserver memanggil invalidateSize TIAP kontainer
    // berubah ukuran (termasuk saat dialog selesai membuka), plus beberapa
    // pemanggilan terjadwal sebagai cadangan bila ResizeObserver tak ada.
    const invalidasi = () => { try { map.invalidateSize(false); } catch { /* peta dibuang */ } };
    const jamInval = [80, 250, 500, 900].map((ms) => setTimeout(invalidasi, ms));
    let ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(invalidasi);
      ro.observe(wadahEl);
    }
    setPetaSiap(true);
    return () => {
      jamInval.forEach(clearTimeout);
      if (ro) ro.disconnect();
      map.remove();
      mapRef.current = null;
      grupGambarRef.current = null;
      rendererKonteksRef.current = null;
      setPetaSiap(false);
    };
  }, [wadahEl]);

  // Pasang/ganti layer gambar denah di peta. Dideklarasikan SEBELUM effect
  // pemuat yang memakainya (dependency array dievaluasi saat render).
  const pasangOverlay = useCallback((ov) => {
    const map = mapRef.current;
    if (!map) return;
    if (overlayLayerRef.current) {
      try { overlayLayerRef.current.remove(); } catch { /* sudah lepas */ }
      overlayLayerRef.current = null;
    }
    const ll = sudutKeLatLng(ov?.sudut);
    if (!ov?.file_id || !ll) return;
    const layer = L.imageOverlay.rotated(
      authMediaUrl(`${API}/spasial/overlay/${ov.file_id}`),
      ll.tl, ll.tr, ll.bl,
      { opacity: ov.opasitas ?? 0.7, interactive: false, pane: "denah-gambar" });
    // Gagal muat (404 / file rusak) tak boleh senyap — tanpa ini alas jiplak
    // kosong dan operator mengira fiturnya mati (temuan tinjauan).
    layer.on("error", () => toast.error(
      "Gambar denah gagal dimuat — file mungkin rusak; coba unggah ulang"));
    layer.addTo(map);
    overlayLayerRef.current = layer;
    sudutKiniRef.current = ov.sudut;
  }, []);

  // ── Muat bentuk tersimpan + konteks sekitar ───────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!petaSiap || !map || !nodeId) return undefined;
    let batal = false;
    // Apakah `map.setView` sudah dipanggil. Tanpa pusat+zoom, Leaflet MELEMPAR
    // pada hampir semua operasi (`getBounds`, `getCenter`, alat gambar), jadi
    // "editor tetap bisa dipakai" hanya BENAR setelah peta terposisi. Watchdog
    // di bawah memakai penanda ini agar tak menjanjikan hal yang mustahil.
    let terposisi = false;
    // Watchdog: apa pun yang terjadi (request menggantung, jaringan mati,
    // galat tak terduga), spinner WAJIB hilang dalam 25 dtk supaya operator
    // tak menatap loading tanpa akhir.
    const jagaWaktu = setTimeout(() => {
      if (batal) return;
      setMemuat(false);
      if (terposisi) {
        toast.error("Memuat konteks peta lambat/gagal — Anda tetap bisa menggambar");
      } else {
        setGalatMuat("Data node tak kunjung dimuat (jaringan lambat atau server sibuk).");
      }
    }, 25000);
    // Timeout per-request supaya satu endpoint yang menggantung tak menahan
    // seluruh pemuatan sampai watchdog.
    const OPS = { timeout: TENGGAT_BAKA };
    (async () => {
      setMemuat(true);
      setGalatMuat("");
      // Bentuk node ditambahkan ke grup ini di bawah. Pada percobaan ULANG grup
      // bisa sudah berisi hasil percobaan sebelumnya yang gagal di tengah;
      // tanpa dibersihkan, kumpulkanGeometri akan menyimpan poligon GANDA.
      grupGambarRef.current?.clearLayers();
      try {
        setTahap("Mengambil batas wilayah…");
        const detail = (await axios.get(`${API}/spasial/node/${nodeId}`, OPS)).data;
        if (batal) return;
        setDetailNode(detail);
        // Gambar denah yang berlaku (milik sendiri / warisan lantai-gedung).
        if (detail?.overlay_efektif) {
          setOverlay(detail.overlay_efektif);
          setOpasitas(detail.overlay_efektif.opasitas ?? 0.7);
          pasangOverlay(detail.overlay_efektif);
        }
        // Batas INDUK diambil PARALEL dengan penempatan peta di bawah, bukan
        // berurutan. Versi lama menunggu dua poligon besar selesai satu per
        // satu sebelum apa pun tampil — untuk kawasan berverteks ribuan itulah
        // "peta lambat lalu akhirnya muncul" yang dilaporkan lapangan. Kini
        // peta terpasang setelah permintaan PERTAMA; induk menyusul.
        const janjiInduk = detail?.parent_id
          ? axios.get(`${API}/spasial/node/${detail.parent_id}`, OPS)
              .then((r) => r.data)
              .catch(() => null)   // lintas-hak/terhapus — konteks, bukan galat
          : Promise.resolve(null);
        if (batal) return;

        setTahap("Menempatkan peta…");
        const induk = await janjiInduk;
        if (batal) return;
        // Batas INDUK sebagai panduan (garis tebal, tak bisa diedit).
        if (induk?.geometry) {
          // TETAP interaktif — `interactive:false` membuat renderer tak pernah
          // mendaftarkan event mouse, sehingga tooltip sticky (butuh mouseover)
          // tak pernah muncul. `pmIgnore` sudah melindunginya dari edit/cut
          // geoman, dan klik pada path tetap merambat ke peta sehingga
          // menggambar tak terganggu.
          L.geoJSON({ type: "Feature", geometry: induk.geometry }, {
            style: { color: "#0f766e", weight: 3, dashArray: "8,6", fillOpacity: 0.03 },
            pmIgnore: true, renderer: rendererKonteksRef.current,
          }).addTo(map).bindTooltip(`Batas induk: ${induk.nama || ""}`, { sticky: true });
        }
        // Posisikan peta + muat bentuk NODE INI (editable) LEBIH DULU — inilah
        // yang dibutuhkan untuk menggambar. Spinner dibereskan tepat setelah
        // ini; konteks tetangga menyusul di latar. Jadi peta selalu tampil
        // seketika, bahkan bila panggilan konteks lambat/gagal/menggantung —
        // penyebab "loading terus tak menampilkan apa pun" (bug lapangan).
        const pusat = pusatAwal(detail, induk);
        map.setView([pusat.lat, pusat.lng], pusat.zoom);
        terposisi = true;
        // Watchdog bisa sudah menyerah lebih dulu (permintaan mengantre di
        // belakang batas koneksi peramban, jadi tenggat per-request-nya belum
        // mulai berjalan) lalu datanya toh sampai. Tanpa baris ini pesan galat
        // itu MENETAP menutupi peta yang justru sudah siap dipakai.
        if (!batal) setGalatMuat("");
        if (detail?.geometry) {
          const lyr = L.geoJSON({ type: "Feature", geometry: detail.geometry });
          lyr.eachLayer((l) => grupGambarRef.current?.addLayer(l));
          // maxZoom WAJIB: untuk geometri TITIK, getBounds() sah (kotak
          // nol-luas) dan fitBounds TIDAK melempar — tanpa plafon peta melompat
          // ke zoom 22 (temuan tinjauan).
          try {
            map.fitBounds(grupGambarRef.current.getBounds().pad(0.3),
                          { maxZoom: 19 });
          } catch { /* grup kosong / titik tunggal */ }
        }
        clearTimeout(jagaWaktu);
        if (!batal) { setMemuat(false); setTahap("Memuat kawasan sekitar…"); }

        // Tetangga di sekitar sebagai konteks redup (best-effort, canvas).
        try {
          const b = map.getBounds();
          const bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
            .map((v) => v.toFixed(6)).join(",");
          // Konteks dibatasi ke tingkat node ini KE ATAS (ordinal <= level
          // node): menggambar Gedung tak perlu menarik SETIAP ruangan & lantai
          // dalam viewport — payload + render terberat, tak berguna sebagai
          // orientasi. Tanpa batas ini `level_maks` default 100 = seluruh pohon.
          const level_maks = Number(detail?.ordinal_level) || 100;
          // `asli: 0` DITULIS TERANG-TERANGAN: tetangga di sini hanya latar
          // orientasi (tak bisa diklik, tak ikut tersimpan), jadi versi ringan
          // sudah cukup dan editor tetap ringan di HP. Bentuk yang DISUNTING
          // datang dari `detail.geometry` — selalu yang asli.
          const ctx = (await axios.get(`${API}/spasial/geojson`,
            { params: { bbox, level_maks, asli: 0 }, timeout: 20000 })).data;
          if (batal) return;
          for (const f of ctx?.features || []) {
            if (f?.properties?.id === nodeId) continue;   // bentuk sendiri = editable, bukan konteks
            if (induk && f?.properties?.id === induk.id) continue;
            L.geoJSON(f, {
              style: { ...gayaFitur(f?.properties?.ordinal_level), opacity: 0.5 },
              pmIgnore: true, interactive: false,
              renderer: rendererKonteksRef.current,
            }).addTo(map);
          }
        } catch { /* konteks gagal — editor tetap berfungsi */ }
        if (!batal) setTahap("");        // konteks selesai; penanda latar padam
      } catch (e) {
        // Kegagalan di sini berarti `map.setView` tak pernah dipanggil: peta
        // tinggal kanvas putih. Dulu satu-satunya jejaknya adalah toast yang
        // padam beberapa detik kemudian, meninggalkan layar yang tampak rusak
        // tanpa satu pun jalan pulih — pemulihan hanya lewat tutup lalu buka
        // ulang dialog. Kini pesannya MENETAP dengan tombol Coba lagi.
        if (!batal) setGalatMuat(pesanGalat(e, "Gagal memuat data node"));
      } finally {
        clearTimeout(jagaWaktu);
        if (!batal) { setMemuat(false); setTahap(""); }
      }
    })();
    return () => { batal = true; clearTimeout(jagaWaktu); };
  }, [nodeId, petaSiap, pasangOverlay, ulangMuat]);

  // ── Belah wilayah dengan garis (Fase 16) ──────────────────────────────────
  const mintaBelah = useCallback(async (garis, terapkan) => {
    if (!nodeId) return;
    setMenyimpan(true);
    try {
      const r = await axios.post(`${API}/spasial/node/${nodeId}/belah`,
                                 { garis, terapkan });
      if (terapkan) {
        toast.success(`Wilayah dibelah menjadi ${r.data?.jumlah} bagian`);
        setBelah(null);
        onSaved?.();
        onClose?.();          // pohon dimuat ulang; editor node ini sudah basi
      } else {
        setBelah({ garis, bagian: r.data?.bagian || [] });
      }
    } catch (e) {
      // Pesan server sengaja berupa kalimat yang bisa ditindaklanjuti
      // ("tarik garis melintas penuh…"), jadi ditampilkan apa adanya.
      toast.error(e?.response?.data?.detail || "Pembelahan gagal", { duration: 8000 });
      setBelah(null);
    } finally { setMenyimpan(false); }
  }, [nodeId, onSaved, onClose]);

  // Handler geoman dipasang SEKALI saat init, jadi ia harus memanggil versi
  // TERBARU lewat ref — bukan closure yang membeku pada render pertama.
  useEffect(() => { belahRef.current = (g) => mintaBelah(g, false); }, [mintaBelah]);

  // ── Overlay gambar denah (Fase 7) ─────────────────────────────────────────
  const lepasMarkerSudut = useCallback(() => {
    for (const m of markerSudutRef.current) {
      try { m.remove(); } catch { /* peta sudah dibuang */ }
    }
    markerSudutRef.current = [];
  }, []);

  const mulaiAturPosisi = useCallback(() => {
    const map = mapRef.current;
    const ll = sudutKeLatLng(sudutKiniRef.current);
    if (!map || !ll) return;
    sudutAsliRef.current = sudutKiniRef.current;
    lepasMarkerSudut();
    markerSudutRef.current = URUTAN_SUDUT.map((k) => {
      const m = L.marker(ll[k], { icon: ikonSudut(k), draggable: true,
                                  pmIgnore: true, zIndexOffset: 1000 }).addTo(map);
      m.on("drag dragend", () => {
        const pos = {};
        URUTAN_SUDUT.forEach((kk, i) => { pos[kk] = markerSudutRef.current[i].getLatLng(); });
        const sudut = latLngKeSudut(pos);
        if (sudut) {
          sudutKiniRef.current = sudut;
          overlayLayerRef.current?.reposition(pos.tl, pos.tr, pos.bl);
        }
      });
      return m;
    });
    setAturPosisi(true);
  }, [lepasMarkerSudut]);

  const simpanPosisi = useCallback(async () => {
    setSibukOverlay(true);
    try {
      await axios.put(`${API}/spasial/node/${nodeId}/overlay`,
                      { sudut: sudutKiniRef.current, opasitas });
      setOverlay((o) => (o ? { ...o, sudut: sudutKiniRef.current, opasitas } : o));
      lepasMarkerSudut();
      setAturPosisi(false);
      toast.success("Penempatan gambar tersimpan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan penempatan");
    } finally {
      setSibukOverlay(false);
    }
  }, [nodeId, opasitas, lepasMarkerSudut]);

  const batalPosisi = useCallback(() => {
    const asli = sudutAsliRef.current;
    const ll = sudutKeLatLng(asli);
    if (ll) {
      sudutKiniRef.current = asli;
      overlayLayerRef.current?.reposition(ll.tl, ll.tr, ll.bl);
    }
    lepasMarkerSudut();
    setAturPosisi(false);
  }, [lepasMarkerSudut]);

  const unggahOverlay = useCallback(async (f) => {
    if (!f) return;
    if (f.size > MAKS_GAMBAR_OVERLAY_MB * 1024 * 1024) {
      toast.error(`Gambar melebihi ${MAKS_GAMBAR_OVERLAY_MB} MB — perkecil dulu`);
      return;
    }
    setSibukOverlay(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await axios.post(`${API}/spasial/node/${nodeId}/overlay`, fd);
      setOverlay(r.data);
      setOpasitas(r.data?.opasitas ?? 0.7);
      pasangOverlay(r.data);
      toast.success("Gambar denah terpasang — atur posisinya lalu jiplak ruangan");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal mengunggah gambar denah");
    } finally {
      setSibukOverlay(false);
      if (fileOverlayRef.current) fileOverlayRef.current.value = "";
    }
  }, [nodeId, pasangOverlay]);

  const hapusOverlay = useCallback(async () => {
    const ok = await confirm({
      title: "Hapus gambar denah?",
      description: "Gambar alas jiplak node ini dihapus permanen. Poligon yang sudah digambar TIDAK ikut terhapus.",
      confirmText: "Hapus", variant: "destructive",
    });
    if (!ok) return;
    setSibukOverlay(true);
    try {
      await axios.delete(`${API}/spasial/node/${nodeId}/overlay`);
      batalPosisi();
      if (overlayLayerRef.current) {
        try { overlayLayerRef.current.remove(); } catch { /* sudah lepas */ }
        overlayLayerRef.current = null;
      }
      // Jatuh kembali ke overlay WARISAN moyang (bila ada) — server yang
      // menghitung; tanpa ini state sesi menyimpang dari kondisi tersimpan
      // sampai editor dibuka ulang (temuan tinjauan).
      let waris = null;
      try {
        waris = (await axios.get(`${API}/spasial/node/${nodeId}`))
          .data?.overlay_efektif || null;
      } catch { /* jaringan goyah — biarkan kosong */ }
      setOverlay(waris);
      if (waris) {
        setOpasitas(waris.opasitas ?? 0.7);
        pasangOverlay(waris);
      }
      toast.success("Gambar denah dihapus");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menghapus gambar denah");
    } finally {
      setSibukOverlay(false);
    }
  }, [nodeId, confirm, batalPosisi, pasangOverlay]);

  // Slider opasitas: visual seketika; nilai dipersistkan saat slider DILEPAS
  // (overlay milik node ini) — dulu hanya tersimpan lewat "Simpan Posisi",
  // jadi menggeser opasitas saja diam-diam kembali ke nilai lama saat editor
  // dibuka lagi (temuan tinjauan). Overlay warisan: sesi ini saja.
  const ubahOpasitas = useCallback((v) => {
    setOpasitas(v);
    overlayLayerRef.current?.setOpacity(v);
  }, []);

  const overlayMilikSendiri = overlay?.dari_node === nodeId;

  const simpanOpasitas = useCallback(async () => {
    if (!overlayMilikSendiri || !sudutKiniRef.current) return;
    try {
      await axios.put(`${API}/spasial/node/${nodeId}/overlay`,
                      { sudut: sudutKiniRef.current, opasitas });
      setOverlay((o) => (o ? { ...o, opasitas } : o));
    } catch {
      toast.error("Opasitas gagal tersimpan — periksa koneksi");
    }
  }, [overlayMilikSendiri, nodeId, opasitas]);

  const kumpulkanGeometri = useCallback(() => {
    const fitur = [];
    grupGambarRef.current?.eachLayer((l) => {
      try { fitur.push(l.toGeoJSON()); } catch { /* layer tanpa geometri */ }
    });
    return fiturKeGeometri(fitur).geometry;   // null = kosong (hapus bentuk)
  }, []);

  // ── Pratinjau validasi (tanpa simpan) ─────────────────────────────────────
  const periksa = useCallback(async () => {
    const geometry = kumpulkanGeometri();
    if (geometry === null) return { valid: true, kosong: true, peringatan: [] };
    try {
      const r = await axios.post(`${API}/spasial/validasi-geometri`, {
        geometry, tipe: node?.tipe || "", parent_id: node?.parent_id || "",
      });
      return { ...r.data, kosong: false, geometry };
    } catch (e) {
      return { valid: false, kosong: false,
               galat: e?.response?.data?.detail || "Validasi gagal — periksa koneksi",
               peringatan: [] };
    }
  }, [kumpulkanGeometri, node]);

  const simpan = useCallback(async () => {
    setMenyimpan(true);
    try {
      const hasil = await periksa();
      setCek(hasil);
      if (!hasil.valid) return;                 // galat tampil di panel bawah
      const geometry = hasil.kosong ? null : hasil.geometry;
      // Ambil detail SEGAR tepat sebelum PUT: dialog bisa terbuka lama sementara
      // orang lain mengganti nama / memindah induk node ini. PUT mengganti
      // SELURUH field, jadi memakai snapshot lama akan membalikkan suntingan
      // mereka tanpa jejak. `detailNode` (hasil GET saat dialog dibuka) jadi
      // cadangan bila fetch ulang gagal.
      //
      // Prop `node` — item dari DAFTAR — SENGAJA TIDAK lagi dipakai sebagai
      // cadangan. Daftar itu diproyeksikan ramping (tanpa `properties`, demi
      // payload pohon), sehingga memakainya sebagai dasar PUT yang mengganti
      // seluruh field akan MENGHAPUS jejak audit impor dan denah overlay node
      // ini — kehilangan data senyap, ditukar dengan kenyamanan menyimpan.
      // Bila tak ada dasar yang lengkap, menolak menyimpan adalah sikap yang
      // benar: gambar tetap di layar dan bisa disimpan lagi setelah sinyal pulih.
      let dasar = detailNode;
      try {
        dasar = (await axios.get(`${API}/spasial/node/${nodeId}`,
                                 { timeout: TENGGAT_BAKA })).data || dasar;
      } catch { /* jaringan goyah — pakai detail dari pembukaan dialog */ }
      if (!dasar) {
        toast.error("Belum bisa menyimpan: data node terbaru gagal dimuat. "
                    + "Periksa sinyal lalu tekan Simpan lagi — gambar Anda "
                    + "masih ada di layar dan tidak hilang.", { duration: 9000 });
        return;
      }
      const r = await axios.put(`${API}/spasial/node/${nodeId}`,
                                payloadSimpan(dasar, geometry));
      for (const p of r.data?.peringatan || []) toast.warning(p, { duration: 8000 });
      toast.success(hasil.kosong ? "Bentuk dihapus" : "Denah tersimpan");
      onSaved?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Gagal menyimpan denah");
    } finally {
      setMenyimpan(false);
    }
  // `node` (item DAFTAR) sengaja BUKAN lagi dependensi: ia tak lagi dipakai
  // sebagai dasar PUT — lihat alasannya di dalam fungsi ini.
  }, [periksa, nodeId, detailNode, onSaved, onClose]);

  // Terapkan usulan make_valid dari server: ganti seluruh isi grup gambar.
  const terapkanPerbaikan = useCallback(() => {
    const usul = cek?.perbaikan;
    if (!usul || !grupGambarRef.current) return;
    grupGambarRef.current.clearLayers();
    const lyr = L.geoJSON({ type: "Feature", geometry: usul });
    lyr.eachLayer((l) => grupGambarRef.current.addLayer(l));
    setCek(null); setKotor(true);
    toast.info("Perbaikan otomatis diterapkan — periksa bentuknya lalu simpan");
  }, [cek]);

  const hapusBentuk = useCallback(() => {
    grupGambarRef.current?.clearLayers();
    setKotor(true); setCek(null);
  }, []);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent
        className="max-w-4xl p-0 gap-0 overflow-hidden"
        data-testid="denah-editor"
        // Escape dipakai geoman untuk MEMBATALKAN goresan yang sedang digambar;
        // membiarkan Radix ikut menutup dialog berarti satu tekan Escape
        // membuang seluruh pekerjaan. Tutup lewat tombol Batal/X saja.
        onEscapeKeyDown={(e) => e.preventDefault()}
        // Klik di luar saat ada perubahan belum tersimpan (goresan ATAU
        // penempatan gambar yang sedang diatur) = kehilangan kerja tanpa
        // peringatan — cegah; tanpa perubahan, tutup seperti biasa.
        onInteractOutside={(e) => { if (kotor || aturPosisi) e.preventDefault(); }}
      >
        <DialogHeader className="px-4 pt-3 pb-2 border-b border-border">
          <DialogTitle className="text-sm flex items-center gap-2">
            Denah: {node?.nama}
            <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{node?.tipe}</span>
          </DialogTitle>
          <DialogDescription className="text-xs">
            Gambar poligon dengan alat di kiri peta. Garis putus-putus hijau = batas induk.
          </DialogDescription>
        </DialogHeader>

        {/* Alas jiplak: gambar denah lantai (Fase 7). Interior tak terlihat di
            citra satelit — unggah ekspor CAD/PDF (PNG/JPG), tempatkan dengan
            3 titik sudut, lalu jiplak ruangan di atasnya. */}
        <div className="px-4 py-1.5 border-b border-border flex flex-wrap items-center gap-2 text-xs"
             data-testid="denah-overlay-bar">
          <input ref={fileOverlayRef} type="file" className="hidden"
                 accept="image/png,image/jpeg,image/webp"
                 onChange={(e) => unggahOverlay(e.target.files?.[0])}
                 data-testid="denah-overlay-file" />
          {!overlay && (
            <>
              <Button variant="outline" size="sm" className="h-7 text-xs"
                      disabled={sibukOverlay || memuat}
                      onClick={() => fileOverlayRef.current?.click()}
                      data-testid="denah-overlay-unggah">
                {sibukOverlay ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                              : <ImagePlus className="w-3.5 h-3.5 mr-1" />}
                Unggah Gambar Denah
              </Button>
              <span className="text-muted-foreground">
                alas jiplak dari CAD/PDF (PNG/JPG, maks {MAKS_GAMBAR_OVERLAY_MB} MB)
              </span>
            </>
          )}
          {overlay && (
            <>
              <span className="truncate max-w-[180px]" title={overlay.nama_file}>
                🖼 {overlay.nama_file}
                {!overlayMilikSendiri && (
                  <span className="text-muted-foreground"> (warisan {overlay.dari_nama})</span>
                )}
              </span>
              <label className="flex items-center gap-1.5">
                <span className="text-muted-foreground">Opasitas</span>
                <input type="range" min="0.1" max="1" step="0.05" value={opasitas}
                       onChange={(e) => ubahOpasitas(Number(e.target.value))}
                       onMouseUp={simpanOpasitas} onTouchEnd={simpanOpasitas}
                       className="w-24 accent-teal-600" data-testid="denah-overlay-opasitas" />
              </label>
              {overlayMilikSendiri && !aturPosisi && (
                <Button variant="outline" size="sm" className="h-7 text-xs"
                        disabled={sibukOverlay || memuat} onClick={mulaiAturPosisi}
                        data-testid="denah-overlay-atur">
                  <Move className="w-3.5 h-3.5 mr-1" />Atur Posisi
                </Button>
              )}
              {aturPosisi && (
                <>
                  <Button size="sm" className="h-7 text-xs" disabled={sibukOverlay}
                          onClick={simpanPosisi} data-testid="denah-overlay-simpan-posisi">
                    {sibukOverlay ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                                  : <Check className="w-3.5 h-3.5 mr-1" />}
                    Simpan Posisi
                  </Button>
                  <Button variant="outline" size="sm" className="h-7 text-xs"
                          disabled={sibukOverlay} onClick={batalPosisi}
                          data-testid="denah-overlay-batal-posisi">
                    <RotateCcw className="w-3.5 h-3.5 mr-1" />Batal
                  </Button>
                </>
              )}
              {overlayMilikSendiri && !aturPosisi && (
                <>
                  <Button variant="outline" size="sm" className="h-7 text-xs"
                          disabled={sibukOverlay} onClick={() => fileOverlayRef.current?.click()}
                          data-testid="denah-overlay-ganti">
                    <ImagePlus className="w-3.5 h-3.5 mr-1" />Ganti
                  </Button>
                  <Button variant="outline" size="sm" className="h-7 text-xs text-red-600"
                          disabled={sibukOverlay} onClick={hapusOverlay}
                          data-testid="denah-overlay-hapus">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </>
              )}
              {!overlayMilikSendiri && (
                <Button variant="outline" size="sm" className="h-7 text-xs"
                        disabled={sibukOverlay || memuat}
                        onClick={() => fileOverlayRef.current?.click()}
                        title="Unggah gambar khusus node ini (menimpa warisan saat ditampilkan)"
                        data-testid="denah-overlay-unggah-sendiri">
                  <ImagePlus className="w-3.5 h-3.5 mr-1" />Unggah utk node ini
                </Button>
              )}
            </>
          )}
        </div>

        <div className="relative">
          {/* callback ref: effect init jalan TEPAT saat node terpasang */}
          <div ref={setWadahEl} className="h-[52vh] min-h-[320px] w-full" data-testid="denah-editor-peta" />
          {/* Spinner BERKETERANGAN. Denah kawasan bisa berverteks puluhan ribu
              dan pemuatannya memang lama; lingkaran berputar tanpa kata membuat
              operator menyimpulkan aplikasi macet lalu menutup dialog tepat saat
              prosesnya hampir selesai (laporan lapangan). */}
          {memuat && (
            <div className="absolute inset-0 z-[500] bg-background/70 flex flex-col
                            items-center justify-center gap-2"
                 data-testid="denah-memuat">
              <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
              <p className="text-xs font-medium text-foreground">
                {tahap || "Menyiapkan peta…"}
              </p>
              <p className="text-[10px] text-muted-foreground max-w-[16rem] text-center">
                Denah kawasan besar butuh beberapa detik. Proses berjalan di
                latar — jangan tutup jendela ini.
              </p>
            </div>
          )}
          {/* Gagal memuat data node = peta TAK PERNAH diposisikan; yang tersisa
              hanyalah kanvas kosong. Pesan ini MENETAP (bukan toast yang padam)
              dan membawa jalan pulih di tempat, supaya operator tak perlu
              menutup lalu membuka ulang dialog untuk mencoba lagi. */}
          {!memuat && galatMuat && (
            <div className="absolute inset-0 z-[600] bg-background/95 flex flex-col
                            items-center justify-center gap-2 px-4 text-center"
                 data-testid="denah-galat-muat">
              <AlertTriangle className="w-6 h-6 text-red-600" />
              <p className="text-xs font-medium text-red-700 dark:text-red-300 max-w-[22rem] break-words">
                {galatMuat}
              </p>
              <p className="text-[10px] text-muted-foreground max-w-[20rem]">
                Bentuk tersimpan dan batas wilayah belum tampil. Menggambar
                sekarang berisiko menimpa data yang belum sempat dimuat.
              </p>
              <Button size="sm" variant="outline" className="mt-1 h-7 text-xs"
                      onClick={() => setUlangMuat((n) => n + 1)}
                      data-testid="denah-muat-ulang">
                <RefreshCw className="w-3.5 h-3.5 mr-1" />Coba lagi
              </Button>
            </div>
          )}
          {/* Konteks sekitar masih menyusul SETELAH peta bisa dipakai — ditandai
              tipis di pojok agar terlihat bekerja tanpa memblokir menggambar. */}
          {!memuat && tahap && (
            <div className="absolute bottom-2 left-2 z-[500] rounded-md bg-background/85
                            border border-border px-2 py-1 flex items-center gap-1.5"
                 data-testid="denah-tahap-latar">
              <Loader2 className="w-3 h-3 animate-spin text-teal-600" />
              <span className="text-[10px] text-muted-foreground">{tahap}</span>
            </div>
          )}
        </div>
        {/* Konfirmasi belah — membelah wilayah mahal dibatalkan, jadi hasilnya
            ditunjukkan lebih dulu berikut luas tiap bagian. Bagian pertama
            MEMPERTAHANKAN node asal (beserta aset & riwayatnya); sisanya lahir
            sebagai draft yang masih harus diperiksa. */}
        {belah && (
          <div className="px-4 py-2 border-t border-border bg-teal-500/10"
               data-testid="denah-belah-konfirmasi">
            <p className="text-xs font-semibold">
              Belah wilayah ini menjadi {belah.bagian.length} bagian?
            </p>
            <div className="mt-1 space-y-0.5">
              {belah.bagian.map((b) => (
                <p key={b.urutan} className="text-[11px] text-muted-foreground">
                  {b.urutan}. <b>{b.nama}</b> — {Math.round(b.luas_m2).toLocaleString("id-ID")} m²
                  {b.urutan === 1 && " (tetap memakai node ini)"}
                </p>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              Bagian ke-2 dan seterusnya dibuat sebagai <b>draft</b> — periksa
              dulu, baru aktifkan.
            </p>
            <div className="flex gap-2 mt-2">
              <Button size="sm" className="min-h-0" disabled={menyimpan}
                      onClick={() => mintaBelah(belah.garis, true)}
                      data-testid="denah-belah-terapkan">
                {menyimpan && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
                Ya, belah
              </Button>
              <Button size="sm" variant="outline" className="min-h-0"
                      onClick={() => setBelah(null)}
                      data-testid="denah-belah-batal">Batal</Button>
            </div>
          </div>
        )}

        {/* Kegagalan init peta TAMPIL — bukan spinner tanpa akhir di atas area
            kosong. Pesan ini juga jadi bahan diagnosis bila terulang. */}
        {galatInit && (
          <div className="px-4 py-2 border-t border-border bg-red-500/10 flex items-start gap-2"
               data-testid="denah-galat-init">
            <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
            <p className="text-xs text-red-700 dark:text-red-300 break-words">{galatInit}</p>
          </div>
        )}

        {/* Panel hasil validasi — galat MEMBLOKIR, peringatan tidak. */}
        {cek && !cek.valid && (
          <div className="px-4 py-2 border-t border-border bg-red-500/10 flex items-start gap-2" data-testid="denah-galat">
            <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-red-700 dark:text-red-300">{cek.galat}</p>
              {cek.perbaikan && (
                <Button size="sm" variant="outline" className="mt-1.5 h-7 text-xs"
                        onClick={terapkanPerbaikan} data-testid="denah-terapkan-perbaikan">
                  <Wand2 className="w-3.5 h-3.5 mr-1" />Terapkan perbaikan otomatis
                </Button>
              )}
            </div>
          </div>
        )}
        {cek?.valid && (cek.peringatan || []).map((p, i) => (
          <div key={i} className="px-4 py-2 border-t border-border bg-amber-500/10 flex items-start gap-2" data-testid="denah-peringatan">
            <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-700 dark:text-amber-300">{p}</p>
          </div>
        ))}

        <div className="px-4 py-3 border-t border-border flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={hapusBentuk}
                  className="text-red-600" data-testid="denah-hapus-bentuk">
            <Trash2 className="w-3.5 h-3.5 mr-1" />Kosongkan
          </Button>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => onClose?.()} data-testid="denah-batal">
            <X className="w-3.5 h-3.5 mr-1" />Batal
          </Button>
          <Button size="sm" onClick={simpan} disabled={menyimpan || memuat || !kotor}
                  data-testid="denah-simpan">
            {menyimpan ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                       : <Save className="w-3.5 h-3.5 mr-1" />}
            Simpan Denah
          </Button>
        </div>
        {confirmDialog}
      </DialogContent>
    </Dialog>
  );
}
