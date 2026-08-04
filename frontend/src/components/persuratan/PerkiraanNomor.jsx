import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Ticket } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Perkiraan nomor booking-otomatis — satu sumber untuk SEMUA halaman yang
 * punya centang "Pesan nomor otomatis dari Registrasi Persuratan".
 *
 * Memanggil endpoint yang sama dengan dialog Booking Nomor
 * (`GET /persuratan/pratinjau-nomor`) dengan modul + jenis naskah + tanggal
 * PERSIS seperti yang dipakai jalur booking backend halaman itu, sehingga
 * angka yang tampil sedertan dengan tata penomoran satker (format, kode
 * klasifikasi hasil pemetaan, kode unit, reset bulanan/tahunan).
 *
 * Nomor final tetap dikunci counter atomik saat dokumen disimpan — bila ada
 * booking lain menyela, nomor bergeser maju; karena itu ini disajikan
 * sebagai "perkiraan", bukan janji.
 *
 * Pakai: <PerkiraanNomor aktif={form.booking_otomatis} modul="penggunaan"
 *          jenisNaskah="Berita Acara" tanggal={form.tanggal}
 *          testId="bast-perkiraan-nomor" />
 */
export default function PerkiraanNomor({
  aktif = false, modul = "", jenisNaskah = "", tanggal = "",
  testId = "perkiraan-nomor", className = "",
}) {
  const [pratinjau, setPratinjau] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    if (!aktif) { setPratinjau(null); return undefined; }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          jenis_naskah: jenisNaskah || "",
          modul: modul || "",
          tanggal_surat: (tanggal || "").slice(0, 10),
        });
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${params}`);
        setPratinjau(r.data?.nomor ? r.data : null);
      } catch { setPratinjau(null); }
    }, 300);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [aktif, modul, jenisNaskah, tanggal]);

  if (!aktif || !pratinjau?.nomor) return null;
  return (
    <p className={`flex items-start gap-1.5 text-[11px] mt-1 text-muted-foreground ${className}`}
      data-testid={testId}>
      <Ticket className="w-3.5 h-3.5 shrink-0 mt-[1px] text-primary/70" />
      <span className="min-w-0">
        Perkiraan nomor:{" "}
        <span className="font-mono font-semibold text-foreground break-all">
          {pratinjau.nomor}
        </span>
        <span className="block text-[10px]">
          Sesuai tata penomoran Persuratan satker — nomor final dikunci saat
          disimpan (bisa bergeser bila ada booking lain menyela).
        </span>
      </span>
    </p>
  );
}
