import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { DayPicker } from "react-day-picker"

import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}) {
  // Mode dropdown (bulan + tahun) dipakai bila pemanggil menyetel
  // `captionLayout="dropdown-buttons"`. Saat itu label caption bawaan
  // disembunyikan — react-day-picker merender <select> bulan & tahun DAN
  // salinan label ber-aria-hidden; tanpa stylesheet bawaannya keduanya
  // tampil dobel, jadi labelnya kita matikan lewat kelas.
  const pakaiDropdown = String(props.captionLayout || "").startsWith("dropdown")
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        months: "flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
        month: "space-y-3",
        caption: "flex justify-center pt-1 relative items-center",
        caption_label: pakaiDropdown ? "hidden" : "text-sm font-medium",
        caption_dropdowns: "flex items-center justify-center gap-1.5",
        // <select> bulan/tahun — ganti bulan & tahun cukup dua ketukan,
        // tak perlu menekan panah berkali-kali.
        dropdown: cn(
          "h-8 min-h-0 min-w-0 rounded-md border border-input bg-background",
          "px-1.5 text-sm font-medium text-foreground cursor-pointer",
          "focus:outline-none focus:ring-1 focus:ring-ring"
        ),
        dropdown_month: "flex items-center",
        dropdown_year: "flex items-center",
        vhidden: "hidden",
        nav: "space-x-1 flex items-center",
        // `min-w-0 min-h-0` WAJIB pada semua tombol di dalam kalender:
        // aturan tap-target 44px global (≤1023px, index.css) membengkakkan
        // tiap <button> — tombol tanggal 32px melar jadi 44px sehingga
        // kolomnya melebar tak sejajar dengan header hari (yang bukan
        // tombol) dan antar tanggal tampak renggang berjauhan di tablet/HP.
        nav_button: cn(
          buttonVariants({ variant: "outline" }),
          "h-7 w-7 min-w-0 min-h-0 bg-transparent p-0 opacity-50 hover:opacity-100"
        ),
        nav_button_previous: "absolute left-1",
        nav_button_next: "absolute right-1",
        table: "w-full border-collapse",
        head_row: "flex",
        // Header hari memakai kotak BERUKURAN SAMA dengan sel tanggal (w-9)
        // dan ikut flex-center — sejajar kolom demi kolom di semua ukuran.
        head_cell: cn(
          "text-muted-foreground w-9 h-7 font-normal text-[0.8rem]",
          "flex items-center justify-center"
        ),
        row: "flex w-full mt-1",
        cell: cn(
          "relative w-9 p-0 text-center text-sm focus-within:relative focus-within:z-20 [&:has([aria-selected])]:bg-accent [&:has([aria-selected].day-outside)]:bg-accent/50 [&:has([aria-selected].day-range-end)]:rounded-r-md",
          props.mode === "range"
            ? "[&:has(>.day-range-end)]:rounded-r-md [&:has(>.day-range-start)]:rounded-l-md first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md"
            : "[&:has([aria-selected])]:rounded-md"
        ),
        day: cn(
          buttonVariants({ variant: "ghost" }),
          "h-9 w-9 min-w-0 min-h-0 p-0 font-normal aria-selected:opacity-100"
        ),
        day_range_start: "day-range-start",
        day_range_end: "day-range-end",
        day_selected:
          "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground",
        day_today: "bg-accent text-accent-foreground",
        day_outside:
          "day-outside text-muted-foreground aria-selected:bg-accent/50 aria-selected:text-muted-foreground",
        day_disabled: "text-muted-foreground opacity-50",
        day_range_middle:
          "aria-selected:bg-accent aria-selected:text-accent-foreground",
        day_hidden: "invisible",
        ...classNames,
      }}
      components={{
        IconLeft: ({ className, ...props }) => (
          <ChevronLeft className={cn("h-4 w-4", className)} {...props} />
        ),
        IconRight: ({ className, ...props }) => (
          <ChevronRight className={cn("h-4 w-4", className)} {...props} />
        ),
      }}
      {...props} />
  );
}
Calendar.displayName = "Calendar"

export { Calendar }
