import React, { useMemo, useRef, useState } from "react";
import { Check, Search, X } from "lucide-react";
import { cariPilihanPeta, pilihanSaringan, SEMUA } from "../../lib/filterPetaKolaborasi";

/** Satu pilihan saringan; dipakai juga oleh status/kondisi pada peta. */
export function PilihanFilter({ aktif, onPilih, label, jumlah, warna, kode }) {
  return (
    <button type="button" onClick={onPilih} aria-pressed={aktif}
      className={`w-full min-w-0 min-h-11 xl:min-h-9 flex items-center gap-2 px-2 py-2 rounded-md text-left ${aktif ? "bg-blue-500/10 text-blue-700 dark:text-blue-300" : "hover:bg-muted"}`}>
      <span aria-hidden="true" className={`w-4 h-4 shrink-0 rounded border flex items-center justify-center ${aktif ? "border-blue-600 bg-blue-600 text-white" : "border-muted-foreground/50"}`}>
        {aktif && <Check className="w-3 h-3" />}
      </span>
      {warna && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: warna }} />}
      <span className="flex-1 min-w-0 text-xs break-words" title={label}>
        {kode && <span className="block font-mono text-[10px] text-muted-foreground">{kode}</span>}
        {label}
      </span>
      <span className="text-[11px] font-semibold text-muted-foreground shrink-0">{jumlah}</span>
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
  const inputRef = useRef(null);
  const nilaiTerpilih = useMemo(() => new Set(pilihanSaringan(aktif)), [aktif]);
  const terpilih = pilihan.filter(p => nilaiTerpilih.has(p.nilai));
  const ubahCari = nilai => { setCari(nilai); setBatas(LANGKAH); };
  return (
    <section className="rounded-lg border border-border overflow-hidden" aria-label={judul} data-testid={testId}>
      <div className="flex items-center gap-1.5 px-2 py-1.5 bg-muted/60">
        <Ikon className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <span className="text-[10.5px] font-bold uppercase tracking-wide text-muted-foreground">{judul}</span>
      </div>
      <div className="p-1.5 space-y-1">
        <div className="peta-filter-search flex items-center gap-2 rounded-lg border border-border bg-background pl-3">
          <Search aria-hidden="true" className="w-4 h-4 shrink-0 text-muted-foreground" />
          {/* text + searchbox menghindari tombol X bawaan browser yang ganda. */}
          <input ref={inputRef} type="text" role="searchbox" value={cari} onChange={e => ubahCari(e.target.value)}
            aria-label={`Cari ${judul.toLowerCase()}`} placeholder={placeholder}
            data-testid={`${testId}-cari`} maxLength={200}
            autoComplete="off" autoCorrect="off" autoCapitalize="none" spellCheck={false}
            className="min-w-0 flex-1 w-full h-11 bg-transparent text-base lg:text-sm text-foreground" />
          <span className="w-11 h-11 shrink-0">
            {cari && <button type="button" aria-label={`Hapus pencarian ${judul.toLowerCase()}`}
              data-testid={`${testId}-hapus-cari`}
              onClick={() => { ubahCari(""); inputRef.current?.focus(); }}
              className="h-11 w-11 rounded-md flex items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground">
              <X aria-hidden="true" className="w-4 h-4" />
            </button>}
          </span>
        </div>
        <p className="text-[10px] text-muted-foreground px-1" aria-live="polite">{hasil.length} dari {pilihan.length} pilihan</p>
        {nilaiTerpilih.size > 0 && <p className="text-[11px] text-blue-700 dark:text-blue-300 px-1 break-words" data-testid={`${testId}-terpilih`}>
          {nilaiTerpilih.size} terpilih: {terpilih.slice(0, 3).map(p => p.kode ? `${p.kode} — ${p.label}` : p.label).join("; ")}
          {terpilih.length > 3 && `; +${terpilih.length - 3} lainnya`}
        </p>}
        <PilihanFilter aktif={nilaiTerpilih.size === 0} onPilih={() => onPilih(SEMUA)} label={labelSemua} jumlah={jumlah} />
      </div>
      <div className="max-h-44 overflow-y-auto p-1 space-y-0.5">
        {hasil.slice(0, batas).map(p => <PilihanFilter key={p.nilai} aktif={nilaiTerpilih.has(p.nilai)}
          onPilih={() => onPilih(p.nilai)} label={p.label} kode={p.kode} jumlah={p.jumlah} />)}
        {!hasil.length && <p className="px-2 py-3 text-xs text-muted-foreground">Tidak ada pilihan yang cocok.</p>}
        {hasil.length > batas && <button type="button" onClick={() => setBatas(n => n + LANGKAH)}
          className="w-full min-h-11 rounded-md px-2 text-xs font-medium text-blue-700 dark:text-blue-300 hover:bg-muted"
          data-testid={`${testId}-lagi`}>Tampilkan {Math.min(LANGKAH, hasil.length - batas)} pilihan lagi</button>}
      </div>
    </section>
  );
}
