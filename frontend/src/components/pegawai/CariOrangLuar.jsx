import React, { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, Search } from "lucide-react";
import IkonKelompok from "@/components/pegawai/IkonKelompok";
import { sebutTataran } from "@/lib/kelompokOrang";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Baris keterangan orang luar: Pusat/Daerah · instansi — satker · jabatan. */
export function keteranganOrangLuar(p) {
  const tempat = [p?.instansi_nama, p?.satker_luar_nama].filter(Boolean).join(" — ");
  return [sebutTataran(p?.kunci_ikon), tempat, p?.jabatan].filter(Boolean).join(" · ");
}

/**
 * Pencarian orang instansi eksternal / pihak ketiga di direktori bersama
 * (`GET /direktori-pegawai`, dicari di server — direktori bisa besar dan tak
 * pernah dikirim utuh ke perangkat). Hanya orang luar yang aktif.
 */
export default function CariOrangLuar({ kelompok, tataran = "", onPilih, testId = "cari-orang-luar",
  terpilihNip = "" }) {
  const [q, setQ] = useState("");
  const [hasil, setHasil] = useState(undefined); // undefined memuat · null gagal · array
  useEffect(() => {
    let batal = false;
    setHasil(undefined);
    const t = setTimeout(() => {
      const params = { kelompok, page_size: 30 };
      if (kelompok === "eksternal" && tataran) params.tataran = tataran;
      if (q.trim()) params.q = q.trim();
      axios.get(`${API}/direktori-pegawai`, { params })
        .then((r) => { if (!batal) setHasil(r.data?.items || []); })
        .catch(() => { if (!batal) setHasil(null); });
    }, 300);
    return () => { batal = true; clearTimeout(t); };
  }, [kelompok, tataran, q]);

  return (
    <div className="space-y-1.5 min-w-0" data-testid={testId}>
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" aria-hidden="true" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama / NIP/NIK / instansi…"
          aria-label="Cari orang luar" data-testid={`${testId}-q`}
          className="w-full h-10 lg:h-8 rounded-md border border-input bg-background pl-8 pr-2 text-sm lg:text-xs" />
      </div>
      <div className="max-h-56 overflow-y-auto space-y-0.5">
        {hasil === undefined ? (
          <p className="flex items-center justify-center gap-1.5 py-3 text-xs text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />Mencari…
          </p>
        ) : hasil === null ? (
          <p className="py-3 text-center text-xs text-muted-foreground">Direktori tak dapat dihubungi (luring?). Isi identitas manual.</p>
        ) : hasil.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">Tidak ditemukan. Catat orangnya di Master Pegawai lebih dulu.</p>
        ) : hasil.map((p) => (
          <button type="button" key={p.id} onClick={() => onPilih(p)}
            className={`w-full text-left px-2 rounded-md flex items-start gap-2 min-w-0 min-h-[44px] lg:min-h-0 lg:py-1.5 hover:bg-muted ${terpilihNip && p.nip === terpilihNip ? "bg-sky-500/10" : ""}`}
            data-testid={`${testId}-opt-${p.id}`}>
            <IkonKelompok kunciIkon={p.kunci_ikon} hiasan className="mt-0.5" />
            <span className="flex-1 min-w-0">
              <span className="block text-xs text-foreground break-words">{p.nama}</span>
              <span className="block text-[10px] text-muted-foreground break-words">
                {[p.nip || "tanpa NIP/NIK", keteranganOrangLuar(p)].filter(Boolean).join(" · ")}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
