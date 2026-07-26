import axios from "axios";
import { Building2, ChevronDown, Check, Globe } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  getSatkerAktif,
  isSuperAdminPusat,
  setSatkerAktif,
} from "@/lib/satkerAktif";

const API = process.env.REACT_APP_BACKEND_URL
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : "/api";

/**
 * Bilah "Satker Aktif" — HANYA untuk super-admin pusat.
 *
 * Super-admin tak terikat satker, sehingga tanpa pemilih ini setiap data yang
 * ia input tak jelas milik satker mana. Memilih Satker Aktif membuat SELURUH
 * aplikasi (lihat + input) berperilaku sebagai satker itu — data terisolasi,
 * tak tercampur. "Semua Satker" = tampilan lintas satker seperti biasa.
 *
 * Mengganti satker memuat ulang halaman: cara paling andal memastikan tak ada
 * sisa data satker lain yang menggantung di memori antar modul.
 */
export default function SatkerAktifBar({ user }) {
  const [daftar, setDaftar] = useState([]);
  const [aktif, setAktif] = useState(getSatkerAktif());
  const [buka, setBuka] = useState(false);
  const ref = useRef(null);

  const superAdmin = isSuperAdminPusat(user);

  useEffect(() => {
    if (!superAdmin) return;
    let batal = false;
    axios
      .get(`${API}/satker`)
      .then((r) => {
        if (batal) return;
        const items = (r.data?.items || []).filter((s) => s.kode_satker);
        setDaftar(items);
      })
      .catch(() => {});
    return () => {
      batal = true;
    };
  }, [superAdmin]);

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setBuka(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  if (!superAdmin) return null;

  const pilih = (kode) => {
    setBuka(false);
    if (kode === aktif) return;
    setSatkerAktif(kode);
    setAktif(kode);
    // Muat ulang agar seluruh data ter-refetch dengan scope satker baru.
    window.location.reload();
  };

  const namaAktif = aktif
    ? daftar.find((s) => s.kode_satker === aktif)?.nama_satker || aktif
    : "Semua Satker";

  return (
    <div
      ref={ref}
      className="relative z-40 flex items-center justify-center gap-2 px-3 py-1.5 text-xs
                 bg-indigo-600 text-white shadow-sm"
      data-testid="satker-aktif-bar"
    >
      <Building2 className="w-3.5 h-3.5 flex-shrink-0 opacity-90" />
      <span className="opacity-90">Satker aktif:</span>
      <button
        type="button"
        onClick={() => setBuka((v) => !v)}
        className="inline-flex items-center gap-1 font-semibold rounded-md bg-white/15
                   hover:bg-white/25 px-2 py-0.5 max-w-[60vw] transition-colors"
        data-testid="satker-aktif-pilih"
      >
        <span className="truncate">{namaAktif}</span>
        <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" />
      </button>

      {buka && (
        <div
          className="absolute top-full mt-1 left-1/2 -translate-x-1/2 w-64 max-h-72 overflow-y-auto
                     rounded-lg border border-border bg-card text-foreground shadow-lg py-1"
        >
          <button
            type="button"
            onClick={() => pilih("")}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
            data-testid="satker-aktif-semua"
          >
            <Globe className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
            <span className="flex-1">Semua Satker (lintas)</span>
            {!aktif && <Check className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />}
          </button>
          <div className="my-1 border-t border-border" />
          {daftar.length === 0 ? (
            <p className="px-3 py-2 text-[11px] text-muted-foreground">
              Belum ada satker di Master Satker.
            </p>
          ) : (
            daftar.map((s) => (
              <button
                key={s.kode_satker}
                type="button"
                onClick={() => pilih(s.kode_satker)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
                data-testid={`satker-aktif-opsi-${s.kode_satker}`}
              >
                <Building2 className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                <span className="flex-1 min-w-0">
                  <span className="block truncate">{s.nama_satker || s.kode_satker}</span>
                  <span className="block font-mono text-[10px] text-muted-foreground">
                    {s.kode_satker}
                  </span>
                </span>
                {aktif === s.kode_satker && (
                  <Check className="w-3.5 h-3.5 text-indigo-600 flex-shrink-0" />
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
