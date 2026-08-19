import React, { memo, useMemo, useState } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";

// ============================================================================
// FILTER MULTI-PILIH — satu filter, banyak nilai
// ============================================================================
// Menggantikan <Select> nilai-tunggal pada filter berbasis PILIHAN (Kondisi,
// Status, Lokasi, Eselon I/II, Stiker, Inventarisasi). Beberapa nilai dalam
// satu filter berarti "ATAU" (aset cocok bila nilainya salah satu dari yang
// dicentang); antar-filter tetap "DAN" seperti sebelumnya.
//
// Radix Popover dipakai (BUKAN Select) karena Select menutup diri setiap kali
// satu item dipilih — mustahil mencentang lima lokasi tanpa membukanya lima
// kali. Kotak pencarian muncul otomatis untuk daftar panjang: Lokasi & Eselon
// bisa berisi ratusan nilai berbeda di satker besar.
//
// Tinggi pemicu (h-7) & ukuran teks disamakan dengan kontrol filter lain.
// `min-h-0 min-w-0` wajib: aturan tap-target 44px global (≤1023px) akan
// menggembungkan tombol setinggi 28px ini jadi 44px dan memecah barisan grid.

const AMBANG_CARI = 8;   // daftar sepanjang ini ke atas mendapat kotak cari
const MAKS_RINGKAS = 2;  // nilai yang disebut namanya di pemicu sebelum "+N"

// Batas "Pilih semua". Nilai filter dikirim sebagai PARAMETER BERULANG di URL
// GET (daftar, statistik, peta, stiker, ekspor), jadi mencentang 2.000 lokasi
// sekaligus menghasilkan querystring puluhan kilobyte — ditolak server/proxy
// sebagai 414 sebelum sempat menyaring apa pun.
//
// Saat daftar melampaui batas ini tombolnya DIMATIKAN, bukan memilih 200 yang
// pertama: memilih sebagian diam-diam menghasilkan filter yang salah tanpa satu
// pun tanda di layar. Jalan keluarnya diarahkan ke kotak cari — dan itu justru
// pemakaian yang paling sering: ketik "Gedung A", lalu pilih semua yang cocok.
export const MAKS_PILIH_SEMUA = 200;

/** Ringkasan isi pemicu: "Semua" · "Baik" · "Baik, Rusak" · "Baik +3". */
export function ringkasTerpilih(terpilih, placeholder = "Semua") {
  const v = Array.isArray(terpilih) ? terpilih : [];
  if (v.length === 0) return placeholder;
  if (v.length <= MAKS_RINGKAS) return v.join(", ");
  return `${v[0]} +${v.length - 1}`;
}

/**
 * Gabungkan pilihan yang sudah ada dengan seluruh nilai yang SEDANG TAMPIL.
 *
 * Menggabung, bukan mengganti: saat kotak cari aktif, nilai yang dipilih lebih
 * dulu di luar hasil pencarian tidak boleh hilang hanya karena "Pilih semua"
 * ditekan pada daftar yang sedang tersaring.
 */
export function gabungPilihan(terpilih, tampil) {
  const awal = Array.isArray(terpilih) ? terpilih : [];
  const keluar = [...awal];
  for (const o of tampil || []) {
    if (!keluar.includes(o)) keluar.push(o);
  }
  return keluar;
}

/** Centang/lepas satu nilai — mengembalikan array BARU (state tak dimutasi). */
export function alihNilai(terpilih, nilai) {
  const v = Array.isArray(terpilih) ? terpilih : [];
  return v.includes(nilai) ? v.filter(x => x !== nilai) : [...v, nilai];
}

