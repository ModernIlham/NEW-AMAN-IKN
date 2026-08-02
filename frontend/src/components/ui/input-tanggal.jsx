import { useMemo, useState } from "react";
import { CalendarDays } from "lucide-react";
import { id as localeId } from "date-fns/locale";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

/**
 * Kolom tanggal ber-POPUP BAHASA INDONESIA.
 *
 * KENAPA BUKAN `<input type="date">`? Dua hal yang tak bisa diperbaiki dari CSS:
 *
 *  1. **Bahasa popup tak bisa dikendalikan halaman.** Kalender bawaan peramban
 *     memakai bahasa ANTARMUKA PERAMBAN/sistem operasi, bukan `lang` dokumen —
 *     jadi di Chrome berbahasa Inggris ia akan selalu menulis "August 2026",
 *     berapa kali pun `lang="id"` dipasang.
 *  2. **Ikon kalendernya milik peramban.** `::-webkit-calendar-picker-indicator`
 *     ditempel mepet tepi kanan dengan padding bawaan yang berbeda-beda antar
 *     peramban; itulah kenapa ikonnya terlihat menggantung di pinggir kolom.
 *
 * Komponen ini memakai `react-day-picker` dengan locale `id` dari `date-fns`,
 * dan ikonnya tombol biasa di dalam kolom — jadi posisinya kita yang tentukan.
 *
 * PENGGANTI LANGSUNG `<Input type="date">`: nilainya tetap ISO `yyyy-mm-dd`
 * dan `onChange` menerima `{ target: { name, value } }`, sehingga penangan
 * `handleInputChange` yang sudah ada tidak perlu diubah sama sekali.
 *
 * @param {Object} props
 * @param {string} props.name Nama field — diteruskan ke `event.target.name`.
 * @param {string} props.value Tanggal ISO `yyyy-mm-dd` ("" bila kosong).
 * @param {(e: {target: {name: string, value: string}}) => void} props.onChange
 * @param {string} [props.className] Kelas untuk tombol pemicu.
 * @param {boolean} [props.disabled]
 * @param {string} [props.placeholder]
 */
export function InputTanggal({
  name,
  value,
  onChange,
  className,
  disabled = false,
  placeholder = "dd/mm/yyyy",
  ...sisa
}) {
  const [buka, setBuka] = useState(false);

  // ISO → Date. Sengaja diurai per bagian, BUKAN `new Date("2026-08-05")`:
  // bentuk itu ditafsirkan sebagai UTC, sehingga di zona waktu Indonesia
  // (UTC+7/8/9) tanggalnya bisa mundur satu hari saat ditampilkan.
  const tanggal = useMemo(() => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
    if (!m) return undefined;
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return Number.isNaN(d.getTime()) ? undefined : d;
  }, [value]);

  const teks = tanggal
    ? `${String(tanggal.getDate()).padStart(2, "0")}/${String(tanggal.getMonth() + 1).padStart(2, "0")}/${tanggal.getFullYear()}`
    : "";

  const pilih = (d) => {
    // Klik pada tanggal yang sedang terpilih membatalkannya (react-day-picker
    // mengirim `undefined`) — itu cara pengguna mengosongkan kolom.
    const iso = d
      ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
      : "";
    onChange?.({ target: { name, value: iso } });
    setBuka(false);
  };

  return (
    <Popover open={buka} onOpenChange={setBuka}>
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
          {/* Ikon jadi bagian tombol, bukan tempelan peramban — jaraknya dari
              tepi ditentukan `px-3` yang sama dengan kolom form lain. */}
          <CalendarDays className="ml-2 h-4 w-4 flex-shrink-0 opacity-60" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={tanggal}
          onSelect={pilih}
          defaultMonth={tanggal}
          locale={localeId}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}

export default InputTanggal;
