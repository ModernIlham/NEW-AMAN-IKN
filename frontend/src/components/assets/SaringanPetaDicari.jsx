import React, { useMemo, useState } from "react";
import { Check, Search, X } from "lucide-react";
import { cariPilihanPeta, SEMUA } from "../../lib/filterPetaKolaborasi";

/** Satu pilihan saringan; dipakai juga oleh status/kondisi pada peta. */
export function PilihanFilter({ aktif, onPilih, label, jumlah, warna, kode }) {
  return (
    <button type="button" onClick={onPilih} aria-pressed={aktif}
      className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-left min-h-0 ${aktif ? "bg-blue-500/10 text-blue-700 dark:text-blue-300" : "hover:bg-muted"}`}>
      <Check className={`w-3 h-3 flex-shrink-0 ${aktif ? "opacity-100" : "opacity-0"}`} />
      {warna && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: warna }} />}
      {kode && <span className="font-mono text-[9.5px] text-muted-foreground flex-shrink-0">{kode}</span>}
      <span className="flex-1 truncate text-[11px]" title={label}>{label}</span>
      <span className="text-[10px] font-semibold text-muted-foreground flex-shrink-0">{jumlah}</span>
    </button>
  );
}

const LANGKAH = 50;

/** Pencarian lokal hanya mengubah opsi yang terlihat, bukan filter/lingkup peta. */
export default function SaringanPetaDicari({ judul, ikon: Ikon, pilihan, aktif,
  onPilih, labelSemua, jumlah, placeholder, testId }) {
  const [cari, setCari] = useState("");
  const [batas, setBatas] = useState(LANGKAH);
  const hasil = useMemo(() => cariPilihanPeta(pilihan, cari), [pilihan, cari]);
  const terpilih = pilihan.find(p => p.nilai === aktif);
  const ubahCari = nilai => { setCari(nilai); setBatas(LANGKAH); };
  return (
    <section className="rounded-lg border border-border overflow-hidden" aria-label={judul} data-testid={testId}>
      <div className="flex items-center gap-1.5 px-2 py-1.5 bg-muted/60">
        <Ikon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <span className="text-[10.5px] font-bold uppercase tracking-wide text-muted-foreground">{judul}</span>
      </div>
      <div className="p-1.5 space-y-1">
        <div className="flex items-center gap-1 rounded-md border border-border bg-background px-2 focus-within:ring-2 focus-within:ring-blue-500">
          <Search className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
          <input type="search" value={cari} onChange={e => ubahCari(e.target.value)}
            aria-label={`Cari ${judul.toLowerCase()}`} placeholder={placeholder}
            data-testid={`${testId}-cari`} maxLength={200}
            className="min-w-0 w-full h-11 bg-transparent text-xs text-foreground outline-none" />
          {cari && <button type="button" aria-label={`Hapus pencarian ${judul.toLowerCase()}`}
            onClick={() => ubahCari("")} className="h-11 w-11 shrink-0 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground">
            <X className="w-3.5 h-3.5" />
          </button>}
        </div>
        <p className="text-[10px] text-muted-foreground px-1" aria-live="polite">{hasil.length} dari {pilihan.length} pilihan</p>
        {terpilih && <p className="text-[10px] text-blue-700 dark:text-blue-300 px-1 break-words" data-testid={`${testId}-terpilih`}>
          Terpilih: {terpilih.kode ? `${terpilih.kode} — ` : ""}{terpilih.label}
        </p>}
        <PilihanFilter aktif={aktif === SEMUA} onPilih={() => onPilih(SEMUA)} label={labelSemua} jumlah={jumlah} />
      </div>
      <div className="max-h-44 overflow-y-auto p-1 space-y-0.5">
        {hasil.slice(0, batas).map(p => <PilihanFilter key={p.nilai} aktif={aktif === p.nilai}
          onPilih={() => onPilih(p.nilai)} label={p.label} kode={p.kode} jumlah={p.jumlah} />)}
        {!hasil.length && <p className="px-2 py-3 text-xs text-muted-foreground">Tidak ada pilihan yang cocok.</p>}
        {hasil.length > batas && <button type="button" onClick={() => setBatas(n => n + LANGKAH)}
          className="w-full min-h-11 rounded-md px-2 text-xs font-medium text-blue-700 dark:text-blue-300 hover:bg-muted"
          data-testid={`${testId}-lagi`}>Tampilkan {Math.min(LANGKAH, hasil.length - batas)} pilihan lagi</button>}
      </div>
    </section>
  );
}
