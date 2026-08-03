/**
 * Komposisi kelas untuk `DialogContent` bersama.
 *
 * Dipisahkan dari komponennya semata-mata agar bisa DIUJI: aturan di sini
 * gampang rusak diam-diam saat orang menambah/menyusun ulang kelas bawaan, dan
 * rusaknya hanya kelihatan di peramban — persis jenis regresi yang lolos lint
 * dan build.
 *
 * Yang dijaga:
 *
 * 1. **Batas tinggi selalu ada, tapi selalu bisa ditimpa.** Dialog `fixed` yang
 *    dipusatkan (`top-1/2 translate-y-[-50%]`) tanpa batas tinggi akan menjulang
 *    ke atas DAN ke bawah viewport saat isinya panjang; karena `fixed`, halaman
 *    di belakangnya tak bisa digulir untuk menjangkaunya — judul dan tombol
 *    aksinya benar-benar hilang di HP, bukan sekadar "penuh". Batasnya dipasang
 *    di sini supaya setiap dialog baru mewarisinya tanpa perlu diingat.
 *
 * 2. **Urutan argumen `cn`: bawaan DULU, `className` BELAKANGAN.** Seluruh
 *    kemampuan menimpa bergantung pada itu. tailwind-merge menyelesaikan
 *    tabrakan dengan aturan "yang belakangan menang", termasuk lintas properti
 *    yang berkaitan: `overflow-hidden` dari sebuah dialog membuang
 *    `overflow-x/y` bawaan, dan `max-h-[85vh]` membuang batas tinggi bawaan.
 *    Menukar urutannya membuat bawaan mengunci semuanya — diam-diam, karena
 *    kelasnya tetap "ada" di DOM. Itulah yang dikunci uji di sini.
 */
import { cn } from "./utils";

/**
 * Kelas bawaan. `--tinggi-dialog` didefinisikan di index.css dengan cadangan
 * `vh` → `dvh` (di HP, `100vh` mengabaikan bilah alamat sehingga dialog
 * setinggi layar tetap terpotong). `p-4 sm:p-6`: di layar 360 px, padding 24 px
 * kiri-kanan memakan 13% lebar.
 */
export const DIALOG_DASAR =
  "fixed left-[50%] top-[50%] z-50 grid w-[calc(100%-2rem)] max-w-lg " +
  "translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-4 sm:p-6 " +
  "shadow-elev-4 duration-200 max-h-[var(--tinggi-dialog)] " +
  "overflow-y-auto overflow-x-hidden [&>*]:min-w-0 " +
  "data-[state=open]:animate-in data-[state=closed]:animate-out " +
  "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 " +
  "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 " +
  "data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] " +
  "data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] " +
  "sm:rounded-xl";

/** Kelas akhir `DialogContent` untuk sebuah `className` tambahan. */
export function kelasDialog(className) {
  return cn(DIALOG_DASAR, className);
}
