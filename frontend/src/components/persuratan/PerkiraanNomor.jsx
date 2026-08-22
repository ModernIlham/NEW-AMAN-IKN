import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Ticket } from "lucide-react";
import { teksSumberKlasifikasi } from "@/lib/klasifikasiNomor";

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
 * PEMILIH KLASIFIKASI (opsional, `onKlasifikasi`). Keluhan pemilik: *"ketika
 * buat BAST dan klik nomor otomatis dari registrasi persuratan, bagian
 * klasifikasi arsip tidak ada dan tidak ada pilihan memilih klasifikasi arsip
 * yang ada"*. Memang: jalur otomatis lintas modul hanya pernah punya SATU
 * sumber kode — aturan pemetaan (modul + jenis naskah). Tak ada aturan yang
 * cocok berarti slot `{kode_klasifikasi}` pada nomor terbit KOSONG, tanpa satu
 * pun galat, dan tanpa cara memperbaikinya dari layar tempat dokumennya
 * dibuat. Dengan prop ini, layar itu punya kolomnya sendiri — urutan
 * prioritasnya sama persis dengan booking manual: isian di sini menang atas
 * aturan pemetaan.
 *
 * Pakai: <PerkiraanNomor aktif={form.booking_otomatis} modul="penggunaan"
 *          jenisNaskah="Berita Acara" tanggal={form.tanggal}
 *          klasifikasi={form.kode_klasifikasi}
 *          onKlasifikasi={(v) => setForm((f) => ({ ...f, kode_klasifikasi: v }))}
 *          testId="bast-perkiraan-nomor" />
 */
export default function PerkiraanNomor({
  aktif = false, modul = "", jenisNaskah = "", tanggal = "",
  testId = "perkiraan-nomor", className = "",
  klasifikasi = "", onKlasifikasi = null,
}) {
  const [pratinjau, setPratinjau] = useState(null);
  const [katalog, setKatalog] = useState([]);
  const timer = useRef(null);
  const bolehPilih = typeof onKlasifikasi === "function";

  useEffect(() => {
    if (!aktif) { setPratinjau(null); return undefined; }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          jenis_naskah: jenisNaskah || "",
          modul: modul || "",
          tanggal_surat: (tanggal || "").slice(0, 10),
          kode_klasifikasi: klasifikasi || "",
        });
        const r = await axios.get(`${API}/persuratan/pratinjau-nomor?${params}`);
        setPratinjau(r.data?.nomor ? r.data : null);
      } catch { setPratinjau(null); }
    }, 300);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [aktif, modul, jenisNaskah, tanggal, klasifikasi]);

  // Katalog kode hanya diambil bila kolomnya memang ditampilkan — halaman yang
  // tak memakai pemilih tak perlu membayar satu permintaan tambahan.
  useEffect(() => {
    if (!aktif || !bolehPilih) return;
    axios.get(`${API}/persuratan/klasifikasi`)
      .then((r) => setKatalog(r.data?.items || []))
      .catch(() => setKatalog([]));
  }, [aktif, bolehPilih]);

  if (!aktif) return null;
  const daftarId = `${testId}-katalog`;
  return (
    <div className={`mt-1 space-y-1 ${className}`} data-testid={`${testId}-blok`}>
      {pratinjau?.nomor && (
        <p className="flex items-start gap-1.5 text-[11px] text-muted-foreground"
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
      )}
      {bolehPilih && (
        <div className="flex flex-wrap items-center gap-1.5">
          <label className="text-[10px] text-muted-foreground"
            htmlFor={`${testId}-klas`}>Kode Klasifikasi Arsip</label>
          <input
            id={`${testId}-klas`} list={daftarId} value={klasifikasi || ""}
            onChange={(e) => onKlasifikasi(e.target.value)}
            placeholder={pratinjau?.kode_klasifikasi
              ? `otomatis: ${pratinjau.kode_klasifikasi}`
              : "kosongkan = ikut aturan otomatis"}
            className="h-7 w-40 rounded-md border border-input bg-background px-2 font-mono text-[11px] min-h-0"
            data-testid={`${testId}-klasifikasi`} />
          <datalist id={daftarId}>
            {katalog.map((k) => (
              <option key={k.id || k.kode} value={k.kode}>{k.uraian}</option>
            ))}
          </datalist>
          {pratinjau && (
            <span className="text-[10px] text-muted-foreground"
              data-testid={`${testId}-sumber-klasifikasi`}>
              {teksSumberKlasifikasi(pratinjau)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
