import React from "react";

/**
 * StatKartu — kartu ringkasan/statistik PADAT & horizontal (hemat ruang di
 * HP): ikon tertinta di kiri, angka besar + label kecil menumpuk di kanan.
 * Menggantikan kartu vertikal (ikon-atas · angka-tengah · label-bawah) yang
 * boros ruang. Meniru kepadatan baris "Aset per Pemegang".
 *
 * Props:
 * - icon: komponen ikon lucide (opsional)
 * - value: angka/teks utama (di-`title` otomatis; boleh di-truncate)
 * - label: keterangan kecil di bawah angka
 * - warna: kelas warna ikon (mis. "text-blue-500")
 * - tint: kelas latar kotak ikon (mis. "bg-blue-500/10")
 * - title: override tooltip angka (default = value)
 * - testid, className, onClick, children (aksi tambahan mis. "lihat daftar")
 */
export default function StatKartu({
  icon: Icon, value, label, warna = "text-blue-500", tint = "bg-blue-500/10",
  title, testid, className = "", onClick, children,
}) {
  const isi = (
    <>
      {Icon && (
        <span className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${tint}`}>
          <Icon className={`w-4 h-4 ${warna}`} />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="text-base font-bold text-foreground leading-none truncate tabular-nums"
          title={title || (value != null ? String(value) : "")}>
          {value}
        </p>
        <p className="text-[10px] text-muted-foreground leading-tight mt-0.5 break-words">{label}</p>
        {children}
      </div>
    </>
  );
  const base = `bg-card rounded-xl border border-border p-2.5 flex items-center gap-2.5 min-w-0 ${className}`;
  if (onClick) {
    return (
      <button type="button" onClick={onClick} data-testid={testid}
        className={`${base} text-left hover:bg-muted/40 transition-colors`}>
        {isi}
      </button>
    );
  }
  return <div className={base} data-testid={testid}>{isi}</div>;
}
