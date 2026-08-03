import React, { useCallback, useEffect, useRef, useState } from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

/**
 * Tooltip yang BISA DIKETUK — sama di tetikus maupun layar sentuh.
 *
 * Radix `Tooltip` hanya terbuka oleh hover dan fokus papan-ketik. Di layar
 * sentuh keduanya tak pernah terjadi: `Tooltip.Trigger` justru MENUTUP diri
 * pada `pointerdown` (mencegah tooltip nyangkut setelah ketukan), dan
 * pembukaan lewat fokus sengaja dilewati bila fokusnya datang dari penunjuk.
 * Hasilnya ikon status di kartu galeri — status inventarisasi, stiker, dan
 * kelengkapan barang — jadi ikon tanpa keterangan apa pun di HP/tablet.
 *
 * Pilihan di sini: SATU primitif (Popover) untuk kedua modalitas, bukan
 * menukar Tooltip↔Popover menurut media query. Penukaran itu terlihat rapi di
 * kertas tetapi menukar komponen di tengah interaksi: state modalitas baru
 * diketahui saat `pointerdown`, React lalu melepas simpul DOM pemicu lama dan
 * memasang yang baru, sehingga `click` ketukan PERTAMA jatuh ke simpul yang
 * sudah tiada. Satu primitif menghindari seluruh kelas masalah itu.
 *
 * Perilaku:
 * - ketuk/klik pemicu → buka (bawaan Popover.Trigger);
 * - tetikus masuk pemicu ATAU isi → buka; keluar → tutup setelah jeda pendek,
 *   supaya kursor sempat menyeberang ke isinya (isi tooltip kelengkapan
 *   memuat tombol buka foto/dokumen yang harus bisa diklik);
 * - ketuk di luar / Esc → tutup (bawaan DismissableLayer);
 * - fokus tak dicuri saat terbuka (`onOpenAutoFocus` dicegah) supaya membuka
 *   dengan tetikus tidak memindahkan fokus papan ketik.
 */
const JEDA_TUTUP_MS = 120;

export default function TooltipKetuk({
  children,
  konten,
  side = "top",
  align = "center",
  sideOffset = 4,
  kelasKonten,
  ...props
}) {
  const [buka, setBuka] = useState(false);
  const jam = useRef(null);

  useEffect(() => () => clearTimeout(jam.current), []);

  const bukaSekarang = useCallback(() => {
    clearTimeout(jam.current);
    setBuka(true);
  }, []);

  // Jeda, bukan tutup seketika: tanpa ini gerakan kursor dari pemicu ke isi
  // melintasi celah `sideOffset` dan tooltip berkedip tertutup di tengah jalan.
  const tundaTutup = useCallback(() => {
    clearTimeout(jam.current);
    jam.current = setTimeout(() => setBuka(false), JEDA_TUTUP_MS);
  }, []);

  // Hanya TETIKUS yang membuka lewat hover. Pointer sentuh/pena juga mengirim
  // pointerenter tepat sebelum ketukan; membiarkannya lewat sini membuat
  // ketukan berikutnya menutup apa yang baru saja terbuka.
  const hover = (fn) => (e) => { if (e.pointerType === "mouse") fn(); };

  return (
    <PopoverPrimitive.Root open={buka} onOpenChange={setBuka}>
      <PopoverPrimitive.Trigger
        asChild
        onPointerEnter={hover(bukaSekarang)}
        onPointerLeave={hover(tundaTutup)}
        {...props}
      >
        {children}
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          side={side}
          align={align}
          sideOffset={sideOffset}
          collisionPadding={8}
          onOpenAutoFocus={(e) => e.preventDefault()}
          onPointerEnter={bukaSekarang}
          onPointerLeave={tundaTutup}
          className={cn(
            // Rupa mengikuti tooltip lama (bg-primary) supaya perpindahan
            // primitif tak terasa sebagai perubahan tampilan.
            "z-50 max-w-[min(18rem,calc(100vw-1rem))] overflow-hidden rounded-md " +
            "bg-primary px-3 py-1.5 text-xs text-primary-foreground shadow-md outline-none " +
            "animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out " +
            "data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 " +
            "origin-[--radix-popover-content-transform-origin]",
            kelasKonten,
          )}
        >
          {konten}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
