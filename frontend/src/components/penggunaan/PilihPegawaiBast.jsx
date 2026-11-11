import React, { useState } from "react";
import PilihanRingkas from "@/components/ui/PilihanRingkas";
import PilihKelompok from "@/components/pegawai/PilihKelompok";
import CariOrangLuar, { keteranganOrangLuar } from "@/components/pegawai/CariOrangLuar";
import IkonKelompok from "@/components/pegawai/IkonKelompok";
import { kelompokDari } from "@/lib/kelompokOrang";

const adalahLuar = (p) => p?.ranah === "luar" || ["eksternal", "pihak_ketiga"].includes(p?.kelompok);

/**
 * Pihak BAST dari catatan orang. Nilai opsi internal selalu UUID pegawai;
 * nama kembar tidak dipilih dengan find(nama).
 *
 * Orang luar: `pegawai_id` = id di direktori luar (pengaman hapus orang
 * luar menghitung rujukan BAST lewat id ini); akses BMN Saya tetap hanya
 * untuk pegawai internal karena server mencocokkan NIP ke Master Pegawai
 * satker (K3). `alamat` = alamat orangnya, jatuh ke "instansi — satker".
 * Kelompok/tataran/instansi ikut dikirim untuk tampilan; server tetap
 * membekukannya sendiri dari NIP (PGW-06).
 */
export function pihakDariPegawai(p) {
  if (adalahLuar(p)) {
    const tempat = [p?.instansi_nama, p?.satker_luar_nama].filter(Boolean).join(" — ");
    return {
      pegawai_id: String(p?.id || ""), nama: String(p?.nama || ""), nip: String(p?.nip || ""),
      jabatan: String(p?.jabatan || ""),
      alamat: String(p?.alamat || tempat).trim(),
      kelompok: String(p?.kelompok || ""), tataran: String(p?.tataran || ""),
      instansi_nama: String(p?.instansi_nama || ""),
    };
  }
  return {
    pegawai_id: String(p?.id || ""), nama: String(p?.nama || ""), nip: String(p?.nip || ""),
    jabatan: String(p?.jabatan || ""),
    alamat: String(p?.alamat || p?.unit_kerja || p?.unit_organisasi || "").trim(),
  };
}

/** `pihak`: isian pihak saat ini — dipakai mengenali tautan ke orang luar
 *  (dari direktori, atau dari BAST lama yang direvisi). */
export default function PilihPegawaiBast({ daftar = [], value = "", onPilih, testId, label = "Tautkan Master Pegawai", pihak = null }) {
  const aktif = daftar.filter(p => p.status !== "meninggal");
  const [kelompok, setKelompok] = useState("internal");
  const [tataran, setTataran] = useState("pusat");
  const [luar, setLuar] = useState(null); // orang luar terakhir dipilih (keterangan & peringatan)
  const pilihLuar = (p) => { setLuar(p); onPilih(p); };
  const tautLuar = !!value && (luar?.id === value
    || ["eksternal", "pihak_ketiga"].includes(pihak?.kelompok));
  return <div className="min-w-0 space-y-1">
    <PilihKelompok kelompok={kelompok} tataran={tataran} awalanTestId={`${testId}-pilih`}
      onKelompok={(k) => { setKelompok(k); setLuar(null); }} onTataran={setTataran} />
    {kelompok === "internal" ? <>
      <PilihanRingkas options={aktif.map(p => ({ value: String(p.id), label: p.nama,
        description: [p.nip || "Tanpa NIP/NIK", p.unit_kerja, p.email, `ID …${String(p.id).slice(-6)}`].filter(Boolean).join(" · "),
        searchText: [p.nama, p.nip, p.unit_kerja, p.unit_organisasi, p.email].join(" "),
      }))} value={value} onChange={id => onPilih(aktif.find(p => String(p.id) === id) || null)} label={label} testId={testId}
        placeholder="Pilih pegawai / isi pihak luar" emptyLabel="Pihak luar — isi identitas manual" />
      {value && !tautLuar && !aktif.some(p => String(p.id) === String(value)) && <p role="alert" className="text-xs text-amber-700 dark:text-amber-300">Pegawai tertaut tidak tersedia. Pilih ulang atau kosongkan untuk pihak luar.</p>}
    </> : <CariOrangLuar kelompok={kelompok} tataran={tataran} onPilih={pilihLuar}
      testId={`${testId}-luar`} terpilihNip={luar?.nip || ""} />}
    {tautLuar && (
      <div className="flex items-start gap-1.5 text-xs text-muted-foreground" data-testid={`${testId}-luar-terpilih`}>
        <IkonKelompok kunciIkon={luar?.id === value ? luar.kunci_ikon : kelompokDari(pihak)} className="mt-0.5" />
        <span className="min-w-0 flex-1 break-words">
          <b className="text-foreground">{luar?.id === value ? luar.nama : pihak?.nama}</b>{" "}
          {luar?.id === value ? keteranganOrangLuar(luar) : (pihak?.instansi_nama || "")}
        </span>
        <button type="button" onClick={() => { setLuar(null); onPilih(null); }}
          className="text-[11px] font-semibold underline underline-offset-2 min-h-[44px] lg:min-h-0"
          data-testid={`${testId}-luar-lepas`}>Lepas</button>
      </div>
    )}
    {luar?.id === value && luar?.kapasitas_bertindak === "petugas" && (
      <p role="alert" className="text-xs text-amber-700 dark:text-amber-300" data-testid={`${testId}-peringatan-petugas`}>
        Orang ini tercatat sebagai petugas/karyawan — bukan pihak yang sah menandatangani atas nama badannya.
        Pastikan ada surat kuasa, atau pilih pengurus yang berwenang.
      </p>
    )}
    <details className="text-xs text-muted-foreground"><summary className="min-h-[44px] cursor-pointer content-center">Tentang identitas & akses BMN Saya</summary><p className="pb-2">Pilihan mengisi identitas otomatis. Email unik yang layak mendapat akses setelah BAST sah; masalah email/akses ditinjau admin. Pihak luar — termasuk orang instansi eksternal dan pihak ketiga dari direktori — tetap dapat dicatat tanpa akses BMN Saya otomatis.</p></details>
  </div>;
}
