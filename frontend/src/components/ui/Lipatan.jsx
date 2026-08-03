import React from "react";
import { cn } from "@/lib/utils";

/**
 * Penjelasan yang DILIPAT — isinya utuh, tapi tak memakan layar sampai diminta.
 *
 * Dipakai untuk teks yang benar sekaligus panjang: aturan kebijakan, langkah
 * perbaikan, alasan sebuah tombol berperilaku tertentu. Di layar HP teks
 * semacam itu rutin memakan 60–130 px di ATAS kontrol yang sebenarnya dicari
 * pengguna, padahal cukup dibaca sekali seumur pemakaian.
 *
 * Sengaja `<details>` bawaan peramban, bukan state React: ia bekerja tanpa
 * JavaScript, sudah punya semantik buka/tutup untuk pembaca layar, dan
 * `<summary>` bukan `<button>` sehingga tidak kena aturan tap-target 44 px
 * global (index.css) yang akan menggembungkannya.
 *
 * `nada` mengganti warna teks agar lipatan yang berada DI DALAM kotak
 * peringatan (amber/merah) tetap satu kesatuan visual dengan kotaknya —
 * `text-muted-foreground` di sana terlihat seperti elemen asing.
 */
const NADA = {
  redup: "text-muted-foreground",
  amber: "text-amber-700/90 dark:text-amber-300/90",
  merah: "text-red-700/90 dark:text-red-300/90",
};

export default function Lipatan({ judul, nada = "redup", className, children, ...props }) {
  return (
    <details className={cn("text-[11px] leading-snug", NADA[nada] || NADA.redup, className)} {...props}>
      <summary className="cursor-pointer select-none underline decoration-dotted underline-offset-2">
        {judul}
      </summary>
      <div className="mt-1 space-y-1">{children}</div>
    </details>
  );
}
