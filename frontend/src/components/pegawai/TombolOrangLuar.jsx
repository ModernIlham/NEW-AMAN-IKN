import React, { useState } from "react";
import { UserSearch } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import PilihKelompok from "@/components/pegawai/PilihKelompok";
import CariOrangLuar from "@/components/pegawai/CariOrangLuar";

/**
 * Pintu ke direktori orang luar dari pemilih yang sudah ada (PGW-08b).
 * Pemilih internal tiap layar tetap seperti semula (daftar `/pegawai` yang
 * sudah termuat); tombol ini menambah pilihan Instansi Eksternal (Pusat/
 * Daerah) dan Pihak Ketiga yang dicari di server. Memilih seseorang
 * memanggil `onPilih(orang)` dengan bentuk jawaban `/direktori-pegawai`.
 */
export default function TombolOrangLuar({ onPilih, testId = "orang-luar", disabled = false,
  label = "Orang luar", kecil = false }) {
  const [buka, setBuka] = useState(false);
  const [kelompok, setKelompok] = useState("eksternal");
  const [tataran, setTataran] = useState("pusat");
  return (
    <Popover open={buka} onOpenChange={setBuka}>
      <PopoverTrigger asChild>
        <button type="button" disabled={disabled} title="Pilih dari direktori instansi eksternal / pihak ketiga"
          aria-label={`${label} — instansi eksternal atau pihak ketiga`}
          className={`inline-flex items-center gap-1 shrink-0 rounded-md border border-input bg-card px-2 text-xs hover:bg-muted disabled:opacity-50 ${kecil ? "h-8 min-h-0 min-w-0" : "min-h-[44px] lg:min-h-0 lg:h-9"}`}
          data-testid={testId}>
          <UserSearch className="w-3.5 h-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">{label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[calc(100vw-2rem)] max-w-sm p-2 space-y-2">
        <PilihKelompok kelompok={kelompok} tataran={tataran} hanyaLuar
          awalanTestId={testId} onKelompok={setKelompok} onTataran={setTataran} />
        <CariOrangLuar kelompok={kelompok} tataran={tataran} testId={`${testId}-cari`}
          onPilih={(p) => { setBuka(false); onPilih(p); }} />
      </PopoverContent>
    </Popover>
  );
}
