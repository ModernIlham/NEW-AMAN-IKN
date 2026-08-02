/**
 * Alat UKUR pada peta Leaflet — jarak & luas, dipakai bersama Peta Aset dan
 * Peta Kolaborasi.
 *
 * Kenapa hook terpisah, bukan disalin ke dua halaman: keduanya butuh perilaku
 * yang PERSIS sama (klik menambah titik, klik-kanan/Escape membatalkan, garis
 * ikut berpindah saat peta digeser). Dua salinan pasti menyimpang, dan
 * penyimpangan pada alat ukur berarti dua angka berbeda untuk bidang yang sama.
 *
 * Perhitungannya sendiri ada di `lib/ukurPeta.js` — murni & diuji unit. Di sini
 * hanya perkabelan Leaflet.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";

import { ringkasUkur, formatJarak } from "../lib/ukurPeta";

const WARNA = "#f59e0b";        // amber — sengaja beda dari semua warna status pin
const WARNA_ISI = "#f59e0b33";

export function useUkurPeta(mapRef, { aktif, onSelesai } = {}) {
  const [titik, setTitik] = useState([]);
  const lapisRef = useRef(null);       // L.LayerGroup untuk garis/bidang/simpul
  const titikRef = useRef([]);

  useEffect(() => { titikRef.current = titik; }, [titik]);

  const bersihkan = useCallback(() => {
    setTitik([]);
    const lapis = lapisRef.current;
    if (lapis) { try { lapis.clearLayers(); } catch { /* peta sudah dilepas */ } }
  }, []);

  // Gambar ulang seluruh bentuk dari daftar titik. Menggambar ulang (bukan
  // menambal) membuat keadaan visual SELALU cerminan data — tak ada jalan bagi
  // garis "hantu" yang tertinggal setelah undo.
  useEffect(() => {
    const map = mapRef?.current;
    if (!map) return;
    if (!lapisRef.current) {
      try { lapisRef.current = L.layerGroup().addTo(map); } catch { return; }
    }
    const lapis = lapisRef.current;
    try { lapis.clearLayers(); } catch { return; }
    if (titik.length === 0) return;

    const latlngs = titik.map((t) => [t.lat, t.lng]);

    // ≥3 titik → bidang tertutup (luas terlihat); 2 titik → garis saja.
    if (titik.length >= 3) {
      L.polygon(latlngs, {
        color: WARNA, weight: 2, fillColor: WARNA_ISI, fillOpacity: 0.25, interactive: false,
      }).addTo(lapis);
    } else if (titik.length === 2) {
      L.polyline(latlngs, { color: WARNA, weight: 2, interactive: false }).addTo(lapis);
    }

    // Simpul kecil + label jarak kumulatif di tiap titik lanjutan, supaya
    // panjang tiap ruas terbaca tanpa harus menutup bidang dulu.
    let kumulatif = 0;
    titik.forEach((t, i) => {
      L.circleMarker([t.lat, t.lng], {
        radius: 4, color: "#fff", weight: 2, fillColor: WARNA, fillOpacity: 1, interactive: false,
      }).addTo(lapis);
      if (i > 0) {
        const r = ringkasUkur(titik.slice(0, i + 1));
        kumulatif = r.panjangMeter;
        L.marker([t.lat, t.lng], {
          interactive: false,
          icon: L.divIcon({
            className: "",
            html: `<span style="background:${WARNA};color:#1c1917;font-size:10px;font-weight:700;
                    padding:1px 5px;border-radius:9999px;white-space:nowrap;
                    box-shadow:0 1px 3px rgba(0,0,0,.35)">${formatJarak(kumulatif)}</span>`,
            iconSize: [0, 0], iconAnchor: [-6, 8],
          }),
        }).addTo(lapis);
      }
    });
  }, [titik, mapRef]);

  // Pasang penangan klik SAAT MODE AKTIF — bukan sekali saat mount.
  //
  // Dulu dipasang sekali di mount dengan penjaga `aktifRef` di dalamnya —
  // kelihatannya hemat, tapi di kedua halaman peta si PETA BARU DIBUAT setelah
  // data termuat (efek init berjalan belakangan), jadi saat efek ini berjalan
  // `mapRef.current` masih null dan listener TIDAK PERNAH terpasang: ketukan
  // di peta tak menambah titik sama sekali (laporan lapangan "alat ukur tidak
  // berfungsi"). Mengaitkan pemasangan pada `aktif` menjamin peta sudah ada —
  // tombolnya baru bisa ditekan setelah peta tampil.
  useEffect(() => {
    if (!aktif) return undefined;
    const map = mapRef?.current;
    if (!map) return undefined;

    const onKlik = (e) => {
      setTitik((t) => [...t, { lat: e.latlng.lat, lng: e.latlng.lng }]);
    };
    // Klik kanan / tekan-lama = UNDO satu titik. Tak memakai dialog: saat
    // mengukur di lapangan, tangan sedang sibuk dan konfirmasi memutus alur.
    const onKananUndo = (e) => {
      if (e.originalEvent) e.originalEvent.preventDefault();
      setTitik((t) => t.slice(0, -1));
    };
    const onTombol = (e) => {
      // Jangan bajak ketikan: Backspace di input/textarea adalah menghapus
      // huruf, bukan membatalkan titik ukur.
      const el = e.target;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) return;
      if (e.key === "Escape") bersihkan();
      if (e.key === "Backspace") setTitik((t) => t.slice(0, -1));
    };

    map.on("click", onKlik);
    map.on("contextmenu", onKananUndo);
    window.addEventListener("keydown", onTombol);
    // Penanda mode di kontainer peta: index.css memakainya untuk (a) kursor
    // crosshair dan (b) mematikan pointer-events pane marker/popup — tanpa
    // itu, ketukan yang jatuh di atas pin aset ditelan popup-nya dan titik
    // ukur tak pernah tertanam di peta yang padat marker.
    const elPeta = typeof map.getContainer === "function" ? map.getContainer() : null;
    if (elPeta) elPeta.classList.add("peta-ukur-aktif");
    return () => {
      try { map.off("click", onKlik); map.off("contextmenu", onKananUndo); } catch { /* peta dilepas */ }
      if (elPeta) { try { elPeta.classList.remove("peta-ukur-aktif"); } catch { /* dilepas */ } }
      window.removeEventListener("keydown", onTombol);
    };
  }, [aktif, mapRef, bersihkan]);

  // Mode dimatikan → buang bentuknya. Hasil terakhir diserahkan ke pemanggil
  // lebih dulu, supaya angkanya bisa dicatat bila memang dibutuhkan.
  useEffect(() => {
    if (aktif) return;
    if (titikRef.current.length > 0) {
      try { onSelesai?.(ringkasUkur(titikRef.current)); } catch { /* jangan sampai menggagalkan pembersihan */ }
    }
    bersihkan();
    // `titik`/`onSelesai` sengaja TIDAK jadi dependensi: efek ini hanya boleh
    // berjalan pada PERALIHAN mode, bukan tiap kali titik bertambah.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aktif]);

  // Lepas lapisan saat komponen dilepas.
  useEffect(() => () => {
    const lapis = lapisRef.current;
    if (lapis) { try { lapis.remove(); } catch { /* noop */ } }
    lapisRef.current = null;
  }, []);

  return {
    titik,
    ringkas: ringkasUkur(titik),
    bersihkan,
    undo: useCallback(() => setTitik((t) => t.slice(0, -1)), []),
  };
}

export default useUkurPeta;
