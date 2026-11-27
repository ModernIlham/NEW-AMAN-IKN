// Lapisan citra eksisting pada Peta Aset — perkabelan React di atas
// lib/lapisanCitra.js (logika murni & pengelola layer ada di sana).
//
// Selama `aktif` false hook ini tidak meminta apa pun ke server dan tidak
// memasang satu layer pun.
import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import {
  ambilDaftarCitra, batasLeaflet, bacaCitraSembunyi, bacaOpasitasCitra,
  buatPengelolaCitra, simpanCitraSembunyi, simpanOpasitasCitra, urutCitra,
  viewportMengenai,
} from "../lib/lapisanCitra";

function viewport(map) {
  try {
    const b = map.getBounds();
    return { barat: b.getWest(), selatan: b.getSouth(), timur: b.getEast(), utara: b.getNorth() };
  } catch { return null; }
}

export function useLapisanCitra(peta, { aktif = false } = {}) {
  const pengelolaRef = useRef(null);
  const [daftar, setDaftar] = useState([]);
  const [memuat, setMemuat] = useState(false);
  const [galat, setGalat] = useState("");
  const [sembunyi, setSembunyi] = useState(() => bacaCitraSembunyi());
  const [opasitas, setOpasitasState] = useState(() => bacaOpasitasCitra());
  const [vp, setVp] = useState(null);
  const [versi, setVersi] = useState(0); // naik = muat ulang paksa

  // Ambil daftar hanya saat dinyalakan.
  useEffect(() => {
    if (!aktif) return undefined;
    let batal = false;
    setMemuat(true);
    setGalat("");
    ambilDaftarCitra({ paksa: versi > 0 })
      .then((d) => { if (!batal) setDaftar(urutCitra(d)); })
      .catch(() => { if (!batal) setGalat("Daftar citra eksisting gagal dimuat"); })
      .finally(() => { if (!batal) setMemuat(false); });
    return () => { batal = true; };
  }, [aktif, versi]);

  // Pasang/lepas layer mengikuti keadaan.
  useEffect(() => {
    if (!peta) return undefined;
    if (!aktif) {
      pengelolaRef.current?.lepas();
      return undefined;
    }
    if (!pengelolaRef.current) pengelolaRef.current = buatPengelolaCitra(peta);
    pengelolaRef.current.atur(daftar, { sembunyi, opasitas });
    return undefined;
  }, [peta, aktif, daftar, sembunyi, opasitas]);

  // Lepas seluruhnya saat peta/komponen dilepas.
  useEffect(() => () => {
    try { pengelolaRef.current?.lepas(); } catch { /* peta sudah dilepas */ }
    pengelolaRef.current = null;
  }, [peta]);

  // Lacak viewport (hanya saat aktif) untuk penanda "di luar area".
  useEffect(() => {
    if (!peta || !aktif) return undefined;
    const perbarui = () => setVp(viewport(peta));
    perbarui();
    peta.on("moveend", perbarui);
    return () => { peta.off("moveend", perbarui); };
  }, [peta, aktif]);

  const toggleLapisan = useCallback((id) => {
    setSembunyi((lama) => {
      const s = new Set(lama);
      const k = String(id);
      if (s.has(k)) s.delete(k); else s.add(k);
      simpanCitraSembunyi(s);
      return s;
    });
  }, []);

  const setOpasitas = useCallback((n) => {
    const v = Math.min(1, Math.max(0.1, Number(n) || 0.85));
    setOpasitasState(v);
    simpanOpasitasCitra(v);
  }, []);

  const menuju = useCallback((l) => {
    if (!peta || !l) return;
    try { peta.fitBounds(L.latLngBounds(batasLeaflet(l)), { maxZoom: Math.min(l.zoom_maks, 18) }); }
    catch { /* peta sudah dilepas */ }
  }, [peta]);

  const muatUlang = useCallback(() => setVersi((v) => v + 1), []);

  const lapis = daftar.map((l) => ({
    ...l,
    tampil: !sembunyi.has(String(l.id)),
    diArea: viewportMengenai(l, vp),
  }));
  const opasitasTampil = opasitas ?? (daftar[0]?.opasitas ?? 0.85);

  return { lapis, memuat, galat, opasitas: opasitasTampil, setOpasitas, toggleLapisan, menuju, muatUlang };
}
