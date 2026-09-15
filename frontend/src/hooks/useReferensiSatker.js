import { useEffect, useState } from "react";
import axios from "axios";
import { REFERENSI_SATKER_EVENT } from "@/lib/referensiSatker";
import { TENGGAT_BAKA, muatAndal } from "@/lib/muatAndal";

const API = process.env.REACT_APP_BACKEND_URL ? `${process.env.REACT_APP_BACKEND_URL}/api` : "/api";

export function useRevisiSatker() {
  const [revisi, setRevisi] = useState(0);
  useEffect(() => {
    const segarkan = () => setRevisi((n) => n + 1);
    const antarTab = (e) => { if (e.key === REFERENSI_SATKER_EVENT) segarkan(); };
    window.addEventListener(REFERENSI_SATKER_EVENT, segarkan);
    window.addEventListener("storage", antarTab);
    window.addEventListener("focus", segarkan);
    return () => {
      window.removeEventListener(REFERENSI_SATKER_EVENT, segarkan);
      window.removeEventListener("storage", antarTab);
      window.removeEventListener("focus", segarkan);
    };
  }, []);
  return revisi;
}

export default function useReferensiSatker(aktif = true) {
  const revisi = useRevisiSatker();
  const [daftar, setDaftar] = useState([]);
  const [gagal, setGagal] = useState(false);
  useEffect(() => {
    if (!aktif) return;
    let batal = false;
    // Daftar pilihan tetap tersedia saat kode aktif lama sudah diganti.
    // Backend tetap membatasi daftar untuk akun yang terikat satker.
    muatAndal(() => axios.get(`${API}/satker`, {
      timeout: TENGGAT_BAKA, headers: { "X-Satker-Aktif": "" },
    })).then((r) => {
      if (!batal) { setDaftar(r.data?.items || []); setGagal(false); }
    }).catch(() => { if (!batal) setGagal(true); });
    return () => { batal = true; };
  }, [aktif, revisi]);
  return { daftar, gagal, revisi };
}
