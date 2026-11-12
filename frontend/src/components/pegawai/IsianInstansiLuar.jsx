import React, { useEffect, useId, useState } from "react";
import axios from "axios";
import { Input } from "@/components/ui/input";
import IkonKelompok from "@/components/pegawai/IkonKelompok";
import { kunciIkon } from "@/lib/kelompokOrang";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Isian teks mitra ber-datalist dari direktori instansi luar (PGW-11).
 *
 * Pola aditif: teks tetap teks — bebas diketik dan disimpan apa adanya
 * sebagai snapshot. Memilih salah satu saran MENAUTKAN catatan ke direktori
 * (`instansiId`); mengubah teks sesudahnya melepas tautan. Tanpa tautan
 * perilaku sama dengan isian lama.
 *
 * `onUbah({ teks, instansi })` — `instansi` = dokumen direktori tertaut atau
 * null.
 *
 * `saranTambahan` ([{ nilai, label }]) — saran teks lain di datalist yang sama
 * (mis. Master Satker); memilihnya TIDAK menautkan apa pun.
 */
export default function IsianInstansiLuar({ id, teks, instansiId, instansi, onUbah,
  placeholder, testId, saranTambahan = [] }) {
  const listId = useId();
  const [saran, setSaran] = useState([]);

  // Cari di server (eksternal + pihak ketiga), ditunda selama mengetik.
  useEffect(() => {
    const q = String(teks || "").trim();
    if (q.length < 2 || instansiId) { setSaran([]); return undefined; }
    let batal = false;
    const t = setTimeout(async () => {
      const hasil = await Promise.allSettled(["eksternal", "pihak_ketiga"].map((kelompok) =>
        axios.get(`${API}/luar/instansi`, { params: { kelompok, q, page_size: 10 } })));
      if (batal) return;
      setSaran(hasil.flatMap((h) => (h.status === "fulfilled" ? h.value.data?.items || [] : []))
        .filter((i) => !i.wadah));
    }, 300);
    return () => { batal = true; clearTimeout(t); };
  }, [teks, instansiId]);

  const ketik = (v) => {
    const cocok = saran.find((i) => i.nama === v);
    onUbah({ teks: v, instansi: cocok || null });
  };
  const tertaut = instansiId && instansi;
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <Input id={id} list={listId} placeholder={placeholder} value={teks}
          onChange={(e) => ketik(e.target.value)} className="flex-1 min-w-0" data-testid={testId} />
        {tertaut && <IkonKelompok kunciIkon={kunciIkon(instansi.kelompok, instansi.tataran)} />}
      </div>
      <datalist id={listId}>
        {saran.map((i) => <option key={i.id} value={i.nama} />)}
        {saranTambahan.map((o) => <option key={`+${o.nilai}`} value={o.nilai}>{o.label}</option>)}
      </datalist>
      <p className="text-[11px] text-muted-foreground" data-testid={testId ? `${testId}-status` : undefined}>
        {tertaut ? "Tertaut ke direktori instansi luar — ubah teks untuk melepas tautan."
          : "Teks bebas. Pilih dari saran untuk menautkan ke direktori instansi luar."}
      </p>
    </div>
  );
}
