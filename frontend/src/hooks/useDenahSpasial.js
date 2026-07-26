// Lapisan DENAH pada peta aset — poligon berlapis (Kawasan → … → Ruangan)
// dari `spasial_node`, dimuat per-viewport dengan LOD per zoom.
//
// Kenapa hook terpisah dari AssetMapFullView: siklus hidupnya berbeda. Pin aset
// mengikuti filter daftar, sedangkan denah mengikuti VIEWPORT peta. Digabung,
// tiap geser peta akan ikut memicu ulang logika pin.
//
// Sisi murni (LOD, gaya, cache bbox) ada di lib/spasialDenah.js dan diuji unit;
// di sini hanya perkabelan Leaflet + fetch.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import axios from "axios";
import { toast } from "sonner";
import { SATKER_AKTIF_EVENT } from "../lib/satkerAktif";
import {
  ORDINAL_GEDUNG, bboxDariBatas, bboxKeParam, gayaFitur, kelompokPerLevel,
  labelLevel, levelMaksUntukZoom, perluMuatUlang, urutFitur, urutLantaiTampilan,
} from "../lib/spasialDenah";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Pane sendiri di BAWAH overlay & marker (overlayPane 400, markerPane 600) —
// denah adalah latar, pin aset harus selalu tetap di atasnya dan tetap diklik.
const PANE = "denahSpasial";
const PANE_Z = 380;

// Peta digeser terus saat mencari lokasi; tanpa jeda tiap frame gerakan jadi
// satu request. 300 ms terasa seketika tapi memangkas request drastis.
const JEDA_MUAT_MS = 300;

/** Ambil batas viewport Leaflet → bentuk polos {barat,selatan,timur,utara}. */
function batasPeta(map) {
  try {
    const b = map.getBounds();
    return { barat: b.getWest(), selatan: b.getSouth(), timur: b.getEast(), utara: b.getNorth() };
  } catch {
    return null;
  }
}