const FilterMultiSelect = memo(({
  label,
  opsi = [],
  terpilih = [],
  onChange,          // (arrayNilaiBaru) => void
  testid,
  placeholder = "Semua",
}) => {
  const [buka, setBuka] = useState(false);
  const [cari, setCari] = useState("");

  const daftar = useMemo(
    () => (opsi || []).filter(o => o !== null && o !== undefined && String(o).trim() !== ""),
    [opsi]);

  const tampil = useMemo(() => {
    const k = cari.trim().toLowerCase();
    if (!k) return daftar;
    return daftar.filter(o => String(o).toLowerCase().includes(k));
  }, [daftar, cari]);

  const jumlah = (terpilih || []).length;
  // Dimatikan bila daftar terlalu panjang (lihat MAKS_PILIH_SEMUA) atau bila
  // seluruh yang tampil memang sudah tercentang — menekannya tak akan mengubah
  // apa pun, dan tombol hidup yang tak melakukan apa-apa membuat orang menekan
  // dua kali lalu mengira filternya rusak.
  const bolehPilihSemua = tampil.length > 0
    && tampil.length <= MAKS_PILIH_SEMUA
    && tampil.some(o => !(terpilih || []).includes(o));

  return (
    <Popover open={buka} onOpenChange={(o) => { setBuka(o); if (!o) setCari(""); }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={testid}
          aria-label={`Filter ${label}`}
          className="min-h-0 min-w-0 h-7 w-full flex items-center justify-between gap-1 px-2 rounded-md border border-input bg-background text-xs text-left hover:bg-accent/50 focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <span className={`truncate ${jumlah ? "text-foreground" : "text-muted-foreground"}`}>
            {ringkasTerpilih(terpilih, placeholder)}
          </span>
          <span className="flex items-center gap-1 flex-shrink-0">
            {jumlah > 1 && (
              <span
                className="px-1 rounded bg-blue-500/15 text-blue-600 dark:text-blue-400 text-[9px] font-semibold tabular-nums"
                data-testid={testid ? `${testid}-jumlah` : undefined}
              >
                {jumlah}
              </span>
            )}
            <ChevronDown className="w-3 h-3 opacity-50" />
          </span>
        </button>
      </PopoverTrigger>

      <PopoverContent align="start" className="w-56 p-0" data-testid={testid ? `${testid}-panel` : undefined}>
        {daftar.length >= AMBANG_CARI && (
          <div className="flex items-center gap-1 border-b px-2 py-1.5">
            <Search className="w-3 h-3 text-muted-foreground flex-shrink-0" />
            <input
              type="text"
              value={cari}
              onChange={e => setCari(e.target.value)}
              placeholder={`Cari ${label.toLowerCase()}...`}
              className="min-w-0 flex-1 h-5 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
              data-testid={testid ? `${testid}-cari` : undefined}
            />
            {cari && (
              <button
                type="button"
                onClick={() => setCari("")}
                aria-label="Hapus kata kunci"
                className="min-h-0 min-w-0 w-4 h-4 inline-flex items-center justify-center rounded hover:bg-muted flex-shrink-0"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        <div className="max-h-56 overflow-y-auto py-1">
          {tampil.length === 0 && (
            <p className="px-2 py-2 text-[11px] text-muted-foreground">
              {daftar.length === 0 ? "Belum ada pilihan" : "Tak ada yang cocok"}
            </p>
          )}
          {tampil.map(o => {
            const aktif = (terpilih || []).includes(o);
            return (
              <button
                key={o}
                type="button"
                role="option"
                aria-selected={aktif}
                onClick={() => onChange(alihNilai(terpilih, o))}
                className="min-h-0 min-w-0 w-full flex items-center gap-2 px-2 py-1.5 text-xs text-left hover:bg-accent"
                data-testid={testid ? `${testid}-opsi` : undefined}
              >
                <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 ${
                  aktif ? "bg-primary border-primary text-primary-foreground" : "border-input"
                }`}>
                  {aktif && <Check className="w-2.5 h-2.5" />}
                </span>
                <span className="truncate">{o}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center justify-between gap-2 border-t px-2 py-1">
          <span className="text-[10px] text-muted-foreground truncate">
            {jumlah ? `${jumlah} dipilih` : "Semua nilai"}
          </span>
          <span className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => onChange(gabungPilihan(terpilih, tampil))}
              disabled={!bolehPilihSemua}
              title={tampil.length > MAKS_PILIH_SEMUA
                ? `Terlalu banyak (${tampil.length}) untuk dipilih sekaligus — persempit dengan kotak cari dulu`
                : undefined}
              className="min-h-0 min-w-0 text-[10px] text-primary hover:underline disabled:opacity-40 disabled:no-underline"
              data-testid={testid ? `${testid}-pilih-semua` : undefined}
            >
              {cari.trim() ? `Pilih ${tampil.length} hasil` : "Pilih semua"}
            </button>
            <button
              type="button"
              onClick={() => onChange([])}
              disabled={!jumlah}
              className="min-h-0 min-w-0 text-[10px] text-muted-foreground hover:text-foreground disabled:opacity-40"
              data-testid={testid ? `${testid}-kosongkan` : undefined}
            >
              Kosongkan
            </button>
          </span>
        </div>
      </PopoverContent>
    </Popover>
  );
});

FilterMultiSelect.displayName = "FilterMultiSelect";

export default FilterMultiSelect;
