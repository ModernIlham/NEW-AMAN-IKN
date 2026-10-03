import React from "react";
import PilihanRingkas from "@/components/ui/PilihanRingkas";

/** Nilai opsi selalu UUID pegawai; nama kembar tidak dipilih dengan find(nama). */
export function pihakDariPegawai(p) {
  return {
    pegawai_id: String(p?.id || ""), nama: String(p?.nama || ""), nip: String(p?.nip || ""),
    jabatan: String(p?.jabatan || ""),
    alamat: String(p?.alamat || p?.unit_kerja || p?.unit_organisasi || "").trim(),
  };
}

export default function PilihPegawaiBast({ daftar = [], value = "", onPilih, testId, label = "Tautkan Master Pegawai" }) {
  const aktif = daftar.filter(p => p.status !== "meninggal");
  return <div className="min-w-0 space-y-1">
    <PilihanRingkas options={aktif.map(p => ({ value: String(p.id), label: p.nama,
      description: [p.nip || "Tanpa NIP/NIK", p.unit_kerja, p.email, `ID …${String(p.id).slice(-6)}`].filter(Boolean).join(" · "),
      searchText: [p.nama, p.nip, p.unit_kerja, p.unit_organisasi, p.email].join(" "),
    }))} value={value} onChange={id => onPilih(aktif.find(p => String(p.id) === id) || null)} label={label} testId={testId}
      placeholder="Pilih pegawai / isi pihak luar" emptyLabel="Pihak luar — isi identitas manual" />
    {value && !aktif.some(p => String(p.id) === String(value)) && <p role="alert" className="text-xs text-amber-700 dark:text-amber-300">Pegawai tertaut tidak tersedia. Pilih ulang atau kosongkan untuk pihak luar.</p>}
    <details className="text-xs text-muted-foreground"><summary className="min-h-[44px] cursor-pointer content-center">Tentang identitas & akses BMN Saya</summary><p className="pb-2">Pilihan mengisi identitas otomatis. Email unik yang layak mendapat akses setelah BAST sah; masalah email/akses ditinjau admin. Pihak luar tetap dapat dicatat tanpa akses BMN Saya otomatis.</p></details>
  </div>;
}