export function useDenahSpasial(peta, { aktif = false } = {}) {
  const grupRef = useRef(new Map());      // ordinal -> L.LayerGroup
  const grupRuanganRef = useRef(null);    // ruangan lantai terpilih (di luar LOD)
  const rendererRef = useRef(null);
  const termuatRef = useRef(null);        // { bbox, level_maks, terpotong }
  const seqRef = useRef(0);
  const batalRef = useRef(null);
  const galatRef = useRef(false);         // cegah toast beruntun saat gagal berulang

  const [memuat, setMemuat] = useState(false);
  const [info, setInfo] = useState({ jumlah: 0, jumlah_total: 0, terpotong: false, level_maks: 0 });
  const [cacahPerLevel, setCacahPerLevel] = useState([]);  // [{ordinal, jumlah}]
  const [levelSembunyi, setLevelSembunyi] = useState(() => new Set());
  const [daftarLevel, setDaftarLevel] = useState([]);
  const [gedung, setGedung] = useState(null);       // {id, nama} yang dibuka
  const [lantai, setLantai] = useState([]);
  const [lantaiId, setLantaiId] = useState("");
  const [memuatLantai, setMemuatLantai] = useState(false);

  const levelSembunyiRef = useRef(levelSembunyi);
  useEffect(() => { levelSembunyiRef.current = levelSembunyi; }, [levelSembunyi]);

  // Registry level dipakai untuk LABEL toggle lapis — sekali saja, jarang berubah.
  useEffect(() => {
    if (!aktif || daftarLevel.length) return;
    let batal = false;
    axios.get(`${API}/spasial/level`)
      .then((r) => { if (!batal) setDaftarLevel(r.data?.items || []); })
      .catch(() => { /* label jatuh ke "Tingkat N" — tak perlu ganggu pengguna */ });
    return () => { batal = true; };
  }, [aktif, daftarLevel.length]);

  // ── Grup lapis ────────────────────────────────────────────────────────────
  const ambilGrup = useCallback((ordinal) => {
    if (!peta) return null;
    let g = grupRef.current.get(ordinal);
    if (!g) {
      g = L.layerGroup();
      grupRef.current.set(ordinal, g);
      if (!levelSembunyiRef.current.has(ordinal)) g.addTo(peta);
    }
    return g;
  }, [peta]);

  const bersihkanSemua = useCallback(() => {
    for (const g of grupRef.current.values()) {
      try { g.clearLayers(); peta?.removeLayer(g); } catch { /* peta sudah dilepas */ }
    }
    grupRef.current.clear();
    if (grupRuanganRef.current) {
      try { grupRuanganRef.current.clearLayers(); peta?.removeLayer(grupRuanganRef.current); }
      catch { /* peta sudah dilepas */ }
      grupRuanganRef.current = null;
    }
  }, [peta]);

  // Bangun layer dari FeatureCollection. `keRuangan` = hasil kueri lantai
  // terpilih (di luar LOD viewport) sehingga ditaruh di grup tersendiri.
  const render = useCallback((fitur, { keRuangan = false } = {}) => {
    if (!peta || !rendererRef.current) return;
    const opsiDasar = { pane: PANE, renderer: rendererRef.current };
    if (keRuangan) {
      if (!grupRuanganRef.current) grupRuanganRef.current = L.layerGroup().addTo(peta);
      grupRuanganRef.current.clearLayers();
    } else {
      for (const g of grupRef.current.values()) g.clearLayers();
    }
    // Diurutkan agar poligon besar masuk lebih dulu → tergambar di bawah.
    for (const f of urutFitur(fitur)) {
      const props = f?.properties || {};
      const ordinal = Number(props.ordinal_level) || 0;
      // Ruangan lantai terpilih digambar sebagai SOROTAN — itu yang sedang
      // dicari pengguna, dan tanpa penebalan ia tenggelam di antara poligon
      // gedung/tapak yang warnanya berdekatan.
      const gaya = gayaFitur(ordinal, { terpilih: keRuangan });
      let layer;
      try {
        layer = L.geoJSON(f, {
          ...opsiDasar,
          style: () => gaya,
          // Fitur titik muncul saat hasil TERPOTONG (server hanya kirim titik
          // wakil) — lingkaran kecil sebagai penanda posisi.
          pointToLayer: (_p, latlng) => L.circleMarker(latlng, {
            ...opsiDasar, ...gaya, radius: 5, fillOpacity: 0.75,
          }),
        });
      } catch {
        continue; // geometri rusak dari data lama — lewati, jangan jatuhkan peta
      }
      const nama = props.nama || "(tanpa nama)";
      const kode = props.kode ? ` · ${props.kode}` : "";
      layer.bindTooltip(`${nama}${kode}`, { sticky: true, direction: "top", opacity: 0.92 });
      // Klik GEDUNG membuka pemilih lantai — satu-satunya jalan masuk ke denah
      // dalam ruangan, karena lantai tak bisa disimpulkan dari koordinat 2D.
      if (ordinal === ORDINAL_GEDUNG && props.id) {
        // Identitas objek dijaga bila gedung yang SAMA diklik lagi — kalau tidak,
        // setiap klik ulang membuat objek baru, memicu efek pemuatan lantai, dan
        // membuang lantai yang sedang dipilih beserta denah ruangannya.
        layer.on("click", () => setGedung(
          (lama) => (lama && lama.id === props.id ? lama : { id: props.id, nama })));
      }
      const grup = keRuangan ? grupRuanganRef.current : ambilGrup(ordinal);
      if (grup) grup.addLayer(layer);
    }
  }, [peta, ambilGrup]);

  // ── Muat per-viewport ─────────────────────────────────────────────────────
  const muat = useCallback(async (paksa = false) => {
    if (!peta || !aktif) return;
    // Peta aset SENGAJA bisa dipakai offline (pin dari snapshot lokal). Denah
    // tak punya snapshot, jadi offline cukup dilewati diam-diam — menembak
    // request yang pasti gagal hanya menghasilkan toast galat di lapangan,
    // tempat sinyal memang sering hilang.
    if (typeof navigator !== "undefined" && navigator.onLine === false) return;
    const batas = batasPeta(peta);
    const viewport = bboxDariBatas(batas, 0); // yang BENAR-BENAR terlihat
    if (!viewport) return;
    const levelMaks = levelMaksUntukZoom(peta.getZoom());
    if (!paksa && !perluMuatUlang(termuatRef.current, viewport, levelMaks)) return;

    const diminta = bboxDariBatas(batas);     // dipadding agar geser kecil tak refetch
    const seq = ++seqRef.current;
    try { batalRef.current?.abort(); } catch { /* sudah selesai */ }
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    batalRef.current = ctrl;
    setMemuat(true);
    try {
      const r = await axios.get(`${API}/spasial/geojson`, {
        params: { bbox: bboxKeParam(diminta), level_maks: levelMaks },
        signal: ctrl?.signal,
      });
      if (seq !== seqRef.current) return; // hasil basi
      const fitur = r.data?.features || [];
      const terpotong = !!r.data?.terpotong;
      termuatRef.current = { bbox: diminta, level_maks: levelMaks, terpotong };
      render(fitur);
      const kelompok = kelompokPerLevel(fitur);
      setCacahPerLevel(Array.from(kelompok.entries())
        .map(([ordinal, arr]) => ({ ordinal, jumlah: arr.length }))
        .sort((a, b) => a.ordinal - b.ordinal));
      setInfo({
        jumlah: r.data?.jumlah || fitur.length,
        jumlah_total: r.data?.jumlah_total || fitur.length,
        terpotong,
        level_maks: levelMaks,
      });
      galatRef.current = false;
    } catch (e) {
      if (axios.isCancel?.(e) || e?.name === "CanceledError" || e?.code === "ERR_CANCELED") return;
      if (seq !== seqRef.current) return;
      // Viewport gagal dimuat → jangan tandai termuat, biar percobaan berikutnya
      // (geser sedikit / muat ulang) mencoba lagi.
      termuatRef.current = null;
      if (!galatRef.current) {
        galatRef.current = true;
        toast.error("Gagal memuat denah kawasan");
      }
    } finally {
      if (seq === seqRef.current) setMemuat(false);
    }
  }, [peta, aktif, render]);

  const muatRef = useRef(muat);
  useEffect(() => { muatRef.current = muat; }, [muat]);

  // Pane + renderer canvas. Canvas (bukan SVG) karena ribuan poligon sebagai
  // node DOM membuat peramban HP tersendat saat pan/zoom.
  useEffect(() => {
    if (!peta) return;
    if (!peta.getPane(PANE)) {
      const p = peta.createPane(PANE);
      p.style.zIndex = String(PANE_Z);
    }
    if (!rendererRef.current) {
      rendererRef.current = L.canvas({ pane: PANE, padding: 0.4 });
    }
  }, [peta]);

  // Muat ulang saat peta digeser/di-zoom (dengan jeda).
  useEffect(() => {
    if (!peta || !aktif) return undefined;
    let timer = null;
    const jadwal = () => {
      clearTimeout(timer);
      timer = setTimeout(() => muatRef.current(), JEDA_MUAT_MS);
    };
    peta.on("moveend zoomend", jadwal);
    jadwal(); // muat pertama
    return () => {
      clearTimeout(timer);
      try { peta.off("moveend zoomend", jadwal); } catch { /* peta sudah dilepas */ }
    };
  }, [peta, aktif]);

  // Dimatikan → bersihkan layer & cache supaya dihidupkan lagi tampil data segar.
  useEffect(() => {
    if (aktif) {
      // Dihidupkan lagi = kesempatan baru; jangan warisi peredam toast dari
      // kegagalan sesi sebelumnya, kalau tidak galat berikutnya tak terlihat.
      galatRef.current = false;
      return;
    }
    try { batalRef.current?.abort(); } catch { /* sudah selesai */ }
    seqRef.current += 1;
    bersihkanSemua();
    termuatRef.current = null;
    setMemuat(false);
    setInfo({ jumlah: 0, jumlah_total: 0, terpotong: false, level_maks: 0 });
    setCacahPerLevel([]);
    setGedung(null);
    setLantai([]);
    setLantaiId("");
  }, [aktif, bersihkanSemua]);

  // Ganti Satker Aktif (super-admin) = kumpulan denah yang berbeda sama sekali.
  useEffect(() => {
    if (!aktif) return undefined;
    const onGanti = () => {
      // Kosongkan layer SEKARANG, jangan tunggu respons. Denah satker lama yang
      // masih tergambar selama request berjalan itu menyesatkan, dan bila
      // request-nya gagal ia akan bertahan di layar tanpa batas waktu.
      try { batalRef.current?.abort(); } catch { /* sudah selesai */ }
      seqRef.current += 1;
      for (const g of grupRef.current.values()) g.clearLayers();
      grupRuanganRef.current?.clearLayers();
      termuatRef.current = null;
      galatRef.current = false;      // satker baru berhak atas pesan galatnya sendiri
      setCacahPerLevel([]);
      setInfo({ jumlah: 0, jumlah_total: 0, terpotong: false, level_maks: 0 });
      setGedung(null); setLantai([]); setLantaiId("");
      muatRef.current(true);
    };
    window.addEventListener(SATKER_AKTIF_EVENT, onGanti);
    return () => window.removeEventListener(SATKER_AKTIF_EVENT, onGanti);
  }, [aktif]);

  // Lepas SEMUA saat komponen dibongkar — termasuk membatalkan request yang
  // masih terbang. Tanpa itu responsnya kembali setelah peta dihancurkan dan
  // `render` menulis ke instance Leaflet yang sudah mati.
  useEffect(() => () => {
    try { batalRef.current?.abort(); } catch { /* sudah selesai */ }
    seqRef.current += 1;
    bersihkanSemua();
  }, [bersihkanSemua]);

  // ── Toggle lapis ──────────────────────────────────────────────────────────
  // Pasang ulang SEMUA grup yang tampil menurut ordinal MENAIK. Renderer canvas
  // Leaflet menggambar sesuai urutan penambahan, dan uji-klik memenangkan layer
  // yang digambar TERAKHIR. Jadi `addTo` polos saat me-unhide menaruh (misal)
  // Kawasan di paling atas — poligon raksasa itu lalu mencuri tooltip & klik
  // gedung di bawahnya. Menyusun ulang mengembalikan aturan "besar di bawah".
  const susunUlangUrutan = useCallback((sembunyi) => {
    if (!peta) return;
    const ordinalNaik = Array.from(grupRef.current.keys()).sort((a, b) => a - b);
    for (const o of ordinalNaik) {
      const g = grupRef.current.get(o);
      if (!g) continue;
      try { peta.removeLayer(g); } catch { /* memang belum terpasang */ }
      if (!sembunyi.has(o)) g.addTo(peta);
    }
    // Ruangan lantai terpilih selalu paling atas — itu fokus pengguna.
    if (grupRuanganRef.current) {
      try { peta.removeLayer(grupRuanganRef.current); } catch { /* belum terpasang */ }
      grupRuanganRef.current.addTo(peta);
    }
  }, [peta]);

  const toggleLapis = useCallback((ordinal) => {
    // Efek Leaflet TIDAK boleh dijalankan di dalam updater setState: updater
    // wajib murni, dan React memanggilnya dua kali di StrictMode — yang membuat
    // layer di-pasang-lepas dua kali dan status visual jadi terbalik.
    const sembunyiBaru = new Set(levelSembunyiRef.current);
    if (sembunyiBaru.has(ordinal)) sembunyiBaru.delete(ordinal);
    else sembunyiBaru.add(ordinal);
    levelSembunyiRef.current = sembunyiBaru;
    setLevelSembunyi(sembunyiBaru);
    susunUlangUrutan(sembunyiBaru);
  }, [susunUlangUrutan]);

  // ── Lantai & ruangan ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!gedung?.id) return undefined;
    let batal = false;
    setMemuatLantai(true);
    setLantaiId("");
    axios.get(`${API}/spasial/lantai/${encodeURIComponent(gedung.id)}`)
      .then((r) => {
        if (batal) return;
        const items = urutLantaiTampilan(r.data?.items || []);
        setLantai(items);
        // Gedung satu lantai → langsung tampilkan, tak perlu memilih.
        if (items.length === 1) setLantaiId(items[0].id);
        else if (items.length === 0) toast.info(`${gedung.nama} belum punya denah lantai`);
      })
      .catch(() => { if (!batal) toast.error("Gagal memuat daftar lantai"); })
      .finally(() => { if (!batal) setMemuatLantai(false); });
    return () => { batal = true; };
  }, [gedung]);

  // Ruangan dimuat per LANTAI TERPILIH (bukan lewat LOD viewport): semua lantai
  // berbagi jejak 2D yang sama, jadi menampilkan semuanya sekaligus hanya
  // menghasilkan tumpukan poligon yang tak terbaca.
  //
  // Memakai `dalam` (seluruh keturunan), BUKAN `induk` (anak langsung): registry
  // mengizinkan Lantai → Sayap → Ruangan, sehingga gedung yang memakai sayap
  // akan tampil KOSONG bila hanya anak langsung yang diambil.
  useEffect(() => {
    if (!peta || !aktif) return undefined;
    if (!lantaiId) {
      if (grupRuanganRef.current) grupRuanganRef.current.clearLayers();
      return undefined;
    }
    if (typeof navigator !== "undefined" && navigator.onLine === false) return undefined;
    let batal = false;
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    axios.get(`${API}/spasial/geojson`, { params: { dalam: lantaiId }, signal: ctrl?.signal })
      .then((r) => { if (!batal) render(r.data?.features || [], { keRuangan: true }); })
      .catch((e) => {
        if (batal || axios.isCancel?.(e) || e?.name === "CanceledError" || e?.code === "ERR_CANCELED") return;
        toast.error("Gagal memuat denah ruangan");
      });
    return () => { batal = true; try { ctrl?.abort(); } catch { /* sudah selesai */ } };
  }, [peta, aktif, lantaiId, render]);

  const tutupGedung = useCallback(() => {
    setGedung(null); setLantai([]); setLantaiId("");
    if (grupRuanganRef.current) grupRuanganRef.current.clearLayers();
  }, []);

  const lapis = useMemo(() => cacahPerLevel.map((c) => ({
    ...c,
    label: labelLevel(c.ordinal, daftarLevel),
    tampil: !levelSembunyi.has(c.ordinal),
  })), [cacahPerLevel, daftarLevel, levelSembunyi]);

  return {
    memuat, info, lapis, toggleLapis,
    gedung, lantai, lantaiId, setLantaiId, memuatLantai, tutupGedung,
    muatUlang: useCallback(() => muatRef.current(true), []),
  };
}
