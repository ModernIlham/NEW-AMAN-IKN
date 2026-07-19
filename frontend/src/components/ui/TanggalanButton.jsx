import React, { useRef } from "react";

/**
 * TanggalanButton — kalender mini seukuran tombol kotak header (persegi,
 * gaya sama dengan tombol kembali/Booking Nomor): strip bulan berwarna,
 * angka tanggal besar, tahun kecil. Klik membuka pemilih tanggal native;
 * tampilan langsung mengikuti tanggal terpilih.
 *
 * Props:
 * - value: string "YYYY-MM-DD" (wajib)
 * - onChange(v): dipanggil dengan tanggal baru "YYYY-MM-DD"
 * - warna: kelas Tailwind strip bulan (default biru)
 * - title, testid: aksesibilitas & uji
 */
export default function TanggalanButton({
  value, onChange, warna = "bg-blue-600", title = "Pilih tanggal",
  testid = "tanggalan",
}) {
  const ref = useRef(null);
  const v = String(value || "").slice(0, 10);
  const bulan = (() => {
    try {
      return new Date(`${v}T00:00:00`).toLocaleDateString("id-ID", { month: "short" });
    } catch {
      return "";
    }
  })();
  return (
    <>
      <button
        type="button"
        onClick={() => {
          const el = ref.current;
          if (!el) return;
          if (typeof el.showPicker === "function") el.showPicker();
          else el.click();
        }}
        className="h-9 w-9 rounded-lg border border-border bg-background flex flex-col items-stretch overflow-hidden flex-shrink-0 hover:bg-muted"
        title={title}
        aria-label={title}
        data-testid={testid}
      >
        <span className={`${warna} text-white text-[8px] font-bold uppercase tracking-wide leading-none py-[2px] text-center`}>
          {bulan}
        </span>
        <span className="flex-1 flex items-center justify-center text-[14px] font-bold text-foreground leading-none">
          {v.slice(8, 10)}
        </span>
        <span className="text-[8px] text-muted-foreground leading-none pb-[2px] text-center">
          {v.slice(0, 4)}
        </span>
      </button>
      <input
        ref={ref} type="date" value={v}
        onChange={(e) => e.target.value && onChange?.(e.target.value)}
        className="sr-only" tabIndex={-1} aria-hidden="true"
        data-testid={`${testid}-input`}
      />
    </>
  );
}
