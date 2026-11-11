import React, { useEffect, useState } from "react";
import TooltipKetuk from "@/components/ui/TooltipKetuk";
import { infoIkon } from "@/lib/kelompokOrang";
import useKelompokOrang, { bacaKelompok } from "@/hooks/useKelompokOrang";

// Gambar dari kelompokOrang.infoIkon (lucide, viewbox 24). Dibedakan BENTUK,
// warna hanya penguat (3.8).
const Gambar = ({ info, ukuran }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={ukuran} height={ukuran} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true" focusable="false">
    {info.elemen.map(([tag, attrs], i) => React.createElement(tag, { key: i, ...attrs }))}
  </svg>
);

const Isi = ({ info, ukuran, denganLabel, className, hiasan }) => {
  // Di dalam tombol/pilihan: tanpa tooltip dan tanpa fokus, supaya tak ada
  // elemen interaktif bersarang. Nama kelompok tetap terbaca pembaca layar
  // sebagai bagian nama tombol.
  if (hiasan) {
    return (
      <span data-testid={`ikon-kelompok-${info.kunci}`}
        className={`inline-flex items-center flex-shrink-0 min-w-0 min-h-0 ${info.kelas} ${className}`}>
        <Gambar info={info} ukuran={ukuran} />
        <span className="sr-only">{info.alt}</span>
      </span>
    );
  }
  const isi = (
    <span role="img" aria-label={info.alt} tabIndex={0} data-testid={`ikon-kelompok-${info.kunci}`}
      className={`inline-flex items-center gap-1 align-middle flex-shrink-0 min-w-0 min-h-0 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${info.kelas} ${className}`}>
      <Gambar info={info} ukuran={ukuran} />
      {denganLabel && <span aria-hidden="true" className="text-[11px] font-semibold leading-none">{info.label}</span>}
    </span>
  );
  return <TooltipKetuk konten={info.alt}>{isi}</TooltipKetuk>;
};

// Nomor yang sedang DIKETIK baru ditanyakan setelah berhenti sejenak —
// jawaban yang sudah tersimpan tetap tampil seketika. Saat dipasang pertama
// kali (baris daftar) nomornya langsung ikut tumpukan, tanpa jeda.
const JEDA_KETIK_MS = 400;
const DariNomor = ({ nomor, ...rest }) => {
  const kini = String(nomor || "").trim();
  const [tanya, setTanya] = useState(kini);
  useEffect(() => {
    if (kini === tanya) return undefined;
    const t = setTimeout(() => setTanya(kini), JEDA_KETIK_MS);
    return () => clearTimeout(t);
  }, [kini, tanya]);
  const peta = useKelompokOrang([tanya]);
  const info = infoIkon(kini === tanya ? peta[kini] : bacaKelompok(kini));
  return info ? <Isi info={info} {...rest} /> : null;
};

/**
 * Ikon kelompok orang (3.8). `kunciIkon` bila kelompoknya sudah diketahui
 * (salinan pada catatan, jawaban direktori); `nomor` bila harus ditanyakan
 * ke penjawab kelompok — permintaannya bertumpuk bersama baris lain.
 * Kelompok tak dikenal → tidak merender apa pun.
 */
export default function IkonKelompok({ kunciIkon, nomor, ukuran = 14, denganLabel = false,
  className = "", hiasan = false }) {
  const rest = { ukuran, denganLabel, className, hiasan };
  if (kunciIkon) {
    const info = infoIkon(kunciIkon);
    return info ? <Isi info={info} {...rest} /> : null;
  }
  if (!String(nomor || "").trim()) return null;
  return <DariNomor nomor={nomor} {...rest} />;
}
