import React from "react";
import IkonKelompok from "@/components/pegawai/IkonKelompok";
import { kunciIkon } from "@/lib/kelompokOrang";
import { KELOMPOK, TATARAN } from "@/lib/ranahPegawai";

/**
 * Pintu masuk Master Pegawai (3.10): pilih kelompok dulu, lalu — untuk
 * Instansi Eksternal — Pusat atau Daerah. Tanpa tombol "terapkan" dan tanpa
 * pilihan "semua": memilih satu langsung memuat daftarnya.
 *
 * `bentuk="layar"`: tiga pilihan besar (belum ada pilihan tersimpan).
 * `bentuk="bilah"`: pilihan yang sama sebagai bilah di kepala halaman.
 * Tinggi tiap pilihan ≥ 44px di ≤ 1023px. Ikon & warnanya dari
 * `IkonKelompok` (satu sumber, 3.8) — berkas ini tidak memilihnya sendiri.
 */

const Cacah = ({ n }) => (n == null ? null : (
  <span className="px-1.5 py-0.5 rounded-full bg-muted text-[10px] font-bold text-muted-foreground tabular-nums">
    {n}
  </span>
));

const Pilihan = ({ aktif, onClick, kunci, label, n, testId, besar }) => (
  <button type="button" onClick={onClick} aria-pressed={aktif} data-testid={testId}
    className={besar
      ? `flex items-center gap-3 w-full text-left rounded-xl border p-3 sm:p-4 min-h-[44px] hover:bg-muted ${aktif ? "border-sky-500 bg-sky-500/5" : "border-border bg-card"}`
      : `inline-flex items-center gap-1.5 rounded-lg border px-2.5 text-xs font-semibold min-h-[44px] lg:min-h-0 lg:h-8 hover:bg-muted ${aktif ? "border-sky-500 bg-sky-500/10 text-foreground" : "border-border bg-card text-muted-foreground"}`}>
    <IkonKelompok kunciIkon={kunci} ukuran={besar ? 24 : 16} hiasan />
    <span className={besar ? "flex-1 min-w-0 text-sm font-semibold text-foreground" : "whitespace-nowrap"}>{label}</span>
    <Cacah n={n} />
  </button>
);

export default function PilihKelompok({ kelompok, tataran, cacah = {}, onKelompok,
  onTataran, bentuk = "bilah", awalanTestId = "pegawai" }) {
  const besar = bentuk === "layar";
  return (
    <div className={besar ? "space-y-3" : "space-y-1.5"} data-testid={`${awalanTestId}-pilih-kelompok-${bentuk}`}>
      {besar && (
        <p className="text-sm text-muted-foreground">
          Pilih kelompok yang ingin dilihat. Pilihan ini diingat di perangkat ini.
        </p>
      )}
      <div className={besar ? "grid grid-cols-1 sm:grid-cols-3 gap-2" : "flex flex-wrap gap-1.5"}
        role="group" aria-label="Kelompok pegawai">
        {KELOMPOK.map((k) => (
          <Pilihan key={k.kunci} besar={besar} aktif={kelompok === k.kunci}
            onClick={() => onKelompok(k.kunci)} kunci={kunciIkon(k.kunci, tataran)}
            label={besar ? k.label : k.ringkas}
            n={cacah[k.kunci]} testId={`${awalanTestId}-kelompok-${k.kunci}`} />
        ))}
      </div>
      {kelompok === "eksternal" && (
        <div className={besar ? "grid grid-cols-1 sm:grid-cols-2 gap-2" : "flex flex-wrap gap-1.5"}
          role="group" aria-label="Tataran instansi eksternal">
          {TATARAN.map((t) => (
            <Pilihan key={t.kunci} besar={besar} aktif={tataran === t.kunci}
              onClick={() => onTataran(t.kunci)} kunci={kunciIkon("eksternal", t.kunci)}
              label={besar ? t.label : t.ringkas}
              n={cacah[t.kunci]} testId={`${awalanTestId}-tataran-${t.kunci}`} />
          ))}
        </div>
      )}
    </div>
  );
}
