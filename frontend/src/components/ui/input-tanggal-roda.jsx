import { useMemo, useState } from "react";
import { CalendarDays, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DateWheelPicker } from "@/components/ui/date-wheel-picker";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Kolom tanggal ber-popup RODA (hari · bulan · tahun) — pembungkus
 * `DateWheelPicker` (desain 21st.dev pilihan pemilik, khusus Master
 * Pegawai) dengan kontrak yang SAMA dengan `InputTanggal`:
 * nilai ISO `yyyy-mm-dd` dan `onChange({ target: { name, value } })` —
 * pengganti langsung `<Input type="date">` tanpa mengubah penangan form.
 *
 * Roda berputar bebas tanpa menyimpan; tombol **Pakai** yang mengunci
 * pilihan (setengah-gulir tak pernah bocor ke form), **Kosongkan**
 * menghapus nilai. ISO diurai per bagian — `new Date("yyyy-mm-dd")`
 * ditafsirkan UTC dan mundur sehari di zona Indonesia.
 *
 * @param {Object} props
 * @param {string} props.name
 * @param {string} props.value ISO `yyyy-mm-dd` ("" bila kosong).
 * @param {(e: {target: {name: string, value: string}}) => void} props.onChange
 * @param {number} [props.minYear]
 * @param {number} [props.maxYear]
 * @param {string} [props.className]
 * @param {boolean} [props.disabled]
 * @param {string} [props.placeholder]
 */
export function InputTanggalRoda({
  name,
  value,
  onChange,
  minYear = 1940,
  maxYear = new Date().getFullYear() + 10,
  className,
  disabled = false,
  placeholder = "dd/mm/yyyy",
  ...sisa
}) {
  const [buka, setBuka] = useState(false);
  // Tanggal yang sedang diputar di roda (belum tentu dipakai)
  const [putaran, setPutaran] = useState(null);

  const tanggal = useMemo(() => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!m) return undefined;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return Number.isNaN(d.getTime()) ? undefined : d;
  }, [value]);

  const teks = tanggal
    ? `${String(tanggal.getDate()).padStart(2, "0")}/${String(tanggal.getMonth() + 1).padStart(2, "0")}/${tanggal.getFullYear()}`
    : "";

  const kirim = (d) => {
    const iso = d
      ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
      : "";
    onChange?.({ target: { name, value: iso } });
  };

  const bukaTutup = (o) => {
    setBuka(o);
    if (o) setPutaran(tanggal || new Date());
  };

  return (
    <Popover open={buka} onOpenChange={bukaTutup}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-full justify-between px-3 font-normal",
            !teks && "text-muted-foreground",
            className,
          )}
          {...sisa}
        >
          <span>{teks || placeholder}</span>
          <CalendarDays className="ml-2 h-4 w-4 flex-shrink-0 opacity-60" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-3" align="start">
        <DateWheelPicker
          value={putaran || new Date()}
          onChange={setPutaran}
          minYear={minYear}
          maxYear={maxYear}
          size="sm"
        />
        <div className="mt-2 flex items-center justify-between gap-2 border-t border-border pt-2">
          <Button
            type="button" size="sm" variant="ghost"
            className="h-8 min-h-0 text-[11px] text-muted-foreground"
            onClick={() => { kirim(null); setBuka(false); }}
            data-testid={`${name || "tanggal"}-roda-kosongkan`}
          >
            <X className="mr-1 h-3.5 w-3.5" />Kosongkan
          </Button>
          <Button
            type="button" size="sm"
            className="h-8 min-h-0 text-[11px]"
            onClick={() => { kirim(putaran || new Date()); setBuka(false); }}
            data-testid={`${name || "tanggal"}-roda-pakai`}
          >
            Pakai
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default InputTanggalRoda;
