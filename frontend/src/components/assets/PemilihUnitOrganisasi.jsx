import React, { useMemo, useState } from "react";
import { Building2, Check, ChevronDown, Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { barisPilihanUnit } from "@/lib/pohonUnit";
import { labelLevel } from "@/lib/eselonSatker";

/**
 * Pemilih unit organisasi pada form aset — tombol + dialog bercari.
 *
 * Permintaan pemilik: *"saat melakukan pemilihan unit organisasi di bagian
 * inventarisasi aset halaman edit dan tambah saya gampang kebingungan tolong
 * perbagus dan rapikan di tampilan pilihannya di mode layar apapun."*
 *
 * Sebelumnya sebuah `<select>` bawaan ber-`<optgroup>`. Empat hal membuatnya
 * membingungkan, dan tiga di antaranya tak dapat diperbaiki di dalam `<select>`
 * sebab pemilih bawaan tak dapat digayakan:
 *
 * 1. **Nama induk tercetak DUA KALI berturut-turut** — sekali sebagai pilihan
 *    yang dapat disentuh, sekali lagi tepat di bawahnya sebagai judul kelompok
 *    yang tidak. Di layar HP keduanya membungkus jadi 2–3 baris, jadi yang
 *    terbaca adalah blok teks yang sama muncul dua kali tanpa keterangan.
 * 2. **Tak ada pencarian.** Empat puluh unit bernama panjang dan berawalan
 *    sama ("Direktorat Peng…") hanya dapat ditemukan dengan menggulir dan
 *    membaca satu per satu.
 * 3. **"(E1)" tersangkut di ujung nama yang membungkus**, jadi penanda
 *    jenjangnya mendarat di tengah baris ketiga dan tak lagi menjadi penanda.
 * 4. **Yang sedang terpilih tak terlihat** selagi memilih.
 *
 * Karena itu pemilihnya menjadi dialog: jenjang digambar dengan indentasi dan
 * garis yang KITA kendalikan (jadi sama di lebar layar mana pun), jenjangnya
 * jadi lencana di depan nama, ada kotak cari, dan yang terpilih bertanda.
 *
 * Dialog, bukan `<select>`, aman di sini: pemilih ini TIDAK pernah dirender di
 * dalam lembar kamera — satu-satunya tempat yang mengharuskan elemen bawaan
 * karena portal Radix tenggelam di bawah lapisannya.
 *
 * Susunan barisnya — indentasi, konteks induk, dan pencariannya — dihitung
 * `barisPilihanUnit` di `@/lib/pohonUnit`, bukan di sini, supaya dapat diuji
 * tanpa merender apa pun.
 */
export default function PemilihUnitOrganisasi({
  pilihan, pohon, nilai, onPilih, disabled = false,
  testId = "asset-unit",
}) {
  const [buka, setBuka] = useState(false);
  const [cari, setCari] = useState("");

  const semua = useMemo(() => barisPilihanUnit(pilihan, pohon),
    [pilihan, pohon]);
  const hasil = useMemo(() => barisPilihanUnit(pilihan, pohon, cari),
    [pilihan, pohon, cari]);
  const terpilih = useMemo(() => semua.find((b) => b.id === nilai) || null,
    [semua, nilai]);

  const tutup = () => { setBuka(false); setCari(""); };
  const pilih = (id) => { onPilih?.(id); tutup(); };

  return (
    <>
      <button type="button" disabled={disabled} onClick={() => setBuka(true)}
        data-testid={`${testId}-pemicu`}
        aria-label={terpilih ? `Unit organisasi: ${terpilih.jalur}`
          : "Pilih unit organisasi"}
        className="w-full flex items-center gap-2 rounded-md border border-input bg-background px-2 py-1.5 text-left text-sm disabled:opacity-50">
        <Building2 className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
        <span className="flex-1 min-w-0">
          {terpilih ? (
            <>
              {/* Nama unitnya BOLEH membungkus: memotongnya membuat dua
                  Direktorat berawalan sama tak dapat dibedakan justru di
                  tempat pilihannya ditampilkan. */}
              <span className="block font-medium leading-snug break-words">
                {terpilih.nama_unit}
              </span>
              {terpilih.jalur_induk && (
                <span className="block text-[10px] text-muted-foreground leading-snug break-words">
                  {terpilih.jalur_induk}
                </span>
              )}
            </>
          ) : (
            <span className="text-muted-foreground">Pilih unit organisasi…</span>
          )}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
      </button>

      <Dialog open={buka} onOpenChange={(o) => { if (!o) tutup(); }}>
        {/* Lebarnya mengikuti layar dengan sisa 0.5rem per sisi di HP —
            nama unit di sini panjang, dan tiap piksel lebar mengurangi jumlah
            baris yang harus dibaca. */}
        <DialogContent className="max-w-lg w-[calc(100%-1rem)] sm:w-[calc(100%-2rem)] p-3 sm:p-5">
          <DialogHeader>
            <DialogTitle>Unit Organisasi</DialogTitle>
            <DialogDescription className="text-xs">
              {semua.length} unit dalam lingkup kegiatan ini. Memilih satu unit
              mengisi Eselon I&ndash;V aset sekaligus.
            </DialogDescription>
          </DialogHeader>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
            <Input value={cari} onChange={(e) => setCari(e.target.value)}
              placeholder="Cari unit / induknya…" className="h-9 pl-8 pr-8 text-sm"
              data-testid={`${testId}-cari`} />
            {cari && (
              <button type="button" onClick={() => setCari("")}
                aria-label="Bersihkan pencarian"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-muted-foreground hover:text-foreground min-w-0 min-h-0">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="border border-border rounded-lg divide-y divide-border/60 max-h-[55vh] overflow-y-auto"
            data-testid={`${testId}-daftar`}>
            {nilai && (
              <button type="button" onClick={() => pilih("")}
                data-testid={`${testId}-kosongkan`}
                className="w-full text-left px-3 py-2 text-xs text-muted-foreground hover:bg-muted">
                &mdash; Kosongkan pilihan &mdash;
              </button>
            )}
            {hasil.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                {cari ? `Tak ada unit yang cocok dengan "${cari}".`
                  : "Master unit kerja masih kosong untuk lingkup kegiatan ini."}
              </p>
            ) : hasil.map((b) => {
              const aktif = b.id === nilai;
              return (
                <button key={b.id} type="button" onClick={() => pilih(b.id)}
                  data-testid={`${testId}-opsi-${b.id}`}
                  aria-pressed={aktif}
                  /* Jorokan dihitung, bukan spasi di dalam teks: spasi tak
                     terlihat pada pemilih bawaan dan ikut terbawa saat nama
                     unitnya membungkus. */
                  style={{ paddingLeft: 10 + b.tingkat * 14 }}
                  className={`w-full flex items-start gap-2 pr-3 py-2 text-left hover:bg-muted ${aktif ? "bg-sky-500/10" : ""}`}>
                  {b.tingkat > 0 && (
                    <span aria-hidden="true"
                      className="text-muted-foreground/60 text-[11px] leading-5 flex-shrink-0">└</span>
                  )}
                  <span className="px-1 py-0.5 rounded bg-muted text-[9px] font-semibold text-muted-foreground uppercase flex-shrink-0 leading-4"
                    title={labelLevel(b.eselon)}>
                    Es. {labelLevel(b.eselon).replace("Eselon ", "") || "?"}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-[12px] leading-snug break-words">
                      {b.nama_unit}
                    </span>
                    {b.konteks && (
                      <span className="block text-[10px] text-muted-foreground leading-snug break-words">
                        {b.konteks}
                      </span>
                    )}
                  </span>
                  {aktif && (
                    <Check className="w-4 h-4 text-sky-600 dark:text-sky-400 flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
