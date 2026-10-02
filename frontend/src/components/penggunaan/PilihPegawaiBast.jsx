import React, { useState } from "react";

/** Nilai opsi selalu UUID pegawai; nama kembar tidak dipilih dengan find(nama). */
export function pihakDariPegawai(p) {
  return {
    pegawai_id: String(p?.id || ""), nama: String(p?.nama || ""), nip: String(p?.nip || ""),
    jabatan: String(p?.jabatan || ""),
    alamat: String(p?.alamat || p?.unit_kerja || p?.unit_organisasi || "").trim(),
  };
}

export default function PilihPegawaiBast({ daftar = [], value = "", onPilih, testId, label = "Tautkan Master Pegawai" }) {
  const [cari, setCari] = useState("");
  const aktif = daftar.filter(p => p.status !== "meninggal");
  const hasil = aktif.filter(p => p.id === value || [p.nama, p.nip, p.unit_kerja, p.email].join(" ").toLowerCase().includes(cari.toLowerCase()));
  return <div className="space-y-1 rounded-lg border border-border bg-muted/20 p-2">
    <label htmlFor={`${testId}-cari`} className="block text-xs font-medium">{label}</label>
    <input id={`${testId}-cari`} data-testid={`${testId}-cari`} value={cari} onChange={e => setCari(e.target.value)}
      placeholder="Cari nama, identitas, unit, atau email" className="w-full min-w-0 rounded-md border border-input bg-background px-2 py-2 text-sm" />
    <select aria-label={label} value={value || ""} data-testid={testId} onChange={e => onPilih(daftar.find(p => p.id === e.target.value) || null)}
      className="min-h-[44px] w-full min-w-0 rounded-md border border-input bg-background px-2 text-sm">
      <option value="">Belum ditautkan / pihak di luar Master Pegawai</option>
      {value && !hasil.some(p => p.id === value) && <option value={value}>Pegawai tertaut tidak tersedia — periksa kembali</option>}
      {hasil.map(p => <option key={p.id} value={p.id}>{[p.nama, p.nip || "Tanpa NIP/NIK", p.unit_kerja, p.email, `ID …${String(p.id).slice(-6)}`].filter(Boolean).join(" · ")}</option>)}
    </select>
    <p className="text-[10px] text-muted-foreground">Pilih pegawai yang tepat sekali. Email unik yang layak mendapat akses awal setelah BAST sah; email bermasalah atau akses pernah dicabut perlu tinjauan admin. Pihak di luar master tidak memperoleh akses BMN Saya otomatis.</p>
  </div>;
}
