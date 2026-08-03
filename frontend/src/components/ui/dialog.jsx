import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"
import { kelasDialog } from "@/lib/kelasDialog"

const Dialog = DialogPrimitive.Root

const DialogTrigger = DialogPrimitive.Trigger

const DialogPortal = DialogPrimitive.Portal

const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80  data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props} />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

// `[&>*]:min-w-0` — WAJIB, bukan hiasan. DialogContent adalah `grid`, dan anak
// grid bawaannya `min-width: auto`: lebar minimumnya = lebar MIN-CONTENT isinya.
// Satu saja keturunan ber-`white-space: nowrap` (mis. `truncate` pada URL panjang,
// nomor kontrak, atau NIP) membuat min-content-nya selebar teks utuh — jalur grid
// ikut melar, SEMUA anak lain teregang selebar itu, lalu terpotong oleh
// `overflow-x-hidden`. Gejalanya: isi dialog "memanjang menyamping" dan tepi
// kanannya hilang. `min-w-0` pada anak grid memutus rantai itu, sehingga
// `truncate` di dalamnya benar-benar bekerja (elipsis) alih-alih melebarkan induk.
//
// Kelas & aturan penimpaannya ada di `lib/kelasDialog` supaya bisa dikunci uji —
// termasuk jebakan `overflow-y-auto` vs `overflow-hidden` yang tak dianggap
// bertabrakan oleh tailwind-merge.
const DialogContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={kelasDialog(className)}
      {...props}>
      {children}
      <DialogPrimitive.Close
        className="absolute right-4 top-4 inline-flex h-7 w-7 items-center justify-center rounded-md opacity-70 ring-offset-background transition-opacity hover:opacity-100 hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({
  className,
  ...props
}) => (
  <div
    className={cn(
      // `pr-11` menyisakan ruang untuk tombol tutup yang di-absolute-kan di
      // `right-4` selebar `w-7` (16px + 28px = 44px). Tanpa ini judul panjang
      // — mis. "Riwayat BAST — <nama pegawai>" — merayap ke bawah tombol ×
      // dan tabrakan, paling parah di layar HP saat teks ter-center.
      "flex flex-col space-y-1.5 pr-11 text-center sm:text-left",
      className)}
    {...props} />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({
  className,
  ...props
}) => (
  <div
    className={cn(
      // gap-2 (bukan space-x saja) agar tetap berjarak ketika membungkus.
      "flex flex-col-reverse gap-2 sm:flex-row sm:flex-wrap sm:justify-end",
      className)}
    {...props} />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      // `leading-none` membuat judul dua baris saling menempel; `break-words`
      // mencegah nama/nomor panjang tanpa spasi menembus tepi dialog.
      "text-lg font-semibold leading-tight tracking-tight break-words",
      className)}
    {...props} />
))
DialogTitle.displayName = DialogPrimitive.Title.displayName

const DialogDescription = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props} />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
