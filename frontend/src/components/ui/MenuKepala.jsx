import React, { useRef } from "react";
import { Download, MoreVertical, Ticket } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import BookingNomorButton from "@/components/persuratan/BookingNomorButton";
import { downloadFileWithProgress } from "@/lib/downloadFile";

/**
 * MENU AKSI KEPALA HALAMAN — mengumpulkan aksi sekunder modul siklus BMN.
 *
 * Permintaan pemilik (verbatim, dengan tangkapan layar halaman Pengadaan):
 * *"kode booking nomor sampai kebawah, buat kumpulkan semua dalam bentuk
 * kategori agar tidak banyak tombol kecuali tombol tambah."*
 *
 * Lima halaman memakai bentuk kepala yang PERSIS SAMA — [Ekspor CSV] +
 * [tombol utama] + [Booking Nomor] — dan Pengadaan (yang punya satu aksi
 * tambahan) sudah tumpah ke baris kedua di HP. Empat sisanya berjarak tepat
 * SATU tombol dari nasib yang sama.
 *
 * Komponen ini menyatukan polanya supaya tak disalin lima kali. Yang dipakai
 * bersama bukan sekadar tampilan, melainkan satu keputusan yang mudah salah:
 *
 *   BookingNomorButton dipasang SEBAGAI SAUDARA DropdownMenu, bukan di dalam
 *   DropdownMenuContent. Radix melepas isi menu dari DOM begitu menu tertutup;
 *   komponen booking memiliki dialognya sendiri, jadi menaruhnya di dalam menu
 *   membuat dialog itu lenyap pada detik yang sama butir menunya ditekan —
 *   gejalanya "menu menutup, lalu tak terjadi apa-apa". Diselesaikan sekali di
 *   sini, bukan lima kesempatan untuk keliru.
 *
 * TOMBOL UTAMA TIDAK IKUT MASUK. "Catat Perolehan", "Catat Usulan", dan
 * seterusnya adalah alasan halamannya dibuka; menyembunyikannya di balik satu
 * ketukan tambahan menukar kerapian dengan kerja harian. Ia tetap dirender
 * halaman masing-masing, di samping menu ini.
 *
 * Pakai:
 *   <MenuKepala
 *     modul="penganggaran"
 *     ekspor={{ url: `${API}/penganggaran/export`,
 *               nama: "register_penganggaran.csv",
 *               label: "Ekspor Register Penganggaran (CSV)" }}
 *     booking={{ jenisNaskah: "Laporan", referensi: "Usulan Anggaran" }}
 *     ekstra={[{ id: "lpb", label: "LPB Gabungan", icon: Boxes,
 *                onSelect: () => …, testid: "…" }]} />
 */
export default function MenuKepala({
  modul,
  ekspor = null,
  booking = null,
  ekstra = [],
  testid = "",
}) {
  const bookingRef = useRef(null);
  const idMenu = testid || `${modul}-menu`;
  // Bagian "Dokumen & Nomor" hanya muncul bila ada isinya — menu berlabel
  // kategori kosong lebih membingungkan daripada tanpa kategori sama sekali.
  const adaDokumen = Boolean(booking) || ekstra.length > 0;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline" className="flex-shrink-0"
            title={`Menu aksi ${modul}`} aria-label={`Menu aksi ${modul}`}
            data-testid={idMenu}>
            <MoreVertical className="w-4 h-4 sm:mr-1.5" />
            <span className="hidden sm:inline">Menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-60">
          {adaDokumen && (
            <DropdownMenuLabel className="text-[11px] text-muted-foreground">
              Dokumen &amp; Nomor
            </DropdownMenuLabel>
          )}
          {booking && (
            <DropdownMenuItem className="min-h-[42px]"
              onSelect={() => bookingRef.current?.mulai()}
              data-testid={`${modul}-menu-booking`}>
              <Ticket className="w-4 h-4 mr-2" />Booking Nomor Surat
            </DropdownMenuItem>
          )}
          {ekstra.map((e) => {
            const Ikon = e.icon;
            return (
              <DropdownMenuItem key={e.id} className="min-h-[42px]"
                onSelect={e.onSelect} data-testid={e.testid || `${modul}-menu-${e.id}`}>
                {Ikon ? <Ikon className="w-4 h-4 mr-2" /> : null}{e.label}
              </DropdownMenuItem>
            );
          })}

          {adaDokumen && ekspor && <DropdownMenuSeparator />}
          {ekspor && (
            <>
              <DropdownMenuLabel className="text-[11px] text-muted-foreground">
                Ekspor
              </DropdownMenuLabel>
              <DropdownMenuItem className="min-h-[42px]"
                onSelect={() => downloadFileWithProgress(
                  ekspor.url, ekspor.nama, { label: ekspor.label }).catch(() => {})}
                data-testid={ekspor.testid || `${modul}-export`}>
                <Download className="w-4 h-4 mr-2" />
                {ekspor.judul || "Unduh Register (CSV)"}
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* DI LUAR menu — lihat catatan Radix di atas. Tanpa tombol sendiri;
          pemicunya butir menu di atas. */}
      {booking && (
        <BookingNomorButton ref={bookingRef} tanpaTombol modul={modul}
          jenisNaskah={booking.jenisNaskah} referensi={booking.referensi}
          kegiatanId={booking.kegiatanId} perihal={booking.perihal} />
      )}
    </>
  );
}
