import { useCallback, useEffect, useRef, useState } from "react";
import { bacaPilihanLensa, cariLensaMakro, daftarLensa, idLensa, simpanPilihanLensa } from "../lib/lensaKamera";

const NORMAL = { deviceId: "", makro: false };
export function useLensaKamera(track, ready) {
  const [daftar, setDaftar] = useState([]);
  const [galat, setGalat] = useState("");
  const [memuat, setMemuat] = useState(false);
  const [dibacaUntuk, setDibacaUntuk] = useState(null);
  const [pilihan, setPilihan] = useState(bacaPilihanLensa);
  const [permintaan, setPermintaan] = useState(NORMAL);
  const sebelumnya = useRef(NORMAL);
  const reqRef = useRef(permintaan);
  reqRef.current = permintaan;
  useEffect(() => {
    if (!track) return;
    let hidup = true, urutan = 0;
    const media = navigator.mediaDevices;
    const muat = async () => {
      const tiket = ++urutan;
      setMemuat(true);
      try {
        if (!media?.enumerateDevices) throw new Error("Daftar kamera tidak tersedia di browser ini.");
        const data = daftarLensa(await media.enumerateDevices());
        if (hidup && tiket === urutan) { setDaftar(data); setGalat(""); }
      } catch {
        if (hidup && tiket === urutan) { setDaftar([]); setGalat("Browser tidak menyediakan daftar kamera. Coba browser lain atau kamera bawaan HP."); }
      } finally { if (hidup && tiket === urutan) { setDibacaUntuk(track); setMemuat(false); } }
    };
    muat(); media?.addEventListener?.("devicechange", muat);
    return () => { hidup = false; media?.removeEventListener?.("devicechange", muat); };
  }, [track]);
  const aktif = !!(ready && track?.readyState === "live" && permintaan.makro && permintaan.deviceId && idLensa(track) === permintaan.deviceId);
  useEffect(() => {
    if (aktif) { simpanPilihanLensa(permintaan.deviceId); setPilihan(permintaan.deviceId); }
  }, [aktif, permintaan.deviceId]);
  const pilih = useCallback(id => {
    if (!ready || !daftar.some(d => d.id === id) || id === idLensa(track)) return false;
    if (!reqRef.current.makro) sebelumnya.current = { deviceId: idLensa(track), makro: false };
    const next = { deviceId: id, makro: true };
    reqRef.current = next; setPermintaan(next);
    return true;
  }, [ready, daftar, track]);
  const kembali = useCallback(() => { reqRef.current = sebelumnya.current; setPermintaan(sebelumnya.current); }, []);
  const reset = useCallback(() => { reqRef.current = NORMAL; setPermintaan(NORMAL); sebelumnya.current = NORMAL; }, []);
  // Sekali kembali ke kamera asal; jika itu juga hilang, coba kamera default.
  // Kegagalan default ditampilkan oleh pemilik stream, tidak berulang tanpa batas.
  const pulihkan = useCallback(id => {
    const req = reqRef.current;
    if (!id || req.deviceId !== id) return false;
    const next = req.makro ? sebelumnya.current : NORMAL;
    reqRef.current = next; setPermintaan(next);
    return true;
  }, []);
  return { daftar, galat, memuat: memuat || (!!track && dibacaUntuk !== track), permintaan, aktif, pilih, kembali, reset, pulihkan,
    kandidat: cariLensaMakro(daftar, pilihan), idAktif: idLensa(track) };
}
